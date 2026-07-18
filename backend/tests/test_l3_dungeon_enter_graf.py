"""TDD: Issue #672 (L3) — Wejście do lochu przez graf.

Weryfikuje:
- enter_dungeon_tiles() zwraca dungeon_run v2 (system=="tiles_v2", graph, positions)
- Brak tile_category_key → ValueError z PL komunikatem
- Gracz na cooldownie → PermissionError
- context_injector._build_loch_block() generuje blok [LOCH] z opisem kafelka
"""
from __future__ import annotations
from _fixtures_schema import table_sql

import json
import sqlite3
from unittest.mock import patch

import pytest


# ─── In-memory DB schema (matching actual DEV schema) ─────────────────────────

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
    label TEXT NOT NULL,
    tile_category_key TEXT,
    tile_count INTEGER,
    boss_tile_id INTEGER,
    endless_growth_n INTEGER DEFAULT 0,
    cooldown_hours INTEGER DEFAULT 72,
    is_active INTEGER DEFAULT 1
);

-- Actual schema: location_key (not dungeon_key), cooldown_until, run_count
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


@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test_l3.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    # Dungeon z kategorią
    conn.execute(
        "INSERT INTO game_dungeons (key, label, tile_category_key, tile_count, cooldown_hours) "
        "VALUES ('test_dungeon', 'Test Dungeon', 'test_cat', 4, 72)"
    )
    # Dungeon BEZ kategorii
    conn.execute(
        "INSERT INTO game_dungeons (key, label, cooldown_hours) "
        "VALUES ('no_cat_dungeon', 'No Category', 72)"
    )
    # Kategoria kafelków
    conn.execute("INSERT INTO dungeon_tile_categories (key, label) VALUES ('test_cat', 'Test')")
    # Kafelki — z drzwiami które pasują (N↔S)
    for label, doors, is_boss in [
        ("T1", ["N", "S", "E"], 0),
        ("T2", ["N", "S", "W"], 0),
        ("T3", ["N", "S"], 0),
        ("Boss", ["N"], 1),
    ]:
        conn.execute(
            "INSERT INTO dungeon_tiles (category_key, label, doors_json, room_description, is_boss_tile) "
            "VALUES (?, ?, ?, ?, ?)",
            ("test_cat", label, json.dumps(doors), f"Opis pomieszczenia {label}.", is_boss),
        )
    # Sesja kampanii
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, '{}')")
    conn.commit()
    yield conn, str(db_file)
    conn.close()


def _patch_db(db_path: str):
    from app.services import dungeon_tile_service as dts
    from app.services import dungeon_service as ds
    dts.DB_PATH = db_path
    ds.DB_PATH = db_path
    return dts


# ─── Test 1: enter buduje dungeon_run v2 ──────────────────────────────────────

def test_enter_builds_v2_run(db):
    """enter_dungeon_tiles() buduje run z system=='tiles_v2', graph, positions."""
    conn, db_path = db
    dts = _patch_db(db_path)

    run = dts.enter_dungeon_tiles(
        campaign_id=1,
        character_id=42,
        dungeon_key="test_dungeon",
        hero_level=3,
    )

    assert run["system"] == "tiles_v2", f"Oczekiwano 'tiles_v2', got: {run['system']!r}"

    assert "graph" in run, "Brak klucza 'graph' w dungeon_run"
    graph = run["graph"]
    assert "nodes" in graph, "Brak nodes w grafie"
    assert "entry_node" in graph, "Brak entry_node w grafie"
    assert "boss_node" in graph, "Brak boss_node w grafie"
    assert graph["entry_node"] in graph["nodes"], "entry_node nie istnieje w nodes"

    # positions per character
    assert "positions" in run, "Brak 'positions' w dungeon_run"
    pos_key = str(42)
    assert pos_key in run["positions"], \
        f"Brak pozycji dla character_id=42 w positions: {run['positions']}"
    assert run["positions"][pos_key] == graph["entry_node"], \
        "Pozycja gracza powinna wskazywać na entry_node"

    # v2 metadata
    assert run["cycle"] == 1, "cycle powinno być 1"
    # L7: checkpoints now starts with entry checkpoint (not empty)
    assert isinstance(run["checkpoints"], list), "checkpoints powinno być listą"
    assert len(run["checkpoints"]) >= 1, "checkpoints powinno mieć entry checkpoint"
    assert run["checkpoints"][0]["source"] == "dungeon_enter"
    assert run["completed"] is False
    assert run["failed"] is False
    assert run["dungeon_key"] == "test_dungeon"


# ─── Test 2: brak tile_category_key → ValueError po PL ───────────────────────

