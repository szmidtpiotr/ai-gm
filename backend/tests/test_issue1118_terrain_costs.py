"""TDD: Issue #1118 — PT8: A* używa travel_hours z hex_type_config (koszty terenu)."""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.services.hex_travel_service import _load_hex_graph, find_path


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_hexes(*items):
    """Build hexes dict from (q, r, hex_type) tuples."""
    return {
        (q, r): {
            "hex_type": htype,
            "teleport_edges": [],
            "encounter_pool": [],
            "encounter_chance": 0.0,
        }
        for q, r, htype in items
    }


def _make_test_conn(hexes_data, type_config):
    """In-memory SQLite with minimal schema for _load_hex_graph tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE world_regions (key TEXT PRIMARY KEY, status TEXT DEFAULT 'live', label TEXT);
        INSERT INTO world_regions VALUES ('kresy', 'live', 'Kresy');

        CREATE TABLE hex_type_config (
            hex_type TEXT PRIMARY KEY,
            is_passable INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            travel_hours REAL DEFAULT 1.0,
            encounter_base_chance REAL DEFAULT 0.15,
            label TEXT DEFAULT '',
            map_color TEXT DEFAULT '#4a6a4a',
            map_icon TEXT,
            spawn_weight INTEGER DEFAULT 0,
            has_submap INTEGER DEFAULT 0,
            placement_mode TEXT,
            location_spawn_chance REAL DEFAULT 0.15,
            required_item TEXT
        );

        CREATE TABLE world_hexes (
            q INTEGER, r INTEGER, hex_type TEXT DEFAULT 'plains',
            label TEXT, encounter_chance REAL DEFAULT 0.15,
            encounter_pool TEXT DEFAULT '[]',
            location_key TEXT, region TEXT DEFAULT 'kresy',
            is_active INTEGER DEFAULT 1, map_level INTEGER DEFAULT 0
        );

        CREATE TABLE hex_teleport_connections (
            from_q INTEGER, from_r INTEGER, to_q INTEGER, to_r INTEGER,
            travel_hours REAL DEFAULT 8.0, is_active INTEGER DEFAULT 1,
            is_bidirectional INTEGER DEFAULT 1, requires_item_key TEXT
        );
    """)
    for hextype, passable in type_config.items():
        conn.execute(
            "INSERT INTO hex_type_config (hex_type, is_passable) VALUES (?, ?)",
            (hextype, 1 if passable else 0),
        )
    for (q, r, htype) in hexes_data:
        conn.execute(
            "INSERT INTO world_hexes (q, r, hex_type) VALUES (?, ?, ?)",
            (q, r, htype),
        )
    conn.commit()
    return conn


# ─── Test 1: A* z wagami terenu ──────────────────────────────────────────────

def test_astar_prefers_road_over_mountains():
    """A* z hex_type_cfg wybiera trasę przez drogę (0.5h/hex) zamiast bezpośredniej przez góry (3.0h/hex).

    Topologia (hex adjacency flat-top):
      Route A (krótka, góry): (0,0) → (1,0)[mountains 3.0] → (2,0)[plains 1.0] = 4.0h
      Route B (objazd, droga): (0,0) → (0,1)[road 0.5] → (1,1)[road 0.5] → (2,0)[plains 1.0] = 2.0h
    Bez wag terrain: A* bierze Route A (2 kroki vs 3 kroki).
    Z wagami: A* bierze Route B (2.0h < 4.0h).
    """
    hexes = _make_hexes(
        (0, 0, "plains"),
        (1, 0, "mountains"),  # bezpośrednia "krótka" trasa przez góry
        (0, 1, "road"),       # objazd drogą
        (1, 1, "road"),
        (2, 0, "plains"),     # cel
    )
    hex_type_cfg = {
        "plains":    {"travel_hours": 1.0},
        "road":      {"travel_hours": 0.5},
        "mountains": {"travel_hours": 3.0},
    }

    path = find_path((0, 0), (2, 0), hexes, hex_type_cfg)

    assert path is not None, "Ścieżka powinna istnieć"
    assert path[-1] == (2, 0), "Cel musi być ostatnim punktem ścieżki"
    assert (0, 1) in path, "Trasa powinna przejść przez drogę (0,1)"
    assert (1, 0) not in path, "Trasa NIE powinna przejść przez góry (1,0)"


