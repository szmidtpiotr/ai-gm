"""TDD: Issue #722 — Riddle tiles must gate forward movement.

Weryfikuje:
- Kafel z riddle_key bez exit_conditions_json → engine auto-injectuje riddle_solved gate
- Próba przejścia przez nieotwarte drzwi zagadkowego kafla → blocked=True + "Rozwiąż zagadkę"
- Po rozwiązaniu zagadki → przejście dozwolone (ok=True)
- Backtracking do odwiedzonego kafla (entry door) NIE jest blokowany przez zagadkę (brak soft-locka)
- _get_tile_content: riddle_key bez exit_cond → auto-inject
- resolve_tile_content: riddle_key bez exit_cond → auto-inject
"""
from __future__ import annotations
from _fixtures_schema import table_sql

import json
import sqlite3

import pytest


SCHEMA = """
CREATE TABLE dungeon_tile_categories (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE dungeon_tiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_key TEXT NOT NULL,
    label TEXT NOT NULL,
    image_url TEXT,
    doors_json TEXT DEFAULT '[]',
    room_description TEXT DEFAULT '',
    enemies_json TEXT DEFAULT '[]',
    items_json TEXT DEFAULT '[]',
    active_states_json TEXT DEFAULT '[]',
    riddle_key TEXT,
    exit_conditions_json TEXT DEFAULT '[]',
    is_boss_tile INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1
);

""" + table_sql("game_config_enemies") + """

""" + table_sql("game_config_items") + """
""" + table_sql("game_config_weapons") + """
""" + table_sql("game_config_consumables") + """

""" + table_sql("game_config_riddles") + """

CREATE TABLE game_dungeons (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT 'Test',
    tile_category_key TEXT,
    tile_count INTEGER DEFAULT 3,
    boss_tile_id INTEGER,
    endless_growth_n INTEGER DEFAULT 0,
    cooldown_hours INTEGER DEFAULT 72,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE character_dungeon_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    location_key TEXT NOT NULL,
    cleared_at TEXT NOT NULL,
    cooldown_until TEXT NOT NULL,
    run_count INTEGER NOT NULL DEFAULT 1,
    UNIQUE(character_id, location_key)
);

CREATE TABLE game_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER UNIQUE NOT NULL,
    session_flags TEXT NOT NULL DEFAULT '{}'
);
"""

RIDDLE_KEY = "riddle_test_722"


def _make_run(riddle_solved: bool = False, node0_visited: bool = True) -> dict:
    """2-node graph: entry (visited) → riddle tile (unvisited)."""
    riddle_content = {
        "key": RIDDLE_KEY,
        "text": "Co ma zęby lecz nie gryzie?",
        "answer": "grzebień",
        "answer_alts": [],
        "hints": [],
        "hints_used": 0,
        "solved": riddle_solved,
    }
    nodes = {
        "node_0": {
            "tile_id": 1,
            "position": [0, 0],
            "doors_open": {"N": "node_1"},
            "door_hints": {},
            "content": {
                "tile_id": 1,
                "label": "Wejście",
                "room_description": "Wejście.",
                "enemies": [],
                "items": [],
                "active_states": [],
                "exit_conditions": [],
                "riddle": None,
                "is_boss_tile": False,
            },
            "visited": node0_visited,
            "cleared": True,
        },
        "node_1": {
            "tile_id": 2,
            "position": [0, 1],
            "doors_open": {"S": "node_0"},  # entry door only — no exit
            "door_hints": {},
            "content": {
                "tile_id": 2,
                "label": "Kaplica Zagadki",
                "room_description": "Zagadkowa sala.",
                "enemies": [],
                "items": [],
                "active_states": [],
                "exit_conditions": [{"type": "riddle_solved"}],
                "riddle": riddle_content,
                "is_boss_tile": False,
            },
            "visited": False,
            "cleared": False,
        },
    }
    return {
        "system": "tiles_v2",
        "dungeon_key": "test_dungeon",
        "dungeon_label": "Test Dungeon",
        "dungeon_difficulty": 1,
        "cycle": 1,
        "graph": {"nodes": nodes, "entry_node": "node_0", "boss_node": None},
        "positions": {"42": "node_0"},
        "checkpoints": [],
        "completed": False,
        "failed": False,
    }


