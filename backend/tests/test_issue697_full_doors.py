"""TDD: Issue #697 (L-doors / Decyzja 2b) — generator wypełnia WSZYSTKIE drzwi kafla.

Problem: `_build_tile_graph` zostawiał `doors_open[d] = None` dla namalowanych-ale-
niepołączonych drzwi → gracz widzi drzwi na obrazku, których nie ma na d-padzie.

Weryfikuje:
- Mając w puli 1-drzwiowe „zaślepki" (N/S/E/W), wygenerowany graf ma ZERO doors_open == None.
- Wypełnione połączenia są symetryczne (A→dir→B ⇒ B→opp→A).
- Brak kolizji pozycji po wypełnieniu.
- Sąsiednie otwarte drzwi są zespawane (weld) zamiast dublować kafel na zajętym polu.
- Mała/niepasująca pula → fallback bez wyjątku, wejście (entry_node) zawsze obecne.
- Backward compat: stary graf nadal poprawny strukturalnie.
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

CREATE TABLE session_flags (
    campaign_id INTEGER PRIMARY KEY,
    flags_json TEXT NOT NULL DEFAULT '{}'
);
"""

OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}


@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test_697.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO dungeon_tile_categories (key, label) VALUES ('test_cat', 'Test')")
    conn.commit()
    yield conn, str(db_file)
    conn.close()


def _add_tile(conn, label, doors, is_boss=False, enemies=None, items=None, riddle_key=None):
    cur = conn.execute(
        "INSERT INTO dungeon_tiles "
        "(category_key, label, doors_json, enemies_json, items_json, riddle_key, is_boss_tile) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("test_cat", label, json.dumps(doors),
         json.dumps(enemies or []), json.dumps(items or []),
         riddle_key, 1 if is_boss else 0),
    )
    conn.commit()
    return cur.lastrowid


def _patch_db(db_path):
    from app.services import dungeon_tile_service as dts
    from app.services import dungeon_service as ds
    dts.DB_PATH = db_path
    ds.DB_PATH = db_path
    return dts


def _add_caps(conn):
    """Add 1-door „zaślepki" for every direction (part-A tiles) so closure is reachable."""
    _add_tile(conn, "CapN", ["N"])
    _add_tile(conn, "CapS", ["S"])
    _add_tile(conn, "CapE", ["E"])
    _add_tile(conn, "CapW", ["W"])


def _count_open_doors(graph):
    return sum(
        1
        for n in graph["nodes"].values()
        for t in (n["doors_open"] or {}).values()
        if t is None
    )


def _assert_symmetric(graph):
    nodes = graph["nodes"]
    for nid, node in nodes.items():
        for direction, target_nid in (node["doors_open"] or {}).items():
            if target_nid is None:
                continue
            assert target_nid in nodes, f"{nid}→{direction}→missing {target_nid}"
            opp = OPPOSITE[direction]
            reverse = (nodes[target_nid]["doors_open"] or {}).get(opp)
            assert reverse == nid, (
                f"Asymetria: {nid}→{direction}→{target_nid}, ale "
                f"{target_nid}→{opp}→{reverse} (oczekiwano {nid})"
            )


def _all_positions(graph):
    return [tuple(n["position"]) for n in graph["nodes"].values()]


# ─── Test 1 (główny): zero otwartych drzwi gdy są zaślepki ───────────────────

def test_no_open_doors_when_caps_available(db):
    conn, db_path = db
    _add_tile(conn, "T1", ["N", "S", "E"])
    _add_tile(conn, "T2", ["N", "S", "W"])
    _add_tile(conn, "T3", ["N", "S", "E", "W"])
    _add_caps(conn)
    _add_tile(conn, "Boss", ["N", "S", "E", "W"], is_boss=True)
    dts = _patch_db(db_path)

    for _ in range(15):
        graph = dts.draw_tile_graph("test_cat", tile_count=4, max_retries=40)
        assert _count_open_doors(graph) == 0, (
            f"Pozostały niepołączone drzwi (doors_open==None): {_count_open_doors(graph)}"
        )


# ─── Test 2: wypełnione połączenia symetryczne ───────────────────────────────

def test_filled_doors_symmetric(db):
    conn, db_path = db
    _add_tile(conn, "T1", ["N", "S", "E"])
    _add_tile(conn, "T2", ["N", "S", "W"])
    _add_caps(conn)
    _add_tile(conn, "Boss", ["N", "E", "W"], is_boss=True)
    dts = _patch_db(db_path)

    for _ in range(15):
        graph = dts.draw_tile_graph("test_cat", tile_count=4, max_retries=40)
        _assert_symmetric(graph)


