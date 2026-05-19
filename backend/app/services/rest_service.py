"""
Rest Service — Stage 2B

Resolves safe-for-rest status for a given hex (q, r) by walking:
    world_hexes.location_key → game_locations.safe_for_rest

Used by /rest endpoints (Stage 2C) and admin diagnostic UI. Returns a
structured result with the "why" so admins can debug inheritance gaps
without spelunking SQL.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import structlog

logger = structlog.get_logger()

DB_PATH = "/data/ai_gm.db"


def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hex_is_safe_for_rest(
    q: int,
    r: int,
    *,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Resolve safe-for-rest for a hex.

    Returns a dict shaped:
        {
            "safe": bool,
            "reason": str,            # one of: safe_via_location |
                                      #   unsafe_location_flag_off |
                                      #   wilderness_no_location |
                                      #   unknown_location_key |
                                      #   no_hex_record
            "location_key": str|None,
            "location_label": str|None,
            "hex_type": str|None,
            "q": int,
            "r": int,
        }
    """
    own_conn = False
    if conn is None:
        conn = _open_conn()
        own_conn = True

    try:
        hex_row = conn.execute(
            """SELECT q, r, hex_type, label, location_key
               FROM world_hexes
               WHERE q = ? AND r = ? AND is_active = 1
               LIMIT 1""",
            (q, r),
        ).fetchone()

        result: dict[str, Any] = {
            "safe": False,
            "reason": "no_hex_record",
            "location_key": None,
            "location_label": None,
            "hex_type": None,
            "q": q,
            "r": r,
        }

        if not hex_row:
            return result

        result["hex_type"] = hex_row["hex_type"]
        location_key = hex_row["location_key"]
        result["location_key"] = location_key

        if not location_key:
            result["reason"] = "wilderness_no_location"
            return result

        loc_row = conn.execute(
            """SELECT key, label, safe_for_rest
               FROM game_locations
               WHERE key = ? AND is_active = 1
               LIMIT 1""",
            (location_key,),
        ).fetchone()

        if not loc_row:
            result["reason"] = "unknown_location_key"
            return result

        result["location_label"] = loc_row["label"]
        is_safe = bool(loc_row["safe_for_rest"])
        result["safe"] = is_safe
        result["reason"] = "safe_via_location" if is_safe else "unsafe_location_flag_off"
        return result
    finally:
        if own_conn:
            conn.close()