def _make_run_riddle_at_current(riddle_solved: bool = False) -> dict:
    """Player is currently ON riddle tile (node_1), entry tile is node_0."""
    riddle_content = {
        "key": RIDDLE_KEY,
        "text": "Co ma zęby lecz nie gryzie?",
        "answer": "grzebień",
        "answer_alts": [],
        "hints": [],
        "hints_used": 0,
        "solved": riddle_solved,
    }
    nodes = {
        "node_0": {
            "tile_id": 1,
            "position": [0, 0],
            "doors_open": {"N": "node_1"},
            "door_hints": {},
            "content": {
                "tile_id": 1,
                "label": "Wejście",
                "room_description": "Wejście.",
                "enemies": [],
                "items": [],
                "active_states": [],
                "exit_conditions": [],
                "riddle": None,
                "is_boss_tile": False,
            },
            "visited": True,
            "cleared": True,
        },
        "node_1": {
            "tile_id": 2,
            "position": [0, 1],
            "doors_open": {"S": "node_0", "N": "node_2"},
            "door_hints": {},
            "content": {
                "tile_id": 2,
                "label": "Kaplica Zagadki",
                "room_description": "Zagadkowa sala.",
                "enemies": [],
                "items": [],
                "active_states": [],
                "exit_conditions": [{"type": "riddle_solved"}],
                "riddle": riddle_content,
                "is_boss_tile": False,
            },
            "visited": True,
            "cleared": False,
        },
        "node_2": {
            "tile_id": 3,
            "position": [0, 2],
            "doors_open": {"S": "node_1"},
            "door_hints": {},
            "content": {
                "tile_id": 3,
                "label": "Boss",
                "room_description": "Komnata.",
                "enemies": [],
                "items": [],
                "active_states": [],
                "exit_conditions": [],
                "riddle": None,
                "is_boss_tile": False,
            },
            "visited": False,
            "cleared": False,
        },
    }
    return {
        "system": "tiles_v2",
        "dungeon_key": "test_dungeon",
        "dungeon_label": "Test Dungeon",
        "dungeon_difficulty": 1,
        "cycle": 1,
        "graph": {"nodes": nodes, "entry_node": "node_0", "boss_node": None},
        "positions": {"42": "node_1"},
        "checkpoints": [],
        "completed": False,
        "failed": False,
    }


@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test722.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO dungeon_tile_categories (key, label) VALUES ('krypta', 'Krypta')"
    )
    conn.execute(
        "INSERT INTO dungeon_tiles (id, category_key, label, doors_json, riddle_key, exit_conditions_json) "
        "VALUES (2, 'krypta', 'Kaplica Zagadki', '[\"N\",\"S\"]', ?, '[]')",
        (RIDDLE_KEY,),
    )
    conn.execute(
        "INSERT INTO game_config_riddles (key, text, answer) VALUES (?, ?, ?)",
        (RIDDLE_KEY, "Co ma zęby lecz nie gryzie?", "grzebień"),
    )
    conn.commit()
    yield conn, str(db_file)
    conn.close()


def _patch(db_path: str):
    import sys
    from app.services import dungeon_tile_service as dts
    from app.services import dungeon_service as ds
    ds.DB_PATH = db_path
    dts.DB_PATH = db_path
    # Ensure the _get_db function's module (which may differ under importlib mode)
    # also gets patched
    real_ds = sys.modules.get("app.services.dungeon_service", ds)
    real_ds.DB_PATH = db_path
    return dts


def _setup_session(conn, run: dict, campaign_id: int = 1, character_id: int = 42):
    conn.execute(
        "INSERT OR REPLACE INTO game_sessions (campaign_id, session_flags) VALUES (?, ?)",
        (campaign_id, json.dumps({"dungeon_run": run})),
    )
    conn.commit()


# ─── Tests: _get_tile_content auto-inject ─────────────────────────────────────

