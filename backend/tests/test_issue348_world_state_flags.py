"""TDD: Issue #348 — B2 world_state_flags helpers in world_state_service."""
import json
import sqlite3

import pytest

from app.services.world_state_service import (
    get_world_state_flags,
    set_world_state_flags,
)

DB_PATH = "/data/ai_gm.db"
TEST_CAMPAIGN_ID = 99348  # synthetic id, won't clash with real data
TEST_SESSION_ID = "test-session-99348"


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_session():
    """Insert a bare game_session row before each test; remove after."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "DELETE FROM game_sessions WHERE campaign_id = ?",
        (TEST_CAMPAIGN_ID,),
    )
    conn.execute(
        """INSERT INTO game_sessions (id, campaign_id, session_flags)
           VALUES (?, ?, '{}')""",
        (TEST_SESSION_ID, TEST_CAMPAIGN_ID),
    )
    conn.commit()
    conn.close()
    yield
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "DELETE FROM game_sessions WHERE campaign_id = ?",
        (TEST_CAMPAIGN_ID,),
    )
    conn.commit()
    conn.close()


# ─── get_world_state_flags ────────────────────────────────────────────────────

def test_get_returns_all_five_keys():
    """get_world_state_flags must return a dict with all 5 World State keys."""
    result = get_world_state_flags(TEST_CAMPAIGN_ID)
    assert isinstance(result, dict)
    for key in ("scene_enemies", "scene_npcs", "scene_cleared", "active_quests", "player_conditions"):
        assert key in result, f"Missing key: {key}"


def test_get_defaults_for_fresh_session():
    """Fresh session returns empty lists and False for scene_cleared."""
    result = get_world_state_flags(TEST_CAMPAIGN_ID)
    assert result["scene_enemies"] == []
    assert result["scene_npcs"] == []
    assert result["scene_cleared"] is False
    assert result["active_quests"] == []
    assert result["player_conditions"] == []


def test_get_no_session_returns_defaults():
    """Campaign with no game_session must not raise — return defaults."""
    result = get_world_state_flags(99999999)  # guaranteed non-existent
    assert result["scene_enemies"] == []
    assert result["scene_cleared"] is False


# ─── set_world_state_flags ────────────────────────────────────────────────────

def test_set_scene_cleared():
    """set_world_state_flags(campaign_id, scene_cleared=True) persists the change."""
    set_world_state_flags(TEST_CAMPAIGN_ID, scene_cleared=True)
    result = get_world_state_flags(TEST_CAMPAIGN_ID)
    assert result["scene_cleared"] is True


def test_set_scene_enemies():
    """set_world_state_flags with scene_enemies list persists it."""
    enemies = [{"key": "goblin_01", "hp": 10}]
    set_world_state_flags(TEST_CAMPAIGN_ID, scene_enemies=enemies)
    result = get_world_state_flags(TEST_CAMPAIGN_ID)
    assert result["scene_enemies"] == enemies


def test_set_partial_update_does_not_overwrite_other_fields():
    """Setting one field must not reset the others to defaults."""
    # First set scene_cleared
    set_world_state_flags(TEST_CAMPAIGN_ID, scene_cleared=True)
    # Then update only scene_npcs
    npcs = [{"key": "merchant", "name": "Handlarz"}]
    set_world_state_flags(TEST_CAMPAIGN_ID, scene_npcs=npcs)
    result = get_world_state_flags(TEST_CAMPAIGN_ID)
    # scene_cleared must still be True
    assert result["scene_cleared"] is True
    assert result["scene_npcs"] == npcs


def test_set_multiple_fields_at_once():
    """set_world_state_flags accepts multiple keyword args in one call."""
    quests = ["znajdź_miecz", "rozmów_się_z_królem"]
    conditions = ["poisoned"]
    set_world_state_flags(TEST_CAMPAIGN_ID, active_quests=quests, player_conditions=conditions)
    result = get_world_state_flags(TEST_CAMPAIGN_ID)
    assert result["active_quests"] == quests
    assert result["player_conditions"] == conditions


def test_set_ignores_unknown_keys():
    """Unknown kwargs must not raise — silently ignored."""
    set_world_state_flags(TEST_CAMPAIGN_ID, nonexistent_key="boom")  # should not raise
    result = get_world_state_flags(TEST_CAMPAIGN_ID)
    assert result["scene_cleared"] is False  # defaults intact


# ─── Backward compatibility ────────────────────────────────────────────────────

def test_existing_snapshots_service_still_imports():
    """B1 functions must still be importable alongside B2."""
    from app.services.world_state_service import get_latest_snapshot, save_snapshot
    assert callable(get_latest_snapshot)
    assert callable(save_snapshot)
