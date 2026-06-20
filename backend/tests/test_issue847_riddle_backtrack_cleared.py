"""TDD: Issue #847 — cofnięcie się z komnaty zagadki nie może ustawiać cleared=True.

Bug: linia 914 dungeon_tile_service.py ustawia cleared=True bezwarunkowo
     przy każdym wyjściu z kafelka — nawet przy cofaniu się (backtrack).
     Skutek: po cofnięciu i powrocie do komnaty zagadki frontend widzi cleared=True
     i ukrywa panel zagadki + przycisk "Odpowiedz".

Fix: cleared=True ustawiać TYLKO wewnątrz bloku `if not target_node.get("visited")`
     (ruch w przód, exit_conditions zweryfikowane i spełnione).
"""
from __future__ import annotations

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

CREATE TABLE game_config_enemies (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    hp_base INTEGER DEFAULT 5,
    ac_base INTEGER DEFAULT 8,
    attack_bonus INTEGER DEFAULT 0,
    damage_die TEXT DEFAULT '1d6',
    damage_bonus INTEGER DEFAULT 0,
    dex_modifier INTEGER DEFAULT 0,
    tier TEXT DEFAULT 'common'
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
    is_active INTEGER DEFAULT 1
);

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


def _make_riddle_run() -> dict:
    """Graf: node_entry (odwiedzony) → node_riddle (gracz stoi tutaj, cleared=False, ma zagadkę)."""
    return {
        "system": "tiles_v2",
        "dungeon_key": "test_dungeon",
        "dungeon_label": "Test Dungeon",
        "graph": {
            "entry_node": "node_entry",
            "boss_node": "node_riddle",
            "nodes": {
                "node_entry": {
                    "tile_id": 1,
                    "tile_label": "Wejście",
                    "position": [0, 0],
                    "doors_open": {"N": "node_riddle", "S": None, "E": None, "W": None},
                    "door_hints": {},
                    "content": {
                        "tile_id": 1,
                        "label": "Wejście",
                        "room_description": "Wejście do lochu.",
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
                "node_riddle": {
                    "tile_id": 2,
                    "tile_label": "Komnata Zagadek",
                    "position": [0, 1],
                    "doors_open": {"S": "node_entry", "N": None, "E": None, "W": None},
                    "door_hints": {},
                    "content": {
                        "tile_id": 2,
                        "label": "Komnata Zagadek",
                        "room_description": "Żołnierz z zagadką strzeże przejścia.",
                        "enemies": [],
                        "items": [],
                        "active_states": [],
                        "exit_conditions": [{"type": "riddle_solved"}],
                        "riddle": {
                            "key": "riddle_shadow",
                            "text": "Podążam za tobą w dzień. Czym jestem?",
                            "answer": "cień",
                            "hints": [],
                            "solved": False,
                        },
                        "is_boss_tile": False,
                    },
                    "visited": True,
                    "cleared": False,
                },
            },
        },
        "positions": {"42": "node_riddle"},
        "cycle": 1,
        "checkpoints": [],
        "completed": False,
        "failed": False,
    }


def _make_corridor_run() -> dict:
    """Graf: node_0 (gracz) → node_1 (nieodwiedzony korytarz). Brak exit_conditions."""
    return {
        "system": "tiles_v2",
        "dungeon_key": "test_dungeon",
        "dungeon_label": "Test Dungeon",
        "graph": {
            "entry_node": "node_0",
            "boss_node": "node_1",
            "nodes": {
                "node_0": {
                    "tile_id": 1,
                    "tile_label": "Wejście",
                    "position": [0, 0],
                    "doors_open": {"N": "node_1", "S": None, "E": None, "W": None},
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
                    "cleared": False,
                },
                "node_1": {
                    "tile_id": 2,
                    "tile_label": "Korytarz",
                    "position": [0, 1],
                    "doors_open": {"S": "node_0", "N": None, "E": None, "W": None},
                    "door_hints": {},
                    "content": {
                        "tile_id": 2,
                        "label": "Korytarz",
                        "room_description": "Korytarz.",
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
            },
        },
        "positions": {"42": "node_0"},
        "cycle": 1,
        "checkpoints": [],
        "completed": False,
        "failed": False,
    }


@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test_847.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, ?)",
        (json.dumps({"dungeon_run": _make_riddle_run()}),),
    )
    conn.commit()
    yield conn, str(db_file)
    conn.close()


def _patch(db_path: str):
    from app.services import dungeon_tile_service as dts
    from app.services import dungeon_service as ds
    dts.DB_PATH = db_path
    ds.DB_PATH = db_path
    return dts


# ─── RED: test główny (backtrack nie czyści riddle room) ─────────────────────

def test_backtrack_from_riddle_room_does_not_set_cleared(db):
    """Cofnięcie się z komnaty zagadki NIE ustawia cleared=True.

    #847: gracz stoi w node_riddle (cleared=False), cofa się do node_entry
    (visited=True → backtrack). Po cofnięciu node_riddle MUSI zostać cleared=False.
    Frontend sprawdza !currentNode.cleared żeby pokazać panel zagadki.
    """
    conn, db_path = db
    dts = _patch(db_path)

    result = dts.move_through_door(campaign_id=1, character_id=42, direction="S")

    assert result["ok"] is True, f"Backtrack powinien działać, got: {result}"

    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    flags = json.loads(row["session_flags"])
    node_riddle = flags["dungeon_run"]["graph"]["nodes"]["node_riddle"]

    assert node_riddle["cleared"] is False, (
        f"#847: cofnięcie się z komnaty zagadki nie powinno ustawiać cleared=True. "
        f"Gracz nie rozwiązał zagadki — panel powinien nadal być widoczny po powrocie. "
        f"got cleared={node_riddle['cleared']!r}"
    )


# ─── RED: po powrocie do komnaty zagadki cleared nadal False ─────────────────

def test_reenter_riddle_room_after_backtrack_cleared_still_false(db):
    """Po cofnięciu i ponownym wejściu do komnaty zagadki: cleared=False.

    #847 flow: node_riddle → backtrack → node_entry → powrót do node_riddle.
    node_riddle.cleared MUSI być False przez cały czas (zagadka nierozwiązana).
    """
    conn, db_path = db
    dts = _patch(db_path)

    # Krok 1: backtrack z riddle room do entry
    r1 = dts.move_through_door(campaign_id=1, character_id=42, direction="S")
    assert r1["ok"] is True, f"Backtrack failed: {r1}"

    # node_riddle powinno być cleared=False po cofnięciu
    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    flags = json.loads(row["session_flags"])
    assert flags["dungeon_run"]["graph"]["nodes"]["node_riddle"]["cleared"] is False, \
        "#847: po cofnięciu node_riddle powinno być cleared=False"

    # Krok 2: powrót do riddle room (node_entry → N → node_riddle, visited=True → backtrack)
    r2 = dts.move_through_door(campaign_id=1, character_id=42, direction="N")
    assert r2["ok"] is True, f"Powrót do riddle room failed: {r2}"

    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    flags = json.loads(row["session_flags"])
    node_riddle_after = flags["dungeon_run"]["graph"]["nodes"]["node_riddle"]

    assert node_riddle_after["cleared"] is False, (
        f"#847: po ponownym wejściu do komnaty zagadki cleared musi być False "
        f"(zagadka nierozwiązana). Frontend ukryje panel jeśli cleared=True. "
        f"got cleared={node_riddle_after['cleared']!r}"
    )


# ─── Backward compat: ruch w przód na pustym korytarzu nadal ustawia cleared ─

def test_forward_move_on_empty_corridor_still_sets_cleared(db):
    """Ruch w przód (do nieodwiedzonego node) nadal ustawia cleared=True na starym kafelku.

    Regresja: fix nie może zepsuć pełnego przebiegu przez puste korytarze.
    """
    conn, db_path = db
    dts = _patch(db_path)

    # Nadpisujemy fixture danymi korytarzowymi
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({"dungeon_run": _make_corridor_run()}),),
    )
    conn.commit()

    result = dts.move_through_door(campaign_id=1, character_id=42, direction="N")

    assert result["ok"] is True, f"Ruch w przód powinien działać, got: {result}"

    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    flags = json.loads(row["session_flags"])
    node_0 = flags["dungeon_run"]["graph"]["nodes"]["node_0"]

    assert node_0["cleared"] is True, (
        f"Ruch w przód (do nieodwiedzonego korytarza) MUSI ustawiać cleared=True "
        f"na opuszczanym kafelku. got cleared={node_0['cleared']!r}"
    )


# ─── Backward compat: backtrack na zwykły (non-riddle) kafelek działa ────────

def test_backtrack_on_normal_corridor_ok(db):
    """Cofnięcie się na normalny odwiedzony korytarz → ok=True, brak walki."""
    conn, db_path = db
    dts = _patch(db_path)

    # Gracz na node_riddle, cofa się do node_entry (odwiedzony, cleared)
    result = dts.move_through_door(campaign_id=1, character_id=42, direction="S")

    assert result["ok"] is True, f"Backtrack do odwiedzonego kafelka powinien działać, got: {result}"
    assert result.get("combat") is None, "Odwiedzony kafelek nie powinien startować walki"
