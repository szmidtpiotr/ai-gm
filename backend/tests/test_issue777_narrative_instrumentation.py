"""TDD: Issue #777 — game_events + turn_decisions empty for narrative campaigns.

Red: game_events has 0 rows after quest_complete/xp_grant/location_new/item_grant/gold_grant.
     turn_decisions has 0 rows globally (writer never called in streaming path).
Green: all narrative event types emit a game_events row; turn_decisions writer verified.
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Minimal schema for testing ───────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    user_id INTEGER NOT NULL DEFAULT 1,
    campaign_id INTEGER,
    sheet_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active',
    visited_location_keys TEXT
);

CREATE TABLE IF NOT EXISTS character_quests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    campaign_id INTEGER NOT NULL,
    quest_type TEXT NOT NULL DEFAULT 'main',
    quest_key TEXT,
    title TEXT NOT NULL,
    narrative TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_turn INTEGER DEFAULT 1,
    completed_turn INTEGER,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS character_xp_grants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    campaign_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    label TEXT,
    amount INTEGER NOT NULL DEFAULT 0,
    turn_number INTEGER,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS game_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    campaign_id INTEGER,
    character_id INTEGER,
    user_id INTEGER,
    event_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS turn_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    character_id INTEGER,
    turn_number REAL,
    user_text TEXT,
    action_type TEXT,
    confidence REAL,
    route TEXT,
    gate_blocked INTEGER,
    gate_reason TEXT,
    handler TEXT,
    correction_applied INTEGER,
    raw_intent TEXT,
    meta TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    location_type TEXT NOT NULL DEFAULT 'micro',
    is_active INTEGER NOT NULL DEFAULT 1
);

INSERT INTO characters (id, name, user_id, campaign_id, sheet_json)
  VALUES (1, 'Aldric', 1, 100, '{"xp": 0, "gold_gp": 50, "current_hp": 20, "max_hp": 20}');

INSERT INTO game_locations (key, label, location_type, is_active)
  VALUES ('dark_forest', 'Ciemny Las', 'macro', 1);

INSERT INTO character_quests (id, character_id, campaign_id, quest_type, quest_key, title, status)
  VALUES (1, 1, 100, 'main', 'rescue_villagers', 'Uratuj wieśniaków', 'active');
"""


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


# ── Test 1: quest_complete emits game_events row ─────────────────────────────

def test_quest_complete_emits_game_event():
    """After QUEST_COMPLETE tag parsed, game_events must have event_type='quest_complete'."""
    conn = _make_db()

    from app.services.xp_sources import process_narrative_xp_tags

    narrative = "Gratulacje bohaterze! [QUEST_COMPLETE: Uratuj wieśniaków] Wioska jest bezpieczna."
    process_narrative_xp_tags(narrative, conn, character_id=1, campaign_id=100, turn_number=5)
    conn.commit()

    rows = conn.execute(
        "SELECT event_type, event_data FROM game_events WHERE campaign_id = 100 AND event_type = 'quest_complete'"
    ).fetchall()

    assert len(rows) >= 1, f"Expected game_events row with event_type='quest_complete', got {len(rows)}. #777 narrative instrumentation missing."
    data = json.loads(rows[0]["event_data"])
    assert "quest" in data or "quest_title" in data or "title" in data, \
        f"event_data should include quest info, got: {data}"


# ── Test 2: xp_grant emits game_events row ───────────────────────────────────

def test_xp_grant_emits_game_event():
    """After XP_GRANT tag parsed, game_events must have event_type='xp_grant'."""
    conn = _make_db()

    from app.services.xp_sources import process_narrative_xp_tags

    narrative = "Za pomoc starszemu [XP_GRANT:pomoc_starszemu:10] dostajesz 10 PD."
    process_narrative_xp_tags(narrative, conn, character_id=1, campaign_id=100, turn_number=3)
    conn.commit()

    rows = conn.execute(
        "SELECT event_type, event_data FROM game_events WHERE campaign_id = 100 AND event_type = 'xp_grant'"
    ).fetchall()

    assert len(rows) >= 1, f"Expected game_events row with event_type='xp_grant', got {len(rows)}. #777 narrative instrumentation missing."
    data = json.loads(rows[0]["event_data"])
    assert data.get("amount") == 10 or data.get("xp") == 10, \
        f"event_data should include xp amount=10, got: {data}"


# ── Test 3: location_new emits game_events row ───────────────────────────────

