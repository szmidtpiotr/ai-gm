"""TDD: Issue #671 (L2) — Generator rozgałęzionego grafu + dungeon_run v2.

Weryfikuje:
- Graf ma entry_node i boss_node
- Spójność drzwi (A→B w kierunku X, B musi mieć drzwi w OPPOSITE[X])
- Brak kolizji pozycji w grafie
- Boss-kafelek na końcu głównej ścieżki (is_boss=True)
- Odnogi: max MAX_BRANCHES, każda max MAX_BRANCH_LENGTH kafelków
- Powtórki nie sąsiadują ze sobą (constraint Decyzja 9)
- Door hints: niepuste stringi dla połączonych drzwi
- Mała pula — fallback do krótszej ścieżki bez wyjątku
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

CREATE TABLE session_flags (
    campaign_id INTEGER PRIMARY KEY,
    flags_json TEXT NOT NULL DEFAULT '{}'
);
"""


@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test_l2.db"
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


# ─── Helper: sprawdź spójność grafu ──────────────────────────────────────────

def _assert_graph_consistent(graph):
    """Każde przejście (A→dir→B) musi mieć symetryczne (B→opp→A)."""
    nodes = graph["nodes"]
    opposite = {"N": "S", "S": "N", "E": "W", "W": "E"}

    for nid, node in nodes.items():
        for direction, target_nid in (node["doors_open"] or {}).items():
            if target_nid is None:
                continue
            assert target_nid in nodes, f"Node {nid} door {direction} → missing {target_nid}"
            target = nodes[target_nid]
            opp = opposite[direction]
            reverse = (target["doors_open"] or {}).get(opp)
            assert reverse == nid, (
                f"Broken door: {nid}→{direction}→{target_nid}, "
                f"but {target_nid}→{opp}→{reverse} (expected {nid})"
            )


def _all_positions(graph):
    return [tuple(n["position"]) for n in graph["nodes"].values()]


# ─── Test 1: draw_tile_graph istnieje i zwraca poprawną strukturę ─────────────

def test_draw_tile_graph_returns_valid_structure(db):
    conn, db_path = db
    _add_tile(conn, "T1", ["N", "S", "E"])
    _add_tile(conn, "T2", ["N", "S", "W"])
    _add_tile(conn, "T3", ["N", "S"])
    _add_tile(conn, "Boss", ["N"], is_boss=True)
    dts = _patch_db(db_path)

    graph = dts.draw_tile_graph("test_cat", tile_count=4)

    assert "nodes" in graph, "brak klucza 'nodes'"
    assert "entry_node" in graph, "brak klucza 'entry_node'"
    assert "boss_node" in graph, "brak klucza 'boss_node'"
    assert graph["entry_node"] in graph["nodes"], "entry_node nie istnieje w nodes"
    assert graph["boss_node"] in graph["nodes"], "boss_node nie istnieje w nodes"


# ─── Test 2: spójność drzwi (symetryczne połączenia) ─────────────────────────

def test_graph_door_consistency(db):
    conn, db_path = db
    for i, doors in enumerate([["N","E"], ["W","S"], ["N","S","E"], ["E","W"]]):
        _add_tile(conn, f"T{i+1}", doors)
    _add_tile(conn, "Boss", ["N","S","E","W"], is_boss=True)
    dts = _patch_db(db_path)

    for _ in range(10):
        graph = dts.draw_tile_graph("test_cat", tile_count=4, max_retries=30)
        _assert_graph_consistent(graph)


# ─── Test 3: brak kolizji pozycji ────────────────────────────────────────────

def test_graph_no_position_collisions(db):
    conn, db_path = db
    for i, doors in enumerate([["N","E"], ["W","S"], ["N","S","E"], ["E","W","N"], ["N","E","W"]]):
        _add_tile(conn, f"T{i+1}", doors)
    _add_tile(conn, "Boss", ["N","S","E","W"], is_boss=True)
    dts = _patch_db(db_path)

    graph = dts.draw_tile_graph("test_cat", tile_count=4, max_retries=50)
    positions = _all_positions(graph)
    assert len(set(positions)) == len(positions), f"Kolizja pozycji: {positions}"


# ─── Test 4: boss-kafelek na boss_node ───────────────────────────────────────

def test_boss_tile_at_boss_node(db):
    conn, db_path = db
    _add_tile(conn, "T1", ["N", "E"])
    _add_tile(conn, "T2", ["W", "S"])
    _add_tile(conn, "Boss", ["N"], is_boss=True)
    dts = _patch_db(db_path)

    graph = dts.draw_tile_graph("test_cat", tile_count=3)
    boss_node = graph["nodes"][graph["boss_node"]]
    assert boss_node.get("is_boss") is True, "boss_node nie ma is_boss=True"


# ─── Test 5: odnogi w granicach (MAX_BRANCHES, MAX_BRANCH_LENGTH) ────────────

