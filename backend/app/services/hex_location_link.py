"""#1243 (R3) — single canonical direction for the hex↔location link.

**Decision (Piotr, 2026-07-05): the OVERWORLD hex is canon.**
`world_hexes.location_key` (map_level=0) is the single source of truth for
"which location sits on this hex". `game_locations.world_hex_q/r` is a DERIVED
CACHE, rebuilt from the hex table — never authored independently.

Chosen over the loc→hex direction (issue's original recommendation) because the
#1243 DB audit showed the `game_locations` coordinate columns were the *polluted*
side: 14 locations stamped `(0,0)`, `brzezino` stamped `(1,0)` while it physically
sits on hex `(39,9)`. The hex table was clean. Hex-wins therefore makes the
migration deterministic and conflict-free (a hex row holds exactly one
`location_key`, so "two locations on one hex" is impossible by construction).

All hex↔location writes go through `link_location_to_hex`; all hex→location reads
through `location_on_hex` / `resolve_location_to_hex`.
`reconcile_location_hex_links` rebuilds the derived cache and clears stale pins.

NOTE: `map_level=1` (local sub-hex ↔ sub-location, FAZA ML) is a DIFFERENT
relationship and is OUT OF SCOPE — only level 0 has a `game_locations` cache
(a sub-location's `world_hex_q/r` is its parent hub's overworld hex, if any).
"""
from __future__ import annotations

import sqlite3

from app.core.logging import get_logger

logger = get_logger(__name__)


def _ml(conn: sqlite3.Connection, level: int) -> tuple[str, list]:
    """Return (sql_fragment, params) for the map_level predicate — but only when
    the `world_hexes.map_level` column exists. Minimal unit-test schemas omit it;
    there everything is implicitly overworld (level 0), so drop the predicate.
    """
    try:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(world_hexes)").fetchall()]
    except sqlite3.Error:
        cols = []
    if "map_level" in cols:
        return " AND map_level = ?", [level]
    return "", []


def _cols(conn: sqlite3.Connection, table: str) -> set:
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


def link_location_to_hex(
    conn: sqlite3.Connection,
    loc_key: str,
    q: int,
    r: int,
    level: int = 0,
    *,
    only_if_empty: bool = False,
    sync_cache: bool = True,
) -> bool:
    """Canonical writer for the hex↔location pairing. THE single write path.

    level 0 (overworld): sets `world_hexes.location_key` (CANON) at (q, r) and
      refreshes the derived cache `game_locations.world_hex_q/r` (+ placement).
    level 1 (local map): sets only `world_hexes.location_key` on the sub-hex —
      there is no `game_locations` cache column for local placement.

    only_if_empty: only claim the hex when its `location_key` is currently NULL/''
      (preserves the BUG-186 / opening-intent "don't steal a claimed hex" guard).
    sync_cache: when False, skip the `game_locations` cache write (for callers that
      immediately re-place / NULL-then-restore the hex).

    Returns True when the hex row was (re)pointed at `loc_key`, else False.
    """
    if not loc_key:
        return False

    ml, mlp = _ml(conn, level)

    if level != 0:
        conn.execute(
            f"UPDATE world_hexes SET location_key = ? WHERE q = ? AND r = ?{ml} AND is_active = 1",
            (loc_key, q, r, *mlp),
        )
        return True

    if only_if_empty:
        cur = conn.execute(
            f"UPDATE world_hexes SET location_key = ? WHERE q = ? AND r = ?{ml} AND is_active = 1 "
            "AND (location_key IS NULL OR location_key = '')",
            (loc_key, q, r, *mlp),
        )
        claimed = cur.rowcount > 0
    else:
        conn.execute(
            f"UPDATE world_hexes SET location_key = ? WHERE q = ? AND r = ?{ml} AND is_active = 1",
            (loc_key, q, r, *mlp),
        )
        claimed = True

    if claimed and sync_cache:
        gl = _cols(conn, "game_locations")
        if "world_hex_q" in gl and "world_hex_r" in gl:
            sets = ["world_hex_q = ?", "world_hex_r = ?"]
            params: list = [q, r]
            if "placement" in gl:
                sets.append("placement = 'placed'")
            params.append(loc_key)
            conn.execute(
                f"UPDATE game_locations SET {', '.join(sets)} WHERE key = ? AND is_active = 1",
                params,
            )
    return claimed


