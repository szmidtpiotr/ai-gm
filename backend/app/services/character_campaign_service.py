import json
import sqlite3


def maybe_reset_hp_for_new_campaign(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
) -> bool:
    """C19: Reset hp_current to max_hp when entering a fresh campaign (0 turns played).

    Resuming an existing campaign leaves HP unchanged.
    Returns True if reset was performed, False otherwise.
    """
    turn_count_row = conn.execute(
        "SELECT COUNT(*) FROM campaign_turns WHERE campaign_id = ?", (campaign_id,)
    ).fetchone()
    if turn_count_row and int(turn_count_row[0]) > 0:
        return False

    char = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    if not char:
        return False

    try:
        sheet = json.loads(char["sheet_json"] or "{}")
    except Exception:
        return False

    max_hp = int(sheet.get("max_hp") or 0)
    if max_hp <= 0:
        return False

    sheet["current_hp"] = max_hp
    conn.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet, ensure_ascii=False), character_id),
    )
    return True
