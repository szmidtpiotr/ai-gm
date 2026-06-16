"""Tests for dungeon_tile_service (issue #224).

Verifies path generation with door matching, dead-end detection, and content
resolution. Uses in-memory SQLite with a minimal schema slice.
"""
from __future__ import annotations

import json
import sqlite3
from unittest.mock import patch

import pytest


SCHEMA = """
CREATE TABLE dungeon_tile_categories (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT DEFAULT '',
    style_modifier TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE dungeon_tiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_key TEXT NOT NULL,
    label TEXT NOT NULL,
    image_url TEXT,
    image_gen_prompt TEXT,
    doors_json TEXT DEFAULT '[]',
    room_description TEXT DEFAULT '',
    enemies_json TEXT DEFAULT '[]',
    items_json TEXT DEFAULT '[]',
    active_states_json TEXT DEFAULT '[]',
    riddle_key TEXT,
    exit_conditions_json TEXT DEFAULT '[]',
    is_boss_tile INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE game_config_enemies (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    hp_base INTEGER DEFAULT 5,
    ac_base INTEGER DEFAULT 8,
    attack_bonus INTEGER DEFAULT 0,
    damage_die TEXT DEFAULT '1d6',
    damage_bonus INTEGER DEFAULT 0,
    dex_modifier INTEGER DEFAULT 0,
    tier TEXT DEFAULT 'common',
    stats_json TEXT DEFAULT NULL
);

CREATE TABLE game_config_items (key TEXT PRIMARY KEY, label TEXT NOT NULL);
CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, label TEXT NOT NULL);
CREATE TABLE game_config_consumables (key TEXT PRIMARY KEY, label TEXT NOT NULL);
CREATE TABLE game_config_riddles (
    key TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    answer TEXT NOT NULL,
    answer_alts TEXT DEFAULT '[]',
    hints TEXT DEFAULT '[]',
    difficulty INTEGER DEFAULT 1,
    theme TEXT DEFAULT 'general',
    is_active INTEGER DEFAULT 1
);
"""


@pytest.fixture
def db(tmp_path):
    """SQLite DB on disk (service hardcodes file path; patch DB_PATH)."""
    db_file = tmp_path / "test_tiles.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO dungeon_tile_categories (key, label) VALUES ('test_cat', 'Test')"
    )
    conn.commit()
    yield conn, str(db_file)
    conn.close()


