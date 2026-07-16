"""Duplicate detector + merge for content config tables (#1399).

LLM-driven content generation (Kuźnia, campaign plan materialization, loot)
routinely creates records whose label already exists. This service finds those
duplicates and merges them safely — re-pointing every DB reference to the
surviving record before deleting the losers.

Scope: game_config_items / game_config_consumables / game_config_weapons.
Cross-table (items↔consumables) matches are reported for information only;
merging never crosses tables.
"""
from __future__ import annotations

import json
import re
import sqlite3
from difflib import SequenceMatcher

# Starting value — tune after first scans on real data (#1399 Numbers Policy).
FUZZY_THRESHOLD = 0.87

_TABLES = {
    "items": "game_config_items",
    "consumables": "game_config_consumables",
    "weapons": "game_config_weapons",
}

# (referencing table, column) pairs re-pointed on merge, per logical table.
_REFS: dict[str, list[tuple[str, str]]] = {
    "items": [
        ("character_inventory", "item_key"),
        ("game_config_loot_entries", "item_key"),
        ("character_rentals", "item_key"),
    ],
    "consumables": [
        ("character_inventory", "consumable_key"),
        ("game_config_loot_entries", "consumable_key"),
    ],
    "weapons": [
        ("character_inventory", "weapon_key"),
        ("game_config_loot_entries", "weapon_key"),
        ("game_config_weapons", "ammo_key"),
    ],
}

_RECIPE_OUTPUT_TYPE = {"items": "item", "consumables": "consumable", "weapons": "weapon"}

# Logical tables accepting "to nie duplikat" (#1401); 'cross' = para items↔consumables.
_IGNORABLE = set(_TABLES) | {"cross"}


def normalize_label(label: str | None) -> str:
    """Lowercase, trim, collapse inner whitespace. Unicode-aware (Ł→ł)."""
    return re.sub(r"\s+", " ", (label or "").strip()).lower()


# ─── Ignorowane fałszywe trafienia (#1401) ───────────────────────────────────