def test_enter_409_no_category(db):
    """Brak tile_category_key → ValueError z polskim komunikatem o kategorii."""
    conn, db_path = db
    dts = _patch_db(db_path)

    with pytest.raises(ValueError) as exc_info:
        dts.enter_dungeon_tiles(
            campaign_id=1,
            character_id=42,
            dungeon_key="no_cat_dungeon",
            hero_level=3,
        )

    err = str(exc_info.value)
    assert "kategori" in err.lower(), (
        f"Komunikat powinien wspominać kategorię po polsku, got: {err!r}"
    )


# ─── Test 3: cooldown → PermissionError ───────────────────────────────────────

def test_enter_423_on_cooldown(db):
    """Gracz na aktywnym cooldownie → PermissionError z tagiem dungeon_on_cooldown."""
    conn, db_path = db
    dts = _patch_db(db_path)

    # Wstaw aktywny cooldown (cooldown_until w przyszłości)
    conn.execute(
        "INSERT OR REPLACE INTO character_dungeon_runs "
        "(character_id, location_key, cleared_at, cooldown_until, run_count) "
        "VALUES (42, 'test_dungeon', datetime('now'), datetime('now', '+71 hours'), 1)"
    )
    conn.commit()

    with pytest.raises(PermissionError) as exc_info:
        dts.enter_dungeon_tiles(
            campaign_id=1,
            character_id=42,
            dungeon_key="test_dungeon",
            hero_level=3,
        )

    assert "dungeon_on_cooldown" in str(exc_info.value), \
        f"PermissionError powinno zawierać 'dungeon_on_cooldown', got: {exc_info.value!r}"


# ─── Test 4: run v2 zapisuje się w session_flags ─────────────────────────────

def test_enter_saves_run_to_session_flags(db):
    """enter_dungeon_tiles() zapisuje run v2 do session_flags kampanii."""
    conn, db_path = db
    dts = _patch_db(db_path)

    dts.enter_dungeon_tiles(
        campaign_id=1,
        character_id=42,
        dungeon_key="test_dungeon",
        hero_level=3,
    )

    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = 1"
    ).fetchone()
    assert row, "Brak rekordu game_sessions dla campaign_id=1"
    flags = json.loads(row["session_flags"])
    run = flags.get("dungeon_run")
    assert run is not None, "Brak dungeon_run w session_flags"
    assert run.get("system") == "tiles_v2", f"system powinien być 'tiles_v2', got: {run.get('system')!r}"


# ─── Test 5: _build_loch_block() generuje blok [LOCH] ────────────────────────

def test_build_loch_block_with_v2_run():
    """context_injector._build_loch_block() zwraca [LOCH] blok gdy dungeon_run.system==tiles_v2."""
    from app.services.context_injector import ContextInjector

    session_flags = {
        "dungeon_run": {
            "system": "tiles_v2",
            "positions": {"42": "main_0"},
            "graph": {
                "entry_node": "main_0",
                "boss_node": "main_3",
                "nodes": {
                    "main_0": {
                        "tile_id": 1,
                        "position": [0, 0],
                        "doors_open": {"N": "main_1", "S": None, "E": None, "W": None},
                        "door_hints": {"N": "Słyszysz kroki za drzwiami."},
                        "content": {
                            "room_description": "Wilgotna komnata z kamiennymi ścianami.",
                            "enemies_json": [],
                        },
                        "visited": True,
                        "cleared": False,
                        "is_boss": False,
                    }
                },
            },
        }
    }

    injector = ContextInjector.__new__(ContextInjector)
    block = injector._build_loch_block(session_flags)

    assert block, "_build_loch_block() zwróciło pusty string"
    assert "[LOCH]" in block, "Brak tagu [LOCH]"
    assert "[/LOCH]" in block, "Brak tagu [/LOCH]"
    assert "Wilgotna komnata" in block, "Brak opisu kafelka w bloku"
    assert "Słyszysz kroki" in block, "Brak hint drzwi w bloku"


# ─── Test 6: _build_loch_block() zwraca '' dla braku dungeon_run ─────────────

def test_build_loch_block_empty_without_dungeon():
    """_build_loch_block() zwraca '' gdy brak dungeon_run lub system != tiles_v2."""
    from app.services.context_injector import ContextInjector

    injector = ContextInjector.__new__(ContextInjector)

    assert injector._build_loch_block({}) == "", "Powinno być '' bez dungeon_run"
    assert injector._build_loch_block({"dungeon_run": {"system": "tiles"}}) == "", \
        "Powinno być '' dla starego formatu 'tiles'"
