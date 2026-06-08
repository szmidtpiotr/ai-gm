"""World State Service — B1/B2 snapshot persistence + live session_flags helpers.

Provides get/save for world_state_snapshots (B1) and get/set helpers for the
5 live World State columns on game_sessions (B2). Used by:
- B3 (Gate Mechanic reads latest snapshot + flags)
- B5 (auto-save per turn)
- B6 (admin viewer)
"""
import json
import sqlite3
from typing import Any

DB_PATH = "/data/ai_gm.db"

# ── B2: live World State column helpers ────────────────────────────────────────

_WORLD_STATE_COLUMNS = {
    "scene_enemies": (list, []),
    "scene_npcs": (list, []),
    "scene_cleared": (bool, False),
    "active_quests": (list, []),
    "player_conditions": (list, []),
}


def get_world_state_flags(campaign_id: int) -> dict:
    """Return the 5 live World State fields for a campaign.

    Reads dedicated columns from game_sessions. Returns defaults when no
    session exists (old campaigns) — never raises KeyError.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT scene_enemies, scene_npcs, scene_cleared,
                      active_quests, player_conditions
               FROM game_sessions WHERE campaign_id = ? LIMIT 1""",
            (campaign_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return {key: default for key, (_, default) in _WORLD_STATE_COLUMNS.items()}

    result = {}
    for key, (typ, default) in _WORLD_STATE_COLUMNS.items():
        raw = row[key]
        if typ is list:
            try:
                result[key] = json.loads(raw) if raw else default
            except (json.JSONDecodeError, TypeError):
                result[key] = default
        elif typ is bool:
            result[key] = bool(raw) if raw is not None else default
        else:
            result[key] = raw if raw is not None else default
    return result


def set_world_state_flags(campaign_id: int, **kwargs) -> None:
    """PATCH specific World State fields on the game_session row.

    Only updates the keys passed in kwargs; unknown keys are silently ignored.
    Does nothing if no session row exists for campaign_id.
    """
    known = {k: v for k, v in kwargs.items() if k in _WORLD_STATE_COLUMNS}
    if not known:
        return

    assignments = []
    values = []
    for key, value in known.items():
        typ, _ = _WORLD_STATE_COLUMNS[key]
        assignments.append(f"{key} = ?")
        if typ is list:
            values.append(json.dumps(value, ensure_ascii=False))
        elif typ is bool:
            values.append(1 if value else 0)
        else:
            values.append(value)

    values.append(campaign_id)
    sql = f"UPDATE game_sessions SET {', '.join(assignments)} WHERE campaign_id = ?"

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(sql, values)
        conn.commit()
    finally:
        conn.close()


def get_latest_snapshot(campaign_id: int) -> dict | None:
    """Return the most recent snapshot for a campaign, or None if none exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT * FROM world_state_snapshots
            WHERE campaign_id = ?
            ORDER BY turn_number DESC, id DESC
            LIMIT 1
            """,
            (campaign_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_snapshot(
    campaign_id: int,
    turn_number: int,
    state_dict: dict[str, Any],
    source: str = "auto",
) -> int:
    """Persist a World State snapshot. Returns the new row id."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            """
            INSERT INTO world_state_snapshots
                (campaign_id, turn_number, snapshot_json, snapshot_source)
            VALUES (?, ?, ?, ?)
            """,
            (campaign_id, turn_number, json.dumps(state_dict, ensure_ascii=False), source),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ── B5: Auto-save snapshot per turn ────────────────────────────────────────────

def build_snapshot(campaign_id: int) -> dict:
    """Build snapshot dict from current campaign state.

    Gathers: scene_enemies, scene_npcs, active_quests, player_conditions,
    turn_number, and campaign_id.
    """
    ws = get_world_state_flags(campaign_id)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Get highest turn_number for this campaign
        turn_row = conn.execute(
            """SELECT MAX(turn_number) as max_turn FROM campaign_turns
               WHERE campaign_id = ?""",
            (campaign_id,),
        ).fetchone()
        turn_number = turn_row["max_turn"] or 0 if turn_row else 0
        # D6 (#381) — narrative_state lives in session_flags JSON (not a dedicated
        # column), so read it here for the snapshot / Stan Świata / Inspector.
        narrative_state: dict = {}
        sf_row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if sf_row and sf_row["session_flags"]:
            try:
                narrative_state = (json.loads(sf_row["session_flags"]) or {}).get("narrative_state") or {}
            except (json.JSONDecodeError, TypeError):
                narrative_state = {}
    finally:
        conn.close()

    snapshot = {
        "campaign_id": campaign_id,
        "turn_number": turn_number,
        "scene_enemies": ws.get("scene_enemies", []),
        "scene_npcs": ws.get("scene_npcs", []),
        "active_quests": ws.get("active_quests", []),
        "player_conditions": ws.get("player_conditions", []),
        "scene_cleared": ws.get("scene_cleared", False),
        "narrative_state": narrative_state,
    }
    return snapshot


def auto_save_snapshot(campaign_id: int, source: str = "auto") -> int:
    """Auto-save snapshot: build + insert + prune to 50.

    Returns the new snapshot id.
    """
    snapshot = build_snapshot(campaign_id)
    turn_number = snapshot["turn_number"]

    # Save
    snapshot_id = save_snapshot(campaign_id, turn_number, snapshot, source)

    # Prune: keep only last 50 per campaign
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            DELETE FROM world_state_snapshots
            WHERE campaign_id = ? AND id NOT IN (
                SELECT id FROM world_state_snapshots
                WHERE campaign_id = ?
                ORDER BY id DESC
                LIMIT 50
            )
            """,
            (campaign_id, campaign_id),
        )
        conn.commit()
    finally:
        conn.close()

    return snapshot_id
