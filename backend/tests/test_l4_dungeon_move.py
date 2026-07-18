"""TDD: Issue #673 (L4) — Ruch przez drzwi: move_through_door + mark_node_cleared.

Weryfikuje:
- Ruch w dozwolonym kierunku (puste pomieszczenie) → ok=True, pozycja zaktualizowana
- Ruch w kierunku bez drzwi → ok=False, blocked=True, reason po PL
- Blokada przy żywych wrogach (enemies + cleared=False) → ok=False, blocked=True
- Backtracking na kafelek cleared=True → ok=True, combat=None
- Fog discovery: nieodwiedzone sąsiednie node'y ujawniane po ruchu
- mark_node_cleared() ustawia cleared=True na bieżącym node
- get_current_tile() zwraca właściwy node dla v2 grafu
"""
from __future__ import annotations
from _fixtures_schema import table_sql

import json
import sqlite3

import pytest


# ─── Minimal in-memory DB schema ──────────────────────────────────────────────

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


def _make_run(positions: dict | None = None, nodes: dict | None = None) -> dict:
    """Build a minimal v2 dungeon_run for tests."""
    if nodes is None:
        # 3-node linear graph: entry → middle → boss
        nodes = {
            "node_0": {
                "tile_id": 1,
                "tile_label": "Wejście",
                "position": [0, 0],
                "doors_open": {"N": "node_1", "S": None, "E": None, "W": None},
                "door_hints": {"N": "Słyszysz odgłosy."},
                "content": {
                    "tile_id": 1,
                    "label": "Wejście",
                    "room_description": "Ciemna komnata wejściowa.",
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
                "doors_open": {"S": "node_0", "N": "node_2", "E": None, "W": None},
                "door_hints": {"N": "Czujesz chłód."},
                "content": {
                    "tile_id": 2,
                    "label": "Korytarz",
                    "room_description": "Długi korytarz.",
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
            "node_2": {
                "tile_id": 3,
                "tile_label": "Boss",
                "position": [0, 2],
                "doors_open": {"S": "node_1", "N": None, "E": None, "W": None},
                "door_hints": {},
                "content": {
                    "tile_id": 3,
                    "label": "Boss",
                    "room_description": "Komnata bossa.",
                    "enemies": [{"enemy_key": "skeleton", "count": 1}],
                    "items": [],
                    "active_states": [],
                    "exit_conditions": [{"type": "enemies_cleared"}],
                    "riddle": None,
                    "is_boss_tile": True,
                },
                "visited": False,
                "cleared": False,
            },
        }
    if positions is None:
        positions = {"42": "node_0"}

    return {
        "system": "tiles_v2",
        "dungeon_key": "test_dungeon",
        "dungeon_label": "Test Dungeon",
        "graph": {
            "nodes": nodes,
            "entry_node": "node_0",
            "boss_node": "node_2",
        },
        "positions": positions,
        "cycle": 1,
        "checkpoints": [],
        "completed": False,
        "failed": False,
    }


@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test_l4.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, ?)",
                 (json.dumps({"dungeon_run": _make_run()}),))
    conn.commit()
    yield conn, str(db_file)
    conn.close()


def _patch(db_path: str):
    from app.services import dungeon_tile_service as dts
    from app.services import dungeon_service as ds
    dts.DB_PATH = db_path
    ds.DB_PATH = db_path
    return dts


# ─── Test 1: Ruch w dozwolonym kierunku (puste pomieszczenie) ─────────────────

def test_move_valid_direction(db):
    """Ruch N z node_0 do node_1 (brak wrogów) → ok=True, pozycja na node_1."""
    conn, db_path = db
    dts = _patch(db_path)

    result = dts.move_through_door(campaign_id=1, character_id=42, direction="N")

    assert result["ok"] is True, f"Oczekiwano ok=True, got: {result}"
    assert result["node_id"] == "node_1", f"Oczekiwano node_1, got: {result.get('node_id')}"
    assert result.get("combat") is None, "Puste pomieszczenie nie powinno startować walki"

    # Verify positions updated in DB
    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    flags = json.loads(row["session_flags"])
    run = flags["dungeon_run"]
    assert run["positions"]["42"] == "node_1", "Pozycja gracza powinna być na node_1 po ruchu"
    assert run["graph"]["nodes"]["node_1"]["visited"] is True, "node_1 powinien być oznaczony jako visited"


# ─── Test 2: Brak drzwi w kierunku ───────────────────────────────────────────

def test_move_no_door_blocked(db):
    """Ruch W z node_0 (brak drzwi na W) → ok=False, blocked=True z PL komunikatem."""
    conn, db_path = db
    dts = _patch(db_path)

    result = dts.move_through_door(campaign_id=1, character_id=42, direction="W")

    assert result["ok"] is False, "Ruch bez drzwi powinien zwrócić ok=False"
    assert result.get("blocked") is True, "Powinno być blocked=True"
    assert result.get("reason"), "Powód blokady powinien być niepusty"
    assert "drzwi" in result["reason"].lower() or "kierunek" in result["reason"].lower(), \
        f"Komunikat powinien wspominać drzwi/kierunek, got: {result['reason']!r}"


# ─── Test 3: Blokada przy żywych wrogach na bieżącym kafelku ─────────────────

def test_move_blocked_by_enemies(db):
    """Próba wyjścia z node_0 gdy ma wrogów i cleared=False → blocked."""
    conn, db_path = db
    dts = _patch(db_path)

    # Ustawiamy node_0 z wrogami i exit_condition + cleared=False
    run = _make_run()
    run["graph"]["nodes"]["node_0"]["content"]["enemies"] = [{"enemy_key": "goblin", "count": 1}]
    run["graph"]["nodes"]["node_0"]["content"]["exit_conditions"] = [{"type": "enemies_cleared"}]
    run["graph"]["nodes"]["node_0"]["cleared"] = False
    conn.execute("UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
                 (json.dumps({"dungeon_run": run}),))
    conn.commit()

    result = dts.move_through_door(campaign_id=1, character_id=42, direction="N")

    assert result["ok"] is False, "Ruch z niepokonanymi wrogami powinien być zablokowany"
    assert result.get("blocked") is True, "Powinno być blocked=True"
    assert "wróg" in result["reason"].lower() or "pokon" in result["reason"].lower(), \
        f"Komunikat powinien wspominać wrogów, got: {result['reason']!r}"


# ─── Test 4: Backtracking na cleared=True → brak walki ────────────────────────

def test_backtrack_cleared_no_combat(db):
    """Powrót na kafelek z cleared=True (poprzednio oczyszczony) → ok=True, combat=None."""
    conn, db_path = db
    dts = _patch(db_path)

    # Pozycja na node_1, node_0 jest cleared
    run = _make_run(positions={"42": "node_1"})
    run["graph"]["nodes"]["node_0"]["cleared"] = True
    run["graph"]["nodes"]["node_0"]["content"]["enemies"] = [{"enemy_key": "goblin", "count": 1}]
    run["graph"]["nodes"]["node_1"]["visited"] = True
    conn.execute("UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
                 (json.dumps({"dungeon_run": run}),))
    conn.commit()

    # Backtrack S: node_1 → node_0
    result = dts.move_through_door(campaign_id=1, character_id=42, direction="S")

    assert result["ok"] is True, f"Backtrack powinien działać, got: {result}"
    assert result.get("combat") is None, \
        "Kafelek cleared=True nie powinien startować walki przy backtracking"
    assert result["is_cleared"] is True, "is_cleared powinno być True dla oczyszczonego kafelka"


# ─── Test 5: Fog discovery po ruchu ───────────────────────────────────────────

def test_fog_discovery_on_move(db):
    """Po ruchu N z node_0 do node_1 → fog_discovered zawiera node_2 (sąsiad node_1)."""
    conn, db_path = db
    dts = _patch(db_path)

    result = dts.move_through_door(campaign_id=1, character_id=42, direction="N")

    assert result["ok"] is True, f"Ruch powinien się udać, got: {result}"
    fog = result.get("fog_discovered") or []
    assert "node_2" in fog, \
        f"node_2 (sąsiad node_1 przez drzwi N) powinien być w fog_discovered, got: {fog}"


# ─── Test 6: mark_node_cleared ustawia cleared=True ──────────────────────────

def test_mark_node_cleared(db):
    """mark_node_cleared() ustawia cleared=True na bieżącym node gracza."""
    conn, db_path = db
    dts = _patch(db_path)

    # Gracz na node_0 (cleared=False)
    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    flags = json.loads(row["session_flags"])
    assert flags["dungeon_run"]["graph"]["nodes"]["node_0"]["cleared"] is False

    dts.mark_node_cleared(campaign_id=1, character_id=42)

    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    flags = json.loads(row["session_flags"])
    assert flags["dungeon_run"]["graph"]["nodes"]["node_0"]["cleared"] is True, \
        "mark_node_cleared() powinno ustawić cleared=True na bieżącym node"


# ─── Test 7: get_current_tile zwraca właściwy node dla v2 ────────────────────

def test_get_current_tile_v2():
    """get_current_tile() zwraca właściwy node dla v2 run, None dla pustych positions."""
    from app.services.dungeon_tile_service import get_current_tile

    run = _make_run()

    tile = get_current_tile(run)
    assert tile is not None, "get_current_tile() powinno zwrócić node dla v2 run"
    assert tile.get("tile_label") == "Wejście", \
        f"Bieżący node to node_0 (Wejście), got: {tile.get('tile_label')!r}"

    # Empty positions → should fall back to entry_node
    run_no_pos = _make_run(positions={})
    tile_fallback = get_current_tile(run_no_pos)
    assert tile_fallback is not None, "get_current_tile() powinno fallbackować do entry_node"