# ─── Test 3: brak kolizji pozycji po wypełnieniu ─────────────────────────────

def test_no_position_collisions_after_fill(db):
    conn, db_path = db
    _add_tile(conn, "T1", ["N", "S", "E", "W"])
    _add_tile(conn, "T2", ["N", "S", "E", "W"])
    _add_caps(conn)
    _add_tile(conn, "Boss", ["N", "S", "E", "W"], is_boss=True)
    dts = _patch_db(db_path)

    for _ in range(15):
        graph = dts.draw_tile_graph("test_cat", tile_count=4, max_retries=40)
        positions = _all_positions(graph)
        assert len(set(positions)) == len(positions), f"Kolizja pozycji: {positions}"


# ─── Test 4: fallback bez wyjątku gdy pula nie domyka się ────────────────────

def test_fallback_when_caps_missing(db):
    conn, db_path = db
    # Same wielodrzwiowe kafle, BRAK 1-drzwiowych zaślepek → pełne domknięcie
    # praktycznie nieosiągalne; generator MUSI zwrócić najlepszy graf, nie rzucać.
    _add_tile(conn, "T1", ["N", "S", "E"])
    _add_tile(conn, "T2", ["N", "S", "W"])
    _add_tile(conn, "Boss", ["N", "S", "E", "W"], is_boss=True)
    dts = _patch_db(db_path)

    graph = dts.draw_tile_graph("test_cat", tile_count=3, max_retries=20)
    assert "nodes" in graph
    assert graph["entry_node"] in graph["nodes"], "Wejście do lochu musi istnieć (fallback)"
    assert graph["boss_node"] in graph["nodes"], "Boss musi istnieć w fallbacku"
    # graf wciąż musi być spójny (symetryczny) nawet jeśli zostały otwarte drzwi
    _assert_symmetric(graph)


# ─── Test 5: sąsiednie otwarte drzwi są zespawane (weld) ─────────────────────

def test_adjacent_open_doors_welded(db):
    conn, db_path = db
    # Pula zmusza odnogi blisko ścieżki głównej; zaślepki domykają resztę.
    for i in range(4):
        _add_tile(conn, f"T{i+1}", ["N", "S", "E", "W"])
    _add_caps(conn)
    _add_tile(conn, "Boss", ["N", "S", "E", "W"], is_boss=True)
    dts = _patch_db(db_path)

    pos_to_nid = {}
    for _ in range(15):
        graph = dts.draw_tile_graph("test_cat", tile_count=5, max_retries=40)
        nodes = graph["nodes"]
        pos_to_nid = {tuple(n["position"]): nid for nid, n in nodes.items()}
        # Dla każdego węzła: jeśli sąsiad istnieje na polu w kierunku drzwi,
        # drzwi NIE mogą wskazywać None (musi być zespawane).
        offset = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
        for nid, node in nodes.items():
            px, py = node["position"]
            for d, tgt in (node["doors_open"] or {}).items():
                dx, dy = offset[d]
                nbr_pos = (px + dx, py + dy)
                nbr_nid = pos_to_nid.get(nbr_pos)
                if nbr_nid is None:
                    continue
                nbr = nodes[nbr_nid]
                # sąsiad ma przeciwległe drzwi → MUSI być połączony (weld)
                if OPPOSITE[d] in (nbr["doors_open"] or {}):
                    assert tgt == nbr_nid, (
                        f"Niezespawane sąsiednie drzwi: {nid}→{d}→{tgt} "
                        f"(sąsiad {nbr_nid} ma {OPPOSITE[d]})"
                    )


# ─── Test 6 (backward compat): podstawowa struktura grafu nienaruszona ───────

def test_graph_structure_still_valid(db):
    conn, db_path = db
    _add_tile(conn, "T1", ["N", "E"])
    _add_tile(conn, "T2", ["W", "S"])
    _add_caps(conn)
    _add_tile(conn, "Boss", ["N"], is_boss=True)
    dts = _patch_db(db_path)

    graph = dts.draw_tile_graph("test_cat", tile_count=3, max_retries=30)
    assert {"nodes", "entry_node", "boss_node"} <= set(graph.keys())
    REQUIRED = {"tile_id", "position", "doors_open", "door_hints", "content", "visited", "cleared"}
    for nid, node in graph["nodes"].items():
        assert not (REQUIRED - set(node.keys())), f"Węzeł {nid} brakuje kluczy"
    boss_node = graph["nodes"][graph["boss_node"]]
    assert boss_node.get("is_boss") is True
