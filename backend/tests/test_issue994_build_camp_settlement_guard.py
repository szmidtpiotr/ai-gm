"""TDD: Issue #994 — build_camp guard too narrow — creates temp_camp inside settlement when sub-location
has safe_for_rest=0 but settlement tree contains safe_for_rest=1 elsewhere."""
import sys
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
    encounter_chance REAL NOT NULL DEFAULT 0.15,
    encounter_pool TEXT NOT NULL DEFAULT '[]',
    location_key TEXT,
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
    safe_for_rest INTEGER NOT NULL DEFAULT 0,
    temporary INTEGER NOT NULL DEFAULT 0,
    canonical INTEGER NOT NULL DEFAULT 0,
    review_status TEXT NOT NULL DEFAULT 'permanent',
    created_by TEXT DEFAULT 'admin_manual',
    source_campaign_id INTEGER,
    location_subtype TEXT,
    biome TEXT,
    tier INTEGER NOT NULL DEFAULT 1,
    usage_count INTEGER NOT NULL DEFAULT 0,
    world_hex_q INTEGER,
    world_hex_r INTEGER,
    ai_generated INTEGER DEFAULT 0,
    placement TEXT NOT NULL DEFAULT 'floating',
    updated_at TEXT DEFAULT (datetime('now'))
);
"""


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def seed_settlement_with_inn(conn):
    """Settlement macro (safe_for_rest=0) + tartak sub (safe_for_rest=0) + inn sub (safe_for_rest=1).
    Hex points to tartak — the buggy scenario."""
    conn.execute(
        "INSERT INTO game_locations (key, label, location_type, safe_for_rest, is_active) "
        "VALUES ('test_osada', 'Testowa Osada', 'macro', 0, 1)"
    )
    conn.execute(
        "INSERT INTO game_locations (key, label, location_type, parent_key, safe_for_rest, is_active) "
        "VALUES ('test_osada_tartak', 'Tartak', 'sub', 'test_osada', 0, 1)"
    )
    conn.execute(
        "INSERT INTO game_locations (key, label, location_type, parent_key, safe_for_rest, is_active) "
        "VALUES ('test_osada_karczma', 'Karczma Pod Dębem', 'sub', 'test_osada', 1, 1)"
    )
    # Hex points to tartak (safe_for_rest=0), not the macro
    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type, location_key, is_active) VALUES (99, 1, 'city', 'test_osada_tartak', 1)"
    )
    conn.commit()


def seed_wilderness_hex(conn):
    """Wild hex with no settlement tree — camp should be allowed."""
    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type, location_key, is_active) VALUES (99, 2, 'forest', NULL, 1)"
    )
    conn.commit()


def seed_safe_macro_hex(conn):
    """Macro location itself is safe_for_rest=1 — existing guard covers this."""
    conn.execute(
        "INSERT INTO game_locations (key, label, location_type, safe_for_rest, is_active) "
        "VALUES ('test_bezpieczna', 'Bezpieczna Wioska', 'macro', 1, 1)"
    )
    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type, location_key, is_active) VALUES (99, 3, 'city', 'test_bezpieczna', 1)"
    )
    conn.commit()


def seed_settlement_no_inn(conn):
    """Settlement with NO safe_for_rest sub-location — camp should be allowed."""
    conn.execute(
        "INSERT INTO game_locations (key, label, location_type, safe_for_rest, is_active) "
        "VALUES ('test_dzika_osada', 'Dzika Osada', 'macro', 0, 1)"
    )
    conn.execute(
        "INSERT INTO game_locations (key, label, location_type, parent_key, safe_for_rest, is_active) "
        "VALUES ('test_dzika_osada_stajnia', 'Stajnia', 'sub', 'test_dzika_osada', 0, 1)"
    )
    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type, location_key, is_active) VALUES (99, 4, 'city', 'test_dzika_osada_stajnia', 1)"
    )
    conn.commit()


# ── Test główny ───────────────────────────────────────────────────────────────

def test_build_camp_blocked_when_settlement_has_inn():
    """build_camp raises 'settlement_has_rest' when settlement tree has safe_for_rest=1 sub."""
    from app.services.world_service import build_camp

    conn = make_conn()
    seed_settlement_with_inn(conn)

    with pytest.raises(ValueError) as exc_info:
        build_camp(conn, campaign_id=1, q=99, r=1)

    msg = str(exc_info.value)
    assert msg.startswith("settlement_has_rest"), (
        f"Expected 'settlement_has_rest' error, got: {msg!r}"
    )


def test_build_camp_returns_suggested_rest_location():
    """settlement_has_rest error encodes suggested_key and suggested_label."""
    from app.services.world_service import build_camp

    conn = make_conn()
    seed_settlement_with_inn(conn)

    with pytest.raises(ValueError) as exc_info:
        build_camp(conn, campaign_id=1, q=99, r=1)

    msg = str(exc_info.value)
    parts = msg.split("|")
    assert len(parts) == 3, f"Expected 'settlement_has_rest|key|label', got: {msg!r}"
    assert parts[1] == "test_osada_karczma", f"Wrong suggested key: {parts[1]}"
    assert "Karczma" in parts[2], f"Wrong suggested label: {parts[2]}"


def test_build_camp_no_camp_created_when_settlement_has_inn():
    """No temp_camp location and no world_hexes update when guard fires."""
    from app.services.world_service import build_camp

    conn = make_conn()
    seed_settlement_with_inn(conn)

    try:
        build_camp(conn, campaign_id=1, q=99, r=1)
    except ValueError:
        pass

    # No temp_camp should exist
    camp = conn.execute(
        "SELECT key FROM game_locations WHERE key LIKE 'temp_camp_%'"
    ).fetchone()
    assert camp is None, f"temp_camp was created despite settlement guard: {camp['key']}"

    # world_hexes.location_key must still point to tartak, not overwritten
    hex_row = conn.execute(
        "SELECT location_key FROM world_hexes WHERE q=99 AND r=1"
    ).fetchone()
    assert hex_row["location_key"] == "test_osada_tartak", (
        f"location_key was overwritten: {hex_row['location_key']}"
    )


# ── Backward compatibility ────────────────────────────────────────────────────

def test_build_camp_allowed_on_wild_hex():
    """Wilderness hex (no location) still allows camp — backward compat."""
    from app.services.world_service import build_camp

    conn = make_conn()
    seed_wilderness_hex(conn)

    result = build_camp(conn, campaign_id=2, q=99, r=2)
    assert result["key"].startswith("temp_camp_")
    assert result["safe_for_rest"] == 1


def test_build_camp_still_blocks_safe_macro():
    """Existing hex_already_safe guard on macro still works — backward compat."""
    from app.services.world_service import build_camp

    conn = make_conn()
    seed_safe_macro_hex(conn)

    with pytest.raises(ValueError) as exc_info:
        build_camp(conn, campaign_id=3, q=99, r=3)

    assert str(exc_info.value) == "hex_already_safe"


def test_build_camp_allowed_when_no_inn_in_settlement():
    """Settlement with no safe_for_rest sub-location — camp allowed."""
    from app.services.world_service import build_camp

    conn = make_conn()
    seed_settlement_no_inn(conn)

    result = build_camp(conn, campaign_id=4, q=99, r=4)
    assert result["key"].startswith("temp_camp_")
