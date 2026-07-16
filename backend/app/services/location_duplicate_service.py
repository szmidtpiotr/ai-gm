"""Duplicate detector + merge + garbage scan for game_locations (#1409).

Same idea as the content duplicate detector (duplicate_service.py, #1399) but
for locations, which the campaign-plan materializer and world_service spawn in
bulk — leaving heaps of duplicates and test junk in Mapa → Lokacje.

Key difference from the item detector (Piotr's explicit scope decision):
**merge NEVER touches world_hexes.** The overworld hex map (world_hexes,
map_level=0) is PIOTR-OWNED. A loser record that a hex still points at via
world_hexes.location_key is therefore NOT deletable — merge skips it and
reports it as hex-locked instead of orphaning the hex.

Repointed on merge: game_locations.parent_id / parent_key (children re-home to
the survivor) and game_sessions.current_location_id. Losers are then hard-
deleted, matching the item-merge behaviour.
"""
from __future__ import annotations

import re
import sqlite3

# Reuse the low-level primitives from the content detector so both tabs behave
# identically (normalization, fuzzy clustering, "to nie duplikat" pairs).
from app.services.duplicate_service import (
    FUZZY_THRESHOLD,  # noqa: F401 (kept for parity / future tuning)
    _ensure_ignore_table,
    _fuzzy_clusters,
    _group_fully_ignored,
    _pair,
    normalize_label,
)

_TABLE = "game_locations"
_IGNORE_KIND = "locations"  # table_name value inside content_duplicate_ignores

# key looks like leftover test/smoke junk: test_ prefix, [TEST] tag, or a long
# timestamp suffix (e.g. _20260712_143501 / _1720000000).
_TEST_KEY_RE = re.compile(r"(^test[_-])|(\[test\])|(_\d{6,}$)", re.IGNORECASE)


# ─── helpers ─────────────────────────────────────────────────────────────────

def _cols(conn: sqlite3.Connection) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({_TABLE})")}


def _hex_linked_keys(conn: sqlite3.Connection) -> set[str]:
    """Location keys a world hex points at — untouchable (PIOTR-OWNED map)."""
    try:
        return {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT location_key FROM world_hexes WHERE location_key IS NOT NULL"
            )
        }
    except sqlite3.OperationalError:
        return set()  # world_hexes absent (minimal test DB)


def _ignored_pairs(conn: sqlite3.Connection) -> set[tuple[str, str]]:
    _ensure_ignore_table(conn)
    return {
        _pair(r[0], r[1])
        for r in conn.execute(
            "SELECT key_a, key_b FROM content_duplicate_ignores WHERE table_name = ?",
            (_IGNORE_KIND,),
        )
    }


def _fetch(conn: sqlite3.Connection) -> list[dict]:
    cols = _cols(conn)
    has_hex = "world_hex_q" in cols
    hex_sel = "world_hex_q, world_hex_r" if has_hex else "NULL AS world_hex_q, NULL AS world_hex_r"
    rows = conn.execute(
        f"SELECT id, key, label, is_active, parent_id, source_campaign_id, "
        f"created_by, location_type, {hex_sel} FROM {_TABLE}"
    ).fetchall()
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "key": r["key"],
            "label": r["label"],
            "norm": normalize_label(r["label"]),
            "is_active": bool(r["is_active"]),
            "parent_id": r["parent_id"],
            "source_campaign_id": r["source_campaign_id"],
            "created_by": r["created_by"],
            "location_type": r["location_type"],
            "world_hex_q": r["world_hex_q"],
        })
    return out


# ─── scan ────────────────────────────────────────────────────────────────────

def _duplicate_groups(records: list[dict], ignored: set[tuple[str, str]], hex_keys: set[str]) -> list[dict]:
    by_norm: dict[str, list[dict]] = {}
    for rec in records:
        if rec["norm"]:
            by_norm.setdefault(rec["norm"], []).append(rec)

    def _public(rec: dict) -> dict:
        out = {k: v for k, v in rec.items() if k != "norm"}
        out["hex_locked"] = rec["key"] in hex_keys
        return out

    groups: list[dict] = []
    for norm, recs in by_norm.items():
        if len(recs) > 1 and not _group_fully_ignored([r["key"] for r in recs], ignored):
            groups.append({
                "match": "exact",
                "label": norm,
                "records": [_public(r) for r in recs],
            })

    for cluster in _fuzzy_clusters(sorted(by_norm.keys())):
        recs = [r for norm in cluster for r in by_norm[norm]]
        if _group_fully_ignored([r["key"] for r in recs], ignored):
            continue
        groups.append({
            "match": "fuzzy",
            "label": " / ".join(sorted(cluster)),
            "records": [_public(r) for r in recs],
        })

    # exact first, then largest groups.
    groups.sort(key=lambda g: (g["match"] != "exact", -len(g["records"])))
    return groups


