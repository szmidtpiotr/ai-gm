"""TDD: Issue #992 — Anchor desync blocks hex-travel.

Root causes tested:
1. deactivate_temporary_location_on_hex sets location_key=NULL instead of restoring parent.
2. Sessions retain stale temp_camp current_location_key after deactivation.
3. game_locations.world_hex_q/r is NULL for canonical locations (Wolanka etc.) — blocks
   local hex map (issue #993) and location_context_injector distance calc.
4. Cross-hex named-destination routing: when target location is on a DIFFERENT hex than
   the player's current_hex, route to hex-travel, NOT sub-location create.
"""
import sys
import json
import sqlite3

sys.path.insert(0, "/app")

# ── Minimal schema (matches production columns needed by the tested functions) ──

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
CREATE TABLE IF NOT EXISTS game_sessions (
    id TEXT PRIMARY KEY,
    campaign_id INTEGER,
    current_location_id INTEGER,
    session_flags TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS hex_teleport_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_q INTEGER NOT NULL, from_r INTEGER NOT NULL,
    to_q INTEGER NOT NULL, to_r INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_bidirectional INTEGER NOT NULL DEFAULT 1,
    travel_hours REAL DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS hex_type_config (
    hex_type TEXT PRIMARY KEY,
    travel_hours REAL NOT NULL DEFAULT 8.0,
    encounter_chance REAL NOT NULL DEFAULT 0.15,
    is_active INTEGER NOT NULL DEFAULT 1
);
"""


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO hex_type_config VALUES ('plains', 8.0, 0.15, 1)")
    conn.commit()
    return conn


# ── Helpers ────────────────────────────────────────────────────────────────────

def _insert_hex(conn, q, r, location_key=None, hex_type="plains", map_level=0):
    conn.execute(
        "INSERT INTO world_hexes (q,r,hex_type,location_key,is_active,map_level)"
        " VALUES (?,?,?,?,1,?)",
        (q, r, hex_type, location_key, map_level),
    )
    conn.commit()


def _insert_location(conn, key, label, **kwargs):
    defaults = dict(
        temporary=0, canonical=1, is_active=1, safe_for_rest=0,
        parent_key=None, location_type="macro", source_campaign_id=None,
        world_hex_q=None, world_hex_r=None,
    )
    defaults.update(kwargs)
    conn.execute(
        """INSERT INTO game_locations
           (key, label, temporary, canonical, is_active, safe_for_rest,
            parent_key, location_type, source_campaign_id, world_hex_q, world_hex_r)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            key, label,
            defaults["temporary"], defaults["canonical"], defaults["is_active"],
            defaults["safe_for_rest"], defaults["parent_key"],
            defaults["location_type"], defaults["source_campaign_id"],
            defaults["world_hex_q"], defaults["world_hex_r"],
        ),
    )
    conn.commit()


def _hex_location_key(conn, q, r):
    row = conn.execute(
        "SELECT location_key FROM world_hexes WHERE q=? AND r=? AND is_active=1", (q, r)
    ).fetchone()
    return row["location_key"] if row else None


# ══════════════════════════════════════════════════════════════════════════════
# Bug 1 — deactivate restores canonical location_key (not NULL)
# ══════════════════════════════════════════════════════════════════════════════

def test_deactivate_temp_camp_restores_parent_location_key():
    """After deactivating a temp_camp, world_hexes.location_key should revert to
    parent_key (e.g. 'brzezino'), NOT NULL.

    Before fix: deactivate_temporary_location_on_hex sets location_key=NULL.
    After fix:  it restores the parent location that was on the hex before the camp.
    """
    conn = _make_conn()

    # canonical settlement at hex (1, 0)
    _insert_hex(conn, 1, 0, location_key="brzezino")
    _insert_location(conn, "brzezino", "Brzezino", canonical=1, safe_for_rest=0)

    # Simulate build_camp: temp_camp replaces canonical key in world_hexes
    camp_key = "temp_camp_99791_1111"
    _insert_location(
        conn, camp_key, "Obozowisko",
        temporary=1, canonical=0, is_active=1, safe_for_rest=1,
        parent_key="brzezino",
    )
    conn.execute(
        "UPDATE world_hexes SET location_key=? WHERE q=1 AND r=0", (camp_key,)
    )
    conn.commit()

    assert _hex_location_key(conn, 1, 0) == camp_key, "Setup: camp key must be active on hex"

    from app.services.world_service import deactivate_temporary_location_on_hex
    result = deactivate_temporary_location_on_hex(conn, 1, 0)

    assert result is not None, "Expected deactivation to return location info"
    restored = _hex_location_key(conn, 1, 0)
    assert restored == "brzezino", (
        f"Expected world_hexes.location_key='brzezino' after deactivation, got {restored!r}"
    )


