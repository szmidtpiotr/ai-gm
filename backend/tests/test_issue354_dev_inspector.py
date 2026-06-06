"""TDD: Issue #354 — B7 DEV Inspector: live intent + world state debugger."""
import json
import sqlite3
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

DB_PATH = "/data/ai_gm.db"
_FAKE_CAMPAIGN_ID = 999_354


def _cleanup():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM campaign_turns WHERE campaign_id = ?", (_FAKE_CAMPAIGN_ID,))
        conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (_FAKE_CAMPAIGN_ID,))
        conn.execute("DELETE FROM world_state_snapshots WHERE campaign_id = ?", (_FAKE_CAMPAIGN_ID,))
        conn.commit()
    finally:
        conn.close()


def _insert_player_turn(text: str, turn_number: int = 1):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT INTO campaign_turns
               (campaign_id, character_id, turn_number, route, user_text, assistant_text, created_at)
               VALUES (?, 0, ?, 'narrative', ?, 'Narracja GM...', datetime('now'))""",
            (_FAKE_CAMPAIGN_ID, turn_number, text),
        )
        conn.commit()
    finally:
        conn.close()


def _set_world_state(scene_enemies=None, scene_cleared=False):
    enemies = json.dumps(scene_enemies or [])
    conn = sqlite3.connect(DB_PATH)
    try:
        existing = conn.execute(
            "SELECT id FROM game_sessions WHERE campaign_id = ?", (_FAKE_CAMPAIGN_ID,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE game_sessions SET scene_enemies=?, scene_cleared=?
                   WHERE campaign_id=?""",
                (enemies, 1 if scene_cleared else 0, _FAKE_CAMPAIGN_ID),
            )
        else:
            conn.execute(
                """INSERT INTO game_sessions (campaign_id, scene_enemies, scene_cleared,
                   scene_npcs, active_quests, player_conditions)
                   VALUES (?, ?, ?, '[]', '[]', '[]')""",
                (_FAKE_CAMPAIGN_ID, enemies, 1 if scene_cleared else 0),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client():
    from app.main import app
    from app.routers.debug import _user_is_admin
    # patch _user_is_admin to always return True for test user_id=0
    import app.routers.debug as debug_mod
    original = debug_mod._user_is_admin
    debug_mod._user_is_admin = lambda uid: True
    yield TestClient(app)
    debug_mod._user_is_admin = original


# ─── Test 1: endpoint exists and returns 200 ─────────────────────────────────

def test_debug_state_endpoint_exists(client):
    """GET /api/campaigns/{id}/debug/state must return 200, not 404."""
    _cleanup()
    _insert_player_turn("atakuję goblin")

    resp = client.get(
        f"/api/debug/campaigns/{_FAKE_CAMPAIGN_ID}/state",
        params={"user_id": 0},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    _cleanup()


# ─── Test 2: response has required top-level keys ────────────────────────────

def test_debug_state_has_required_keys(client):
    """Response must have: intent, world_state, gate_result."""
    _cleanup()
    _insert_player_turn("atakuję goblin")

    resp = client.get(
        f"/api/debug/campaigns/{_FAKE_CAMPAIGN_ID}/state",
        params={"user_id": 0},
    )
    assert resp.status_code == 200
    data = resp.json()
    for key in ("intent", "world_state", "gate_result"):
        assert key in data, f"Missing key '{key}' in response: {list(data.keys())}"
    _cleanup()


# ─── Test 3: intent reflects last player turn ─────────────────────────────────

def test_debug_state_intent_reflects_player_turn(client):
    """intent.action_type must match what parse_intent detects from last turn."""
    _cleanup()
    _insert_player_turn("atakuję goblin z mieczem")

    resp = client.get(
        f"/api/debug/campaigns/{_FAKE_CAMPAIGN_ID}/state",
        params={"user_id": 0},
    )
    data = resp.json()
    intent = data["intent"]
    assert "action_type" in intent
    assert intent["action_type"] == "attack", \
        f"Expected 'attack', got '{intent['action_type']}'"
    assert "confidence" in intent
    _cleanup()


# ─── Test 4: world_state has all 5 required columns ──────────────────────────

def test_debug_state_world_state_has_5_columns(client):
    """world_state must expose all 5 columns: scene_enemies, scene_npcs, active_quests, player_conditions, scene_cleared."""
    _cleanup()
    _insert_player_turn("rozglądam się")

    resp = client.get(
        f"/api/debug/campaigns/{_FAKE_CAMPAIGN_ID}/state",
        params={"user_id": 0},
    )
    ws = resp.json()["world_state"]
    for col in ("scene_enemies", "scene_npcs", "active_quests", "player_conditions", "scene_cleared"):
        assert col in ws, f"Missing column '{col}' in world_state: {list(ws.keys())}"
    _cleanup()


# ─── Test 5: gate_result has blocked + reason ────────────────────────────────

def test_debug_state_gate_result_structure(client):
    """gate_result must have: blocked (bool), reason, feedback."""
    _cleanup()
    _insert_player_turn("idę do lasu")

    resp = client.get(
        f"/api/debug/campaigns/{_FAKE_CAMPAIGN_ID}/state",
        params={"user_id": 0},
    )
    gr = resp.json()["gate_result"]
    assert "blocked" in gr, f"Missing 'blocked' in gate_result: {gr}"
    assert isinstance(gr["blocked"], bool)
    assert "reason" in gr
    _cleanup()


# ─── Test 6: gate blocks non-combat during active combat ─────────────────────

def test_debug_state_gate_blocks_movement_during_combat(client):
    """gate_result.blocked=True when movement attempted with alive enemies present."""
    _cleanup()
    _set_world_state(scene_enemies=[{"key": "goblin", "name": "Goblin", "hp": 20}])
    _insert_player_turn("idę do lasu")

    resp = client.get(
        f"/api/debug/campaigns/{_FAKE_CAMPAIGN_ID}/state",
        params={"user_id": 0},
    )
    gr = resp.json()["gate_result"]
    assert gr["blocked"] is True, f"Expected blocked=True, got: {gr}"
    assert gr["reason"] == "combat_active"
    _cleanup()


# ─── Test 7: no turns → empty/null state gracefully ─────────────────────────

def test_debug_state_handles_no_turns(client):
    """When no turns exist for campaign, endpoint returns 200 with null intent."""
    _cleanup()

    resp = client.get(
        f"/api/debug/campaigns/{_FAKE_CAMPAIGN_ID}/state",
        params={"user_id": 0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "intent" in data
    # Either None or action_type='other' is acceptable
    if data["intent"] is not None:
        assert "action_type" in data["intent"]
    _cleanup()
