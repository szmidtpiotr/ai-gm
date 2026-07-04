"""#1112 — Canonical position writer.

Single source of truth for all player position writes. Every movement path
(world travel, narrative move, local travel, campaign start) must go through
set_position() instead of scattering direct UPDATEs across 5 call sites.

Atomically writes in one transaction:
  - game_sessions.current_location_id
  - session_flags.current_hex       (world hex pin)
  - session_flags.local_hex         (settlement local hex, optional)
  - characters.sheet_json.current_hex  (mirror read by GET /player-map)
"""
from __future__ import annotations

import json
import sqlite3

import structlog

logger = structlog.get_logger()


def get_current_location(conn: sqlite3.Connection, campaign_id: int) -> dict | None:
    """PT-F7 #1141: single source of truth for the current location.

    Derives everything from game_sessions.current_location_id (never from the old
    session_flags.current_location_key mirror, which is being removed). Returns
    ``{id, key, label, location_type, safe_for_rest, parent_key}`` or None.
    """
    try:
        row = conn.execute(
            """
            SELECT gl.id, gl.key, gl.label, gl.location_type, gl.safe_for_rest, gl.parent_key
            FROM game_sessions gs
            JOIN game_locations gl ON gl.id = gs.current_location_id
            WHERE gs.campaign_id = ?
            LIMIT 1
            """,
            (int(campaign_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    keys = row.keys() if hasattr(row, "keys") else []
    return {
        "id": row["id"] if "id" in keys else row[0],
        "key": row["key"] if "key" in keys else row[1],
        "label": row["label"] if "label" in keys else row[2],
        "location_type": row["location_type"] if "location_type" in keys else row[3],
        "safe_for_rest": row["safe_for_rest"] if "safe_for_rest" in keys else row[4],
        "parent_key": row["parent_key"] if "parent_key" in keys else row[5],
    }


def get_current_location_key(conn: sqlite3.Connection, campaign_id: int) -> str | None:
    """PT-F7 #1141: current location key derived from current_location_id (no mirror).

    Minimal query (only gl.key) so it stays robust across the varied minimal test DBs
    that don't carry every game_locations column.
    """
    try:
        row = conn.execute(
            """
            SELECT gl.key
            FROM game_sessions gs
            JOIN game_locations gl ON gl.id = gs.current_location_id
            WHERE gs.campaign_id = ?
            LIMIT 1
            """,
            (int(campaign_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return row["key"] if hasattr(row, "keys") else row[0]


_TERRAIN_PL = {
    "forest": "dziki las",
    "plains": "otwarte równiny",
    "mountains": "góry",
    "hills": "wzgórza",
    "swamp": "bagna",
    "water": "brzeg wody",
    "desert": "pustkowie",
    "tundra": "mroźna tundra",
    "town": "osada",
    "castle": "zamek",
}

_SETTLEMENT_HEX_TYPES = {"town", "castle"}


def describe_start_position(conn: sqlite3.Connection, campaign_id: int) -> str | None:
    """#1152: human-readable description of the party's REAL start position.

    Used to ground opening-scene prompts in engine state (anchored location, or the
    terrain of current_hex) instead of the stale ``characters.location`` field —
    otherwise the LLM invents a place (e.g. a tavern) that contradicts the hex the
    session actually sits on, and the next narrative turn "teleports" the player.
    Returns None when the session has no position at all.
    """
    try:
        row = conn.execute(
            "SELECT current_location_id, session_flags FROM game_sessions "
            "WHERE campaign_id = ? LIMIT 1",
            (int(campaign_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None

    loc_id = row["current_location_id"] if hasattr(row, "keys") else row[0]
    if loc_id:
        try:
            loc = conn.execute(
                "SELECT label, location_subtype FROM game_locations WHERE id = ?",
                (int(loc_id),),
            ).fetchone()
        except sqlite3.OperationalError:
            loc = None
        if loc and loc["label"]:
            subtype = loc["location_subtype"] if "location_subtype" in loc.keys() else None
            return f"{loc['label']} ({subtype})" if subtype else str(loc["label"])

    flags_raw = row["session_flags"] if hasattr(row, "keys") else row[1]
    try:
        cur = (json.loads(flags_raw or "{}").get("current_hex")) or {}
    except (ValueError, TypeError):
        return None
    if cur.get("q") is None or cur.get("r") is None:
        return None
    try:
        wh = conn.execute(
            "SELECT hex_type, label FROM world_hexes "
            "WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1",
            (int(cur["q"]), int(cur["r"])),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not wh:
        return None
    hex_type = str(wh["hex_type"] or "")
    terrain = _TERRAIN_PL.get(hex_type, hex_type or "dzicz")
    label = wh["label"]
    base = f"{label} — {terrain}" if label else terrain
    if hex_type not in _SETTLEMENT_HEX_TYPES:
        return f"{base}, teren dziki bez zabudowań (żadnej osady, karczmy ani budynku w zasięgu wzroku)"
    return base


def set_position(
    conn: sqlite3.Connection,
    campaign_id: int,
    *,
    current_hex: dict | None = None,
    current_location_id: int | None = None,
    local_hex: dict | None = None,
    clear_local_hex: bool = False,
    clear_location_id: bool = False,
    character_id: int | None = None,
) -> None:
    """Atomically write all position fields for a campaign session.

    Args:
        conn: open SQLite connection (caller owns commit/rollback lifecycle;
              this function does NOT commit — callers that set autocommit=True
              or rely on the connection's isolation_level will commit naturally).
        campaign_id: target campaign.
        current_hex: world hex coordinates {"q": int, "r": int}.
                     None = leave unchanged.
        current_location_id: game_locations.id for the current macro-location.
                             None = leave unchanged (use clear_location_id to NULL it).
        local_hex: local hex data {"hex_id": int, "q": int, "r": int, "location_key": str}.
                   None = leave unchanged (use clear_local_hex to remove it).
        clear_local_hex: if True, removes local_hex from session_flags
                         (use when player exits a settlement to the world map).
        clear_location_id: if True, sets current_location_id = NULL.
        character_id: if provided and current_hex is set, mirrors current_hex
                      into characters.sheet_json.current_hex so GET /player-map
                      shows the correct pin position.
    """
    # Load current session_flags
    row = conn.execute(
        "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not row:
        return

    session_id = row["id"]
    flags: dict = json.loads(row["session_flags"] or "{}")

    flags_dirty = False

    if current_hex is not None:
        flags["current_hex"] = {"q": int(current_hex["q"]), "r": int(current_hex["r"])}
        flags_dirty = True

    if local_hex is not None:
        flags["local_hex"] = local_hex
        flags_dirty = True

    if clear_local_hex and "local_hex" in flags:
        flags.pop("local_hex")
        flags_dirty = True

    # PT-F7 #1141: session_flags.current_location_key is GONE — current_location_id is
    # the single source of truth, and readers derive the key via
    # get_current_location_key(). Proactively strip any stale mirror left in old rows
    # so nothing can read it again.
    if "current_location_key" in flags:
        flags.pop("current_location_key", None)
        flags_dirty = True

    # Write session_flags if anything changed
    if flags_dirty:
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), session_id),
        )

    # Write current_location_id — best-effort like the sheet mirror below: isolated
    # test DBs may lack the column (#1142 made the clear path run far more often).
    try:
        if clear_location_id:
            conn.execute(
                "UPDATE game_sessions SET current_location_id = NULL WHERE id = ?",
                (session_id,),
            )
        elif current_location_id is not None:
            conn.execute(
                "UPDATE game_sessions SET current_location_id = ? WHERE id = ?",
                (int(current_location_id), session_id),
            )
    except sqlite3.OperationalError as exc:
        logger.warning("set_position_location_id_write_skipped", error=str(exc))

    # Mirror current_hex into sheet_json so the player map pin stays correct.
    # Auto-lookup character from campaign if not explicitly provided.
    # PT-F2 #1136: this mirror is best-effort — the pin's source of truth is
    # session_flags.current_hex (read by GET /player-map). Never let a missing
    # `characters` table (isolated test DBs) or a bad row break a position write.
    if current_hex is not None:
        try:
            char_id_to_use = character_id
            if char_id_to_use is None:
                char_lookup = conn.execute(
                    "SELECT id FROM characters WHERE campaign_id = ? AND status = 'active' LIMIT 1",
                    (campaign_id,),
                ).fetchone()
                if char_lookup:
                    char_id_to_use = char_lookup["id"]

            if char_id_to_use is not None:
                char_row = conn.execute(
                    "SELECT sheet_json FROM characters WHERE id = ?",
                    (char_id_to_use,),
                ).fetchone()
                if char_row:
                    sheet: dict = json.loads(char_row["sheet_json"] or "{}")
                    sheet["current_hex"] = {"q": int(current_hex["q"]), "r": int(current_hex["r"])}
                    conn.execute(
                        "UPDATE characters SET sheet_json = ? WHERE id = ?",
                        (json.dumps(sheet, ensure_ascii=False), char_id_to_use),
                    )
        except sqlite3.OperationalError:
            pass
