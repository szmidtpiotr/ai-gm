"""L6 tests — resolve_tile_action: chest, riddle, trap, fallback.

Issue #675. Verifies:
- Chest: DEX roll, 3-attempt cap, 30% trap on fail, locked_forever, loot on success
- Riddle: answer matching, 3-attempt cap, hints (max 2), trap on fail
- riddle_hint action: return next hint without consuming attempt
- rest action: returns heal_pct
- Fallback (U22): missing node → ok=True, fallback=True (no crash)
- Soft-lock impossible: riddle_solved exit_condition does not block boss path
"""
from __future__ import annotations

import json
import sqlite3
from unittest.mock import patch

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
CREATE TABLE game_config_loot_tables (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT 'Table',
    gold_min INTEGER DEFAULT 0,
    gold_max INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1
);
CREATE TABLE game_config_loot_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    loot_table_key TEXT NOT NULL,
    item_key TEXT,
    consumable_key TEXT,
    weapon_key TEXT,
    weight INTEGER DEFAULT 100,
    qty_min INTEGER DEFAULT 1,
    qty_max INTEGER DEFAULT 1
);
CREATE TABLE game_config_enemies (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT 'Enemy',
    hp_base INTEGER DEFAULT 5,
    ac_base INTEGER DEFAULT 8,
    attack_bonus INTEGER DEFAULT 0,
    damage_die TEXT DEFAULT '1d6',
    damage_bonus INTEGER DEFAULT 0,
    dex_modifier INTEGER DEFAULT 0,
    tier TEXT DEFAULT 'common',
    stats_json TEXT DEFAULT NULL
);
CREATE TABLE game_config_items (key TEXT PRIMARY KEY, label TEXT NOT NULL DEFAULT 'Item');
CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, label TEXT NOT NULL DEFAULT 'Weapon');
CREATE TABLE game_config_consumables (key TEXT PRIMARY KEY, label TEXT NOT NULL DEFAULT 'Potion');
"""


@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test_l6.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO dungeon_tile_categories (key, label) VALUES ('crypt', 'Krypta')")
    conn.commit()
    yield conn, str(db_file)
    conn.close()


def _patch_db(db_path: str):
    from app.services import dungeon_tile_service as dts
    from app.services import dungeon_service as ds
    dts.DB_PATH = db_path
    ds.DB_PATH = db_path
    return dts


def _insert_dungeon(conn, key="test_dungeon", chest_loot_table_key=None, difficulty=1):
    conn.execute(
        "INSERT OR REPLACE INTO game_dungeons (key, label, location_key, dungeon_difficulty, "
        "chest_loot_table_key) VALUES (?, ?, ?, ?, ?)",
        (key, "Test Dungeon", "loc1", difficulty, chest_loot_table_key),
    )
    conn.commit()


def _insert_character(conn, character_id=1, dex=14):
    sheet = {"DEX": dex, "level": 1, "current_hp": 20, "max_hp": 20}
    conn.execute(
        "INSERT OR REPLACE INTO characters (id, user_id, name, system_id, sheet_json) "
        "VALUES (?, 1, 'Hero', 'core', ?)",
        (character_id, json.dumps(sheet)),
    )
    conn.commit()


def _insert_session(conn, campaign_id=1, run: dict | None = None):
    flags = {"dungeon_run": run} if run else {}
    conn.execute(
        "INSERT OR REPLACE INTO game_sessions (id, campaign_id, session_flags) VALUES (?, ?, ?)",
        (f"s{campaign_id}", campaign_id, json.dumps(flags)),
    )
    conn.commit()


def _make_v2_run(dungeon_key="test_dungeon", tier=1, node_content: dict | None = None,
                  character_id: int = 1) -> dict:
    """Minimal tiles_v2 dungeon run for testing resolve_tile_action."""
    content = node_content or {
        "tile_id": 1, "label": "Komnata", "enemies": [], "items": [],
        "active_states": [], "exit_conditions": [], "riddle": None,
        "is_boss_tile": False, "room_description": "Test room.",
    }
    node = {
        "tile_id": 1,
        "position": [0, 0],
        "visited": True,
        "cleared": False,
        "doors_open": {"N": "node2"},
        "content": content,
    }
    return {
        "system": "tiles_v2",
        "dungeon_key": dungeon_key,
        "dungeon_difficulty": tier,
        "cycle": 1,
        "positions": {str(character_id): "node1"},
        "graph": {
            "entry_node": "node1",
            "nodes": {"node1": node},
        },
        "completed": False,
        "failed": False,
    }


# ── Chest tests ───────────────────────────────────────────────────────────────

class TestChest:
    def test_chest_success_returns_loot(self, db):
        """DEX roll success → loot returned, chest opened."""
        conn, db_path = db
        _insert_dungeon(conn, chest_loot_table_key="loot_chest")
        conn.execute("INSERT INTO game_config_loot_tables (key, label) VALUES ('loot_chest', 'Test')")
        conn.execute(
            "INSERT INTO game_config_items (key, label) VALUES ('potion', 'Mikstura')"
        )
        conn.execute(
            "INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max) "
            "VALUES ('loot_chest', 'potion', 100, 1, 1)"
        )
        conn.commit()
        _insert_character(conn, dex=20)  # DEX mod +5, always passes DC 13 (12+1)
        run = _make_v2_run(tier=1)
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        with patch("random.random", return_value=0.99):  # trap won't trigger
            with patch("random.randint", side_effect=[20, 1, 1]):  # d20=20, loot qty
                result = dts.resolve_tile_action(1, 1, "open_chest")

        assert result["ok"] is True
        assert result["action"] == "open_chest"
        assert result["success"] is True
        assert result["roll"] == 20
        assert result["attempt"] == 1
        assert result["trap"] is None

    def test_chest_fail_increments_attempt(self, db):
        """DEX fail → attempt counted, no loot."""
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn, dex=8)  # DEX mod -1
        run = _make_v2_run(tier=1)
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        with patch("random.random", return_value=0.99):  # no trap
            with patch("random.randint", return_value=1):  # d20=1, always fails
                result = dts.resolve_tile_action(1, 1, "open_chest")

        assert result["ok"] is True
        assert result["success"] is False
        assert result["attempt"] == 1
        assert result["max_attempts"] == 3
        assert result["chest_locked_forever"] is False
        assert result["loot"] == []

    def test_chest_three_fails_locks_forever(self, db):
        """3 consecutive fails → locked_forever=True on 3rd attempt."""
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn, dex=8)  # always fails
        run = _make_v2_run(tier=1)
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        with patch("random.random", return_value=0.99):
            with patch("random.randint", return_value=1):
                dts.resolve_tile_action(1, 1, "open_chest")
                dts.resolve_tile_action(1, 1, "open_chest")
                result = dts.resolve_tile_action(1, 1, "open_chest")

        assert result["chest_locked_forever"] is True
        assert result["attempt"] == 3

    def test_chest_locked_forever_blocks_further_attempts(self, db):
        """4th attempt after lock → returns locked message without rolling."""
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn, dex=8)
        run = _make_v2_run(tier=1)
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        with patch("random.random", return_value=0.99):
            with patch("random.randint", return_value=1):
                dts.resolve_tile_action(1, 1, "open_chest")
                dts.resolve_tile_action(1, 1, "open_chest")
                dts.resolve_tile_action(1, 1, "open_chest")
            # 4th attempt — no more rolls
            result = dts.resolve_tile_action(1, 1, "open_chest")

        assert result["chest_locked_forever"] is True

    def test_chest_fail_triggers_trap_30pct(self, db):
        """Trap triggers when random < 0.30 after chest fail."""
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn, dex=8)
        run = _make_v2_run(tier=1)
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        # First random() call → trap check; randint for d20=1 (fail) then trap damage
        with patch("random.random", return_value=0.10):  # 10% < 30% → trap triggers
            with patch("random.randint", side_effect=[1, 3]):  # d20=1, trap dmg roll=3
                result = dts.resolve_tile_action(1, 1, "open_chest")

        assert result["success"] is False
        assert result["trap"] is not None
        assert result["trap"]["triggered"] is True
        assert result["trap"]["damage"] >= 1

    def test_chest_fail_no_trap_when_random_high(self, db):
        """No trap when random ≥ 0.30 after chest fail."""
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn, dex=8)
        run = _make_v2_run(tier=1)
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        with patch("random.random", return_value=0.50):  # above 30% → no trap
            with patch("random.randint", return_value=1):
                result = dts.resolve_tile_action(1, 1, "open_chest")

        assert result["trap"] is None

    def test_chest_dc_scales_with_tier(self, db):
        """DC = 12 + tier."""
        conn, db_path = db
        _insert_dungeon(conn, difficulty=3)
        _insert_character(conn, dex=10)  # DEX mod 0
        run = _make_v2_run(tier=3)
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        with patch("random.random", return_value=0.99):
            with patch("random.randint", return_value=10):
                result = dts.resolve_tile_action(1, 1, "open_chest")

        assert result["dc"] == 15  # 12 + tier 3
        assert result["roll"] == 10  # total 10+0=10 < 15 → fail


# ── Riddle tests ──────────────────────────────────────────────────────────────

def _run_with_riddle(riddle_key="r1", tier=1) -> dict:
    content = {
        "tile_id": 1, "label": "Zagadka", "enemies": [], "items": [],
        "active_states": [], "exit_conditions": [{"type": "riddle_solved"}],
        "riddle": {
            "key": riddle_key, "text": "Co ma zęby, lecz nie gryzie?",
            "answer": "grzebień", "answer_alts": ["grzebien"],
            "hints": ["Używasz go codziennie.", "Dotyczy włosów."],
            "hints_used": 0, "solved": False,
        },
        "is_boss_tile": False, "room_description": "Zagadkowa sala.",
    }
    return _make_v2_run(tier=tier, node_content=content)


def _run_with_riddle_key(riddle_key="r1", tier=1) -> dict:
    """Graph-realistic run: node content stores `riddle` as a STRING key (as the
    generator does via _get_tile_content), NOT a pre-resolved dict. Regression for
    the smoke-loch 500 (AttributeError: 'str' object has no attribute 'get')."""
    content = {
        "tile_id": 1, "label": "Zagadka", "enemies": [], "items": [],
        "active_states": [], "exit_conditions": [],
        "riddle": riddle_key,  # <-- string key, exactly what the graph stores
        "is_boss_tile": False, "room_description": "Zagadkowa sala.",
    }
    return _make_v2_run(tier=tier, node_content=content)


def _seed_riddle(conn, key="r1"):
    conn.execute(
        "INSERT INTO game_config_riddles (key, text, answer, answer_alts, hints, is_active) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        (key, "Co ma zęby, lecz nie gryzie?", "grzebień",
         json.dumps(["grzebien"]), json.dumps(["Używasz go codziennie.", "Dotyczy włosów."])),
    )
    conn.commit()


class TestRiddleStringKey:
    """Riddle stored as a bare string key in the graph node must still resolve
    (entry-run AND endless segments store it this way)."""

    def test_hint_with_string_key_does_not_crash(self, db):
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn)
        _seed_riddle(conn)
        run = _run_with_riddle_key()
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        result = dts.resolve_tile_action(1, 1, "riddle_hint", None)
        assert result["ok"] is True
        assert result["hint"] == "Używasz go codziennie."

    def test_answer_with_string_key_solves(self, db):
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn)
        _seed_riddle(conn)
        run = _run_with_riddle_key()
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        result = dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "grzebień"})
        assert result["ok"] is True
        assert result["solved"] is True

    def test_wrong_answer_with_string_key_does_not_crash(self, db):
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn)
        _seed_riddle(conn)
        run = _run_with_riddle_key()
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        with patch("app.services.dungeon_tile_service.random.random", return_value=0.99):
            result = dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "krzesło"})
        assert result["ok"] is True
        assert result["solved"] is False


class TestRiddle:
    def test_correct_answer_solves_riddle(self, db):
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn)
        run = _run_with_riddle()
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        result = dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "grzebień"})

        assert result["ok"] is True
        assert result["solved"] is True
        assert result["trap"] is None

    def test_alt_answer_also_solves(self, db):
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn)
        run = _run_with_riddle()
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        result = dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "grzebien"})
        assert result["solved"] is True

    def test_wrong_answer_returns_hint(self, db):
        """First wrong answer → hint returned, trap possibly triggered."""
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn)
        run = _run_with_riddle()
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        with patch("random.random", return_value=0.99):  # no trap
            result = dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "krzesło"})

        assert result["solved"] is False
        assert result["attempt"] == 1
        assert result["hint"] is not None
        assert result["failed_permanently"] is False

    def test_wrong_answer_triggers_trap(self, db):
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn)
        run = _run_with_riddle()
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        with patch("random.random", return_value=0.10):  # trap triggers
            with patch("random.randint", return_value=3):
                result = dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "krzesło"})

        assert result["trap"] is not None
        assert result["trap"]["triggered"] is True

    def test_three_wrong_answers_fail_permanently(self, db):
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn)
        run = _run_with_riddle()
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        with patch("random.random", return_value=0.99):
            dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "źle1"})
            dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "źle2"})
            result = dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "źle3"})

        assert result["solved"] is False
        assert result["failed_permanently"] is True
        assert result["attempt"] == 3

    def test_riddle_hint_action(self, db):
        """riddle_hint action returns next hint without consuming attempt."""
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn)
        run = _run_with_riddle()
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        result = dts.resolve_tile_action(1, 1, "riddle_hint")

        assert result["ok"] is True
        assert result["hint"] is not None
        assert result["hint"] == "Używasz go codziennie."

    def test_riddle_hint_max_two(self, db):
        """After 2 hints exhausted, riddle_hint returns no_more_hints."""
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn)
        run = _run_with_riddle()
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        dts.resolve_tile_action(1, 1, "riddle_hint")
        dts.resolve_tile_action(1, 1, "riddle_hint")
        result = dts.resolve_tile_action(1, 1, "riddle_hint")

        assert result["ok"] is True
        assert result.get("no_more_hints") is True or result.get("hint") is None

    def test_already_solved_riddle(self, db):
        """Calling answer_riddle on solved riddle returns already_solved."""
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn)
        run = _run_with_riddle()
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "grzebień"})
        result = dts.resolve_tile_action(1, 1, "answer_riddle", {"answer": "grzebień"})

        assert result["ok"] is True
        assert result["solved"] is True


# ── Rest action ───────────────────────────────────────────────────────────────

class TestRest:
    def test_rest_returns_heal_pct(self, db):
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn)
        run = _make_v2_run()
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        result = dts.resolve_tile_action(1, 1, "rest")

        assert result["ok"] is True
        assert result["action"] == "rest"
        assert result.get("heal_pct", 0) > 0


# ── Fallback (U22) ────────────────────────────────────────────────────────────

class TestFallback:
    def test_missing_node_returns_empty_corridor(self, db):
        """If node not in graph, return fallback response (no crash)."""
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn)
        # Run with wrong positions entry
        run = _make_v2_run()
        run["positions"] = {"1": "nonexistent_node"}  # points to missing node
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        result = dts.resolve_tile_action(1, 1, "open_chest")

        assert result["ok"] is True
        assert result.get("fallback") is True

    def test_no_active_run_raises(self, db):
        """ValueError when no active v2 run."""
        conn, db_path = db
        _insert_session(conn)  # no run in flags
        dts = _patch_db(db_path)

        with pytest.raises(ValueError):
            dts.resolve_tile_action(1, 1, "open_chest")

    def test_unknown_action_raises(self, db):
        """ValueError for unknown action string."""
        conn, db_path = db
        _insert_dungeon(conn)
        _insert_character(conn)
        run = _make_v2_run()
        _insert_session(conn, run=run)
        dts = _patch_db(db_path)

        with pytest.raises(ValueError, match="Nieznana akcja"):
            dts.resolve_tile_action(1, 1, "explode")


# ── Soft-lock prevention ──────────────────────────────────────────────────────

class TestNoSoftLock:
    def test_riddle_exit_condition_on_branch_not_boss_path(self, db):
        """check_exit_conditions: riddle_solved blocks branch tile but boss path stays clear.

        The generator (L2) ensures riddle_solved conditions appear only on branch tiles.
        This test verifies check_exit_conditions itself: a tile with riddle_solved condition
        blocks movement, while a tile WITHOUT that condition (boss path) does not block.
        """
        conn, db_path = db
        dts = _patch_db(db_path)

        # Branch tile has riddle_solved condition and unsolved riddle
        branch_tile = {
            "riddle": {"solved": False},
            "exit_conditions": [{"type": "riddle_solved"}],
            "cleared": False,
        }
        allowed, reason = dts.check_exit_conditions(branch_tile, 1)
        assert allowed is False
        assert reason is not None

        # Boss path tile has NO riddle condition — always passable
        boss_path_tile = {
            "enemies": [],
            "exit_conditions": [],
            "cleared": True,
        }
        allowed2, reason2 = dts.check_exit_conditions(boss_path_tile, 1)
        assert allowed2 is True

    def test_solved_riddle_unblocks_exit(self, db):
        """After riddle solved, exit_condition riddle_solved no longer blocks."""
        conn, db_path = db
        dts = _patch_db(db_path)

        tile = {
            "riddle": {"solved": True},
            "exit_conditions": [{"type": "riddle_solved"}],
            "cleared": False,
        }
        allowed, _ = dts.check_exit_conditions(tile, 1)
        assert allowed is True
