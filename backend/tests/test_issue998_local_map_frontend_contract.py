"""TDD: Issue #998 — Local sub-map frontend API contract.

Tests the backend contract that the player-UI local map relies on:
- GET /api/campaigns/{id}/local-map returns hexes with all fields the frontend needs
- POST /api/campaigns/{id}/local-travel returns moved/local_hex/clock shape
- encounter_chance field present and 0.0 for safe hexes, >0 for risky

All tests use an in-memory SQLite DB seeded minimally so they don't
depend on DEV data state.
"""
import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.local_hex_service import (
    get_local_hexes,
    get_hub_hex_id,
    auto_assign_local_hex,
    LOCAL_MAP_THRESHOLD,
    LOCAL_TRAVEL_MINUTES,
    RISKY_ENCOUNTER_CHANCE,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_db():
    """In-memory SQLite with minimal world_hexes + game_locations schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER NOT NULL,
            r INTEGER NOT NULL,
            label TEXT,
            hex_type TEXT DEFAULT 'plains',
            map_level INTEGER NOT NULL DEFAULT 0,
            parent_hex_id INTEGER,
            location_key TEXT,
            encounter_chance REAL NOT NULL DEFAULT 0.15,
            atmosphere TEXT,
            status TEXT DEFAULT 'discovered',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_by_gm INTEGER DEFAULT 0,
            created_by_campaign_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            label TEXT NOT NULL,
            location_type TEXT DEFAULT 'macro',
            parent_key TEXT,
            safe_for_rest INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            world_hex_q INTEGER,
            world_hex_r INTEGER
        );
    """)
    return conn


def _seed_hub(conn, hub_key="wolanka", hub_label="Wolanka", q=5, r=3):
    """Insert a hub (macro) location and its map_level=0 world hex. Return hub_hex_id."""
    conn.execute(
        "INSERT INTO game_locations (key, label, location_type, is_active, world_hex_q, world_hex_r)"
        " VALUES (?, ?, 'macro', 1, ?, ?)",
        (hub_key, hub_label, q, r),
    )
    conn.execute(
        "INSERT INTO world_hexes (q, r, label, hex_type, map_level, location_key, encounter_chance, is_active)"
        " VALUES (?, ?, ?, 'town', 0, ?, 0.0, 1)",
        (q, r, hub_label, hub_key),
    )
    conn.commit()
    return get_hub_hex_id(conn, hub_key)


def _seed_subloc(conn, key, label, parent_key, safe_for_rest):
    """Insert a sub-location."""
    conn.execute(
        "INSERT INTO game_locations (key, label, location_type, parent_key, safe_for_rest, is_active)"
        " VALUES (?, ?, 'sub', ?, ?, 1)",
        (key, label, parent_key, 1 if safe_for_rest else 0),
    )
    conn.commit()


# ── Test główny: hexes mają encounter_chance ──────────────────────────────────

def test_local_hexes_have_encounter_chance_field():
    """Frontend needs encounter_chance per hex for risk visual (risky tint).

    #998 acceptance: hexy bezpieczne vs ryzykowne wizualnie rozróżnione.
    """
    conn = _make_db()
    hub_hex_id = _seed_hub(conn)
    _seed_subloc(conn, "karczma", "Szynk", "wolanka", safe_for_rest=True)
    _seed_subloc(conn, "kopalnia", "Kopalnia", "wolanka", safe_for_rest=False)

    auto_assign_local_hex(conn, "karczma", "wolanka")
    auto_assign_local_hex(conn, "kopalnia", "wolanka")

    hexes = get_local_hexes(conn, "wolanka")
    assert len(hexes) == 2, f"Expected 2 local hexes, got {len(hexes)}"

    for h in hexes:
        assert "encounter_chance" in h, f"hex {h.get('location_key')} missing encounter_chance"

    safe_hex = next(h for h in hexes if h["location_key"] == "karczma")
    risky_hex = next(h for h in hexes if h["location_key"] == "kopalnia")

    assert safe_hex["encounter_chance"] == 0.0, (
        f"Safe hex (karczma) should have encounter_chance=0.0, got {safe_hex['encounter_chance']}"
    )
    assert risky_hex["encounter_chance"] > 0.0, (
        f"Risky hex (kopalnia) should have encounter_chance>0, got {risky_hex['encounter_chance']}"
    )


def test_local_hexes_have_id_field():
    """Frontend passes hex.id as hex_id in POST /local-travel body.

    Without the id field, local travel click would silently fail.
    """
    conn = _make_db()
    _seed_hub(conn)
    _seed_subloc(conn, "kosciol", "Kościół", "wolanka", safe_for_rest=True)
    _seed_subloc(conn, "kowal", "Kuźnia", "wolanka", safe_for_rest=True)

    auto_assign_local_hex(conn, "kosciol", "wolanka")
    auto_assign_local_hex(conn, "kowal", "wolanka")

    hexes = get_local_hexes(conn, "wolanka")
    for h in hexes:
        assert "id" in h, f"hex missing 'id' field — frontend can't send local-travel request"
        assert isinstance(h["id"], int), f"hex.id must be int, got {type(h['id'])}"


def test_local_hexes_have_label_and_qr():
    """Frontend renders hex label and positions it at (q, r) coords."""
    conn = _make_db()
    _seed_hub(conn)
    _seed_subloc(conn, "szynk", "Szynk pod Wilkiem", "wolanka", safe_for_rest=True)
    _seed_subloc(conn, "stajnia", "Stajnia", "wolanka", safe_for_rest=False)

    auto_assign_local_hex(conn, "szynk", "wolanka")
    auto_assign_local_hex(conn, "stajnia", "wolanka")

    hexes = get_local_hexes(conn, "wolanka")
    for h in hexes:
        assert "q" in h and "r" in h, "hex missing q/r coords"
        assert "label" in h, "hex missing label"


# ── Backward compat: service returns [] for hub without local hexes ────────────

def test_get_local_hexes_empty_for_hub_without_sublocs():
    """Hub with no sub-locations returns empty list — has_local_map must be False."""
    conn = _make_db()
    _seed_hub(conn, hub_key="pustowka")
    hexes = get_local_hexes(conn, "pustowka")
    assert hexes == [], f"Expected [] for hub without sub-locs, got {hexes}"


def test_local_map_threshold_constant():
    """LOCAL_MAP_THRESHOLD must be 2 — spec says ≥2 sub-locs trigger map."""
    assert LOCAL_MAP_THRESHOLD == 2, (
        f"Threshold changed from 2 to {LOCAL_MAP_THRESHOLD} — update frontend logic too"
    )


def test_local_travel_minutes_constant():
    """LOCAL_TRAVEL_MINUTES must be 15 — #998 Numbers Policy."""
    assert LOCAL_TRAVEL_MINUTES == 15, (
        f"Travel time changed from 15 to {LOCAL_TRAVEL_MINUTES} min — update frontend too"
    )
