"""TDD: Issue #759 — Boss zawsze w najgłębszej komnacie.

Weryfikuje że _fill_open_doors nie tworzy skrótów do bossa przez weld.
BFS entry→boss musi zawsze wynosić >= tile_count-1 kroków (czyli gracz
nie może dotrzeć do bossa szybciej niż przez całą ścieżkę główną).
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


@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test_759.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO dungeon_tile_categories (key, label) VALUES ('test_cat', 'Test')")
    conn.commit()
    yield conn, str(db_file)
    conn.close()


def _add_tile(conn, label, doors, is_boss=False):
    cur = conn.execute(
        "INSERT INTO dungeon_tiles "
        "(category_key, label, doors_json, is_boss_tile) "
        "VALUES (?, ?, ?, ?)",
        ("test_cat", label, json.dumps(doors), 1 if is_boss else 0),
    )
    conn.commit()
    return cur.lastrowid


def _patch_db(db_path):
    from app.services import dungeon_tile_service as dts
    from app.services import dungeon_service as ds
    dts.DB_PATH = db_path
    ds.DB_PATH = db_path
    return dts


def _bfs_distance(nodes, start, goal):
    """BFS shortest path length from start to goal in the door graph."""
    if start == goal:
        return 0
    dist = {start: 0}
    queue = [start]
    while queue:
        cur = queue.pop(0)
        for tgt in nodes[cur]["doors_open"].values():
            if tgt is not None and tgt not in dist:
                dist[tgt] = dist[cur] + 1
                if tgt == goal:
                    return dist[tgt]
                queue.append(tgt)
    return None  # unreachable


def test_boss_not_reachable_via_shortcut(db):
    """BFS entry→boss must equal tile_count-1 for 20 random graphs.

    Uses a 4-door boss tile (N/S/E/W) to maximise the chance of welding.
    Without the fix, some graphs have boss_dist < tile_count-1.
    """
    conn, db_path = db
    # Regular tiles: mixed door counts to produce varied layouts
    _add_tile(conn, "T-NS",    ["N", "S"])
    _add_tile(conn, "T-EW",    ["E", "W"])
    _add_tile(conn, "T-NSE",   ["N", "S", "E"])
    _add_tile(conn, "T-NSW",   ["N", "S", "W"])
    _add_tile(conn, "T-NEW",   ["N", "E", "W"])
    _add_tile(conn, "T-SEW",   ["S", "E", "W"])
    _add_tile(conn, "T-NSEW",  ["N", "S", "E", "W"])
    # Boss with all 4 doors — maximum risk of accidental welds
    _add_tile(conn, "Boss",    ["N", "S", "E", "W"], is_boss=True)

    dts = _patch_db(db_path)

    TILE_COUNT = 5  # path: 4 regular + 1 boss → required depth = 4
    required_depth = TILE_COUNT - 1
    failures = []

    for i in range(20):
        graph = dts.draw_tile_graph("test_cat", tile_count=TILE_COUNT, max_retries=50)
        nodes = graph["nodes"]
        entry = graph["entry_node"]
        boss = graph["boss_node"]

        dist = _bfs_distance(nodes, entry, boss)
        assert dist is not None, f"Run {i}: boss nieosiągalny z entry"
        if dist < required_depth:
            failures.append(f"Run {i}: boss osiągalny w {dist} krokach (wymagane >= {required_depth})")

    assert not failures, "Boss osiągalny przez skrót:\n" + "\n".join(failures)


def test_boss_has_exactly_one_entry_door(db):
    """Boss node should have exactly one connected door (the path entry).

    All other boss doors should be either None (unclosable) or capped
    by a 1-door stub — never welded to a non-path node.
    """
    conn, db_path = db
    _add_tile(conn, "T-NS",   ["N", "S"])
    _add_tile(conn, "T-NSE",  ["N", "S", "E"])
    _add_tile(conn, "T-NSW",  ["N", "S", "W"])
    _add_tile(conn, "T-NSEW", ["N", "S", "E", "W"])
    _add_tile(conn, "Boss",   ["N", "S", "E", "W"], is_boss=True)

    dts = _patch_db(db_path)

    for i in range(15):
        graph = dts.draw_tile_graph("test_cat", tile_count=4, max_retries=50)
        nodes = graph["nodes"]
        boss_nid = graph["boss_node"]
        boss = nodes[boss_nid]

        # Count connections from boss to non-cap nodes
        connected_real = [
            tgt for tgt in boss["doors_open"].values()
            if tgt is not None and not tgt.startswith("fill_")
        ]
        assert len(connected_real) == 1, (
            f"Run {i}: boss ma {len(connected_real)} połączeń z nieboss węzłami "
            f"(oczekiwane 1): {connected_real}"
        )