# ─── Test 2: Backward compat ─────────────────────────────────────────────────

def test_astar_without_cfg_falls_back_to_unit_cost():
    """Backward compat: find_path(start, goal, hexes) bez hex_type_cfg działa jak dotąd (koszt 1.0)."""
    hexes = _make_hexes(
        (0, 0, "plains"),
        (1, 0, "mountains"),
        (2, 0, "plains"),
    )
    # bez cfg: każdy hex = 1.0, bezpośrednia trasa (2 kroki)
    path = find_path((0, 0), (2, 0), hexes)  # brak hex_type_cfg

    assert path is not None, "Ścieżka powinna istnieć"
    assert path == [(0, 0), (1, 0), (2, 0)], "Bez wag: bezpośrednia 2-hexowa trasa"


# ─── Test 3: is_passable filtruje hexe z grafu ───────────────────────────────

def test_load_hex_graph_excludes_impassable_hexes():
    """_load_hex_graph nie wczytuje hexów których typ ma is_passable=0 (woda, morze)."""
    conn = _make_test_conn(
        hexes_data=[(0, 0, "plains"), (1, 0, "water"), (2, 0, "plains")],
        type_config={"plains": True, "water": False},
    )
    hexes = _load_hex_graph(conn)
    conn.close()

    assert (0, 0) in hexes, "Plains (is_passable=1) musi być w grafie"
    assert (2, 0) in hexes, "Plains (is_passable=1) musi być w grafie"
    assert (1, 0) not in hexes, "Water (is_passable=0) NIE może być w grafie"


def test_path_blocked_by_impassable_water():
    """Trasa zablokowana przez wodę (is_passable=0) → find_path zwraca None."""
    # Tylko droga przez wodę — brak objazdów
    hexes = _make_hexes(
        (0, 0, "plains"),
        (2, 0, "plains"),
        # hex (1,0) celowo POMINIĘTY — jak gdyby odfiltrowany przez is_passable=0
    )
    path = find_path((0, 0), (2, 0), hexes)
    assert path is None, "Brak ścieżki gdy jedyna droga jest nieprzejezdna"


# ─── Test 4: integracyjny — wartości w DEV DB po migracji ────────────────────

def test_terrain_cost_defaults_in_dev_db():
    """Wartości travel_hours w hex_type_config po migracji PT8 (integracyjny — wymaga DEV DB)."""
    if not os.path.exists("/data/ai_gm.db"):
        pytest.skip("Brak DEV DB — skip integracyjny")

    import sqlite3 as _sq
    from app.services.hex_travel_service import _load_hex_type_config

    conn = _sq.connect("/data/ai_gm.db")
    conn.row_factory = _sq.Row
    cfg = _load_hex_type_config(conn)
    conn.close()

    assert cfg.get("road", {}).get("travel_hours") == 0.5, "Droga: 0.5h/hex"
    assert cfg.get("plains", {}).get("travel_hours") == 1.0, "Równina: 1.0h/hex"
    assert cfg.get("forest", {}).get("travel_hours") == 2.0, "Las: 2.0h/hex"
    assert cfg.get("hills", {}).get("travel_hours") == 2.0, "Wzgórza: 2.0h/hex"
    assert cfg.get("mountains", {}).get("travel_hours") == 3.0, "Góry: 3.0h/hex"
    assert cfg.get("swamp", {}).get("travel_hours") == 4.0, "Bagno: 4.0h/hex"
