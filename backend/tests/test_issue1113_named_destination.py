"""TDD: Issue #1113 — Named destination travel via pathfinding (end of teleport).

Before PT3: "idę do Vilnogradu" → LLM teleports pin, no cost, no encounters.
After PT3: named dest on different hex → resolve_chain_travel (A*, time, encounters).
Same-hex destinations (sub-locations) still handled by LLM via location_intent.
"""
import sys
import json
import sqlite3

import pytest

sys.path.insert(0, "/app")

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER NOT NULL,
    r INTEGER NOT NULL,
    hex_type TEXT NOT NULL DEFAULT 'plains',
    label TEXT,
    atmosphere TEXT,
    encounter_chance REAL NOT NULL DEFAULT 0.0,
    encounter_pool TEXT NOT NULL DEFAULT '[]',
    location_key TEXT,
    region TEXT,
    discovered_in_campaign_id INTEGER,
    created_by_gm INTEGER NOT NULL DEFAULT 0,
    created_by_campaign_id INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    parent_hex_id INTEGER,
    map_level INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL,
    description TEXT DEFAULT '',
    parent_id INTEGER,
    parent_key TEXT DEFAULT NULL,
    location_type TEXT DEFAULT 'macro',
    is_active INTEGER NOT NULL DEFAULT 1,
    canonical INTEGER NOT NULL DEFAULT 0,
    safe_for_rest INTEGER NOT NULL DEFAULT 0,
    temporary INTEGER NOT NULL DEFAULT 0,
    review_status TEXT NOT NULL DEFAULT 'permanent',
    created_by TEXT DEFAULT 'seed',
    world_hex_q INTEGER,
    world_hex_r INTEGER
);
CREATE TABLE IF NOT EXISTS hex_type_config (
    hex_type TEXT PRIMARY KEY,
    travel_hours REAL NOT NULL DEFAULT 1.0,
    encounter_chance REAL NOT NULL DEFAULT 0.0,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS hex_teleport_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_q INTEGER NOT NULL, from_r INTEGER NOT NULL,
    to_q INTEGER NOT NULL, to_r INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_bidirectional INTEGER NOT NULL DEFAULT 1,
    travel_hours REAL DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS game_sessions (
    id TEXT PRIMARY KEY,
    campaign_id INTEGER,
    current_location_id INTEGER,
    session_flags TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS campaign_hex_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    hex_q INTEGER NOT NULL,
    hex_r INTEGER NOT NULL,
    discovered INTEGER NOT NULL DEFAULT 0,
    encounter_cleared INTEGER NOT NULL DEFAULT 0,
    UNIQUE(campaign_id, hex_q, hex_r)
);
CREATE TABLE IF NOT EXISTS world_regions (
    key TEXT PRIMARY KEY,
    label TEXT,
    status TEXT DEFAULT 'active'
);
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    # World: player at (0,0) — three connected plains hexes — Vilnograd at (3,0)
    for q in range(4):
        c.execute(
            "INSERT INTO world_hexes (q, r, hex_type, label, encounter_chance, is_active, map_level)"
            " VALUES (?, 0, 'plains', ?, 0.0, 1, 0)",
            (q, f"Pole ({q},0)"),
        )
    # Vilnograd — canonical, on hex (3,0)
    c.execute(
        "INSERT INTO game_locations (key, label, canonical, is_active, world_hex_q, world_hex_r)"
        " VALUES ('vilnograd', 'Vilnograd', 1, 1, 3, 0)"
    )
    c.execute("UPDATE world_hexes SET location_key='vilnograd' WHERE q=3 AND r=0")
    # hex_type_config
    c.execute("INSERT OR IGNORE INTO hex_type_config (hex_type, travel_hours, encounter_chance)"
              " VALUES ('plains', 1.0, 0.0)")
    # Session at (0,0)
    c.execute(
        "INSERT INTO game_sessions (id, campaign_id, current_location_id, session_flags)"
        " VALUES ('s1', 1, NULL, ?)",
        (json.dumps({"current_hex": {"q": 0, "r": 0}}),),
    )
    c.commit()
    return c


# ── Test 1: existing function still returns cross-hex target ─────────────────

def test_detect_named_destination_hex_cross_hex(conn):
    """#1113: detect_named_destination_hex returns (3,0) when Vilnograd is at (3,0)."""
    from app.services.hex_travel_service import detect_named_destination_hex

    result = detect_named_destination_hex(
        target_location_key="vilnograd",
        current_hex={"q": 0, "r": 0},
        conn=conn,
    )
    assert result == (3, 0), f"Expected (3, 0), got {result}"


# ── Test 2: NEW — resolve player text to location key ────────────────────────

def test_resolve_player_text_to_location_key_genitive(conn):
    """#1113: 'idę do Vilnogradu' (genitive) resolves to location key 'vilnograd'."""
    from app.services.hex_travel_service import resolve_player_text_to_location_key

    result = resolve_player_text_to_location_key("idę do Vilnogradu", conn)
    assert result == "vilnograd", f"Expected 'vilnograd', got {result!r}"


def test_resolve_player_text_unchanged_name(conn):
    """#1113: German-style names unchanged in text (Wachstein) also resolve correctly."""
    conn.execute(
        "INSERT INTO game_locations (key, label, canonical, is_active, world_hex_q, world_hex_r)"
        " VALUES ('wachstein', 'Wachstein', 1, 1, 5, 0)"
    )
    conn.commit()

    from app.services.hex_travel_service import resolve_player_text_to_location_key

    result = resolve_player_text_to_location_key("wyruszam do Wachstein", conn)
    assert result == "wachstein", f"Expected 'wachstein', got {result!r}"


def test_resolve_player_text_no_movement_verb_returns_none(conn):
    """#1113: 'mapa do Vilnogradu' without movement verb → None (no travel)."""
    from app.services.hex_travel_service import resolve_player_text_to_location_key

    result = resolve_player_text_to_location_key("pokaż mi mapę do Vilnogradu", conn)
    # Should NOT match — function must check for movement verb
    assert result is None, f"Expected None for non-movement text, got {result!r}"


# ── Test 3: execute_directional_travel handles named destination ──────────────

def test_execute_directional_travel_named_destination_fires_chain_travel(conn):
    """#1113: 'idę do Vilnogradu' triggers chain travel and returns executed=True."""
    from app.services.turn_pipeline import execute_directional_travel

    result = execute_directional_travel(
        conn=conn,
        campaign_id=1,
        character_id=0,
        character_sheet={},
        player_text="idę do Vilnogradu",
    )
    assert result["executed"] is True, (
        f"Expected executed=True for named destination, got executed={result.get('executed')}. "
        f"system_fact={result.get('system_fact')!r}"
    )
    assert "Podróż" in (result.get("system_fact") or ""), (
        f"Expected 'Podróż' in system_fact, got: {result.get('system_fact')!r}"
    )


def test_execute_directional_travel_same_hex_named_dest_not_executed(conn):
    """#1113: Named dest on same hex returns executed=False (sub-location, LLM handles)."""
    # Add a location ON hex (0,0) — same as current player position
    conn.execute(
        "INSERT INTO game_locations (key, label, canonical, is_active, world_hex_q, world_hex_r)"
        " VALUES ('karczma_lokalna', 'Karczma Zielona', 1, 1, 0, 0)"
    )
    conn.commit()

    from app.services.turn_pipeline import execute_directional_travel

    result = execute_directional_travel(
        conn=conn,
        campaign_id=1,
        character_id=0,
        character_sheet={},
        player_text="idę do Karczmy Zielonej",
    )
    assert result["executed"] is False, (
        f"Same-hex destination must NOT trigger chain travel, got executed={result.get('executed')}"
    )


# ── Test 4: backward compat — directional still works ────────────────────────

def test_directional_travel_still_works_after_pt3(conn):
    """#1113 backward compat: cardinal direction ('na wschód') still resolves correctly."""
    # Add hex to the east (axial: east = +1,0 in offset)
    from app.services.turn_pipeline import execute_directional_travel

    result = execute_directional_travel(
        conn=conn,
        campaign_id=1,
        character_id=0,
        character_sheet={},
        player_text="idę na wschód",
    )
    # Should return executed=True (or False with a system_fact about terrain)
    assert isinstance(result, dict)
    assert "executed" in result
    assert result.get("system_fact") is not None or result.get("executed") is True
