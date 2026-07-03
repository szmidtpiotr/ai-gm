"""TDD: Issue #356 — C2 Mechanical hex movement: terrain validation + World State update."""
import json
import sqlite3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.world_state_machine import WorldStateMachine


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER NOT NULL, r INTEGER NOT NULL,
            hex_type TEXT NOT NULL DEFAULT 'plains',
            label TEXT, is_active INTEGER NOT NULL DEFAULT 1,
            location_key TEXT,
            encounter_chance REAL NOT NULL DEFAULT 0.15,
            encounter_pool TEXT NOT NULL DEFAULT '[]',
            created_by_gm INTEGER NOT NULL DEFAULT 0,
            created_by_campaign_id INTEGER,
            atmosphere TEXT, discovered_in_campaign_id INTEGER,
            map_level INTEGER NOT NULL DEFAULT 0, parent_hex_id INTEGER
        );
        CREATE TABLE hex_type_config (
            hex_type TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            travel_hours REAL NOT NULL DEFAULT 1.0,
            encounter_base_chance REAL NOT NULL DEFAULT 0.15,
            map_color TEXT NOT NULL DEFAULT '#4a6a4a',
            map_icon TEXT, is_active INTEGER NOT NULL DEFAULT 1,
            is_passable INTEGER NOT NULL DEFAULT 1,
            required_item TEXT
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE, label TEXT NOT NULL,
            safe_for_rest INTEGER DEFAULT 0, npc_keys TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL UNIQUE,
            session_flags TEXT NOT NULL DEFAULT '{}',
            current_location_id INTEGER
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, sheet_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE character_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL, condition_type TEXT NOT NULL,
            severity INTEGER NOT NULL DEFAULT 1, rounds_remaining INTEGER DEFAULT NULL,
            expires_at TEXT DEFAULT NULL, source TEXT NOT NULL DEFAULT '',
            effect_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL, item_key TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY AUTOINCREMENT, gm_plan_json TEXT);
        CREATE TABLE location_npc_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            npc_key TEXT NOT NULL, location_key TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        );
    """)
    # hex_type_config: plains passable, lake impassable (requires boat)
    conn.execute("INSERT INTO hex_type_config (hex_type, label, is_passable) VALUES ('plains', 'Równiny', 1)")
    conn.execute("INSERT INTO hex_type_config (hex_type, label, is_passable, required_item) VALUES ('lake', 'Jezioro', 0, 'boat')")
    # Hexes
    conn.execute("INSERT INTO world_hexes (q, r, hex_type, label) VALUES (0, 0, 'plains', 'Start')")
    conn.execute("INSERT INTO world_hexes (q, r, hex_type, label) VALUES (1, 0, 'plains', 'Polana')")
    conn.execute("INSERT INTO world_hexes (q, r, hex_type, label) VALUES (2, 0, 'lake', 'Jezioro')")
    conn.execute("INSERT INTO world_hexes (q, r, hex_type, label, location_key) VALUES (3, 0, 'plains', 'Wioska', 'village_1')")
    conn.execute("INSERT INTO game_locations (key, label) VALUES ('village_1', 'Wioska Elderoak')")
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, '{}')")
    conn.execute("INSERT INTO characters (id, campaign_id, sheet_json) VALUES (1, 1, '{}')")
    conn.commit()
    return conn


# ─── Test 1: Impassable terrain (lake) blocks movement ──────────────────────

def test_impassable_terrain_blocks_movement():
    """Movement to a lake hex without boat must be blocked."""
    conn = _make_conn()
    wsm = WorldStateMachine(conn)
    result = wsm.validate_and_route(
        {"state": "NARRATIVE"}, "MOVEMENT", {"destination_q": 2, "destination_r": 0},
        character_id=1, campaign_id=1,
    )
    assert result.valid is False
    assert result.blocked_message


# ─── Test 2: Passable terrain allows movement ────────────────────────────────

def test_passable_terrain_allows_movement():
    """Movement to a normal plains hex must be valid."""
    conn = _make_conn()
    wsm = WorldStateMachine(conn)
    result = wsm.validate_and_route(
        {"state": "NARRATIVE"}, "MOVEMENT", {"destination_q": 1, "destination_r": 0},
        character_id=1, campaign_id=1,
    )
    assert result.valid is True


# ─── Test 3: Non-existent hex still blocked (backward compat) ───────────────

def test_nonexistent_hex_still_blocked():
    """Hex not in DB must still return blocked (existing behavior preserved)."""
    conn = _make_conn()
    wsm = WorldStateMachine(conn)
    result = wsm.validate_and_route(
        {"state": "NARRATIVE"}, "MOVEMENT", {"destination_q": 99, "destination_r": 99},
        character_id=1, campaign_id=1,
    )
    assert result.valid is False


# ─── Test 4: Required item present → impassable becomes passable ─────────────

def test_impassable_terrain_with_required_item_allows_movement():
    """Player with a boat can enter lake hex."""
    conn = _make_conn()
    conn.execute("INSERT INTO character_inventory (character_id, item_key, quantity) VALUES (1, 'boat', 1)")
    conn.commit()
    wsm = WorldStateMachine(conn)
    result = wsm.validate_and_route(
        {"state": "NARRATIVE"}, "MOVEMENT", {"destination_q": 2, "destination_r": 0},
        character_id=1, campaign_id=1,
    )
    assert result.valid is True


# ─── Test 5: Hex type not in config defaults to passable ─────────────────────

def test_movement_hex_type_not_in_config_defaults_passable():
    """Unknown hex_type not in hex_type_config must be treated as passable."""
    conn = _make_conn()
    conn.execute("INSERT INTO world_hexes (q, r, hex_type, label) VALUES (5, 0, 'unknown_type', 'Mystery')")
    conn.commit()
    wsm = WorldStateMachine(conn)
    result = wsm.validate_and_route(
        {"state": "NARRATIVE"}, "MOVEMENT", {"destination_q": 5, "destination_r": 0},
        character_id=1, campaign_id=1,
    )
    assert result.valid is True


# ─── Test 6: World State current_hex updated after hex movement ──────────────

def test_movement_updates_current_hex_in_flags():
    """After successful hex movement, session_flags['current_hex'] must equal destination."""
    from app.services.turn_pipeline import _update_hex_world_state
    conn = _make_conn()
    session_flags = {}
    _update_hex_world_state(
        mechanic_result={"action_type": "MOVEMENT", "outcome": "SUCCESS",
                         "destination_q": 1, "destination_r": 0},
        session_flags=session_flags,
        conn=conn,
        campaign_id=1,
    )
    assert session_flags.get("current_hex") == {"q": 1, "r": 0}


# ─── Test 7: location_key synced when destination hex has one ─────────────────

def test_movement_updates_location_key_for_hex_with_location():
    """PT-F7 #1141: destination location is anchored via current_location_id; the key
    is DERIVED (not mirrored into session_flags)."""
    from app.services.turn_pipeline import _update_hex_world_state
    from app.services.location_state_service import get_current_location_key
    conn = _make_conn()
    session_flags = {}
    _update_hex_world_state(
        mechanic_result={"action_type": "MOVEMENT", "outcome": "SUCCESS",
                         "destination_q": 3, "destination_r": 0},
        session_flags=session_flags,
        conn=conn,
        campaign_id=1,
    )
    assert session_flags.get("current_hex") == {"q": 3, "r": 0}
    assert get_current_location_key(conn, 1) == "village_1"
    assert "current_location_key" not in session_flags


# ─── Test 8: No update on failed movement ────────────────────────────────────

def test_failed_movement_does_not_update_hex():
    """If outcome != SUCCESS, current_hex must not change."""
    from app.services.turn_pipeline import _update_hex_world_state
    conn = _make_conn()
    session_flags = {"current_hex": {"q": 0, "r": 0}}
    _update_hex_world_state(
        mechanic_result={"action_type": "MOVEMENT", "outcome": "FAIL",
                         "destination_q": 1, "destination_r": 0},
        session_flags=session_flags,
        conn=conn,
        campaign_id=1,
    )
    assert session_flags["current_hex"] == {"q": 0, "r": 0}
