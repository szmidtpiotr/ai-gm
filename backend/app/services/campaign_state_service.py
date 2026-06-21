"""G16 (#784): per-campaign battle state (HP/mana/conditions) for multiplayer isolation."""
import json
import sqlite3


def is_mp_campaign(conn: sqlite3.Connection, campaign_id: int) -> bool:
    """True if campaign mode is 'multiplayer'."""
    row = conn.execute(
        "SELECT mode FROM campaigns WHERE id = ?", (campaign_id,)
    ).fetchone()
    return bool(row and row["mode"] == "multiplayer")


def get_battle_state(
    conn: sqlite3.Connection, campaign_id: int, character_id: int
) -> dict | None:
    """Return character_campaign_state row as dict, or None if not found."""
    row = conn.execute(
        "SELECT * FROM character_campaign_state WHERE character_id=? AND campaign_id=?",
        (character_id, campaign_id),
    ).fetchone()
    if not row:
        return None
    return {
        "current_hp": int(row["current_hp"] or 0),
        "max_hp": int(row["max_hp"] or 0),
        "current_mana": int(row["current_mana"] or 0),
        "max_mana": int(row["max_mana"] or 0),
        "conditions": json.loads(row["conditions_json"] or "[]"),
        "position": json.loads(row["position_json"] or "null") if row["position_json"] else None,
    }


def save_battle_state(
    conn: sqlite3.Connection, campaign_id: int, character_id: int, sheet: dict
) -> None:
    """Write HP/mana/conditions from sheet into character_campaign_state (upsert)."""
    conditions = sheet.get("conditions")
    if not isinstance(conditions, list):
        conditions = []
    conn.execute(
        """INSERT INTO character_campaign_state
               (character_id, campaign_id, current_hp, max_hp, current_mana, max_mana, conditions_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(character_id, campaign_id) DO UPDATE SET
               current_hp=excluded.current_hp,
               max_hp=excluded.max_hp,
               current_mana=excluded.current_mana,
               max_mana=excluded.max_mana,
               conditions_json=excluded.conditions_json,
               updated_at=CURRENT_TIMESTAMP""",
        (
            int(character_id),
            int(campaign_id),
            int(sheet.get("current_hp") or 0),
            int(sheet.get("max_hp") or 0),
            int(sheet.get("current_mana") or 0),
            int(sheet.get("max_mana") or 0),
            json.dumps(conditions, ensure_ascii=False),
        ),
    )


def create_initial_state(
    conn: sqlite3.Connection, campaign_id: int, character_id: int, sheet: dict
) -> None:
    """Create CCS row from sheet on first join. No-op if row already exists."""
    conditions = sheet.get("conditions")
    if not isinstance(conditions, list):
        conditions = []
    conn.execute(
        """INSERT OR IGNORE INTO character_campaign_state
               (character_id, campaign_id, current_hp, max_hp, current_mana, max_mana, conditions_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            int(character_id),
            int(campaign_id),
            int(sheet.get("current_hp") or 0),
            int(sheet.get("max_hp") or 0),
            int(sheet.get("current_mana") or 0),
            int(sheet.get("max_mana") or 0),
            json.dumps(conditions, ensure_ascii=False),
        ),
    )


def overlay_sheet_from_campaign_state(
    conn: sqlite3.Connection, campaign_id: int, character_id: int, sheet: dict
) -> None:
    """Overlay HP/mana/conditions in sheet from CCS for MP campaigns (in place).

    Solo campaigns: no-op — sheet_json remains authoritative.
    """
    if not is_mp_campaign(conn, campaign_id):
        return
    state = get_battle_state(conn, campaign_id, character_id)
    if state is None:
        return
    sheet["current_hp"] = state["current_hp"]
    sheet["max_hp"] = state["max_hp"]
    sheet["current_mana"] = state["current_mana"]
    sheet["max_mana"] = state["max_mana"]
    sheet["conditions"] = state["conditions"]