class TestGetTileContentAutoInject:
    """_get_tile_content must auto-inject riddle_solved when riddle_key present."""

    def test_riddle_key_empty_exit_cond_gets_gate_injected(self, db):
        _, db_path = db
        dts = _patch(db_path)
        tile_row = {"id": 2, "riddle_key": RIDDLE_KEY, "exit_conditions_json": "[]",
                    "doors_json": '["N","S"]', "enemies_json": "[]", "items_json": "[]",
                    "active_states_json": "[]", "label": "Kaplica", "image_url": None,
                    "room_description": "", "is_boss_tile": 0}
        content = dts._get_tile_content(tile_row)
        assert {"type": "riddle_solved"} in content["exit_conditions"], (
            "riddle_key tile must auto-get riddle_solved exit condition"
        )

    def test_riddle_key_null_exit_cond_gets_gate_injected(self, db):
        _, db_path = db
        dts = _patch(db_path)
        tile_row = {"id": 2, "riddle_key": RIDDLE_KEY, "exit_conditions_json": None,
                    "doors_json": '["N","S"]', "enemies_json": "[]", "items_json": "[]",
                    "active_states_json": "[]", "label": "Kaplica", "image_url": None,
                    "room_description": "", "is_boss_tile": 0}
        content = dts._get_tile_content(tile_row)
        assert {"type": "riddle_solved"} in content["exit_conditions"]

    def test_no_riddle_key_no_auto_inject(self, db):
        _, db_path = db
        dts = _patch(db_path)
        tile_row = {"id": 1, "riddle_key": None, "exit_conditions_json": "[]",
                    "doors_json": '["N"]', "enemies_json": "[]", "items_json": "[]",
                    "active_states_json": "[]", "label": "Korytarz", "image_url": None,
                    "room_description": "", "is_boss_tile": 0}
        content = dts._get_tile_content(tile_row)
        assert content["exit_conditions"] == []

    def test_riddle_key_with_existing_gate_not_duplicated(self, db):
        _, db_path = db
        dts = _patch(db_path)
        tile_row = {"id": 2, "riddle_key": RIDDLE_KEY,
                    "exit_conditions_json": '[{"type":"riddle_solved"}]',
                    "doors_json": '["N","S"]', "enemies_json": "[]", "items_json": "[]",
                    "active_states_json": "[]", "label": "Kaplica", "image_url": None,
                    "room_description": "", "is_boss_tile": 0}
        content = dts._get_tile_content(tile_row)
        riddle_solved_conds = [c for c in content["exit_conditions"] if c.get("type") == "riddle_solved"]
        assert len(riddle_solved_conds) == 1, "should not duplicate riddle_solved gate"


# ─── Tests: resolve_tile_content auto-inject ──────────────────────────────────

class TestResolveTileContentAutoInject:
    """resolve_tile_content must auto-inject riddle_solved when riddle_key present."""

    def test_riddle_tile_from_db_gets_gate(self, db):
        _, db_path = db
        dts = _patch(db_path)
        result = dts.resolve_tile_content(tile_id=2)
        assert result is not None
        assert {"type": "riddle_solved"} in result["exit_conditions"]

    def test_riddle_tile_riddle_field_populated(self, db):
        _, db_path = db
        dts = _patch(db_path)
        result = dts.resolve_tile_content(tile_id=2)
        assert result is not None
        assert result["riddle"] is not None
        assert result["riddle"]["key"] == RIDDLE_KEY


# ─── Tests: move_through_door gate enforcement ────────────────────────────────

class TestMoveRiddleGate:
    """move_through_door blocks unresolved riddle tile exit."""

    def test_entering_riddle_tile_succeeds(self, db):
        conn, db_path = db
        dts = _patch(db_path)
        run = _make_run(riddle_solved=False)  # player at node_0, going N to riddle tile
        _setup_session(conn, run)
        result = dts.move_through_door(1, 42, "N")
        # Moving INTO riddle tile is fine (no exit condition on node_0)
        assert result.get("ok") is True

    def test_forward_exit_from_riddle_tile_blocked_unsolved(self, db):
        conn, db_path = db
        dts = _patch(db_path)
        run = _make_run_riddle_at_current(riddle_solved=False)
        _setup_session(conn, run)
        result = dts.move_through_door(1, 42, "N")
        assert result.get("ok") is False
        assert result.get("blocked") is True
        assert "zagadkę" in result.get("reason", "").lower()

    def test_forward_exit_from_riddle_tile_allowed_solved(self, db):
        conn, db_path = db
        dts = _patch(db_path)
        run = _make_run_riddle_at_current(riddle_solved=True)
        _setup_session(conn, run)
        result = dts.move_through_door(1, 42, "N")
        assert result.get("ok") is True

    def test_backtrack_through_entry_door_not_blocked_by_riddle(self, db):
        """Backtracking to a visited node must bypass exit_conditions — no soft-lock."""
        conn, db_path = db
        dts = _patch(db_path)
        run = _make_run_riddle_at_current(riddle_solved=False)
        # node_0 is already visited=True — player should be able to go back
        _setup_session(conn, run)
        result = dts.move_through_door(1, 42, "S")
        assert result.get("ok") is True, (
            f"Backtracking to visited node must not be blocked by riddle. Got: {result}"
        )
