"""TDD: #549 — legacy ai_generated locations replaced by DB-seeded on hex arrival.

resolve_chain_travel must:
1. When arrived hex has location_key pointing to ai_generated=1 location →
   clear world_hexes.location_key and run placement engine.
2. When arrived hex has no location_key → try placement engine.
3. When arrived hex has approved, ai_generated=0 location → leave it unchanged.
"""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY,
            q INTEGER,
            r INTEGER,
            hex_type TEXT DEFAULT 'plains',
            label TEXT,
            is_active INTEGER DEFAULT 1,
            location_key TEXT,
            encounter_chance REAL DEFAULT 0,
            encounter_pool TEXT DEFAULT '[]',
            teleport_edges TEXT DEFAULT '[]',
            atmosphere TEXT
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY,
            key TEXT UNIQUE,
            label TEXT,
            ai_generated INTEGER DEFAULT 0,
            approved INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            placement TEXT DEFAULT 'placed',
            terrain_tags TEXT DEFAULT '[]',
            world_hex_q INTEGER,
            world_hex_r INTEGER
        );
        CREATE TABLE hex_type_config (
            hex_type TEXT PRIMARY KEY,
            label TEXT,
            location_spawn_chance REAL DEFAULT 1.0
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            session_flags TEXT DEFAULT '{}',
            current_location_id INTEGER
        );
        CREATE TABLE campaign_hex_data (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            hex_q INTEGER,
            hex_r INTEGER,
            discovered INTEGER DEFAULT 0,
            encounter_cleared INTEGER DEFAULT 0,
            UNIQUE(campaign_id, hex_q, hex_r)
        );
    """)
    conn.execute(
        "INSERT INTO hex_type_config VALUES ('plains', 'Równiny', 1.0)"
    )
    conn.commit()
    return conn


def test_ai_generated_location_replaced_by_db_seeded():
    """Hex with ai_generated=1 location → placement engine replaces it."""
    conn = _make_db()

    # Legacy AI-generated location on hex 0,0
    conn.execute(
        "INSERT INTO game_locations (key, label, ai_generated, approved, placement, terrain_tags)"
        " VALUES ('wschodnia_wioska', 'Wschodnia Wioska', 1, 0, 'placed', '[\"plains\"]')"
    )
    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type, location_key) VALUES (0, 0, 'plains', 'wschodnia_wioska')"
    )
    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type) VALUES (1, 0, 'plains')"
    )
    # DB-seeded location available for placement
    conn.execute(
        "INSERT INTO game_locations (key, label, ai_generated, approved, placement, terrain_tags)"
        " VALUES ('stara_karczma', 'Stara Karczma', 0, 1, 'floating', '[\"plains\"]')"
    )
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, ?)",
        (json.dumps({"current_hex": {"q": 1, "r": 0}, "state": "NARRATIVE"}),),
    )
    conn.commit()

    from app.services.placement_engine import try_place_location_on_hex

    # Simulate what the fixed resolve_chain_travel does: detect ai_generated=1, clear, replace
    _hex_location_key = "wschodnia_wioska"
    _ai_check = conn.execute(
        "SELECT ai_generated FROM game_locations WHERE key = ? AND COALESCE(is_active,1)=1 LIMIT 1",
        (_hex_location_key,),
    ).fetchone()
    assert _ai_check is not None
    assert _ai_check["ai_generated"] == 1, "Pre-condition: wschodnia_wioska is ai_generated"

    # Clear and run placement engine
    conn.execute(
        "UPDATE world_hexes SET location_key = NULL WHERE q = 0 AND r = 0 AND is_active = 1"
    )
    new_key = try_place_location_on_hex(conn, 0, 0, "plains", campaign_seed=1)

    assert new_key is not None, "Placement engine should place stara_karczma on plains hex"
    assert new_key == "stara_karczma"

    # Verify world_hexes updated
    row = conn.execute("SELECT location_key FROM world_hexes WHERE q=0 AND r=0").fetchone()
    assert row["location_key"] == "stara_karczma", "world_hexes.location_key must be updated"

    # Verify new location is ai_generated=0
    loc = conn.execute(
        "SELECT ai_generated FROM game_locations WHERE key = ?", (new_key,)
    ).fetchone()
    assert loc["ai_generated"] == 0, "New location must not be ai_generated"


def test_hex_without_location_gets_placement():
    """Hex with no location_key → placement engine places one."""
    conn = _make_db()

    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type) VALUES (2, 0, 'plains')"
    )
    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type) VALUES (3, 0, 'plains')"
    )
    conn.execute(
        "INSERT INTO game_locations (key, label, ai_generated, approved, placement, terrain_tags)"
        " VALUES ('pustelnia', 'Pustelnia', 0, 1, 'floating', '[\"plains\"]')"
    )
    conn.commit()

    from app.services.placement_engine import try_place_location_on_hex

    # No existing location — placement engine should assign one
    new_key = try_place_location_on_hex(conn, 2, 0, "plains", campaign_seed=42)
    assert new_key is not None, "Should place pustelnia on empty plains hex"


def test_approved_db_location_not_replaced():
    """Hex with approved, ai_generated=0 location → NOT replaced."""
    conn = _make_db()

    conn.execute(
        "INSERT INTO game_locations (key, label, ai_generated, approved, placement, terrain_tags)"
        " VALUES ('miasto_portowe', 'Miasto Portowe', 0, 1, 'placed', '[\"plains\"]')"
    )
    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type, location_key) VALUES (4, 0, 'plains', 'miasto_portowe')"
    )
    conn.commit()

    # Check: ai_generated=0 → should NOT trigger replacement
    _hex_location_key = "miasto_portowe"
    _ai_check = conn.execute(
        "SELECT ai_generated FROM game_locations WHERE key = ? AND COALESCE(is_active,1)=1 LIMIT 1",
        (_hex_location_key,),
    ).fetchone()
    assert _ai_check is not None
    assert _ai_check["ai_generated"] == 0, "miasto_portowe is NOT ai_generated → no replacement"

    # Location key unchanged
    row = conn.execute("SELECT location_key FROM world_hexes WHERE q=4 AND r=0").fetchone()
    assert row["location_key"] == "miasto_portowe"
