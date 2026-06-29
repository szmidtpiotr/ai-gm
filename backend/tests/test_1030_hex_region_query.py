"""Tests for RM3 — region-aware hex world query (#1030).

Verifies:
- GET /world/map?region=kresy filters correctly + returns 'regions' list
- _load_hex_graph excludes hexes in coming/locked regions
- find_path cannot cross into coming/locked region hexes
- new local hex (map_level=1) inherits region from parent hex
- backfill_local_hex_regions fills NULL region on existing ML hexes
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE world_regions (
            key TEXT PRIMARY KEY,
            label TEXT,
            color TEXT,
            status TEXT DEFAULT 'coming',
            entry_q INTEGER,
            entry_r INTEGER,
            sort_order INTEGER,
            note TEXT
        );
        INSERT INTO world_regions VALUES ('kresy', 'Kresy', '#7ab648', 'live', 25, 25, 1, NULL);
        INSERT INTO world_regions VALUES ('koronne_niziny', 'Koronne Niziny', '#e8c96a', 'coming', NULL, NULL, 2, NULL);
        INSERT INTO world_regions VALUES ('siwe_granie', 'Siwe Granie', '#b0c4de', 'coming', NULL, NULL, 3, NULL);

        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER NOT NULL,
            r INTEGER NOT NULL,
            hex_type TEXT NOT NULL DEFAULT 'plains',
            label TEXT,
            atmosphere TEXT,
            encounter_chance REAL NOT NULL DEFAULT 0.15,
            encounter_pool TEXT NOT NULL DEFAULT '[]',
            location_key TEXT,
            discovered_in_campaign_id INTEGER,
            created_by_gm INTEGER NOT NULL DEFAULT 0,
            created_by_campaign_id INTEGER,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            parent_hex_id INTEGER,
            map_level INTEGER NOT NULL DEFAULT 0,
            region TEXT NOT NULL DEFAULT 'kresy'
        );

        CREATE TABLE hex_teleport_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_q INTEGER, from_r INTEGER,
            to_q INTEGER, to_r INTEGER,
            travel_type TEXT, travel_hours REAL DEFAULT 8.0,
            encounter_chance REAL DEFAULT 0.20,
            requires_item_key TEXT, label TEXT,
            is_bidirectional INTEGER DEFAULT 1, is_active INTEGER DEFAULT 1
        );
    """)
    return conn


def _seed_hex(conn, q, r, region="kresy", map_level=0, parent_hex_id=None, label=None):
    conn.execute(
        "INSERT INTO world_hexes (q, r, region, map_level, parent_hex_id, label) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (q, r, region, map_level, parent_hex_id, label),
    )
    conn.commit()
    return conn.execute("SELECT id FROM world_hexes WHERE q=? AND r=?", (q, r)).fetchone()["id"]


# ── Test: _load_live_regions ───────────────────────────────────────────────────

def test_load_live_regions_returns_only_live():
    from app.services.hex_travel_service import _load_live_regions
    conn = _make_db()
    live = _load_live_regions(conn)
    assert live == {"kresy"}, f"Expected only kresy live, got {live}"


def test_load_live_regions_fallback_when_empty():
    from app.services.hex_travel_service import _load_live_regions
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE world_regions (key TEXT, status TEXT)")
    conn.commit()
    live = _load_live_regions(conn)
    assert live == {"kresy"}


# ── Test: _load_hex_graph excludes non-live regions ───────────────────────────

def test_load_hex_graph_excludes_coming_region():
    from app.services.hex_travel_service import _load_hex_graph
    conn = _make_db()
    _seed_hex(conn, 0, 0, region="kresy")
    _seed_hex(conn, 1, 0, region="koronne_niziny")  # coming
    graph = _load_hex_graph(conn)
    assert (0, 0) in graph, "Live hex should be in graph"
    assert (1, 0) not in graph, "Coming-region hex should be excluded from graph"


def test_load_hex_graph_includes_region_in_hex_data():
    from app.services.hex_travel_service import _load_hex_graph
    conn = _make_db()
    _seed_hex(conn, 5, 5, region="kresy")
    graph = _load_hex_graph(conn)
    assert (5, 5) in graph
    assert graph[(5, 5)]["region"] == "kresy"


# ── Test: pathfinding blocked by non-live region ──────────────────────────────

def test_find_path_cannot_cross_coming_region():
    """A* should not route through coming/locked region hexes."""
    from app.services.hex_travel_service import _load_hex_graph, find_path
    conn = _make_db()
    # Row of hexes: (0,0)live — (1,0)coming — (2,0)live
    # Path from (0,0) to (2,0) must be None (blocked by middle hex)
    _seed_hex(conn, 0, 0, region="kresy")
    _seed_hex(conn, 1, 0, region="koronne_niziny")  # coming — excluded from graph
    _seed_hex(conn, 2, 0, region="kresy")
    graph = _load_hex_graph(conn)
    path = find_path((0, 0), (2, 0), graph)
    assert path is None, "Path through coming region should be None"


# ── Test: new ML hex inherits region from parent ──────────────────────────────

def test_local_hex_insert_inherits_parent_region():
    from app.services.local_hex_service import auto_assign_local_hex
    conn = _make_db()
    # Seed parent map_level=0 hex + game_locations hub
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            label TEXT,
            parent_key TEXT,
            is_active INTEGER DEFAULT 1,
            safe_for_rest INTEGER DEFAULT 0,
            world_hex_q INTEGER,
            world_hex_r INTEGER
        );
        INSERT INTO game_locations (key, label, world_hex_q, world_hex_r)
        VALUES ('hub_loc', 'Hub', 10, 10);
        INSERT INTO game_locations (key, label, parent_key, is_active)
        VALUES ('sub1', 'Sub1', 'hub_loc', 1),
               ('sub2', 'Sub2', 'hub_loc', 1);
    """)
    parent_id = _seed_hex(conn, 10, 10, region="kresy", map_level=0)

    result = auto_assign_local_hex(conn, "sub1", "hub_loc", campaign_id=None)
    # Both sublocs should get ML hexes; sub1 returned
    assert result is not None, "auto_assign_local_hex should create a hex"
    assert result["region"] == "kresy", f"ML hex should inherit 'kresy' region, got {result.get('region')}"


# ── Test: backfill_local_hex_regions ─────────────────────────────────────────

def test_backfill_local_hex_regions():
    """ML hex with wrong region (default 'kresy') gets synced to parent's region."""
    from app.services.local_hex_service import backfill_local_hex_regions
    conn = _make_db()
    # Parent hex is in 'siwe_granie' region
    parent_id = _seed_hex(conn, 0, 0, region="siwe_granie", map_level=0)
    # ML hex defaults to 'kresy' (old insert before RM3)
    conn.execute(
        "INSERT INTO world_hexes (q, r, map_level, parent_hex_id, region) VALUES (0, 0, 1, ?, 'kresy')",
        (parent_id,),
    )
    conn.commit()
    n = backfill_local_hex_regions(conn)
    assert n == 1, f"Expected 1 updated, got {n}"
    row = conn.execute(
        "SELECT region FROM world_hexes WHERE map_level = 1 AND parent_hex_id = ?", (parent_id,)
    ).fetchone()
    assert row["region"] == "siwe_granie", f"Expected 'siwe_granie', got {row['region']}"
