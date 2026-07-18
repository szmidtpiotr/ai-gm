"""TDD: Issue #736 (LB2) — soft-init w pierwszej komnacie lochu.

Niezmiennik: w PIERWSZEJ walce runu lochu (combats_started==0) bohater
zawsze jest na pozycji 0 w turn_order, niezależnie od wylosowanej inicjatywy.

Tests:
- T1: move_through_door na kaflu z wrogami (combats_started brak/0) →
       initiate_combat wywołany z _dungeon_first_combat=True
- T2: move_through_door gdy combats_started=1 →
       initiate_combat wywołany z _dungeon_first_combat=False (lub bez flagi)
- T3: combats_started inkrementowany po pierwszej walce w run
- T4: initiate_combat przyjmuje parametr _dungeon_first_combat (sprawdź sygnaturę)
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from unittest.mock import patch, MagicMock

import pytest

import sys
sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

import app.services.dungeon_tile_service as dts
import app.services.dungeon_service as ds


# ─── Minimal schema (tylko to co move_through_door potrzebuje) ────────────────

SCHEMA = """
CREATE TABLE game_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER UNIQUE NOT NULL,
    session_flags TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE dungeon_tile_categories (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    is_active INTEGER DEFAULT 1
);

""" + table_sql("game_config_enemies") + """