def test_branches_within_limits(db):
    conn, db_path = db
    # Dużo kafelków z wieloma drzwiami → wiele możliwości odnóg
    for i in range(8):
        _add_tile(conn, f"T{i+1}", ["N", "S", "E", "W"])
    _add_tile(conn, "Boss", ["N", "S", "E", "W"], is_boss=True)
    dts = _patch_db(db_path)

    graph = dts.draw_tile_graph("test_cat", tile_count=4, max_retries=50)
    nodes = graph["nodes"]

    # Zlicz węzły gałęzi (branch_*)
    branch_nodes = [nid for nid in nodes if nid.startswith("branch_")]
    # Policz ile unikalnych indeksów gałęzi
    branch_indices = set()
    for nid in branch_nodes:
        parts = nid.split("_")
        if len(parts) >= 2:
            branch_indices.add(parts[1])

    assert len(branch_indices) <= dts.MAX_BRANCHES, (
        f"Za dużo gałęzi: {len(branch_indices)} > {dts.MAX_BRANCHES}"
    )

    # Każda gałąź max MAX_BRANCH_LENGTH węzłów
    for bi in branch_indices:
        branch_count = sum(1 for nid in branch_nodes if nid.startswith(f"branch_{bi}_"))
        assert branch_count <= dts.MAX_BRANCH_LENGTH, (
            f"Gałąź {bi} za długa: {branch_count} > {dts.MAX_BRANCH_LENGTH}"
        )


# ─── Test 6: powtórki nie sąsiadują ──────────────────────────────────────────

def test_repeated_tiles_not_adjacent(db):
    conn, db_path = db
    # Mała pula — MUSIMY powtarzać kafelki
    t1_id = _add_tile(conn, "T1", ["N", "S", "E", "W"])
    _add_tile(conn, "Boss", ["N", "S", "E", "W"], is_boss=True)
    dts = _patch_db(db_path)

    # tile_count=5, ale tylko 1 zwykły kafelek → musi się powtarzać
    # Testujemy że przy wielokrotnym użyciu tego samego kafelka nie sąsiadują
    graph = dts.draw_tile_graph("test_cat", tile_count=5, max_retries=50)
    nodes = graph["nodes"]
    opposite = {"N": "S", "S": "N", "E": "W", "W": "E"}

    for nid, node in nodes.items():
        for direction, target_nid in (node["doors_open"] or {}).items():
            if target_nid is None:
                continue
            target = nodes[target_nid]
            assert node["tile_id"] != target["tile_id"], (
                f"Ten sam kafelek sąsiaduje ze sobą: {nid} → {target_nid} (tile_id={node['tile_id']})"
            )


# ─── Test 7: door hints jako niepuste stringi dla połączonych drzwi ──────────

def test_door_hints_present_for_connected_doors(db):
    conn, db_path = db
    _add_tile(conn, "T1", ["N", "S"])
    _add_tile(conn, "T2", ["N", "S"])
    _add_tile(conn, "Boss", ["N"], is_boss=True)
    dts = _patch_db(db_path)

    graph = dts.draw_tile_graph("test_cat", tile_count=3, max_retries=30)
    nodes = graph["nodes"]

    for nid, node in nodes.items():
        hints = node.get("door_hints") or {}
        doors_open = node.get("doors_open") or {}
        for direction, target_nid in doors_open.items():
            if target_nid is not None:
                hint = hints.get(direction)
                assert hint and isinstance(hint, str) and len(hint) > 0, (
                    f"Brak hint dla {nid}→{direction}→{target_nid}: {hint!r}"
                )


# ─── Test 8: mała pula — fallback bez wyjątku ────────────────────────────────

def test_small_pool_no_crash(db):
    conn, db_path = db
    _add_tile(conn, "T1", ["N", "S"])
    _add_tile(conn, "Boss", ["N"], is_boss=True)
    dts = _patch_db(db_path)

    # tile_count=6, ale tylko 1 zwykły kafelek — powinien skrócić lub powtórzyć
    graph = dts.draw_tile_graph("test_cat", tile_count=6, max_retries=50)
    assert "nodes" in graph
    assert len(graph["nodes"]) >= 2  # co najmniej entry + boss


# ─── Test 9: boss_tile_id override ───────────────────────────────────────────

def test_specific_boss_tile_id_override(db):
    conn, db_path = db
    _add_tile(conn, "T1", ["N", "S"])
    _add_tile(conn, "T2", ["N", "S"])  # 2nd non-boss tile so tile_count=3 is reachable
    _add_tile(conn, "Boss1", ["N"], is_boss=True)
    boss2_id = _add_tile(conn, "Boss2", ["N", "E"], is_boss=True)
    dts = _patch_db(db_path)

    graph = dts.draw_tile_graph("test_cat", tile_count=3, boss_tile_id=boss2_id, max_retries=30)
    boss_node = graph["nodes"][graph["boss_node"]]
    assert boss_node["tile_id"] == boss2_id, f"Oczekiwano boss tile_id={boss2_id}, got {boss_node['tile_id']}"


# ─── Test 10: każdy węzeł ma wymagane klucze ─────────────────────────────────

def test_node_has_required_keys(db):
    conn, db_path = db
    _add_tile(conn, "T1", ["N", "S"])
    _add_tile(conn, "T2", ["N", "S"])
    _add_tile(conn, "Boss", ["N"], is_boss=True)
    dts = _patch_db(db_path)

    graph = dts.draw_tile_graph("test_cat", tile_count=3)
    REQUIRED = {"tile_id", "position", "doors_open", "door_hints", "content", "visited", "cleared"}
    for nid, node in graph["nodes"].items():
        missing = REQUIRED - set(node.keys())
        assert not missing, f"Węzeł {nid} brakuje kluczy: {missing}"


# ─── Test 11: draw_tile_sequence nadal działa (backward compat) ──────────────

def test_draw_tile_sequence_still_works(db):
    conn, db_path = db
    _add_tile(conn, "T1", ["N", "E"])
    _add_tile(conn, "T2", ["W", "S"])
    _add_tile(conn, "Boss", ["N"], is_boss=True)
    dts = _patch_db(db_path)

    seq = dts.draw_tile_sequence("test_cat", 3)
    assert len(seq) == 3
    assert seq[-1].get("is_boss") is True
