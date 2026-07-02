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

    # Write session_flags if anything changed
    if flags_dirty:
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), session_id),
        )

    # Write current_location_id
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

    # Mirror current_hex into sheet_json so the player map pin stays correct.
    # Auto-lookup character from campaign if not explicitly provided.
    if current_hex is not None:
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