def _garbage(records: list[dict], hex_keys: set[str]) -> dict:
    active_ids = {r["id"] for r in records if r["is_active"]}
    all_ids = {r["id"] for r in records}

    def slim(rec: dict) -> dict:
        return {
            "id": rec["id"], "key": rec["key"], "label": rec["label"],
            "is_active": rec["is_active"], "hex_locked": rec["key"] in hex_keys,
        }

    test, orphaned, floating, inactive = [], [], [], []
    for rec in records:
        key = rec["key"] or ""
        if _TEST_KEY_RE.search(key) or (rec["created_by"] or "").lower() in ("test", "smoke"):
            test.append(slim(rec))
        pid = rec["parent_id"]
        if pid is not None and pid not in active_ids:
            # parent gone entirely, or only survives as an inactive row.
            if pid not in all_ids or pid not in active_ids:
                orphaned.append(slim(rec))
        if (
            rec["parent_id"] is None
            and rec["world_hex_q"] is None
            and rec["key"] not in hex_keys
            and rec["source_campaign_id"] is None
            and rec["is_active"]
        ):
            floating.append(slim(rec))
        if not rec["is_active"]:
            inactive.append(slim(rec))

    return {"test": test, "orphaned": orphaned, "floating": floating, "inactive": inactive}


def scan_location_duplicates(conn: sqlite3.Connection) -> dict:
    conn.row_factory = sqlite3.Row
    records = _fetch(conn)
    ignored = _ignored_pairs(conn)
    hex_keys = _hex_linked_keys(conn)
    groups = _duplicate_groups(records, ignored, hex_keys)
    garbage = _garbage(records, hex_keys)
    return {
        "groups": groups,
        "garbage": garbage,
        "excess": count_location_duplicates(conn),
        "garbage_total": sum(len(v) for v in garbage.values()),
    }


def count_location_duplicates(conn: sqlite3.Connection) -> int:
    """Excess exact duplicates (badge). Skips fully-ignored groups (#1401)."""
    conn.row_factory = sqlite3.Row
    ignored = _ignored_pairs(conn)
    by_norm: dict[str, list[str]] = {}
    for r in conn.execute(f"SELECT key, label FROM {_TABLE}"):
        n = normalize_label(r["label"])
        if n:
            by_norm.setdefault(n, []).append(r["key"])
    total = 0
    for keys in by_norm.values():
        if len(keys) > 1 and not _group_fully_ignored(keys, ignored):
            total += len(keys) - 1
    return total


# ─── ignore («to nie duplikat») ──────────────────────────────────────────────

def ignore_location_duplicates(conn: sqlite3.Connection, keys: list[str]) -> int:
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
                (_IGNORE_KIND, ka, kb),
            ).rowcount
    conn.commit()
    return n


# ─── merge ───────────────────────────────────────────────────────────────────

def merge_location_duplicates(
    conn: sqlite3.Connection,
    keep_key: str,
    remove_keys: list[str],
) -> dict:
    """Re-home children + sessions onto keep_key, then delete the losers.

    world_hexes is never touched: any loser a hex still points at is left in
    place and returned under `skipped_hex_locked`. Point the group's survivor at
    the hex-linked record (or unlink the hex in admin → Mapa first) to purge it.
    """
    remove = [k for k in dict.fromkeys(remove_keys) if k]
    if not remove:
        raise ValueError("Brak lokacji do usunięcia")
    if keep_key in remove:
        raise ValueError("Klucz ocalałej lokacji nie może być na liście do usunięcia")

    conn.row_factory = sqlite3.Row
    keep = conn.execute(f"SELECT id FROM {_TABLE} WHERE key = ?", (keep_key,)).fetchone()
    if not keep:
        raise ValueError(f"Lokacja ocalała '{keep_key}' nie istnieje")
    keep_id = keep["id"]

    hex_keys = _hex_linked_keys(conn)
    rows = {
        r["key"]: r["id"]
        for r in conn.execute(
            f"SELECT key, id FROM {_TABLE} WHERE key IN ({','.join('?' * len(remove))})", remove
        )
    }
    missing = [k for k in remove if k not in rows]
    if missing:
        raise ValueError(f"Lokacje do usunięcia nie istnieją: {sorted(missing)}")

    skipped = [k for k in remove if k in hex_keys]   # anchored to a world hex → keep
    deletable = [k for k in remove if k not in hex_keys]
    del_ids = [rows[k] for k in deletable]

    repointed: dict[str, int] = {}
    try:
        if del_ids:
            ph = ",".join("?" * len(del_ids))
            cols = _cols(conn)
            cur = conn.execute(
                f"UPDATE {_TABLE} SET parent_id = ? WHERE parent_id IN ({ph})", [keep_id, *del_ids]
            )
            if cur.rowcount:
                repointed["game_locations.parent_id"] = cur.rowcount
            if "parent_key" in cols:
                cur = conn.execute(
                    f"UPDATE {_TABLE} SET parent_key = ? WHERE parent_key IN ({','.join('?' * len(deletable))})",
                    [keep_key, *deletable],
                )
                if cur.rowcount:
                    repointed["game_locations.parent_key"] = cur.rowcount
            try:
                cur = conn.execute(
                    f"UPDATE game_sessions SET current_location_id = ? WHERE current_location_id IN ({ph})",
                    [keep_id, *del_ids],
                )
                if cur.rowcount:
                    repointed["game_sessions.current_location_id"] = cur.rowcount
            except sqlite3.OperationalError:
                pass  # game_sessions absent (minimal test DB)

            conn.execute(f"DELETE FROM {_TABLE} WHERE id IN ({ph})", del_ids)
            try:
                dph = ",".join("?" * len(deletable))
                conn.execute(
                    f"DELETE FROM content_duplicate_ignores WHERE key_a IN ({dph}) OR key_b IN ({dph})",
                    [*deletable, *deletable],
                )
            except sqlite3.OperationalError:
                pass
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "kept": keep_key,
        "deleted": deletable,
        "skipped_hex_locked": skipped,
        "repointed": repointed,
    }
