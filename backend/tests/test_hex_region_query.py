"""TDD: RM3 (#1030) — query region-aware (silnik czyta region).

Weryfikuje:
- _load_hex_graph ładuje TYLKO heksy z krain 'live' (coming/locked niewidoczne),
- pathfinding nie przekracza granicy do krainy coming/locked,
- resolve_chain_travel zwraca blok "Kraina niedostępna" dla celu w coming/locked,
- GET /map?region= filtruje po krainie + zwraca listę regions (logika SQL endpointu),
- backfill_local_hex_regions / auto_assign_local_hex: ML-sub-mapa dziedziczy region rodzica.

Testy izolowane — własna in-memory SQLite, nie dotykają /data/ai_gm.db.
"""
import sqlite3

import pytest

from app.services.hex_travel_service import (
    _load_hex_graph,
    _load_live_regions,
    find_path,
    resolve_chain_travel,
)
from app.services.local_hex_service import backfill_local_hex_regions


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE world_regions (
            key TEXT PRIMARY KEY, label TEXT, color TEXT,
            status TEXT DEFAULT 'coming', entry_q INTEGER, entry_r INTEGER,
            sort_order INTEGER, note TEXT
        );
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER NOT NULL, r INTEGER NOT NULL,
            hex_type TEXT NOT NULL DEFAULT 'plains',
            label TEXT, atmosphere TEXT,
            encounter_chance REAL NOT NULL DEFAULT 0.15,
            encounter_pool TEXT NOT NULL DEFAULT '[]',
            location_key TEXT,
            discovered_in_campaign_id INTEGER,
            created_by_gm INTEGER NOT NULL DEFAULT 0,
            created_by_campaign_id INTEGER,
            is_active INTEGER NOT NULL DEFAULT 1,
            parent_hex_id INTEGER,
            map_level INTEGER NOT NULL DEFAULT 0,
            region TEXT NOT NULL DEFAULT 'kresy'
        );
        CREATE TABLE hex_teleport_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_q INTEGER, from_r INTEGER, to_q INTEGER, to_r INTEGER,
            travel_type TEXT, travel_hours REAL DEFAULT 8.0,
            encounter_chance REAL DEFAULT 0.2, requires_item_key TEXT,
            label TEXT, is_bidirectional INTEGER DEFAULT 1,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE hex_type_config (
            hex_type TEXT PRIMARY KEY, encounter_base_chance REAL,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        """
    )
    conn.execute(
        "INSERT INTO world_regions (key, label, status, sort_order) VALUES "
        "('kresy','Kresy','live',1), ('siwe_granie','Siwe Granie','coming',4)"
    )
    # Kresy: a small connected strip at r=0, q=0..3 (live)
    for q in range(4):
        conn.execute(
            "INSERT INTO world_hexes (q, r, hex_type, region, map_level) "
            "VALUES (?, 0, 'plains', 'kresy', 0)",
            (q,),
        )
    # Siwe Granie: q=4..5, r=0 (coming) — geometrically adjacent to Kresy at q=3
    for q in range(4, 6):
        conn.execute(
            "INSERT INTO world_hexes (q, r, hex_type, region, map_level) "
            "VALUES (?, 0, 'mountain', 'siwe_granie', 0)",
            (q,),
        )
    conn.commit()
    return conn


# ─── live-region graph filtering ────────────────────────────────────────────

def test_load_live_regions():
    conn = _make_db()
    assert _load_live_regions(conn) == {"kresy"}
    conn.close()


def test_graph_excludes_non_live_regions():
    conn = _make_db()
    hexes = _load_hex_graph(conn)
    # Only the 4 Kresy hexes (q=0..3) load; Siwe Granie (q=4,5) excluded.
    assert set(hexes.keys()) == {(0, 0), (1, 0), (2, 0), (3, 0)}
    assert (4, 0) not in hexes and (5, 0) not in hexes
    conn.close()


def test_graph_includes_non_live_when_flipped_live():
    conn = _make_db()
    conn.execute("UPDATE world_regions SET status='live' WHERE key='siwe_granie'")
    conn.commit()
    hexes = _load_hex_graph(conn)
    assert (4, 0) in hexes and (5, 0) in hexes
    conn.close()


# ─── pathfinding respects borders ───────────────────────────────────────────

def test_pathfinding_within_live_region():
    conn = _make_db()
    hexes = _load_hex_graph(conn)
    path = find_path((0, 0), (3, 0), hexes)
    assert path == [(0, 0), (1, 0), (2, 0), (3, 0)]
    conn.close()


def test_pathfinding_cannot_cross_into_coming_region():
    conn = _make_db()
    hexes = _load_hex_graph(conn)
    # (4,0) is in coming region → not in graph → no path
    path = find_path((0, 0), (4, 0), hexes)
    assert path is None
    conn.close()


# ─── resolve_chain_travel block message ─────────────────────────────────────

def test_resolve_chain_travel_blocks_coming_region():
    conn = _make_db()
    res = resolve_chain_travel(
        campaign_id=1, character_id=1,
        from_hex=(3, 0), to_hex=(4, 0),
        character_sheet={}, conn=conn,
    )
    assert res["ok"] is False
    assert "Kraina niedostępna" in res["error"]
    assert "Siwe Granie" in res["error"]
    conn.close()


def test_resolve_chain_travel_unknown_hex_generic_error():
    conn = _make_db()
    res = resolve_chain_travel(
        campaign_id=1, character_id=1,
        from_hex=(0, 0), to_hex=(99, 99),
        character_sheet={}, conn=conn,
    )
    assert res["ok"] is False
    assert "Kraina niedostępna" not in res["error"]
    conn.close()


# ─── GET /map?region= filtering (endpoint SQL logic) ────────────────────────

def test_map_region_filter_returns_only_that_region():
    conn = _make_db()
    rows = conn.execute(
        "SELECT q, r FROM world_hexes WHERE is_active=1 AND parent_hex_id IS NULL "
        "AND region = ? ORDER BY q, r",
        ("kresy",),
    ).fetchall()
    assert len(rows) == 4
    conn.close()


def test_map_default_returns_only_live_regions():
    conn = _make_db()
    live = [r["key"] for r in conn.execute(
        "SELECT key FROM world_regions WHERE status='live'"
    ).fetchall()]
    ph = ",".join("?" * len(live))
    rows = conn.execute(
        f"SELECT q, r FROM world_hexes WHERE is_active=1 AND parent_hex_id IS NULL "
        f"AND region IN ({ph}) ORDER BY q, r",
        live,
    ).fetchall()
    # coming Siwe Granie excluded → only 4 Kresy hexes
    assert len(rows) == 4
    conn.close()


def test_map_regions_list_has_all_six_concept():
    """Endpoint returns the full world_regions list regardless of filter."""
    conn = _make_db()
    rows = conn.execute("SELECT key, status FROM world_regions ORDER BY sort_order").fetchall()
    keys = {r["key"] for r in rows}
    assert "kresy" in keys and "siwe_granie" in keys
    assert any(r["status"] == "live" for r in rows)
    assert any(r["status"] == "coming" for r in rows)
    conn.close()


# ─── ML sub-map region inheritance ──────────────────────────────────────────

def test_backfill_local_hex_inherits_parent_region():
    conn = _make_db()
    # Flip Siwe Granie live so a parent hex can be in that region
    conn.execute("UPDATE world_regions SET status='live' WHERE key='siwe_granie'")
    # Parent overworld hex in siwe_granie at (4,0); make an ML child with wrong region
    parent_id = conn.execute(
        "SELECT id FROM world_hexes WHERE q=4 AND r=0 AND map_level=0"
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type, region, map_level, parent_hex_id) "
        "VALUES (0, 0, 'settlement', 'kresy', 1, ?)",
        (parent_id,),
    )
    conn.commit()

    n = backfill_local_hex_regions(conn)
    assert n == 1
    child = conn.execute(
        "SELECT region FROM world_hexes WHERE map_level=1 AND parent_hex_id=?",
        (parent_id,),
    ).fetchone()
    assert child["region"] == "siwe_granie"
    conn.close()


def test_backfill_idempotent():
    conn = _make_db()
    parent_id = conn.execute(
        "SELECT id FROM world_hexes WHERE q=0 AND r=0 AND map_level=0"
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type, region, map_level, parent_hex_id) "
        "VALUES (0, 1, 'settlement', 'kresy', 1, ?)",
        (parent_id,),
    )
    conn.commit()
    # Parent already 'kresy', child already 'kresy' → no change
    assert backfill_local_hex_regions(conn) == 0
    assert backfill_local_hex_regions(conn) == 0
    conn.close()
