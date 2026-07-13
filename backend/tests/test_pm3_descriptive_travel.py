"""TDD: PM3 #1222 — descriptive travel to KNOWN hexes (deadlock #1050).

"szukam drogi do mostu" / "udaję się w stronę wioski" resolve a lowercase
common-noun destination against the campaign's known/discovered hexes (by label
AND Polish hex_type name) and travel there via the unified execute_travel path.

A named target the hero does NOT know → NO move, a "ask around" hint instead.
Regression: "idę do Vilnogradu" (canonical #1113) still works; "rozglądam się"
never triggers travel.
"""
import sys
import json
import sqlite3

import pytest

sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

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
    is_active INTEGER NOT NULL DEFAULT 1,
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
    ai_generated INTEGER NOT NULL DEFAULT 0,
    usage_count INTEGER NOT NULL DEFAULT 0,
    world_hex_q INTEGER,
    world_hex_r INTEGER
);
CREATE TABLE IF NOT EXISTS hex_type_config (
    hex_type TEXT PRIMARY KEY,
    label TEXT,
    travel_hours REAL NOT NULL DEFAULT 1.0,
    encounter_chance REAL NOT NULL DEFAULT 0.0,
    is_passable INTEGER NOT NULL DEFAULT 1,
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
    known INTEGER NOT NULL DEFAULT 0,
    encounter_cleared INTEGER NOT NULL DEFAULT 0,
    UNIQUE(campaign_id, hex_q, hex_r)
);
CREATE TABLE IF NOT EXISTS world_regions (
    key TEXT PRIMARY KEY,
    label TEXT,
    status TEXT DEFAULT 'live'
);
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER,
    sheet_json TEXT NOT NULL DEFAULT '{}'
);
""" + table_sql("game_config_meta") + """
"""


@pytest.fixture(autouse=True)
def _no_encounters(monkeypatch):
    # hex encounter_chance 0.0 becomes 0.15 via `or 0.15` in _roll_encounter, so
    # random encounters would interrupt travel non-deterministically. Force none.
    import app.services.hex_travel_service as _h
    monkeypatch.setattr(_h.random, "random", lambda: 1.0)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    c.execute("INSERT INTO world_regions (key, label, status) VALUES ('kresy','Kresy','live')")

    def hx(q, r, ht="plains", label=None, key=None):
        c.execute(
            "INSERT INTO world_hexes (q, r, hex_type, label, location_key, region, is_active, map_level)"
            " VALUES (?,?,?,?,?, 'kresy', 1, 0)",
            (q, r, ht, label, key),
        )

    # East corridor: (0,0) start → bridge at (2,0); Vilnograd at (4,0).
    hx(0, 0, "plains", "Rozstaje")
    hx(1, 0, "plains", "Trakt")
    hx(2, 0, "bridge", "Most na rzece")
    hx(3, 0, "plains", "Pole")
    hx(4, 0, "town", "Vilnograd", key="vilnograd")
    # South corridor: villages at (0,3) [near] and (0,5) [far].
    hx(0, 1, "plains", "Ścieżka")
    hx(0, 2, "plains", "Łąka")
    hx(0, 3, "village", "Wioska Dębowa")
    hx(0, 4, "plains", "Miedza")
    hx(0, 5, "village", "Wioska Zła")

    c.execute(
        "INSERT INTO game_locations (key, label, canonical, is_active, world_hex_q, world_hex_r)"
        " VALUES ('vilnograd', 'Vilnograd', 1, 1, 4, 0)"
    )

    for ht, lab in [("plains", "Równina"), ("bridge", "Most"), ("village", "Wioska"),
                    ("town", "Miasto"), ("river", "Rzeka")]:
        c.execute(
            "INSERT INTO hex_type_config (hex_type, label, travel_hours, encounter_chance, is_passable, is_active)"
            " VALUES (?,?, 1.0, 0.0, 1, 1)",
            (ht, lab),
        )

    c.execute("INSERT INTO characters (id, campaign_id, sheet_json) VALUES (1, 1, '{}')")
    c.execute(
        "INSERT INTO game_sessions (id, campaign_id, current_location_id, session_flags)"
        " VALUES ('s1', 1, NULL, ?)",
        (json.dumps({"current_hex": {"q": 0, "r": 0}, "known_regions": ["kresy"]}),),
    )
    # Hero knows the bridge and both villages (discovered).
    for q, r in [(2, 0), (0, 3), (0, 5)]:
        c.execute(
            "INSERT INTO campaign_hex_data (campaign_id, hex_q, hex_r, discovered) VALUES (1, ?, ?, 1)",
            (q, r),
        )
    c.commit()
    return c


def _run(conn, text):
    from app.services.turn_pipeline import execute_directional_travel
    return execute_directional_travel(
        conn=conn, campaign_id=1, character_id=1, character_sheet={}, player_text=text,
    )


def _current_hex(conn):
    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    return json.loads(row["session_flags"] or "{}").get("current_hex")


# ── Resolver unit tests ───────────────────────────────────────────────────────

def test_resolver_do_mostu_matches_bridge(conn):
    from app.services.hex_travel_service import resolve_player_text_to_known_hex
    assert resolve_player_text_to_known_hex("szukam drogi do mostu", conn, 1, 1) == (2, 0)


def test_resolver_w_strone_wioski_picks_nearest(conn):
    from app.services.hex_travel_service import resolve_player_text_to_known_hex
    # (0,3) is nearer than (0,5).
    assert resolve_player_text_to_known_hex("udaję się w stronę wioski", conn, 1, 1) == (0, 3)


def test_resolver_unknown_target_returns_sentinel(conn):
    from app.services.hex_travel_service import (
        resolve_player_text_to_known_hex, KNOWN_HEX_UNKNOWN,
    )
    assert resolve_player_text_to_known_hex("szukam drogi do zamku", conn, 1, 1) == KNOWN_HEX_UNKNOWN


def test_resolver_no_phrase_returns_none(conn):
    from app.services.hex_travel_service import resolve_player_text_to_known_hex
    assert resolve_player_text_to_known_hex("rozglądam się dookoła", conn, 1, 1) is None


# ── End-to-end via execute_directional_travel ─────────────────────────────────

def test_do_mostu_known_moves(conn):
    res = _run(conn, "szukam drogi do mostu na rzece")
    assert res["executed"] is True, res
    assert _current_hex(conn) == {"q": 2, "r": 0}


def test_w_strone_wioski_moves_to_nearest(conn):
    res = _run(conn, "udaję się w stronę wioski")
    assert res["executed"] is True, res
    assert _current_hex(conn) == {"q": 0, "r": 3}


def test_unknown_target_hint_no_move(conn):
    res = _run(conn, "szukam drogi do zamku warownego")
    assert res["executed"] is False, res
    assert "nie wie gdzie" in (res["system_fact"] or "")
    assert _current_hex(conn) == {"q": 0, "r": 0}  # did NOT move


def test_idę_do_vilnogradu_still_works(conn):
    res = _run(conn, "idę do Vilnogradu")
    assert res["executed"] is True, res
    assert _current_hex(conn) == {"q": 4, "r": 0}


def test_rozglądam_się_does_not_trigger(conn):
    res = _run(conn, "rozglądam się dookoła")
    assert res["executed"] is False
    assert res["system_fact"] is None
    assert _current_hex(conn) == {"q": 0, "r": 0}