def _add_tile(conn, label, doors, is_boss=False, enemies=None, items=None,
              active_states=None, exit_conditions=None, riddle_key=None):
    cur = conn.execute(
        """INSERT INTO dungeon_tiles
           (category_key, label, doors_json, enemies_json, items_json,
            active_states_json, exit_conditions_json, riddle_key, is_boss_tile)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("test_cat", label, json.dumps(doors),
         json.dumps(enemies or []), json.dumps(items or []),
         json.dumps(active_states or []), json.dumps(exit_conditions or []),
         riddle_key, 1 if is_boss else 0),
    )
    conn.commit()
    return cur.lastrowid


def _patched_service(db_path):
    """Import and patch dungeon_tile_service to use the test DB."""
    from app.services import dungeon_tile_service as dts
    from app.services import dungeon_service as ds
    dts.DB_PATH = db_path  # service reads via ds._get_db which reads ds.DB_PATH
    ds.DB_PATH = db_path
    return dts


def test_draw_simple_path(db):
    conn, db_path = db
    # T1 NE, T2 WS, T3(boss) N
    _add_tile(conn, "T1", ["N", "E"])
    _add_tile(conn, "T2", ["W", "S"])
    _add_tile(conn, "Boss", ["N"], is_boss=True)
    dts = _patched_service(db_path)
    seq = dts.draw_tile_sequence("test_cat", 3)
    assert len(seq) == 3
    # First tile entry_door is None
    assert seq[0]["entry_door"] is None
    # Last tile is the boss
    assert seq[-1].get("is_boss") is True
    # Door chain: each consecutive pair's exit/entry must be opposites
    for a, b in zip(seq, seq[1:]):
        assert dts.OPPOSITE[a["exit_door"]] == b["entry_door"]


def test_dead_end_raises(db):
    conn, db_path = db
    # Only tiles with single doors all N — can't chain
    _add_tile(conn, "T1", ["N"])
    _add_tile(conn, "T2", ["N"])
    _add_tile(conn, "Boss", ["N"], is_boss=True)
    dts = _patched_service(db_path)
    with pytest.raises(ValueError):
        dts.draw_tile_sequence("test_cat", 3)


def test_insufficient_tiles_raises(db):
    conn, db_path = db
    _add_tile(conn, "Boss", ["N"], is_boss=True)
    dts = _patched_service(db_path)
    with pytest.raises(ValueError, match="Insufficient tiles"):
        dts.draw_tile_sequence("test_cat", 4)


def test_path_positions_no_collision(db):
    conn, db_path = db
    # Multi-direction tile pool
    for i, doors in enumerate([["N","E"], ["W","S"], ["N","S"], ["E","W"]]):
        _add_tile(conn, f"T{i+1}", doors)
    _add_tile(conn, "Boss", ["N","S","E","W"], is_boss=True)
    dts = _patched_service(db_path)
    seq = dts.draw_tile_sequence("test_cat", 4, max_retries=50)
    positions = [tuple(s["position"]) for s in seq]
    assert len(set(positions)) == len(positions), "tiles should not overlap"


def test_resolve_tile_content_with_enemy(db):
    conn, db_path = db
    conn.execute(
        "INSERT INTO game_config_enemies (key, label, hp_base, ac_base, "
        "attack_bonus, damage_die) VALUES ('szczur', 'Szczur', 4, 7, 1, '1d4')"
    )
    conn.commit()
    tid = _add_tile(conn, "T1", ["N"], enemies=[{"enemy_key": "szczur", "count": 2}])
    dts = _patched_service(db_path)
    content = dts.resolve_tile_content(tid, hero_level=1)
    assert content is not None
    assert content["label"] == "T1"
    assert content["doors"] == ["N"]
    assert len(content["enemies"]) == 1
    enemy = content["enemies"][0]
    assert enemy["enemy_key"] == "szczur"
    assert enemy["count"] == 2
    assert enemy["stats"]["hp_base"] > 0


def test_resolve_tile_content_with_riddle(db):
    conn, db_path = db
    conn.execute(
        "INSERT INTO game_config_riddles (key, text, answer, answer_alts, hints) "
        "VALUES ('r1', 'q?', 'a', '[]', '[\"hint1\"]')"
    )
    conn.commit()
    tid = _add_tile(conn, "T1", ["N"], riddle_key="r1")
    dts = _patched_service(db_path)
    content = dts.resolve_tile_content(tid, hero_level=1)
    assert content["riddle"] is not None
    assert content["riddle"]["text"] == "q?"
    assert content["riddle"]["answer"] == "a"
    assert content["riddle"]["hints"] == ["hint1"]


def test_specific_boss_tile_id(db):
    conn, db_path = db
    _add_tile(conn, "T1", ["N", "S"])
    _add_tile(conn, "Boss1", ["N"], is_boss=True)
    boss2_id = _add_tile(conn, "Boss2", ["N", "E"], is_boss=True)
    dts = _patched_service(db_path)
    seq = dts.draw_tile_sequence("test_cat", 2, boss_tile_id=boss2_id, max_retries=20)
    # Last tile should be Boss2 specifically (not Boss1)
    assert seq[-1]["tile_id"] == boss2_id


def test_door_match_rule(db):
    """If A exits east, B must have a west door."""
    conn, db_path = db
    _add_tile(conn, "T1", ["E"])
    _add_tile(conn, "Boss", ["W"], is_boss=True)
    dts = _patched_service(db_path)
    seq = dts.draw_tile_sequence("test_cat", 2, max_retries=10)
    assert seq[0]["exit_door"] == "E"
    assert seq[1]["entry_door"] == "W"


def test_use_legacy_env_flag(monkeypatch):
    """The router should consult DUNGEON_SYSTEM env var."""
    from app.services import dungeon_service as ds
    monkeypatch.setenv("DUNGEON_SYSTEM", "legacy")
    assert ds._use_legacy() is True
    monkeypatch.setenv("DUNGEON_SYSTEM", "tiles")
    assert ds._use_legacy() is False
    monkeypatch.delenv("DUNGEON_SYSTEM", raising=False)
    assert ds._use_legacy() is False  # default = tiles