def _ensure_ignore_table(conn: sqlite3.Connection) -> None:
    # Defensive twin of the migrations_admin.py DDL — keeps old DBs and test
    # fixtures working without running full migrations.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS content_duplicate_ignores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            key_a TEXT NOT NULL,
            key_b TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(table_name, key_a, key_b)
        )
        """
    )


def _pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def ignore_duplicates(conn: sqlite3.Connection, table: str, keys: list[str]) -> int:
    """Mark every pair within keys as "not a duplicate". Returns pairs stored."""
    if table not in _IGNORABLE:
        raise ValueError(f"Nieznana tabela: {table}")
    uniq = [k for k in dict.fromkeys(keys) if k]
    if len(uniq) < 2:
        raise ValueError("Potrzebne co najmniej dwa klucze")
    _ensure_ignore_table(conn)
    n = 0
    for i, a in enumerate(uniq):
        for b in uniq[i + 1:]:
            ka, kb = _pair(a, b)
            n += conn.execute(
                "INSERT OR IGNORE INTO content_duplicate_ignores (table_name, key_a, key_b) VALUES (?, ?, ?)",
                (table, ka, kb),
            ).rowcount
    conn.commit()
    return n


def list_ignores(conn: sqlite3.Connection) -> list[dict]:
    _ensure_ignore_table(conn)
    conn.row_factory = sqlite3.Row
    return [
        dict(r)
        for r in conn.execute(
            "SELECT id, table_name, key_a, key_b, created_at FROM content_duplicate_ignores ORDER BY id DESC"
        )
    ]


def unignore(conn: sqlite3.Connection, ignore_id: int) -> None:
    _ensure_ignore_table(conn)
    conn.execute("DELETE FROM content_duplicate_ignores WHERE id = ?", (ignore_id,))
    conn.commit()


def _ignored_pairs(conn: sqlite3.Connection, table: str) -> set[tuple[str, str]]:
    _ensure_ignore_table(conn)
    return {
        _pair(r[0], r[1])
        for r in conn.execute(
            "SELECT key_a, key_b FROM content_duplicate_ignores WHERE table_name = ?", (table,)
        )
    }


def _group_fully_ignored(keys: list[str], ignored: set[tuple[str, str]]) -> bool:
    """True when EVERY pair of the group is ignored — a new member reopens it."""
    if not ignored:
        return False
    return all(
        _pair(a, b) in ignored
        for i, a in enumerate(keys)
        for b in keys[i + 1:]
    )


# ─── Prewencja przy tworzeniu (#1400) ────────────────────────────────────────

def _ensure_prevention_table(conn: sqlite3.Connection) -> None:
    # Defensive twin of the migrations_admin.py DDL (same reason as ignores).
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS content_duplicate_preventions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            label TEXT NOT NULL,
            action TEXT NOT NULL,
            existing_key TEXT,
            new_key TEXT,
            source TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def _reusable_records(conn: sqlite3.Connection, table: str) -> list:
    """Records eligible for silent reuse: active, global, not template clones.

    Template clones (tpl*) duplicate labels BY DESIGN (per-template reward
    copies) — reusing or matching against them would break that mechanic.
    """
    real = _TABLES[table]
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({real})")}
    conds = ["is_active = 1"]
    if "template_id" in cols:
        conds.append("template_id IS NULL")
    if "hidden" in cols:
        conds.append("(hidden IS NULL OR hidden = 0)")
    if "campaign_id" in cols:
        conds.append("campaign_id IS NULL")
    return conn.execute(f"SELECT key, label FROM {real} WHERE {' AND '.join(conds)}").fetchall()


def resolve_new_label(conn: sqlite3.Connection, table: str, label: str, source: str = "") -> dict:
    """Decide what to do before creating a record with this label.

    - exact match (normalized) → {"action": "reuse", "key": <existing>} — logged;
      caller must NOT create and should use the existing key instead
    - fuzzy match → {"action": "create_flagged", "similar_to": <closest key>} —
      caller creates, then calls log_flagged_creation() with the new key
    - no match → {"action": "create"}
    """
    if table not in _TABLES:
        raise ValueError(f"Nieznana tabela: {table}")
    norm = normalize_label(label)
    if not norm:
        return {"action": "create"}

    best_key, best_ratio = None, 0.0
    for key, existing_label in _reusable_records(conn, table):
        existing_norm = normalize_label(existing_label)
        if existing_norm == norm:
            _ensure_prevention_table(conn)
            conn.execute(
                "INSERT INTO content_duplicate_preventions (table_name, label, action, existing_key, source) "
                "VALUES (?, ?, 'reuse', ?, ?)",
                (table, label, key, source),
            )
            return {"action": "reuse", "key": key}
        ratio = SequenceMatcher(None, norm, existing_norm).ratio()
        if ratio > best_ratio:
            best_ratio, best_key = ratio, key

    if best_key is not None and best_ratio >= FUZZY_THRESHOLD:
        return {"action": "create_flagged", "similar_to": best_key}
    return {"action": "create"}


def log_flagged_creation(
    conn: sqlite3.Connection,
    table: str,
    new_key: str,
    label: str,
    similar_to: str,
    source: str = "",
) -> None:
    """Record a fuzzy-suspicious creation so the detector surfaces it first."""
    _ensure_prevention_table(conn)
    conn.execute(
        "INSERT INTO content_duplicate_preventions (table_name, label, action, existing_key, new_key, source) "
        "VALUES (?, ?, 'flagged', ?, ?, ?)",
        (table, label, similar_to, new_key, source),
    )


def get_prevention_stats(conn: sqlite3.Connection) -> dict:
    """{'reused': n, 'flagged': n} — ile duplikatów uniknięto / oflagowano."""
    _ensure_prevention_table(conn)
    stats = {"reused": 0, "flagged": 0}
    for action, n in conn.execute(
        "SELECT action, COUNT(*) FROM content_duplicate_preventions GROUP BY action"
    ):
        if action == "reuse":
            stats["reused"] = n
        elif action == "flagged":
            stats["flagged"] = n
    return stats


def _flagged_keys(conn: sqlite3.Connection, table: str) -> set[str]:
    _ensure_prevention_table(conn)
    return {
        r[0]
        for r in conn.execute(
            "SELECT new_key FROM content_duplicate_preventions WHERE table_name = ? AND action = 'flagged' AND new_key IS NOT NULL",
            (table,),
        )
    }


# ─── Scan ────────────────────────────────────────────────────────────────────

def _fetch_records(conn: sqlite3.Connection, real_table: str) -> list[dict]:
    rows = conn.execute(
        f"SELECT key, label, rarity, price_gp, description, created_at FROM {real_table}"
    ).fetchall()
    return [
        {
            "key": r["key"],
            "label": r["label"],
            "norm": normalize_label(r["label"]),
            "rarity": r["rarity"],
            "price_gp": r["price_gp"],
            "description": r["description"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def _ref_count(conn: sqlite3.Connection, logical: str, key: str) -> int:
    total = 0
    for tbl, col in _REFS[logical]:
        try:
            total += conn.execute(
                f"SELECT COUNT(*) FROM {tbl} WHERE {col} = ?", (key,)
            ).fetchone()[0]
        except sqlite3.OperationalError:
            continue  # referencing table absent (minimal test DB)
    return total


def _fuzzy_clusters(labels: list[str]) -> list[set[str]]:
    """Greedy clustering of distinct normalized labels by similarity ratio."""
    clusters: list[set[str]] = []
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            if SequenceMatcher(None, a, b).ratio() < FUZZY_THRESHOLD:
                continue
            merged = False
            for c in clusters:
                if a in c or b in c:
                    c.update((a, b))
                    merged = True
                    break
            if not merged:
                clusters.append({a, b})
    return clusters


def _scan_table(conn: sqlite3.Connection, logical: str) -> list[dict]:
    records = _fetch_records(conn, _TABLES[logical])
    ignored = _ignored_pairs(conn, logical)
    flagged = _flagged_keys(conn, logical)
    by_norm: dict[str, list[dict]] = {}
    for rec in records:
        by_norm.setdefault(rec["norm"], []).append(rec)

    def _public(rec: dict) -> dict:
        out = {k: v for k, v in rec.items() if k != "norm"}
        out["refs"] = _ref_count(conn, logical, rec["key"])
        return out

    groups: list[dict] = []
    for norm, recs in by_norm.items():
        if len(recs) > 1 and not _group_fully_ignored([r["key"] for r in recs], ignored):
            groups.append({
                "match": "exact",
                "label": norm,
                "flagged": any(r["key"] in flagged for r in recs),
                "records": [_public(r) for r in recs],
            })

    for cluster in _fuzzy_clusters(sorted(by_norm.keys())):
        recs = [r for norm in cluster for r in by_norm[norm]]
        if _group_fully_ignored([r["key"] for r in recs], ignored):
            continue
        groups.append({
            "match": "fuzzy",
            "label": " / ".join(sorted(cluster)),
            "flagged": any(r["key"] in flagged for r in recs),
            "records": [_public(r) for r in recs],
        })

    # exact przed fuzzy; wewnątrz — oflagowane przez prewencję (#1400) na górze.
    groups.sort(key=lambda g: (g["match"] != "exact", not g["flagged"], -len(g["records"])))
    return groups


def scan_duplicates(conn: sqlite3.Connection) -> dict:
    """Full duplicate report: per-table exact/fuzzy groups + cross-table info."""
    conn.row_factory = sqlite3.Row
    tables = {logical: _scan_table(conn, logical) for logical in _TABLES}

    item_norms: dict[str, list[str]] = {}
    for rec in _fetch_records(conn, _TABLES["items"]):
        item_norms.setdefault(rec["norm"], []).append(rec["key"])
    cross = []
    for rec in _fetch_records(conn, _TABLES["consumables"]):
        if rec["norm"] in item_norms:
            cross.append({
                "label": rec["norm"],
                "item_keys": item_norms[rec["norm"]],
                "consumable_keys": [rec["key"]],
            })
    merged_cross: dict[str, dict] = {}
    for entry in cross:
        slot = merged_cross.setdefault(
            entry["label"],
            {"label": entry["label"], "item_keys": entry["item_keys"], "consumable_keys": []},
        )
        slot["consumable_keys"].extend(entry["consumable_keys"])

    # #1401: wpis cross znika, gdy każda para item↔consumable jest zignorowana.
    cross_ignored = _ignored_pairs(conn, "cross")
    visible_cross = [
        c for c in merged_cross.values()
        if not cross_ignored or not all(
            _pair(ik, ck) in cross_ignored
            for ik in c["item_keys"]
            for ck in c["consumable_keys"]
        )
    ]

    return {
        "tables": tables,
        "cross": visible_cross,
        "excess": count_duplicates(conn),
        "prevention": get_prevention_stats(conn),
    }


def count_duplicates(conn: sqlite3.Connection) -> int:
    """Excess exact duplicates across all three tables (badge number).

    Skips groups fully marked "to nie duplikat" (#1401).
    """
    total = 0
    for logical, real in _TABLES.items():
        ignored = _ignored_pairs(conn, logical)
        by_norm: dict[str, list[str]] = {}
        for key, label in conn.execute(f"SELECT key, label FROM {real}"):
            by_norm.setdefault(normalize_label(label), []).append(key)
        for keys in by_norm.values():
            if len(keys) > 1 and not _group_fully_ignored(keys, ignored):
                total += len(keys) - 1
    return total


# ─── Merge ───────────────────────────────────────────────────────────────────

def merge_duplicates(
    conn: sqlite3.Connection,
    table: str,
    keep_key: str,
    remove_keys: list[str],
) -> dict:
    """Re-point all references from remove_keys to keep_key, then delete them.

    Single transaction — either everything is re-pointed and deleted, or
    nothing changes.
    """
    if table not in _TABLES:
        raise ValueError(f"Nieznana tabela: {table}")
    remove = [k for k in dict.fromkeys(remove_keys) if k]
    if not remove:
        raise ValueError("Brak kluczy do usunięcia")
    if keep_key in remove:
        raise ValueError("Klucz ocalałego nie może być na liście do usunięcia")

    real = _TABLES[table]
    conn.row_factory = sqlite3.Row
    if not conn.execute(f"SELECT 1 FROM {real} WHERE key = ?", (keep_key,)).fetchone():
        raise ValueError(f"Rekord ocalały '{keep_key}' nie istnieje w {real}")
    existing = {
        r["key"]
        for r in conn.execute(
            f"SELECT key FROM {real} WHERE key IN ({','.join('?' * len(remove))})", remove
        )
    }
    missing = set(remove) - existing
    if missing:
        raise ValueError(f"Rekordy do usunięcia nie istnieją: {sorted(missing)}")

    placeholders = ",".join("?" * len(remove))
    repointed: dict[str, int] = {}
    try:
        for tbl, col in _REFS[table]:
            try:
                cur = conn.execute(
                    f"UPDATE {tbl} SET {col} = ? WHERE {col} IN ({placeholders})",
                    [keep_key, *remove],
                )
                if cur.rowcount:
                    repointed[f"{tbl}.{col}"] = cur.rowcount
            except sqlite3.OperationalError:
                continue  # referencing table absent (minimal test DB)

        try:
            cur = conn.execute(
                f"UPDATE game_config_recipes SET output_key = ? "
                f"WHERE output_type = ? AND output_key IN ({placeholders})",
                [keep_key, _RECIPE_OUTPUT_TYPE[table], *remove],
            )
            if cur.rowcount:
                repointed["game_config_recipes.output_key"] = cur.rowcount

            if table == "items":
                removed_set = set(remove)
                rows = conn.execute(
                    "SELECT key, inputs_json FROM game_config_recipes WHERE inputs_json IS NOT NULL"
                ).fetchall()
                touched = 0
                for row in rows:
                    try:
                        inputs = json.loads(row["inputs_json"])
                    except (TypeError, ValueError):
                        continue
                    changed = False
                    for entry in inputs if isinstance(inputs, list) else []:
                        if isinstance(entry, dict) and entry.get("item_key") in removed_set:
                            entry["item_key"] = keep_key
                            changed = True
                    if changed:
                        conn.execute(
                            "UPDATE game_config_recipes SET inputs_json = ? WHERE key = ?",
                            (json.dumps(inputs, ensure_ascii=False), row["key"]),
                        )
                        touched += 1
                if touched:
                    repointed["game_config_recipes.inputs_json"] = touched
        except sqlite3.OperationalError:
            pass  # recipes table absent

        conn.execute(f"DELETE FROM {real} WHERE key IN ({placeholders})", remove)
        try:
            conn.execute(
                f"DELETE FROM content_duplicate_ignores WHERE key_a IN ({placeholders}) OR key_b IN ({placeholders})",
                [*remove, *remove],
            )
        except sqlite3.OperationalError:
            pass  # ignore table absent
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {"kept": keep_key, "deleted": remove, "repointed": repointed}
