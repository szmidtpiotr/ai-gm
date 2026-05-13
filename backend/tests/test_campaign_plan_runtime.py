"""
Tests for Campaign Plan Runtime — V2 Phase 04 Task 13
"""
import json
import sqlite3
import pytest
from app.services.campaign_plan_runtime import (
    get_plan, save_plan, mark_beat_visited, mark_npc_dead,
    log_deviation, get_narrator_context_block
)

SAMPLE_PLAN = {
    "title": "Test Campaign",
    "premise": "A test.",
    "active_act": 1,
    "acts": [
        {
            "number": 1, "title": "Act 1", "summary": "The beginning.",
            "key_beats": [
                {"beat_key": "meet_informant", "title": "Meet informant", "visited": False},
                {"beat_key": "find_clue", "title": "Find clue", "visited": False},
            ],
            "completed": False
        },
        {
            "number": 2, "title": "Act 2", "summary": "The middle.", "key_beats": [], "completed": False
        },
    ],
    "key_npcs": [
        {"key": "informant", "name": "Boris", "alive": True, "importance": "critical", "deviation_consequence": "branch"},
        {"key": "merchant", "name": "Aldric", "alive": True, "importance": "supporting", "deviation_consequence": "steer"},
    ],
    "endings": [],
    "deviations": [],
    "deviation_level": "normal",
}


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY, gm_plan_json TEXT DEFAULT '{}')")
    conn.execute("INSERT INTO campaigns VALUES (1, ?)", (json.dumps(SAMPLE_PLAN),))
    conn.commit()
    yield conn
    conn.close()


def test_get_plan(db):
    plan = get_plan(1, db)
    assert plan["title"] == "Test Campaign"
    assert len(plan["acts"]) == 2


def test_get_plan_missing(db):
    assert get_plan(999, db) == {}


def test_save_plan(db):
    plan = get_plan(1, db)
    plan["title"] = "Changed"
    save_plan(1, plan, db)
    assert get_plan(1, db)["title"] == "Changed"


def test_mark_beat_visited(db):
    result = mark_beat_visited(1, "meet_informant", 5, db)
    assert result is True
    plan = get_plan(1, db)
    beat = next(b for b in plan["acts"][0]["key_beats"] if b["beat_key"] == "meet_informant")
    assert beat["visited"] is True
    assert beat["visited_at_turn"] == 5


def test_mark_beat_already_visited(db):
    mark_beat_visited(1, "meet_informant", 5, db)
    result = mark_beat_visited(1, "meet_informant", 6, db)
    assert result is False  # already visited


def test_mark_npc_dead(db):
    consequence = mark_npc_dead(1, "informant", db)
    assert consequence == "branch"
    plan = get_plan(1, db)
    npc = next(n for n in plan["key_npcs"] if n["key"] == "informant")
    assert npc["alive"] is False


def test_log_deviation(db):
    log_deviation(1, "Player killed Boris early", "major", db)
    plan = get_plan(1, db)
    assert len(plan["deviations"]) == 1
    assert plan["deviation_level"] == "major"


def test_narrator_context_block(db):
    block = get_narrator_context_block(1, db)
    assert "Act 1" in block
    assert "Boris" in block or "CAMPAIGN" in block


def test_narrator_context_empty_plan(db):
    db.execute("UPDATE campaigns SET gm_plan_json = '{}' WHERE id = 1")
    db.commit()
    block = get_narrator_context_block(1, db)
    assert block == ""
