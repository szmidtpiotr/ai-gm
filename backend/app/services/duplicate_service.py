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


def normalize_label(label: str | None) -> str:
    """Lowercase, trim, collapse inner whitespace. Unicode-aware (Ł→ł)."""
    return re.sub(r"\s+", " ", (label or "").strip()).lower()


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
    by_norm: dict[str, list[dict]] = {}
    for rec in records:
        by_norm.setdefault(rec["norm"], []).append(rec)

    def _public(rec: dict) -> dict:
        out = {k: v for k, v in rec.items() if k != "norm"}
        out["refs"] = _ref_count(conn, logical, rec["key"])
        return out

    groups: list[dict] = []
    for norm, recs in by_norm.items():
        if len(recs) > 1:
            groups.append({
                "match": "exact",
                "label": norm,
                "records": [_public(r) for r in recs],
            })

    for cluster in _fuzzy_clusters(sorted(by_norm.keys())):
        recs = [r for norm in cluster for r in by_norm[norm]]
        groups.append({
            "match": "fuzzy",
            "label": " / ".join(sorted(cluster)),
            "records": [_public(r) for r in recs],
        })

    groups.sort(key=lambda g: (g["match"] != "exact", -len(g["records"])))
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

    return {
        "tables": tables,
        "cross": list(merged_cross.values()),
        "excess": count_duplicates(conn),
    }


def count_duplicates(conn: sqlite3.Connection) -> int:
    """Excess exact duplicates across all three tables (badge number)."""
    total = 0
    for real in _TABLES.values():
        labels = [normalize_label(r[0]) for r in conn.execute(f"SELECT label FROM {real}")]
        total += len(labels) - len(set(labels))
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
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {"kept": keep_key, "deleted": remove, "repointed": repointed}
