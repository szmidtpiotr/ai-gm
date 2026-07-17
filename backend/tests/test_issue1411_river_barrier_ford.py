"""TDD: Issue #1411 — rzeka to bariera; przeprawa tylko przez most/bród.

Model A: `river.is_passable=0` → rzeki wypadają z grafu podróży (jak woda). Nowy typ
`brod` (is_passable=1) = przechodnia przeprawa (wolniejsza, groźniejsza niż most).
Pathfinding sam prowadzi brzegiem do najbliższej przeprawy (emergentny Model B).
"""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.services.hex_travel_service import _load_hex_graph, find_path


def _conn(hexes_data, type_config):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE world_regions (key TEXT PRIMARY KEY, status TEXT DEFAULT 'live', label TEXT);
        INSERT INTO world_regions VALUES ('kresy', 'live', 'Kresy');
        CREATE TABLE hex_type_config (
            hex_type TEXT PRIMARY KEY, is_passable INTEGER DEFAULT 1, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE world_hexes (
            q INTEGER, r INTEGER, hex_type TEXT DEFAULT 'plains',
            label TEXT, encounter_chance REAL DEFAULT 0.15, encounter_pool TEXT DEFAULT '[]',
            location_key TEXT, region TEXT DEFAULT 'kresy', is_active INTEGER DEFAULT 1,
            map_level INTEGER DEFAULT 0
        );
        CREATE TABLE hex_teleport_connections (
            from_q INTEGER, from_r INTEGER, to_q INTEGER, to_r INTEGER,
            travel_hours REAL DEFAULT 8.0, is_active INTEGER DEFAULT 1,
            is_bidirectional INTEGER DEFAULT 1, requires_item_key TEXT
        );
    """)
    for htype, passable in type_config.items():
        conn.execute("INSERT INTO hex_type_config (hex_type, is_passable) VALUES (?, ?)",
                     (htype, 1 if passable else 0))
    for (q, r, htype) in hexes_data:
        conn.execute("INSERT INTO world_hexes (q, r, hex_type) VALUES (?, ?, ?)", (q, r, htype))
    conn.commit()
    return conn


# ─── 1. graf: rzeka poza grafem, bród w grafie ───────────────────────────────

def test_river_excluded_ford_included():
    """river (is_passable=0) NIE wchodzi do grafu; brod (is_passable=1) wchodzi."""
    conn = _conn(
        hexes_data=[(0, 0, "plains"), (1, 0, "river"), (2, 0, "brod"), (3, 0, "plains")],
        type_config={"plains": True, "river": False, "brod": True},
    )
    hexes = _load_hex_graph(conn)
    conn.close()
    assert (0, 0) in hexes and (3, 0) in hexes
    assert (1, 0) not in hexes, "rzeka musi być poza grafem (bariera)"
    assert (2, 0) in hexes, "bród musi być w grafie (przeprawa)"


# ─── 2. routing: rzeka blokuje, bród przeprawia ──────────────────────────────

def test_ford_bridges_two_banks():
    """Ląd — BRÓD — ląd: trasa przechodzi PRZEZ bród. Sam hex rzeki nie łączy brzegów."""
    # (0,0) ląd — (1,0) BRÓD — (2,0) ląd
    hexes = {
        (0, 0): {"hex_type": "plains", "teleport_edges": [], "encounter_pool": [], "encounter_chance": 0.0},
        (1, 0): {"hex_type": "brod", "teleport_edges": [], "encounter_pool": [], "encounter_chance": 0.0},
        (2, 0): {"hex_type": "plains", "teleport_edges": [], "encounter_pool": [], "encounter_chance": 0.0},
    }
    path = find_path((0, 0), (2, 0), hexes)
    assert path == [(0, 0), (1, 0), (2, 0)], "przeprawa przez bród łączy brzegi"


def test_river_hex_absent_blocks_direct_cross():
    """Gdy rzeka odfiltrowana (brak w grafie) i brak przeprawy — brzegi rozłączone."""
    # (0,0) ląd i (2,0) ląd; (1,0) rzeka odfiltrowana → brak połączenia w tej osi
    hexes = {
        (0, 0): {"hex_type": "plains", "teleport_edges": [], "encounter_pool": [], "encounter_chance": 0.0},
        (2, 0): {"hex_type": "plains", "teleport_edges": [], "encounter_pool": [], "encounter_chance": 0.0},
    }
    path = find_path((0, 0), (2, 0), hexes)
    assert path is None, "bez mostu/brodu brzegi rozłączone"


# ─── 3. integracja na DEV DB (po migracji) ───────────────────────────────────

def test_dev_db_river_impassable_and_ford_exists():
    """Po migracji #1411: river.is_passable=0; typ 'brod' istnieje, passable, wolniejszy."""
    if not os.path.exists("/data/ai_gm.db"):
        pytest.skip("Brak DEV DB — skip integracyjny")
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    river = conn.execute("SELECT is_passable FROM hex_type_config WHERE hex_type='river'").fetchone()
    brod = conn.execute(
        "SELECT is_passable, travel_hours, label FROM hex_type_config WHERE hex_type='brod'"
    ).fetchone()
    conn.close()
    assert river is not None and river["is_passable"] == 0, "river musi być nieprzechodnia"
    assert brod is not None, "typ 'brod' musi istnieć w hex_type_config"
    assert brod["is_passable"] == 1, "bród musi być przechodni"
    assert brod["travel_hours"] == 1.5, "bród wolniejszy niż zwykły teren (startowo 1.5h)"
    assert brod["label"] == "Bród"


def test_dev_db_river_hexes_left_graph():
    """Sanity: w DEV DB są hexy river i po migracji nie ma ich w grafie podróży."""
    if not os.path.exists("/data/ai_gm.db"):
        pytest.skip("Brak DEV DB — skip integracyjny")
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    n_river = conn.execute(
        "SELECT COUNT(*) c FROM world_hexes WHERE map_level=0 AND is_active=1 AND hex_type='river'"
    ).fetchone()["c"]
    hexes = _load_hex_graph(conn)
    conn.close()
    if n_river == 0:
        pytest.skip("Brak hexów river w DEV DB")
    river_in_graph = [k for k, v in hexes.items() if v.get("hex_type") == "river"]
    assert not river_in_graph, f"żaden hex river nie może być w grafie, jest {len(river_in_graph)}"
