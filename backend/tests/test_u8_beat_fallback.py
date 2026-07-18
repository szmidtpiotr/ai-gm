"""TDD: #532 U8 — Beat fallback: auto-complete beats via objective_type."""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")
from _fixtures_schema import table_sql


def _make_db(plan_dict, template_key=None):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            gm_plan_json TEXT,
            template_key TEXT
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            turn_number INTEGER
        );
        """ + table_sql("game_config_meta") + """
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            session_flags TEXT DEFAULT '{}'
        );
    """)
    conn.execute(
        "INSERT INTO campaigns VALUES (1, ?, ?)",
        (json.dumps(plan_dict), template_key),
    )
    conn.execute("INSERT INTO game_sessions VALUES (1, 1, '{}')")
    conn.commit()
    return conn


def _beat(key, objective_type=None, objective_value=None, visited=False):
    b = {"beat_key": key, "description": f"Beat {key}", "visited": visited}
    if objective_type:
        b["objective_type"] = objective_type
        b["objective_value"] = objective_value
    return b


def _plan(*beats):
    return {"acts": [{"key_beats": list(beats)}]}


# ─── Auto-complete by event type ─────────────────────────────────────────────

def test_beat_auto_complete_kill_enemy():
    """Beat with kill_enemy objective completes when matching enemy killed."""
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event

    conn = _make_db(_plan(_beat("kill_boss", "kill_enemy", "Goblin Szef")))
    result = auto_complete_beats_by_event(1, "kill_enemy", "Goblin Szef", 5, conn)
    assert result is True

    row = conn.execute("SELECT gm_plan_json FROM campaigns WHERE id=1").fetchone()
    beat = json.loads(row[0])["acts"][0]["key_beats"][0]
    assert beat["visited"] is True
    assert beat["visited_at_turn"] == 5


def test_beat_auto_complete_visit_location():
    """Beat with visit_location objective completes when location visited."""
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event

    conn = _make_db(_plan(_beat("go_tower", "visit_location", "Wieża Magów")))
    result = auto_complete_beats_by_event(1, "visit_location", "Wieża Magów", 8, conn)
    assert result is True

    beat = json.loads(
        conn.execute("SELECT gm_plan_json FROM campaigns WHERE id=1").fetchone()[0]
    )["acts"][0]["key_beats"][0]
    assert beat["visited"] is True
    assert beat["visited_at_turn"] == 8


def test_beat_auto_complete_talk_to_npc():
    """Beat with talk_to_npc objective completes when NPC talked to."""
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event

    conn = _make_db(_plan(_beat("meet_hrothgar", "talk_to_npc", "Hrothgar Kowal")))
    result = auto_complete_beats_by_event(1, "talk_to_npc", "Hrothgar Kowal", 3, conn)
    assert result is True

    beat = json.loads(
        conn.execute("SELECT gm_plan_json FROM campaigns WHERE id=1").fetchone()[0]
    )["acts"][0]["key_beats"][0]
    assert beat["visited"] is True


def test_beat_auto_complete_find_item():
    """Beat with find_item objective completes when item found/used."""
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event

    conn = _make_db(_plan(_beat("get_key", "find_item", "Starożytny Klucz")))
    result = auto_complete_beats_by_event(1, "find_item", "Starożytny Klucz", 12, conn)
    assert result is True

    beat = json.loads(
        conn.execute("SELECT gm_plan_json FROM campaigns WHERE id=1").fetchone()[0]
    )["acts"][0]["key_beats"][0]
    assert beat["visited"] is True


def test_beat_without_objective_not_auto_completed():
    """Beat without objective_type is not auto-completed (still requires LLM tag)."""
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event

    conn = _make_db(_plan(_beat("narrative_beat")))  # no objective_type
    result = auto_complete_beats_by_event(1, "kill_enemy", "Goblin Szef", 5, conn)
    assert result is False

    beat = json.loads(
        conn.execute("SELECT gm_plan_json FROM campaigns WHERE id=1").fetchone()[0]
    )["acts"][0]["key_beats"][0]
    assert beat["visited"] is False


def test_beat_already_visited_not_double_marked():
    """Already visited beat is not marked again."""
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event

    conn = _make_db(
        _plan(_beat("kill_boss", "kill_enemy", "Goblin Szef", visited=True))
    )
    # manually set visited_at_turn=3
    plan = json.loads(
        conn.execute("SELECT gm_plan_json FROM campaigns WHERE id=1").fetchone()[0]
    )
    plan["acts"][0]["key_beats"][0]["visited_at_turn"] = 3
    conn.execute("UPDATE campaigns SET gm_plan_json=? WHERE id=1", (json.dumps(plan),))
    conn.commit()

    result = auto_complete_beats_by_event(1, "kill_enemy", "Goblin Szef", 10, conn)
    assert result is False  # already visited — no change

    beat = json.loads(
        conn.execute("SELECT gm_plan_json FROM campaigns WHERE id=1").fetchone()[0]
    )["acts"][0]["key_beats"][0]
    assert beat["visited_at_turn"] == 3  # unchanged


def test_keyword_match_polish_declension():
    """Polish name declension handled (Hrothgar → Hrothgara match)."""
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event

    conn = _make_db(_plan(_beat("meet_hrothgar", "talk_to_npc", "Hrothgar")))
    # NPC label from DB might be "Hrothgara" (genitive) in narrative
    result = auto_complete_beats_by_event(1, "talk_to_npc", "Hrothgara Kowal", 4, conn)
    assert result is True


def test_wrong_event_type_no_match():
    """Event type mismatch does not complete beat."""
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event

    conn = _make_db(_plan(_beat("kill_boss", "kill_enemy", "Goblin Szef")))
    result = auto_complete_beats_by_event(1, "visit_location", "Goblin Szef", 5, conn)
    assert result is False
