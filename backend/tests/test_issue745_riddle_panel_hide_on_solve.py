"""#745 — dungeon riddle panel stays visible after correct answer (cleared=False, solved=True)

Root cause: frontend hasRiddle = content.riddle && !currentNode.cleared
Bug: after correct answer backend sets content.riddle.solved=True but NOT currentNode.cleared=True
Fix: frontend must also check !content.riddle.solved and !riddle_state.failed_permanently

These tests verify the backend contract — session_flags contain the right state after each action.
"""
from __future__ import annotations

import json
import sqlite3

import pytest


SCHEMA = """
CREATE TABLE game_sessions (
    id TEXT PRIMARY KEY,
    campaign_id INTEGER,
    session_flags TEXT DEFAULT '{}'
);
CREATE TABLE characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER,
    user_id INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL DEFAULT 'Hero',
    system_id TEXT NOT NULL DEFAULT 'core',
    sheet_json TEXT NOT NULL DEFAULT '{}',
    is_active INTEGER DEFAULT 1,
    gold INTEGER DEFAULT 0,
    gold_gp INTEGER DEFAULT 0,
    hero_status TEXT DEFAULT 'active',
    visited_location_keys TEXT DEFAULT '[]',
    status TEXT DEFAULT 'idle'
);
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
CREATE TABLE game_config_riddles (
    key TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    answer TEXT NOT NULL,
    answer_alts TEXT DEFAULT '[]',
    hints TEXT DEFAULT '[]',
    is_active INTEGER DEFAULT 1
);
CREATE TABLE game_dungeons (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT 'Test Dungeon',
    location_key TEXT NOT NULL DEFAULT 'loc',
    rooms INTEGER DEFAULT 4,
    enemy_pool TEXT DEFAULT '[]',
    boss_enemy TEXT,
    loot_tier TEXT DEFAULT 'standard',
    cooldown_hours INTEGER DEFAULT 72,
    min_level INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    chest_loot_table_key TEXT,
    dungeon_difficulty INTEGER DEFAULT 1,
    tile_category_key TEXT,
    tile_count INTEGER,
    boss_tile_id INTEGER,
    endless_growth_n INTEGER DEFAULT 0
);
CREATE TABLE game_config_loot_tables (key TEXT PRIMARY KEY, label TEXT NOT NULL DEFAULT 'Table', gold_min INTEGER DEFAULT 0, gold_max INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1);
CREATE TABLE game_config_loot_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, loot_table_key TEXT NOT NULL, item_key TEXT, consumable_key TEXT, weapon_key TEXT, weight INTEGER DEFAULT 100, qty_min INTEGER DEFAULT 1, qty_max INTEGER DEFAULT 1);
CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY, label TEXT NOT NULL DEFAULT 'Enemy', hp_base INTEGER DEFAULT 5, ac_base INTEGER DEFAULT 8, attack_bonus INTEGER DEFAULT 0, damage_die TEXT DEFAULT '1d6', damage_bonus INTEGER DEFAULT 0, dex_modifier INTEGER DEFAULT 0, tier TEXT DEFAULT 'common', stats_json TEXT DEFAULT NULL);
CREATE TABLE game_config_items (key TEXT PRIMARY KEY, label TEXT NOT NULL DEFAULT 'Item');
CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, label TEXT NOT NULL DEFAULT 'Weapon');
CREATE TABLE game_config_consumables (key TEXT PRIMARY KEY, label TEXT NOT NULL DEFAULT 'Potion');
"""

_MAX_ATTEMPTS = 3  # matches dungeon_tile_service._MAX_RIDDLE_ATTEMPTS


@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test_745.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO dungeon_tile_categories (key, label) VALUES ('crypt', 'Krypta')")
    conn.execute(
        "INSERT INTO game_dungeons (key, label, location_key) VALUES ('test_dungeon', 'Test', 'loc1')"
    )
    conn.execute(
        "INSERT INTO characters (id, user_id, name, system_id, sheet_json) VALUES (1, 1, 'Hero', 'core', ?)",
        (json.dumps({"level": 1, "current_hp": 20, "max_hp": 20}),),
    )
    conn.execute(
        "INSERT INTO game_config_riddles (key, text, answer, answer_alts, hints, is_active) "
        "VALUES ('r1', 'Co ma zęby?', 'grzebień', ?, ?, 1)",
        (json.dumps(["grzebien"]), json.dumps(["Hint 1", "Hint 2"])),
    )
    conn.commit()
    yield conn, str(db_file)
    conn.close()


