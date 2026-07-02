"""TDD: Issue #1115 — PT5 cleanup: dead import, (0,0) overlap, already-here clock, RANDOM fallback."""
import sqlite3
import sys
import os
import pytest

sys.path.insert(0, "/app")


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("""
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER NOT NULL, r INTEGER NOT NULL,
            hex_type TEXT DEFAULT 'settlement',
            label TEXT, location_key TEXT,
            map_level INTEGER DEFAULT 0,
            parent_hex_id INTEGER,
            encounter_chance REAL DEFAULT 0.0,
            created_by_gm INTEGER DEFAULT 0,
            created_by_campaign_id INTEGER,
            region TEXT DEFAULT 'kresy',
            is_active INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE, label TEXT,
            location_type TEXT DEFAULT 'macro',
            parent_key TEXT,
            world_hex_q INTEGER, world_hex_r INTEGER,
            safe_for_rest INTEGER DEFAULT 0,
            canonical INTEGER DEFAULT 0,
            map_icon TEXT,
            review_status TEXT DEFAULT 'permanent',
            is_active INTEGER DEFAULT 1,
            created_by TEXT DEFAULT 'seed'
        )
    """)
    conn.execute("""
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER UNIQUE,
            session_flags TEXT DEFAULT '{}'
        )
    """)
    conn.commit()
    return conn


# ── Fix 1: Dead import ────────────────────────────────────────────────────────

def test_dead_import_absent_in_turns():
    """_auto_generate_local_hexes import must not exist in turns.py — it's a ghost."""
    turns_path = "/app/app/api/turns.py"
    if not os.path.exists(turns_path):
        pytest.skip("turns.py not in container")
    content = open(turns_path).read()
    assert "_auto_generate_local_hexes" not in content, (
        "Dead import _auto_generate_local_hexes still present in turns.py — remove it"
    )


# ── Fix 2: (0,0) overlap ─────────────────────────────────────────────────────

def test_no_00_overlap_for_hub_without_world_hex():
    """Two sub-locs in a hub with no world hex must get DIFFERENT (q,r)."""
    from app.services.local_hex_service import auto_assign_local_hex, LOCAL_MAP_THRESHOLD

    conn = _make_conn()
    # Hub location (no world hex anchor)
    conn.execute(
        "INSERT INTO game_locations (key, label, location_type, parent_key, canonical, review_status) "
        "VALUES ('hub_test', 'Hub Test', 'macro', NULL, 1, 'permanent')"
    )
    # Add enough sub-locs to cross threshold
    for i in range(LOCAL_MAP_THRESHOLD + 1):
        conn.execute(
            "INSERT INTO game_locations (key, label, location_type, parent_key, safe_for_rest, review_status) "
            f"VALUES ('sub_{i}', 'Sub {i}', 'sub', 'hub_test', 1, 'permanent')"
        )
    conn.commit()

    # Assign hexes for first two sub-locs
    h1 = auto_assign_local_hex(conn, "sub_0", "hub_test")
    h2 = auto_assign_local_hex(conn, "sub_1", "hub_test")

    assert h1 is not None, "First sub-loc should get a hex"
    assert h2 is not None, "Second sub-loc should get a hex"
    assert (h1["q"], h1["r"]) != (h2["q"], h2["r"]), (
        f"Both sub-locs got same coords ({h1['q']},{h1['r']}) — (0,0) overlap bug still present"
    )


# ── Fix 3a: Already-here clock — narrative path ───────────────────────────────

def test_narrative_local_travel_skips_clock_when_already_here():
    """_sync_local_hex_narrative_move source must guard clock advance on same-hex."""
    source = open("/app/app/api/turns.py").read()
    # Find the _sync_local_hex_narrative_move function body
    func_start = source.find("def _sync_local_hex_narrative_move(")
    assert func_start != -1, "_sync_local_hex_narrative_move not found in turns.py"
    # Get the function body (up to next top-level def)
    func_body = source[func_start:func_start + 4000]
    # After fix: must compare current local_hex id with new lh["id"] before calling clock.
    # The guard looks like: current_hex_id = sf.get("local_hex", {}).get("hex_id")
    #                        if lh["id"] != current_hex_id:  <- guard
    #                            _adv_clock(...)
    assert "current_hex_id" in func_body, (
        "_sync_local_hex_narrative_move missing already-here guard — must read current "
        "local_hex hex_id into variable (e.g. current_hex_id) and skip clock when unchanged"
    )


# ── Fix 3b: Already-here clock — local-travel endpoint ───────────────────────

def test_local_travel_endpoint_skips_clock_when_same_hex():
    """POST /local-travel source must guard clock advance when hex_id unchanged."""
    source = open("/app/app/routers/local_map.py").read()
    # Find local_travel function body
    func_start = source.find("def local_travel(")
    assert func_start != -1, "local_travel not found in local_map.py"
    func_body = source[func_start:func_start + 3000]
    # After fix: must have a guard comparing body.hex_id with current local_hex hex_id
    # before calling advance_clock
    guard_present = (
        "current_hex_id" in func_body
        or ("hex_id" in func_body and (
            "body.hex_id ==" in func_body
            or "== body.hex_id" in func_body
            or "already" in func_body.lower()
        ))
    )
    assert guard_present, (
        "local_travel missing already-here guard — must skip clock when "
        "body.hex_id == current local_hex hex_id"
    )


# ── Fix 4: RANDOM fallback → deterministic ───────────────────────────────────

def test_s17_canonical_fallback_not_random():
    """S17 canonical location fallback must use ORDER BY id ASC, not RANDOM."""
    source = open("/app/app/services/hex_travel_service.py").read()
    lines = source.splitlines()
    # Find the fallback query (lines with both canonical=1 and is_active=1 and review_status)
    # within the s17 fallback block — check 15 lines BEFORE s17_canonical_location_fallback
    for i, line in enumerate(lines):
        if "s17_canonical_location_fallback" in line:
            # The ORDER BY RANDOM() is in the 15 lines BEFORE this log call
            snippet = "\n".join(lines[max(0, i-15):i+5])
            assert "RANDOM()" not in snippet, (
                f"s17_canonical_location_fallback block still uses ORDER BY RANDOM() "
                f"(around line {i+1}) — must be deterministic (ORDER BY id ASC)"
            )


# ── Fix 5: First move without position uses resolve_starting_hex ─────────────

def test_hex_world_local_travel_uses_resolve_starting_hex():
    """hex-travel endpoint must call resolve_starting_hex when no current_hex, not hardcode (0,0)."""
    source = open("/app/app/routers/hex_world.py").read()
    # After fix: the (0, 0) silent fallback must be replaced with resolve_starting_hex call
    # We check the endpoint no longer contains the bare (0, 0) fallback pattern
    # The old pattern: `from_hex = (0, 0) if origin_exists else ...`
    assert "from_hex = (0, 0)" not in source, (
        "hex_world.py still has silent (0,0) fallback — must use resolve_starting_hex"
    )
