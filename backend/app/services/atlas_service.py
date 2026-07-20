"""Atlas Kresów (#1191) — cross-campaign exploration stats per hero.

Hex discovery is stored PER-CAMPAIGN (campaign_hex_data.discovered). A hero
(Hero-First model) plays many campaigns, so the Atlas aggregates on-read across
all of a hero's campaigns — current (characters.campaign_id) plus completed
(character_campaign_history.campaign_id) — mirroring the Hero Chronicle pattern.
It NEVER writes; world_hexes (map_level=0) is Piotr-owned and read-only here.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.core.logging import get_logger
from app.core.db_runtime import resolve_db_path

logger = get_logger(__name__)

ATLAS_DB_PATH = resolve_db_path()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(ATLAS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _hero_campaign_ids(conn: sqlite3.Connection, character_id: int) -> list[int]:
    ids: set[int] = set()
    cur = conn.execute(
        "SELECT campaign_id FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    if cur and cur["campaign_id"]:
        ids.add(int(cur["campaign_id"]))
    for r in conn.execute(
        "SELECT DISTINCT campaign_id FROM character_campaign_history WHERE character_id = ?",
        (character_id,),
    ).fetchall():
        if r["campaign_id"]:
            ids.add(int(r["campaign_id"]))
    return sorted(ids)


def get_atlas(character_id: Any, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Aggregate exploration stats for the endpoint (#1191 E3).

    Returns hexes (discovered/total/pct + per-region), locations discovered,
    and rumors (heard/confirmed, #1191 E4). Robust: unknown hero → empty sums,
    never raises 500.
    """
    try:
        cid = int(character_id)
    except (TypeError, ValueError):
        return _empty_atlas()
    own = conn is None
    c = conn or _conn()
    try:
        camp_ids = _hero_campaign_ids(c, cid)

        # ── total overworld hexes (map_level 0) ──
        total_hexes = c.execute(
            "SELECT COUNT(*) FROM world_hexes WHERE COALESCE(map_level, 0) = 0 "
            "AND COALESCE(is_active, 1) = 1"
        ).fetchone()[0]

        discovered_pairs: set[tuple[int, int]] = set()
        region_counts: dict[str, int] = {}
        location_count = 0
        if camp_ids:
            ph = ",".join("?" for _ in camp_ids)
            disc = c.execute(
                f"SELECT DISTINCT hex_q, hex_r FROM campaign_hex_data "
                f"WHERE campaign_id IN ({ph}) AND discovered = 1",
                (*camp_ids,),
            ).fetchall()
            discovered_pairs = {(int(r["hex_q"]), int(r["hex_r"])) for r in disc}

            # per-region breakdown via world_hexes lookup (overworld only)
            for (q, r) in discovered_pairs:
                reg_row = c.execute(
                    "SELECT region FROM world_hexes "
                    "WHERE q = ? AND r = ? AND COALESCE(map_level, 0) = 0 LIMIT 1",
                    (q, r),
                ).fetchone()
                reg = (reg_row["region"] if reg_row and reg_row["region"] else "nieznany")
                region_counts[reg] = region_counts.get(reg, 0) + 1

            # locations sitting on a discovered hex
            if discovered_pairs:
                pair_ph = " OR ".join("(world_hex_q = ? AND world_hex_r = ?)"
                                      for _ in discovered_pairs)
                flat: list[int] = []
                for (q, r) in discovered_pairs:
                    flat.extend((q, r))
                location_count = c.execute(
                    f"SELECT COUNT(DISTINCT key) FROM game_locations "
                    f"WHERE COALESCE(is_active, 1) = 1 AND ({pair_ph})",
                    (*flat,),
                ).fetchone()[0]

        discovered = len(discovered_pairs)
        pct = round(100 * discovered / total_hexes) if total_hexes else 0
        regions = [
            {"region": k, "discovered": v}
            for k, v in sorted(region_counts.items(), key=lambda kv: -kv[1])
        ]

        rumors = _rumor_summary(c, cid)
        treasures = _treasure_summary(c, cid)

        return {
            "hexes": {
                "discovered": discovered,
                "total": total_hexes,
                "pct": pct,
                "regions": regions,
            },
            "locations": {"discovered": location_count},
            "rumors": rumors,
            "treasure_sites": treasures,
        }
    except Exception as e:
        logger.warning("atlas_get_failed", character_id=character_id, error=str(e))
        return _empty_atlas()
    finally:
        if own:
            c.close()


def _rumor_summary(conn: sqlite3.Connection, character_id: int) -> dict[str, Any]:
    """Rumor counts + list. #1190 adds debunked count + suspected/truth flags on
    each entry (for the „fałszywa"/„podejrzana" badges). Tolerant of the pre-#1190
    schema (missing columns) — falls back to the legacy column set."""
    try:
        rows = conn.execute(
            "SELECT rumor_text, target_type, target_key, status, heard_at, confirmed_at, "
            "       COALESCE(suspected,0) AS suspected, COALESCE(truth_flag,1) AS truth_flag "
            "FROM character_rumors WHERE character_id = ? ORDER BY heard_at DESC",
            (character_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        try:
            rows = conn.execute(
                "SELECT rumor_text, target_type, target_key, status, heard_at, confirmed_at "
                "FROM character_rumors WHERE character_id = ? ORDER BY heard_at DESC",
                (character_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            return {"heard": 0, "confirmed": 0, "debunked": 0, "entries": []}
    heard = sum(1 for r in rows if r["status"] == "heard")
    confirmed = sum(1 for r in rows if r["status"] == "confirmed")
    debunked = sum(1 for r in rows if r["status"] == "debunked")
    entries = [dict(r) for r in rows]
    return {"heard": heard, "confirmed": confirmed, "debunked": debunked, "entries": entries}


def _treasure_summary(conn: sqlite3.Connection, character_id: int) -> dict[str, Any]:
    """#1196 — treasures this hero has dug up (found). Empty if table missing."""
    try:
        rows = conn.execute(
            "SELECT label, region, hex_q, hex_r, found_at FROM world_treasures "
            "WHERE found_by_character_id = ? AND state = 'found' ORDER BY found_at DESC",
            (character_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return {"found": 0, "entries": []}
    entries = [
        {"label": r["label"] or "Skarb", "region": r["region"],
         "hex": {"q": r["hex_q"], "r": r["hex_r"]}, "found_at": r["found_at"]}
        for r in rows
    ]
    return {"found": len(entries), "entries": entries}


def _empty_atlas() -> dict[str, Any]:
    return {
        "hexes": {"discovered": 0, "total": 0, "pct": 0, "regions": []},
        "locations": {"discovered": 0},
        "rumors": {"heard": 0, "confirmed": 0, "debunked": 0, "entries": []},
        "treasure_sites": {"found": 0, "entries": []},
    }