def _make_run_with_riddle(character_id: int = 1) -> dict:
    content = {
        "tile_id": 1, "label": "Zagadka", "enemies": [], "items": [],
        "active_states": [], "exit_conditions": [{"type": "riddle_solved"}],
        "riddle": {
            "key": "r1", "text": "Co ma zęby?",
            "answer": "grzebień", "answer_alts": ["grzebien"],
            "hints": ["Hint 1", "Hint 2"], "hints_used": 0, "solved": False,
        },
        "is_boss_tile": False, "room_description": "Test.",
    }
    node = {
        "tile_id": 1, "position": [0, 0], "visited": True, "cleared": False,
        "doors_open": {"N": "node2"},
        "content": content,
    }
    return {
        "system": "tiles_v2",
        "dungeon_key": "test_dungeon",
        "dungeon_difficulty": 1,
        "cycle": 1,
        "positions": {str(character_id): "node1"},
        "graph": {"entry_node": "node1", "nodes": {"node1": node}},
        "completed": False, "failed": False,
    }


def _insert_session(conn, run: dict, campaign_id: int = 1):
    conn.execute(
        "INSERT OR REPLACE INTO game_sessions (id, campaign_id, session_flags) VALUES (?, ?, ?)",
        (f"s{campaign_id}", campaign_id, json.dumps({"dungeon_run": run})),
    )
    conn.commit()


def _load_current_node(conn, campaign_id: int = 1, character_id: int = 1) -> dict:
    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ?", (campaign_id,)
    ).fetchone()
    flags = json.loads(row["session_flags"])
    run = flags["dungeon_run"]
    node_id = run["positions"][str(character_id)]
    return run["graph"]["nodes"][node_id]


def _patch_db(db_path: str):
    from app.services import dungeon_tile_service as dts
    from app.services import dungeon_service as ds
    dts.DB_PATH = db_path
    ds.DB_PATH = db_path
    return dts


class TestRiddle745:
    """Regression tests for #745 — panel zagadki nie znika po rozwiązaniu."""

    def test_correct_answer_sets_riddle_solved_in_persisted_node(self, db):
        """After correct answer, content.riddle.solved=True must be in session_flags.
        Frontend can use this flag: hasRiddle = content.riddle && !content.riddle.solved
        """
        conn, db_path = db
        run = _make_run_with_riddle()
        _insert_session(conn, run)
        dts = _patch_db(db_path)

        result = dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "grzebień"})

        assert result["solved"] is True

        node = _load_current_node(conn)
        riddle = node["content"]["riddle"]
        assert isinstance(riddle, dict), "riddle must be a dict after solve"
        assert riddle["solved"] is True, "content.riddle.solved must be True after correct answer"
        assert node.get("cleared") is not True, "cleared stays False — only set on room exit"
        assert node["riddle_state"]["solved"] is True

    def test_correct_answer_does_not_set_node_cleared(self, db):
        """Solving a riddle does NOT set node.cleared=True — that happens on room exit.
        Frontend must NOT rely on cleared=True to hide the panel.
        """
        conn, db_path = db
        run = _make_run_with_riddle()
        _insert_session(conn, run)
        dts = _patch_db(db_path)

        dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "grzebień"})

        node = _load_current_node(conn)
        assert not node.get("cleared"), "cleared must stay False after riddle solve (only set on move)"

    def test_wrong_answer_riddle_solved_stays_false(self, db):
        """Wrong answer — riddle.solved stays False, panel should remain visible."""
        conn, db_path = db
        run = _make_run_with_riddle()
        _insert_session(conn, run)
        dts = _patch_db(db_path)

        from unittest.mock import patch
        with patch("random.random", return_value=0.99):
            result = dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "stół"})

        assert result["solved"] is False
        node = _load_current_node(conn)
        riddle = node["content"]["riddle"]
        assert riddle["solved"] is False, "riddle.solved must stay False after wrong answer"

    def test_exhausted_attempts_sets_failed_permanently_in_riddle_state(self, db):
        """After max wrong answers, node.riddle_state.failed_permanently=True.
        Frontend must check riddleState.failed_permanently to hide panel.
        """
        conn, db_path = db
        run = _make_run_with_riddle()
        _insert_session(conn, run)
        dts = _patch_db(db_path)

        from unittest.mock import patch
        for _ in range(_MAX_ATTEMPTS):
            with patch("random.random", return_value=0.99):
                result = dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "stół"})

        assert result["failed_permanently"] is True
        node = _load_current_node(conn)
        assert node["riddle_state"]["failed_permanently"] is True

    def test_already_solved_riddle_returns_solved_immediately(self, db):
        """If riddle.solved=True already (e.g. after page reload), backend returns solved=True
        without consuming another attempt — idempotent."""
        conn, db_path = db
        run = _make_run_with_riddle()
        # Pre-mark as solved (simulate reload scenario)
        run["graph"]["nodes"]["node1"]["content"]["riddle"]["solved"] = True
        run["graph"]["nodes"]["node1"]["riddle_state"] = {"solved": True}
        _insert_session(conn, run)
        dts = _patch_db(db_path)

        result = dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "cokolwiek"})

        assert result["solved"] is True
