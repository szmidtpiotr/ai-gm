"""TDD: Issue #681 — L12 Wybór drzwi w UI + obraz kafelka w scenie.

Backend contract tests verifying move_through_door + resolve_tile_action + helpers.
RED element: Playwright spec (new HTML elements don't exist yet).
"""
import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _get_db():
    import sqlite3
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    return conn


def _setup_test_run(char_id: int, run_data: dict) -> int:
    """Create a test campaign + game_session with v2 dungeon run. Returns campaign_id."""
    conn = _get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO campaigns (title, system_id, model_id, owner_user_id, mode, status) "
            "VALUES ('[L12TEST]', 'fantasy', 'default', 1, 'dungeon', 'active') RETURNING id"
        )
        campaign_id = cursor.fetchone()[0]
        conn.execute(
            "INSERT INTO game_sessions (id, campaign_id, session_flags) "
            "VALUES (?, ?, ?)",
            (f"l12test_{campaign_id}", campaign_id, json.dumps({"dungeon_run": run_data})),
        )
        conn.commit()
        return campaign_id
    finally:
        conn.close()


def _teardown_test_run(campaign_id: int):
    """Remove test campaign and session."""
    conn = _get_db()
    try:
        conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (campaign_id,))
        conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
        conn.commit()
    finally:
        conn.close()


def _get_any_char_id() -> int | None:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT id FROM characters WHERE status != 'dead' LIMIT 1"
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


# ─── move_through_door contract ───────────────────────────────────────────────

def test_move_blocked_no_run():
    """move_through_door raises ValueError when no v2 run exists for campaign."""
    from app.services.dungeon_tile_service import move_through_door

    with pytest.raises(ValueError, match="kafelkowego"):
        move_through_door(campaign_id=0, character_id=0, direction="N")


def test_move_bad_direction_returns_blocked():
    """move_through_door returns {ok:False, blocked:True} for unavailable direction."""
    from app.services.dungeon_tile_service import move_through_door

    char_id = _get_any_char_id()
    if char_id is None:
        pytest.skip("Brak postaci")

    run = {
        "system": "tiles_v2",
        "graph": {
            "nodes": {
                "n0": {
                    "tile_id": 1, "position": [0, 0],
                    "doors_open": {"S": "n1"}, "door_hints": {"S": "Ciemność"},
                    "content": {"enemies": [], "riddle": None, "chest": False, "image_url": None},
                    "visited": True, "cleared": True,
                },
                "n1": {
                    "tile_id": 1, "position": [0, 1],
                    "doors_open": {"N": "n0"}, "door_hints": {},
                    "content": {"enemies": [], "riddle": None, "chest": False, "image_url": None},
                    "visited": False, "cleared": False,
                },
            },
            "entry_node": "n0", "boss_node": "n1",
        },
        "positions": {str(char_id): "n0"},
        "cycle": 1, "checkpoints": [], "completed": False, "failed": False,
        "dungeon_key": "test", "dungeon_label": "Test", "loot_tier": "standard",
    }
    campaign_id = _setup_test_run(char_id, run)
    try:
        result = move_through_door(campaign_id, char_id, "W")
        assert result.get("ok") is False, f"Kierunek W (brak drzwi) powinien być blocked: {result}"
        assert result.get("blocked") is True
    finally:
        _teardown_test_run(campaign_id)


def test_move_valid_direction_succeeds():
    """move_through_door returns {ok:True, node_id, narrative, content} for valid dir."""
    from app.services.dungeon_tile_service import move_through_door

    char_id = _get_any_char_id()
    if char_id is None:
        pytest.skip("Brak postaci")

    run = {
        "system": "tiles_v2",
        "graph": {
            "nodes": {
                "n0": {
                    "tile_id": 1, "position": [0, 0],
                    "doors_open": {"E": "n1"}, "door_hints": {"E": "Blask"},
                    "content": {"enemies": [], "riddle": None, "chest": False, "image_url": None,
                                "room_description": "Korytarz"},
                    "visited": True, "cleared": True,
                },
                "n1": {
                    "tile_id": 1, "position": [1, 0],
                    "doors_open": {"W": "n0"}, "door_hints": {},
                    "content": {"enemies": [], "riddle": None, "chest": True, "image_url": None,
                                "room_description": "Komnata ze skrzynią"},
                    "visited": False, "cleared": False,
                },
            },
            "entry_node": "n0", "boss_node": "n1",
        },
        "positions": {str(char_id): "n0"},
        "cycle": 1, "checkpoints": [], "completed": False, "failed": False,
        "dungeon_key": "test", "dungeon_label": "Test", "loot_tier": "standard",
    }
    campaign_id = _setup_test_run(char_id, run)
    try:
        result = move_through_door(campaign_id, char_id, "E")
        assert result.get("ok") is True, f"Ruch E powinien być OK: {result}"
        assert result.get("node_id") == "n1", "Cel to n1"
        assert "narrative" in result, "Response musi zawierać 'narrative'"
        assert "content" in result, "Response musi zawierać 'content'"
        assert "node" in result, "Response musi zawierać 'node'"
    finally:
        _teardown_test_run(campaign_id)


# ─── resolve_tile_action contract ─────────────────────────────────────────────

def test_resolve_tile_blocked_no_run():
    """resolve_tile_action raises ValueError when no v2 run exists."""
    from app.services.dungeon_tile_service import resolve_tile_action

    with pytest.raises(ValueError, match="kafelkowego"):
        resolve_tile_action(campaign_id=0, character_id=0, action="open_chest")


# ─── Helper: get_current_node_id ─────────────────────────────────────────────

def test_get_current_node_id_uses_positions():
    """get_current_node_id returns the node from positions dict (v2)."""
    from app.services.dungeon_tile_service import get_current_node_id

    run = {
        "system": "tiles_v2",
        "graph": {"nodes": {}, "entry_node": "n0"},
        "positions": {"42": "node_7"},
    }
    assert get_current_node_id(run, character_id=42) == "node_7"


def test_get_current_node_id_fallback_entry():
    """get_current_node_id falls back to entry_node when char not in positions."""
    from app.services.dungeon_tile_service import get_current_node_id

    run = {
        "system": "tiles_v2",
        "graph": {"nodes": {}, "entry_node": "entry_x"},
        "positions": {},
    }
    assert get_current_node_id(run, character_id=99) == "entry_x"