def test_location_new_emits_game_event():
    """First visit to a location must write game_events with event_type='location_new'."""
    conn = _make_db()

    from app.services.xp_sources import grant_first_location_visit

    grant_first_location_visit(conn, character_id=1, campaign_id=100,
                               location_key="dark_forest", turn_number=2)
    conn.commit()

    rows = conn.execute(
        "SELECT event_type, event_data FROM game_events WHERE campaign_id = 100 AND event_type = 'location_new'"
    ).fetchall()

    assert len(rows) >= 1, f"Expected game_events row with event_type='location_new', got {len(rows)}. #777 narrative instrumentation missing."
    data = json.loads(rows[0]["event_data"])
    assert data.get("location_key") == "dark_forest", \
        f"event_data should include location_key, got: {data}"


# ── Test 4: turn_decisions writer works at record level ──────────────────────

def test_turn_decisions_writer_saves_row():
    """record_turn_decision must insert a row — verifies the writer is not broken."""
    conn = _make_db()

    from app.services.decision_log_service import record_turn_decision

    row_id = record_turn_decision(
        campaign_id=100,
        character_id=1,
        turn_number=7,
        user_text="Idę do lasu",
        action_type="MOVEMENT",
        confidence=0.8,
        route="narrative",
        gate_blocked=False,
        gate_reason=None,
        handler="narrative",
        conn=conn,
    )
    conn.commit()

    assert row_id is not None, "record_turn_decision returned None — writer failed."
    rows = conn.execute(
        "SELECT * FROM turn_decisions WHERE campaign_id = 100"
    ).fetchall()
    assert len(rows) == 1, f"Expected 1 turn_decision row, got {len(rows)}"
    assert rows[0]["action_type"] == "MOVEMENT"
    assert rows[0]["route"] == "narrative"


# ── Test 5: item_grant emits game_events row ─────────────────────────────────

def test_item_grant_event_logged():
    """write_game_event called for item_grant must persist an event_type='item_grant' row."""
    conn = _make_db()

    from app.services.event_logger import write_game_event

    write_game_event(
        "item_grant",
        campaign_id=100,
        character_id=1,
        user_id=1,
        data={"item_label": "Miecz ognisty", "source": "gm_grant_item"},
        conn=conn,
    )
    conn.commit()

    rows = conn.execute(
        "SELECT event_type, event_data FROM game_events WHERE event_type='item_grant' AND campaign_id=100"
    ).fetchall()
    assert len(rows) == 1, f"item_grant event not saved, got {len(rows)} rows"
    data = json.loads(rows[0]["event_data"])
    assert data.get("item_label") == "Miecz ognisty"


# ── Test 6: gold_grant emits game_events row ─────────────────────────────────

def test_gold_grant_event_logged():
    """write_game_event called for gold_grant must persist an event_type='gold_grant' row."""
    conn = _make_db()

    from app.services.event_logger import write_game_event

    write_game_event(
        "gold_grant",
        campaign_id=100,
        character_id=1,
        user_id=1,
        data={"amount": 50, "new_total_gp": 100},
        conn=conn,
    )
    conn.commit()

    rows = conn.execute(
        "SELECT event_type, event_data FROM game_events WHERE event_type='gold_grant' AND campaign_id=100"
    ).fetchall()
    assert len(rows) == 1, f"gold_grant event not saved, got {len(rows)} rows"
    data = json.loads(rows[0]["event_data"])
    assert data.get("amount") == 50


# ── Backward compat: existing combat events still work ────────────────────────

def test_write_game_event_combat_still_works():
    """Existing combat event logging must continue to work unchanged."""
    conn = _make_db()

    from app.services.event_logger import write_game_event

    write_game_event(
        "combat_victory",
        campaign_id=100,
        character_id=1,
        user_id=1,
        data={"enemy": "goblin", "xp": 25},
        conn=conn,
    )
    conn.commit()

    rows = conn.execute(
        "SELECT event_type FROM game_events WHERE event_type='combat_victory' AND campaign_id=100"
    ).fetchall()
    assert len(rows) == 1, "combat_victory event broken — backward compat failure"


def test_record_turn_decision_existing_signature_still_works():
    """Old callers passing minimal args must still work — backward compat."""
    conn = _make_db()

    from app.services.decision_log_service import record_turn_decision

    row_id = record_turn_decision(
        campaign_id=100,
        route="narrative",
        gate_blocked=False,
        gate_reason=None,
        handler="gate",
        conn=conn,
    )
    conn.commit()

    assert row_id is not None, "Backward-compat call to record_turn_decision returned None"
    rows = conn.execute("SELECT * FROM turn_decisions WHERE campaign_id=100").fetchall()
    assert len(rows) == 1
