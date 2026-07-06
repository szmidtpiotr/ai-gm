"""TDD: Issue #1247 (R7) — trzy drobne przecieki ruchu.

1. Ruch narracyjny do lokacji **macro** musi kasować pending travel_plan
   (gałąź sub już to robiła; macro tylko czyściła local_hex).
2. Sublokacja w hubie z <2 sublokacjami → brak mapy lokalnej; sesja nie może
   zostać ze stalym local_hex z poprzedniej osady.
3. resolve_chain_travel NULL-uje location_key przed re-placementem — gdy
   placement zawiedzie, poprzedni location_key musi zostać przywrócony
   (inaczej "przybycie donikąd": hex i sesja bez lokacji).
"""
import sys
import json
import sqlite3
from unittest.mock import patch

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
    world_hex_r INTEGER,
    ai_generated INTEGER NOT NULL DEFAULT 0
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
    id INTEGER PRIMARY KEY,
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
CREATE TABLE IF NOT EXISTS active_combat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER UNIQUE,
    character_id INTEGER,
    status TEXT DEFAULT 'active',
    ended_reason TEXT
);
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER,
    sheet_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS campaign_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER,
    turn_number INTEGER DEFAULT 0
);
"""


def _mkconn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


# ── Leak #1: narrative move to macro clears travel_plan ───────────────────────

def test_narrative_move_to_macro_clears_travel_plan():
    """Ruch narracyjny do lokacji macro kasuje wiszący travel_plan."""
    from app.api.turns import _sync_local_hex_narrative_move

    conn = _mkconn()
    # Macro destination
    conn.execute(
        "INSERT INTO game_locations (id, key, label, location_type, is_active)"
        " VALUES (7, 'vilnograd', 'Vilnograd', 'macro', 1)"
    )
    # Session has both a stale local_hex AND a pending travel_plan
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, current_location_id, session_flags)"
        " VALUES (1, 1, 7, ?)",
        (json.dumps({
            "current_hex": {"q": 5, "r": 5},
            "local_hex": {"hex_id": 99, "q": 0, "r": 0},
            "travel_plan": {"destination_hex": {"q": 9, "r": 9}, "interrupt_reason": "encounter"},
        }),),
    )
    conn.commit()

    _sync_local_hex_narrative_move(conn, session_id=1, campaign_id=1, resolved_location_id=7)

    flags = json.loads(
        conn.execute("SELECT session_flags FROM game_sessions WHERE id=1").fetchone()[0]
    )
    assert "travel_plan" not in flags, f"travel_plan powinien zniknąć, mam: {flags}"
    assert "local_hex" not in flags, "macro branch powinna też wyczyścić local_hex"


# ── Leak #2: sub-location without local map clears stale local_hex ────────────

def test_sub_without_local_map_clears_stale_local_hex():
    """Sub w hubie z 1 sublok. → brak mapy; stary local_hex musi być wyczyszczony."""
    from app.api.turns import _sync_local_hex_narrative_move

    conn = _mkconn()
    # Hub + exactly ONE sub-loc (below LOCAL_MAP_THRESHOLD=2) → no local map
    conn.execute(
        "INSERT INTO game_locations (id, key, label, location_type, parent_key, is_active)"
        " VALUES (10, 'mizel_hub', 'Mizel', 'macro', NULL, 1)"
    )
    conn.execute(
        "INSERT INTO game_locations (id, key, label, location_type, parent_key, is_active)"
        " VALUES (11, 'mizel_karczma', 'Karczma', 'sub', 'mizel_hub', 1)"
    )
    # Session still points local_hex at a PREVIOUS settlement's hex
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, current_location_id, session_flags)"
        " VALUES (1, 1, 11, ?)",
        (json.dumps({
            "current_hex": {"q": 5, "r": 5},
            "local_hex": {"hex_id": 42, "q": 1, "r": 0, "location_key": "stara_osada_rynek"},
        }),),
    )
    conn.commit()

    _sync_local_hex_narrative_move(conn, session_id=1, campaign_id=1, resolved_location_id=11)

    flags = json.loads(
        conn.execute("SELECT session_flags FROM game_sessions WHERE id=1").fetchone()[0]
    )
    assert "local_hex" not in flags, (
        f"stary local_hex musi zniknąć gdy sub nie ma mapy lokalnej, mam: {flags}"
    )


# ── Leak #3: placement failure restores previous location_key (no strand) ─────

def test_placement_failure_restores_previous_location_key():
    """Gdy re-placement na hexie z ai_generated lokacją zawiedzie → poprzedni
    location_key przywrócony; ani hex ani sesja nie zostają bez lokacji."""
    from app.services.hex_travel_service import resolve_chain_travel

    conn = _mkconn()
    conn.execute("INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (1, 1, ?)",
                 (json.dumps({"current_hex": {"q": 3, "r": 0}}),))
    # Path (3,0) → (4,0); arrived hex carries an ai_generated legacy location
    for q, r, loc_key in [(3, 0, None), (4, 0, "ai_ruiny")]:
        conn.execute(
            "INSERT INTO world_hexes (q, r, hex_type, encounter_chance, encounter_pool,"
            " location_key, is_active, map_level) VALUES (?, ?, 'plains', 0.0, '[]', ?, 1, 0)",
            (q, r, loc_key),
        )
    conn.execute(
        "INSERT INTO game_locations (id, key, label, location_type, is_active, ai_generated,"
        " world_hex_q, world_hex_r) VALUES (5, 'ai_ruiny', 'Ruiny', 'macro', 1, 1, 4, 0)"
    )
    conn.commit()

    # Force the replacement placement to fail
    with patch("app.services.placement_engine.try_place_location_on_hex", return_value=None):
        result = resolve_chain_travel(
            campaign_id=1, character_id=None,
            from_hex=(3, 0), to_hex=(4, 0),
            character_sheet={}, conn=conn,
        )

    assert result.get("arrived_hex") == {"q": 4, "r": 0}

    # Hex must NOT be left with a NULL location_key
    hex_key = conn.execute(
        "SELECT location_key FROM world_hexes WHERE q=4 AND r=0 AND is_active=1"
    ).fetchone()["location_key"]
    assert hex_key == "ai_ruiny", f"location_key powinien być przywrócony, mam: {hex_key}"

    # Session must NOT be stranded without a current_location_id
    flags = json.loads(
        conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0]
    )
    cur = conn.execute(
        "SELECT current_location_id FROM game_sessions WHERE campaign_id=1"
    ).fetchone()["current_location_id"]
    assert cur == 5, f"sesja nie może zostać bez lokacji (przybycie donikąd), current_location_id={cur}, flags={flags}"