def test_deactivate_temp_camp_updates_stale_sessions():
    """Sessions that reference the deactivated temp_camp key in session_flags should
    have current_location_key updated to the parent key.

    Before fix: sessions keep stale temp_camp key forever → LLM gets wrong location context.
    After fix:  current_location_key in session_flags switches to parent_key.
    """
    conn = _make_conn()
    _insert_hex(conn, 1, 0, location_key="brzezino")
    _insert_location(conn, "brzezino", "Brzezino", canonical=1)

    camp_key = "temp_camp_99791_2222"
    _insert_location(conn, camp_key, "Obozowisko", temporary=1, canonical=0,
                     is_active=1, parent_key="brzezino")
    conn.execute("UPDATE world_hexes SET location_key=? WHERE q=1 AND r=0", (camp_key,))

    # Session anchored at temp_camp
    flags = json.dumps({"current_hex": {"q": 1, "r": 0}, "current_location_key": camp_key})
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES ('sess1', 99, ?)",
        (flags,)
    )
    conn.commit()

    from app.services.world_service import deactivate_temporary_location_on_hex
    deactivate_temporary_location_on_hex(conn, 1, 0)

    updated = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE id='sess1'"
    ).fetchone()
    sf = json.loads(updated["session_flags"])
    assert sf.get("current_location_key") == "brzezino", (
        f"Expected session current_location_key='brzezino', got {sf.get('current_location_key')!r}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Bug 2 — world_hex_q/r sync for canonical locations
# ══════════════════════════════════════════════════════════════════════════════

def test_sync_location_hex_coordinates_fills_null_world_hex_qr():
    """Locations that have a world_hexes entry (via location_key) but NULL world_hex_q/r
    should get those coordinates stamped by the sync utility.

    This is the Wolanka scenario: world_hexes (21,1) points to 'wolanka' but
    game_locations.wolanka.world_hex_q = NULL.
    """
    conn = _make_conn()
    _insert_hex(conn, 21, 1, location_key="wolanka")
    _insert_location(conn, "wolanka", "Wolanka", canonical=1, world_hex_q=None, world_hex_r=None)

    from app.services.world_service import sync_location_hex_coordinates
    synced = sync_location_hex_coordinates(conn)

    row = conn.execute(
        "SELECT world_hex_q, world_hex_r FROM game_locations WHERE key='wolanka'"
    ).fetchone()
    assert row["world_hex_q"] == 21, f"Expected world_hex_q=21, got {row['world_hex_q']}"
    assert row["world_hex_r"] == 1, f"Expected world_hex_r=1, got {row['world_hex_r']}"
    assert synced >= 1, "sync_location_hex_coordinates should report ≥1 updated row"


def test_sync_location_hex_coordinates_skips_already_stamped():
    """Locations already having world_hex_q/r should NOT be overwritten."""
    conn = _make_conn()
    _insert_hex(conn, 5, 3, location_key="strazyn")
    _insert_location(conn, "strazyn", "Strażyn", canonical=1, world_hex_q=5, world_hex_r=3)

    from app.services.world_service import sync_location_hex_coordinates
    sync_location_hex_coordinates(conn)

    row = conn.execute(
        "SELECT world_hex_q, world_hex_r FROM game_locations WHERE key='strazyn'"
    ).fetchone()
    assert row["world_hex_q"] == 5
    assert row["world_hex_r"] == 3


# ══════════════════════════════════════════════════════════════════════════════
# Bug 3 — resolve_location_key_to_hex fallback via world_hex_q/r
# ══════════════════════════════════════════════════════════════════════════════

def test_resolve_location_key_to_hex_via_world_hex_qr_fallback():
    """When world_hexes has NO entry with location_key='wolanka' (because temp_camp
    displaced it), resolve_location_key_to_hex should fall back to
    game_locations.world_hex_q/r if set.

    Before fix: returns None → from_hex can't be determined → hex-travel fails.
    After fix:  returns (21, 1) from game_locations.world_hex_q/r.
    """
    conn = _make_conn()
    # world_hexes does NOT have location_key='wolanka' (temp_camp displaced it)
    _insert_hex(conn, 21, 1, location_key="temp_camp_99791_9999")
    _insert_location(conn, "wolanka", "Wolanka", canonical=1, world_hex_q=21, world_hex_r=1)

    from app.services.hex_travel_service import resolve_location_key_to_hex
    result = resolve_location_key_to_hex("wolanka", conn)

    assert result == (21, 1), (
        f"Expected (21, 1) via world_hex_q/r fallback, got {result!r}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Bug 4 — cross-hex named destination → hex-travel, not sub-location create
# ══════════════════════════════════════════════════════════════════════════════

def test_resolve_named_destination_cross_hex_detected():
    """When the player wants to go to a named location that is on a DIFFERENT hex than
    their current_hex, detect_named_destination_hex should return the target (q,r).

    Scenario: player is at hex (21,1)='wolanka', wants to go to 'strazyn' at hex (33,6).
    """
    conn = _make_conn()
    _insert_hex(conn, 21, 1, location_key="wolanka")
    _insert_hex(conn, 33, 6, location_key="strazyn")
    _insert_location(conn, "wolanka", "Wolanka", canonical=1, world_hex_q=21, world_hex_r=1)
    _insert_location(conn, "strazyn", "Strażyn", canonical=1, world_hex_q=33, world_hex_r=6)

    from app.services.hex_travel_service import detect_named_destination_hex
    result = detect_named_destination_hex(
        target_location_key="strazyn",
        current_hex={"q": 21, "r": 1},
        conn=conn,
    )

    assert result is not None, "Expected cross-hex destination to be detected"
    assert result == (33, 6), f"Expected target hex (33,6), got {result!r}"


def test_resolve_named_destination_same_hex_returns_none():
    """When the target location is on the SAME hex as the player, detect_named_destination_hex
    should return None (intra-hex move, not a hex-travel trigger).
    """
    conn = _make_conn()
    _insert_hex(conn, 21, 1, location_key="wolanka")
    _insert_location(conn, "wolanka", "Wolanka", canonical=1, world_hex_q=21, world_hex_r=1)
    # Sub-location inside wolanka, same hex
    _insert_location(conn, "wolanka_szynk", "Szynk Górniczy",
                     canonical=1, parent_key="wolanka", world_hex_q=21, world_hex_r=1,
                     location_type="sub")

    from app.services.hex_travel_service import detect_named_destination_hex
    result = detect_named_destination_hex(
        target_location_key="wolanka_szynk",
        current_hex={"q": 21, "r": 1},
        conn=conn,
    )

    assert result is None, "Expected None for intra-hex movement"


def test_resolve_named_destination_via_parent_key():
    """Sub-location inherits hex from parent. 'brzezino_tartak' (parent='brzezino' at hex 39,9)
    should resolve to (39,9) when current_hex is (21,1).
    """
    conn = _make_conn()
    _insert_hex(conn, 21, 1, location_key="wolanka")
    _insert_hex(conn, 39, 9, location_key="brzezino")
    _insert_location(conn, "wolanka", "Wolanka", canonical=1, world_hex_q=21, world_hex_r=1)
    _insert_location(conn, "brzezino", "Brzezino", canonical=1, world_hex_q=39, world_hex_r=9)
    # Sub-location of brzezino — does NOT have its own world_hex_q/r
    _insert_location(conn, "brzezino_tartak", "Tartak Starego Jerzego",
                     canonical=1, parent_key="brzezino", location_type="sub")

    from app.services.hex_travel_service import detect_named_destination_hex
    result = detect_named_destination_hex(
        target_location_key="brzezino_tartak",
        current_hex={"q": 21, "r": 1},
        conn=conn,
    )

    assert result == (39, 9), (
        f"Expected tartak's parent hex (39,9), got {result!r}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Backward compatibility
# ══════════════════════════════════════════════════════════════════════════════

def test_deactivate_no_temp_returns_none():
    """deactivate_temporary_location_on_hex on a hex with NO temp location → None."""
    conn = _make_conn()
    _insert_hex(conn, 5, 5, location_key="strazyn")
    _insert_location(conn, "strazyn", "Strażyn", temporary=0, canonical=1)

    from app.services.world_service import deactivate_temporary_location_on_hex
    result = deactivate_temporary_location_on_hex(conn, 5, 5)
    assert result is None, "Should return None when no temporary location on hex"
    # Canonical location_key must not be touched
    assert _hex_location_key(conn, 5, 5) == "strazyn"


def test_resolve_location_key_to_hex_primary_path_unchanged():
    """resolve_location_key_to_hex must still work via world_hexes.location_key (primary path)."""
    conn = _make_conn()
    _insert_hex(conn, 39, 9, location_key="brzezino")
    _insert_location(conn, "brzezino", "Brzezino", canonical=1)

    from app.services.hex_travel_service import resolve_location_key_to_hex
    result = resolve_location_key_to_hex("brzezino", conn)
    assert result == (39, 9), f"Primary path broken: expected (39,9), got {result!r}"


def test_detect_named_destination_unknown_location_returns_none():
    """detect_named_destination_hex for an unknown location_key → None (graceful)."""
    conn = _make_conn()
    _insert_hex(conn, 21, 1, location_key="wolanka")

    from app.services.hex_travel_service import detect_named_destination_hex
    result = detect_named_destination_hex(
        target_location_key="nieznana_lokacja",
        current_hex={"q": 21, "r": 1},
        conn=conn,
    )
    assert result is None
