"""TDD: Issue #1114 — PT4 Desync correction: active correction not just logging.

Before PT4: guard_travel_desync() logs 'travel_narrated_without_move' and returns True.
After PT4: also saves corrective [SYSTEM:...] fact to session_flags so next turn
narrator prompt is corrected. Tracks consecutive desync count — 2+ → stronger hint.
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
    is_active INTEGER NOT NULL DEFAULT 1,
    canonical INTEGER NOT NULL DEFAULT 0,
    world_hex_q INTEGER,
    world_hex_r INTEGER
);
CREATE TABLE IF NOT EXISTS game_sessions (
    id TEXT PRIMARY KEY,
    campaign_id INTEGER,
    current_location_id INTEGER,
    session_flags TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS llm_tag_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER,
    turn_number INTEGER,
    tag_raw TEXT,
    error_type TEXT,
    ts TEXT DEFAULT (datetime('now'))
);
"""

TRAVEL_NARRATIVE = (
    "Wyruszasz w drogę, przemierzając rozległe pola ku horyzontowi. "
    "Wędrujesz przez godzinę, zanim zatrzymujesz się na odpoczynek."
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    # Player at hex (2,3), named location nearby
    c.execute(
        "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES ('s1', 1, ?)",
        (json.dumps({
            "current_hex": {"q": 2, "r": 3},
            "current_location_key": "karczmisko",
        }),),
    )
    c.execute(
        "INSERT INTO game_locations (key, label, canonical, is_active, world_hex_q, world_hex_r)"
        " VALUES ('karczmisko', 'Karczmisko', 1, 1, 2, 3)"
    )
    # Neighbor hexes for stronger hint
    for nq, nr, label in [(3, 2, "Las Północny"), (3, 3, "Pole Wschodnie"), (2, 4, "Rzeka")]:
        c.execute(
            "INSERT INTO world_hexes (q, r, hex_type, label, is_active, map_level)"
            " VALUES (?, ?, 'plains', ?, 1, 0)",
            (nq, nr, label),
        )
    c.commit()
    return c


# ── RED tests: current behavior missing ──────────────────────────────────────

def test_desync_guard_saves_correction_to_session_flags(conn):
    """#1114 RED: guard_travel_desync saves corrective fact to session_flags when desync detected."""
    from app.services.turn_pipeline import guard_travel_desync

    result = guard_travel_desync(conn, 1, TRAVEL_NARRATIVE, move_executed=False, turn_number=1)

    assert result is True, "guard must return True on desync"

    flags = json.loads(
        conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0]
    )
    assert "travel_desync_correction" in flags, (
        "session_flags must contain 'travel_desync_correction' after desync — "
        f"got keys: {list(flags.keys())}"
    )
    correction = flags["travel_desync_correction"]
    assert "[SYSTEM:" in correction, f"Correction must be a [SYSTEM:...] fact, got: {correction!r}"
    assert "NIE" in correction or "stoi" in correction.lower() or "zmieniła" in correction, (
        f"Correction must state player did NOT move, got: {correction!r}"
    )


def test_pop_desync_correction_returns_and_clears(conn):
    """#1114 RED: pop_desync_correction returns the fact and clears it from session_flags."""
    from app.services.turn_pipeline import guard_travel_desync, pop_desync_correction

    guard_travel_desync(conn, 1, TRAVEL_NARRATIVE, move_executed=False, turn_number=1)
    conn.commit()

    correction = pop_desync_correction(conn, 1)

    assert correction is not None, "pop must return the correction string"
    assert "[SYSTEM:" in correction, f"Must be a [SYSTEM:...] fact, got: {correction!r}"

    # Verify it's cleared
    flags = json.loads(
        conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0]
    )
    assert "travel_desync_correction" not in flags, (
        "travel_desync_correction must be cleared after pop"
    )


def test_consecutive_desync_stronger_hint(conn):
    """#1114 RED: 2 consecutive desyncs → stronger hint includes neighbor list."""
    from app.services.turn_pipeline import guard_travel_desync, pop_desync_correction

    # First desync
    guard_travel_desync(conn, 1, TRAVEL_NARRATIVE, move_executed=False, turn_number=1)
    conn.commit()
    pop_desync_correction(conn, 1)
    conn.commit()

    # Second desync
    guard_travel_desync(conn, 1, TRAVEL_NARRATIVE, move_executed=False, turn_number=2)
    conn.commit()

    flags = json.loads(
        conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0]
    )
    assert flags.get("travel_desync_consecutive", 0) >= 2, (
        "consecutive counter must be ≥2 after two desyncs"
    )
    correction = flags.get("travel_desync_correction", "")
    # Stronger hint: should mention neighbor hexes
    assert any(label in correction for label in ["Las Północny", "Pole Wschodnie", "Rzeka"]), (
        f"2nd consecutive desync hint must include neighbor hexes, got: {correction!r}"
    )


# ── GREEN / backward-compat tests ────────────────────────────────────────────

def test_pop_returns_none_when_no_correction(conn):
    """#1114: pop_desync_correction returns None when no pending correction."""
    from app.services.turn_pipeline import pop_desync_correction

    result = pop_desync_correction(conn, 1)
    assert result is None, f"Expected None when no correction pending, got: {result!r}"


def test_clean_move_resets_consecutive_counter(conn):
    """#1114: successful move (move_executed=True) resets consecutive desync counter."""
    from app.services.turn_pipeline import guard_travel_desync

    # Simulate prior desync counter in session_flags
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = 1",
        (json.dumps({"current_hex": {"q": 2, "r": 3}, "travel_desync_consecutive": 3}),),
    )
    conn.commit()

    guard_travel_desync(conn, 1, TRAVEL_NARRATIVE, move_executed=True, turn_number=5)
    conn.commit()

    flags = json.loads(
        conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0]
    )
    assert flags.get("travel_desync_consecutive", 0) == 0, (
        f"Counter must be reset to 0 after successful move, got {flags.get('travel_desync_consecutive')}"
    )
    assert "travel_desync_correction" not in flags, (
        "No correction must be saved when move_executed=True"
    )


def test_no_travel_narrative_no_desync(conn):
    """#1114: guard returns False when narrative has no travel language."""
    from app.services.turn_pipeline import guard_travel_desync

    clean_narrative = "Bohater rozmawia z karczmarzem o lokalnych plotkach."
    result = guard_travel_desync(conn, 1, clean_narrative, move_executed=False, turn_number=1)

    assert result is False, "No travel markers → should not flag desync"
    flags = json.loads(
        conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0]
    )
    assert "travel_desync_correction" not in flags, (
        "No correction must be saved when narrative has no travel markers"
    )
