"""TDD: Issue #355 — STORY_STALE injection after N turns without location change."""
import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _fixtures_schema import table_sql

from app.services.context_injector import ContextInjector

STALE_THRESHOLD = 5


def _make_conn():
    """Minimal in-memory DB sufficient for ContextInjector.build()."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY, key TEXT, label TEXT,
            description TEXT, location_type TEXT, rules TEXT,
            safe_for_rest INTEGER DEFAULT 0, npc_keys TEXT
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, name TEXT, sheet_json TEXT, archetype TEXT
        );
        CREATE TABLE character_inventory (
            id INTEGER, character_id INTEGER, item_key TEXT, weapon_key TEXT
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY, campaign_id INTEGER,
            turn_number INTEGER, created_at TEXT
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY, campaign_id INTEGER,
            session_flags TEXT, current_location_id INTEGER,
            last_turn_at TEXT
        );
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY, key TEXT, label TEXT,
            is_active INTEGER, attitude TEXT, personality_prompt TEXT, npc_type TEXT
        );
        CREATE TABLE location_npc_assignments (
            id INTEGER PRIMARY KEY, location_key TEXT, npc_key TEXT, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, tone TEXT, gm_plan_json TEXT);
        CREATE TABLE character_conditions (
            id INTEGER PRIMARY KEY, character_id INTEGER,
            condition_type TEXT, severity TEXT, expires_at INTEGER
        );
        """ + table_sql("game_config_conditions") + """
    """)
    conn.execute("INSERT INTO characters VALUES (1, 'Bohater', '{\"current_hp\":10,\"max_hp\":10,\"archetype\":\"warrior\"}', 'warrior')")
    conn.execute("INSERT INTO campaigns VALUES (1, 'mroczny', NULL)")
    conn.commit()
    return conn


# ─── STORY_STALE injection ────────────────────────────────────────────────────

def test_stale_block_injected_at_threshold():
    """Exactly 5 turns without movement → STORY_STALE in narrator prompt."""
    conn = _make_conn()
    injector = ContextInjector(conn)
    session_flags = {
        "current_location_key": "village",
        "state": "NARRATIVE",
        "turns_at_location": STALE_THRESHOLD,
    }
    prompt = injector.build(
        session_flags=session_flags,
        mechanic_result={"action_type": "NARRATIVE", "outcome": "SUCCESS"},
        action_type="NARRATIVE",
        character_id=1,
        campaign_id=1,
    )
    assert "[STORY_STALE:" in prompt
    assert f"{STALE_THRESHOLD} tur bez ruchu" in prompt


def test_stale_block_injected_above_threshold():
    """10 turns without movement → STORY_STALE with correct count."""
    conn = _make_conn()
    injector = ContextInjector(conn)
    session_flags = {
        "current_location_key": "dungeon",
        "state": "NARRATIVE",
        "turns_at_location": 10,
    }
    prompt = injector.build(
        session_flags=session_flags,
        mechanic_result={"action_type": "NARRATIVE", "outcome": "SUCCESS"},
        action_type="NARRATIVE",
        character_id=1,
        campaign_id=1,
    )
    assert "[STORY_STALE:" in prompt
    assert "10 tur bez ruchu" in prompt


def test_no_stale_block_below_threshold():
    """4 turns without movement → no STORY_STALE."""
    conn = _make_conn()
    injector = ContextInjector(conn)
    session_flags = {
        "current_location_key": "village",
        "state": "NARRATIVE",
        "turns_at_location": STALE_THRESHOLD - 1,
    }
    prompt = injector.build(
        session_flags=session_flags,
        mechanic_result={"action_type": "NARRATIVE", "outcome": "SUCCESS"},
        action_type="NARRATIVE",
        character_id=1,
        campaign_id=1,
    )
    assert "[STORY_STALE:" not in prompt


def test_no_stale_block_missing_key():
    """session_flags without turns_at_location → no stale (backward compat)."""
    conn = _make_conn()
    injector = ContextInjector(conn)
    session_flags = {
        "current_location_key": "village",
        "state": "NARRATIVE",
    }
    prompt = injector.build(
        session_flags=session_flags,
        mechanic_result={"action_type": "NARRATIVE", "outcome": "SUCCESS"},
        action_type="NARRATIVE",
        character_id=1,
        campaign_id=1,
    )
    assert "[STORY_STALE:" not in prompt


# ─── Counter management ───────────────────────────────────────────────────────

def test_counter_increments_on_non_movement():
    """_update_turns_at_location increments counter for non-MOVEMENT turn."""
    from app.services.turn_pipeline import _update_turns_at_location

    conn = _make_conn()
    conn.execute("INSERT INTO game_sessions VALUES (1, 1, ?, NULL, NULL)",
                 (json.dumps({"state": "NARRATIVE", "turns_at_location": 2}),))
    conn.commit()

    session_flags = {"state": "NARRATIVE", "turns_at_location": 2}
    mechanic_result = {"action_type": "NARRATIVE", "outcome": "SUCCESS"}
    _update_turns_at_location(mechanic_result, session_flags, conn, campaign_id=1)

    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    flags = json.loads(row[0])
    assert flags["turns_at_location"] == 3


def test_counter_resets_on_movement_success():
    """_update_turns_at_location resets to 0 on MOVEMENT SUCCESS."""
    from app.services.turn_pipeline import _update_turns_at_location

    conn = _make_conn()
    conn.execute("INSERT INTO game_sessions VALUES (1, 1, ?, NULL, NULL)",
                 (json.dumps({"state": "NARRATIVE", "turns_at_location": 7}),))
    conn.commit()

    session_flags = {"state": "NARRATIVE", "turns_at_location": 7}
    mechanic_result = {"action_type": "MOVEMENT", "outcome": "SUCCESS"}
    _update_turns_at_location(mechanic_result, session_flags, conn, campaign_id=1)

    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    flags = json.loads(row[0])
    assert flags["turns_at_location"] == 0


def test_counter_not_reset_on_movement_failure():
    """_update_turns_at_location keeps counter on MOVEMENT that didn't succeed."""
    from app.services.turn_pipeline import _update_turns_at_location

    conn = _make_conn()
    conn.execute("INSERT INTO game_sessions VALUES (1, 1, ?, NULL, NULL)",
                 (json.dumps({"state": "NARRATIVE", "turns_at_location": 4}),))
    conn.commit()

    session_flags = {"state": "NARRATIVE", "turns_at_location": 4}
    mechanic_result = {"action_type": "MOVEMENT", "outcome": "FAILURE"}
    _update_turns_at_location(mechanic_result, session_flags, conn, campaign_id=1)

    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    flags = json.loads(row[0])
    assert flags["turns_at_location"] == 5


def test_counter_initializes_from_zero():
    """_update_turns_at_location handles missing key → starts from 0."""
    from app.services.turn_pipeline import _update_turns_at_location

    conn = _make_conn()
    conn.execute("INSERT INTO game_sessions VALUES (1, 1, ?, NULL, NULL)",
                 (json.dumps({"state": "NARRATIVE"}),))
    conn.commit()

    session_flags = {"state": "NARRATIVE"}
    mechanic_result = {"action_type": "NARRATIVE", "outcome": "SUCCESS"}
    _update_turns_at_location(mechanic_result, session_flags, conn, campaign_id=1)

    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    flags = json.loads(row[0])
    assert flags["turns_at_location"] == 1
