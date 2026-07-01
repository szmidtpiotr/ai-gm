"""#1086: Collect beat/quest completion events for the current turn → [DONE] payload."""
import json
import sqlite3


def collect_turn_notifications(
    campaign_id: int,
    turn_number: int,
    conn: sqlite3.Connection,
    enabled: bool = True,
) -> dict:
    """Return completed_beats/completed_quests for this turn, or {} if none / disabled."""
    if not enabled:
        return {}

    rows = conn.execute(
        "SELECT event_type, event_data FROM game_events "
        "WHERE campaign_id=? AND event_type IN ('beat_complete','quest_complete') "
        "AND json_extract(event_data, '$.turn')=? ORDER BY id",
        (campaign_id, turn_number),
    ).fetchall()

    if not rows:
        return {}

    beats = []
    quests = []
    for row in rows:
        data = json.loads(row["event_data"] or "{}")
        if row["event_type"] == "beat_complete":
            beats.append({"key": data.get("beat_key", ""), "label": ""})
        else:
            quests.append({"title": data.get("quest_title", ""), "xp": data.get("xp", 0)})

    if beats:
        plan_row = conn.execute(
            "SELECT gm_plan_json FROM campaigns WHERE id=?", (campaign_id,)
        ).fetchone()
        if plan_row and plan_row["gm_plan_json"]:
            plan = json.loads(plan_row["gm_plan_json"])
            beat_map = {}
            for act in plan.get("acts", []):
                for beat in act.get("key_beats", []):
                    if isinstance(beat, dict):
                        beat_map[beat.get("beat_key", "")] = beat.get("summary", "")
            for b in beats:
                b["label"] = beat_map.get(b["key"], b["key"])
        else:
            for b in beats:
                b["label"] = b["key"]

    result = {}
    if beats:
        result["completed_beats"] = beats
    if quests:
        result["completed_quests"] = quests
    return result