CREATE TABLE game_dungeons (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    dungeon_difficulty INTEGER DEFAULT 1,
    tile_category_key TEXT,
    tile_count INTEGER DEFAULT 4,
    is_active INTEGER DEFAULT 1
);
"""


def _make_run(combats_started: int | None = None) -> dict:
    """Minimal v2 dungeon run: entry → combat node."""
    run = {
        "system": "tiles_v2",
        "dungeon_key": "test_dungeon",
        "dungeon_label": "Test",
        "dungeon_difficulty": 1,
        "cycle": 1,
        "graph": {
            "nodes": {
                "node_0": {
                    "tile_id": 1,
                    "tile_label": "Wejście",
                    "position": [0, 0],
                    "doors_open": {"N": "node_1"},
                    "door_hints": {},
                    "content": {
                        "enemies": [],
                        "items": [],
                        "active_states": [],
                        "exit_conditions": [],
                        "is_boss_tile": False,
                        "room_description": "",
                    },
                    "visited": True,
                    "cleared": True,
                },
                "node_1": {
                    "tile_id": 2,
                    "tile_label": "Komnata walki",
                    "position": [0, 1],
                    "doors_open": {"S": "node_0"},
                    "door_hints": {},
                    "content": {
                        "enemies": [{"enemy_key": "skeleton", "count": 1}],
                        "items": [],
                        "active_states": [],
                        "exit_conditions": [{"type": "enemies_cleared"}],
                        "is_boss_tile": False,
                        "room_description": "Ciemna komnata.",
                    },
                    "visited": False,
                    "cleared": False,
                },
            },
            "entry_node": "node_0",
            "boss_node": "node_1",
        },
        "positions": {"42": "node_0"},
        "checkpoints": [],
        "completed": False,
        "failed": False,
    }
    if combats_started is not None:
        run["combats_started"] = combats_started
    return run


@pytest.fixture
def db(tmp_path):
    db_file = str(tmp_path / "test_lb2.db")
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO game_dungeons (key, label) VALUES ('test_dungeon', 'Test')"
    )
    conn.execute(
        "INSERT INTO game_config_enemies (key, label) VALUES ('skeleton', 'Szkielet')"
    )
    conn.commit()
    yield conn, db_file
    conn.close()


def _setup_run(conn, run: dict) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO game_sessions (campaign_id, session_flags) VALUES (1, ?)",
        (json.dumps({"dungeon_run": run}),),
    )
    conn.commit()


def _get_run(conn) -> dict:
    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1"
    ).fetchone()
    return json.loads(row["session_flags"])["dungeon_run"]


# ─── T1: Pierwsza walka → _dungeon_first_combat=True ─────────────────────────

def test_first_combat_passes_soft_init_flag(db):
    """move_through_door na 1. kaflu bojowym runu → initiate_combat z _dungeon_first_combat=True."""
    conn, db_path = db
    dts.DB_PATH = db_path
    ds.DB_PATH = db_path
    _setup_run(conn, _make_run())  # brak combats_started → pierwsze starcie

    captured_kwargs = {}

    def fake_initiate_combat(campaign_id, character_id, enemy_keys, **kwargs):
        captured_kwargs.update(kwargs)
        return {"turn_order": ["player", "skeleton_01"], "combatants": []}

    with patch("app.services.combat_service.initiate_combat", side_effect=fake_initiate_combat):
        result = dts.move_through_door(campaign_id=1, character_id=42, direction="N")

    assert result.get("ok") is True, f"Ruch powinien się udać: {result}"
    assert captured_kwargs.get("_dungeon_first_combat") is True, (
        f"Pierwsza walka runu musi używać _dungeon_first_combat=True, "
        f"got kwargs={captured_kwargs}"
    )


# ─── T2: Druga walka → _dungeon_first_combat=False ───────────────────────────

def test_second_combat_no_soft_init_flag(db):
    """move_through_door gdy combats_started=1 → initiate_combat z _dungeon_first_combat=False."""
    conn, db_path = db
    dts.DB_PATH = db_path
    ds.DB_PATH = db_path
    _setup_run(conn, _make_run(combats_started=1))

    captured_kwargs = {}

    def fake_initiate_combat(campaign_id, character_id, enemy_keys, **kwargs):
        captured_kwargs.update(kwargs)
        return {"turn_order": ["skeleton_01", "player"], "combatants": []}

    with patch("app.services.combat_service.initiate_combat", side_effect=fake_initiate_combat):
        result = dts.move_through_door(campaign_id=1, character_id=42, direction="N")

    assert result.get("ok") is True
    assert captured_kwargs.get("_dungeon_first_combat") is False or \
           "_dungeon_first_combat" not in captured_kwargs or \
           captured_kwargs.get("_dungeon_first_combat") is False, (
        f"Kolejne walki NIE powinny mieć _dungeon_first_combat=True, got={captured_kwargs}"
    )


# ─── T3: combats_started inkrementowany po inicjacji walki ───────────────────

def test_combats_started_incremented_after_first_combat(db):
    """Po pierwszej walce runu, run['combats_started'] powinno być 1."""
    conn, db_path = db
    dts.DB_PATH = db_path
    ds.DB_PATH = db_path
    run = _make_run()
    assert "combats_started" not in run, "Nowy run nie powinien mieć combats_started"
    _setup_run(conn, run)

    def fake_initiate_combat(campaign_id, character_id, enemy_keys, **kwargs):
        return {"turn_order": ["player", "skeleton_01"], "combatants": []}

    with patch("app.services.combat_service.initiate_combat", side_effect=fake_initiate_combat):
        dts.move_through_door(campaign_id=1, character_id=42, direction="N")

    updated_run = _get_run(conn)
    assert updated_run.get("combats_started") == 1, (
        f"combats_started powinno być 1 po pierwszej walce, got={updated_run.get('combats_started')}"
    )


# ─── T4: initiate_combat przyjmuje _dungeon_first_combat ─────────────────────

def test_initiate_combat_accepts_dungeon_first_combat_param():
    """initiate_combat musi przyjmować parametr _dungeon_first_combat (sygnatura)."""
    from app.services.combat_service import initiate_combat
    sig = inspect.signature(initiate_combat)
    assert "_dungeon_first_combat" in sig.parameters, (
        f"initiate_combat() musi mieć parametr _dungeon_first_combat. "
        f"Aktualne parametry: {list(sig.parameters.keys())}"
    )
    param = sig.parameters["_dungeon_first_combat"]
    assert param.default is False or param.default == False, (
        f"_dungeon_first_combat powinien domyślnie być False, got={param.default!r}"
    )