def location_on_hex(
    conn: sqlite3.Connection, q: int, r: int, level: int = 0
) -> str | None:
    """Canonical reader: key of the location on hex (q, r), or None.

    level 0: canon = `world_hexes.location_key`; if that key is missing/inactive,
      fall back to a `game_location` whose derived cache still points here — and
      LOG the drift (#1243 log-only phase; reconcile should have removed these).
    level 1: `world_hexes.location_key` on the sub-hex only.
    """
    ml, mlp = _ml(conn, level)
    try:
        row = conn.execute(
            f"SELECT location_key FROM world_hexes WHERE q = ? AND r = ?{ml} AND is_active = 1 "
            "AND location_key IS NOT NULL AND location_key != '' LIMIT 1",
            (q, r, *mlp),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row:
        key = row["location_key"] if isinstance(row, sqlite3.Row) else row[0]
        loc = conn.execute(
            "SELECT key FROM game_locations WHERE key = ? AND COALESCE(is_active, 1) = 1 LIMIT 1",
            (key,),
        ).fetchone()
        if loc:
            return loc["key"] if isinstance(loc, sqlite3.Row) else loc[0]
        # canon points at a missing/inactive location → fall through to cache

    if level != 0 or "world_hex_q" not in _cols(conn, "game_locations"):
        return None

    try:
        fb = conn.execute(
            "SELECT key FROM game_locations "
            "WHERE world_hex_q = ? AND world_hex_r = ? AND COALESCE(is_active, 1) = 1 "
            "ORDER BY (location_type = 'macro') DESC, (parent_key IS NULL) DESC, id LIMIT 1",
            (q, r),
        ).fetchone()
    except sqlite3.OperationalError:
        fb = None
    if fb:
        key = fb["key"] if isinstance(fb, sqlite3.Row) else fb[0]
        logger.info("hex_location_cache_fallback", q=q, r=r, key=key)
        return key
    return None


def resolve_location_to_hex(
    conn: sqlite3.Connection, loc_key: str
) -> tuple[int, int] | None:
    """Canonical reader: (q, r) of the overworld hex a location sits on, or None.

    Primary: `world_hexes.location_key` (canon). Fallback: the derived
    `game_locations.world_hex_q/r` cache, logging drift (log-only phase).
    """
    if not loc_key:
        return None
    ml, mlp = _ml(conn, 0)
    row = conn.execute(
        f"SELECT q, r FROM world_hexes WHERE location_key = ?{ml} AND is_active = 1 LIMIT 1",
        (loc_key, *mlp),
    ).fetchone()
    if row:
        return (int(row["q"]), int(row["r"]))
    if "world_hex_q" not in _cols(conn, "game_locations"):
        return None
    loc = conn.execute(
        "SELECT world_hex_q, world_hex_r FROM game_locations "
        "WHERE key = ? AND is_active = 1 AND world_hex_q IS NOT NULL LIMIT 1",
        (loc_key,),
    ).fetchone()
    if loc:
        logger.info(
            "resolve_location_to_hex_cache_fallback",
            loc_key=loc_key, q=int(loc["world_hex_q"]), r=int(loc["world_hex_r"]),
        )
        return (int(loc["world_hex_q"]), int(loc["world_hex_r"]))
    return None


def reconcile_location_hex_links(conn: sqlite3.Connection) -> dict:
    """Rebuild the derived `game_locations.world_hex_q/r` cache from hex canon.

    HEX WINS (Piotr's decision). Steps:
      1. Smears — a `location_key` sitting on ≥2 overworld hexes: keep the hex
         matching the location's current cached coords (else the lowest q,r), NULL
         the others' `location_key`.
      2. Backfill — for every hex→location canon pairing, stamp the location's
         `world_hex_q/r` to the hex (overwriting stale values like brzezino (1,0)).
      3. Clear — any active location whose cached coords are NOT the canonical
         (hex-backed) pairing loses its pin (`world_hex_q/r`=NULL). It stays
         narrative-playable, just without a world-map pin.

    Deterministic and ambiguity-free by construction (a hex holds one key). Every
    change is logged. Returns a report dict.
    """
    report: dict = {"smears": [], "backfilled": [], "promoted": [], "cleared": [], "canonical_pairs": 0}

    # Step 1 — resolve smears (same key on multiple overworld hexes).
    dup = conn.execute(
        "SELECT location_key FROM world_hexes "
        "WHERE map_level = 0 AND is_active = 1 "
        "AND location_key IS NOT NULL AND location_key != '' "
        "GROUP BY location_key HAVING COUNT(*) > 1"
    ).fetchall()
    for d in dup:
        lk = d["location_key"]
        hexes = conn.execute(
            "SELECT q, r FROM world_hexes "
            "WHERE map_level = 0 AND is_active = 1 AND location_key = ? ORDER BY q, r",
            (lk,),
        ).fetchall()
        cur = conn.execute(
            "SELECT world_hex_q, world_hex_r FROM game_locations WHERE key = ? AND is_active = 1",
            (lk,),
        ).fetchone()
        keep = None
        if cur and cur["world_hex_q"] is not None:
            for h in hexes:
                if h["q"] == int(cur["world_hex_q"]) and h["r"] == int(cur["world_hex_r"]):
                    keep = (h["q"], h["r"])
                    break
        if keep is None:
            keep = (hexes[0]["q"], hexes[0]["r"])
        for h in hexes:
            if (h["q"], h["r"]) != keep:
                conn.execute(
                    "UPDATE world_hexes SET location_key = NULL "
                    "WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1",
                    (h["q"], h["r"]),
                )
                report["smears"].append({"key": lk, "kept": keep, "cleared_hex": (h["q"], h["r"])})
                logger.warning(
                    "reconcile_smear_cleared", key=lk, kept=keep, cleared_hex=(h["q"], h["r"])
                )

    # Step 2 — build canon map and backfill the derived cache from hexes.
    holders = conn.execute(
        "SELECT wh.q, wh.r, wh.location_key FROM world_hexes wh "
        "JOIN game_locations gl ON gl.key = wh.location_key AND gl.is_active = 1 "
        "WHERE wh.map_level = 0 AND wh.is_active = 1 "
        "AND wh.location_key IS NOT NULL AND wh.location_key != ''"
    ).fetchall()
    canonical: dict[str, tuple[int, int]] = {
        h["location_key"]: (int(h["q"]), int(h["r"])) for h in holders
    }
    for key, (q, r) in canonical.items():
        row = conn.execute(
            "SELECT world_hex_q, world_hex_r FROM game_locations WHERE key = ? AND is_active = 1",
            (key,),
        ).fetchone()
        if not row:
            continue
        if row["world_hex_q"] != q or row["world_hex_r"] != r:
            conn.execute(
                "UPDATE game_locations SET world_hex_q = ?, world_hex_r = ?, "
                "placement = 'placed' WHERE key = ?",
                (q, r, key),
            )
            report["backfilled"].append(
                {"key": key, "from": (row["world_hex_q"], row["world_hex_r"]), "to": (q, r)}
            )
            logger.info(
                "reconcile_cache_backfilled",
                key=key, to=(q, r), was=(row["world_hex_q"], row["world_hex_r"]),
            )

    # Step 3 — resolve stale pins not backed by hex canon. A pin is PROMOTED to
    # canon when its hex row exists, is empty, and nobody else claims those coords
    # (this preserves template start locations whose hex-claim was never written —
    # the old #1206/#1212 bug — instead of dropping their map pin). Otherwise the
    # pin is junk/displaced and is CLEARED (location stays narrative-playable).
    taken = set(canonical.values())
    stray = conn.execute(
        "SELECT key, world_hex_q, world_hex_r FROM game_locations "
        "WHERE is_active = 1 AND world_hex_q IS NOT NULL"
    ).fetchall()
    for s in stray:
        key = s["key"]
        q, r = int(s["world_hex_q"]), int(s["world_hex_r"])
        if canonical.get(key) == (q, r):
            continue
        hx = conn.execute(
            "SELECT location_key FROM world_hexes "
            "WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1 LIMIT 1",
            (q, r),
        ).fetchone()
        empty_hex = hx is not None and (hx["location_key"] is None or hx["location_key"] == "")
        if empty_hex and (q, r) not in taken:
            link_location_to_hex(conn, key, q, r)  # promote: write hex canon
            canonical[key] = (q, r)
            taken.add((q, r))
            report["promoted"].append({"key": key, "hex": (q, r)})
            logger.info("reconcile_stale_pin_promoted", key=key, hex=(q, r))
        else:
            conn.execute(
                "UPDATE game_locations SET world_hex_q = NULL, world_hex_r = NULL, "
                "placement = 'floating' WHERE key = ?",
                (key,),
            )
            report["cleared"].append({"key": key, "was": (q, r)})
            logger.info(
                "reconcile_stale_pin_cleared",
                key=s["key"], was=(int(s["world_hex_q"]), int(s["world_hex_r"])),
            )

    report["canonical_pairs"] = len(canonical)
    conn.commit()
    logger.info(
        "reconcile_location_hex_links_done",
        smears=len(report["smears"]),
        backfilled=len(report["backfilled"]),
        promoted=len(report["promoted"]),
        cleared=len(report["cleared"]),
        pairs=len(canonical),
    )
    return report
