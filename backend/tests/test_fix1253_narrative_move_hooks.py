"""TDD: #1253 (TS1 defect) — narrative move hooks independent of LLM location_intent.

When the narrator describes a march in prose but emits ``location_intent: null``,
the move must still be recovered from the player's own declaration
("idę do kuźni") and committed, and any interrupted world travel_plan dropped.

These cover the deterministic pieces the recovery is built from:
  - resolve_declared_move_target: text → placed location (hub-preferring),
  - _synthesize_move_intent_from_text: → LocationIntent(move),
  - _clear_stale_travel_plan: removes a lingering world travel_plan.
The full apply path (validate_move → set_position) is integration-verified on DEV.
"""
import sys
import json
import sqlite3

import pytest

sys.path.insert(0, "/app")

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER, r INTEGER, hex_type TEXT DEFAULT 'plains', label TEXT,
    location_key TEXT, region TEXT, is_active INTEGER DEFAULT 1, map_level INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL, label TEXT NOT NULL,
    parent_id INTEGER, parent_key TEXT, location_type TEXT DEFAULT 'macro',
    is_active INTEGER DEFAULT 1, canonical INTEGER DEFAULT 0, ai_generated INTEGER DEFAULT 0,
    world_hex_q INTEGER, world_hex_r INTEGER
);
CREATE TABLE IF NOT EXISTS game_sessions (
    id TEXT PRIMARY KEY, campaign_id INTEGER, current_location_id INTEGER,
    session_flags TEXT NOT NULL DEFAULT '{}'
);
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    c.execute("INSERT INTO world_hexes (q,r,hex_type,label,location_key,region) "
              "VALUES (0,0,'village','Błotstein','blotstein','kresy')")
    # Hub (macro) placed on hex (0,0)
    c.execute("INSERT INTO game_locations (id,key,label,location_type,canonical,world_hex_q,world_hex_r) "
              "VALUES (1,'blotstein','Błotstein','macro',1,0,0)")
    # Sub-location of the hub (a building in the settlement)
    c.execute("INSERT INTO game_locations (id,key,label,parent_id,parent_key,location_type,canonical,world_hex_q,world_hex_r) "
              "VALUES (2,'kuznia_na_skraju_wsi','Kuźnia na skraju wsi',1,'blotstein','sub',1,0,0)")
    # Session: hero currently in the hub
    c.execute("INSERT INTO game_sessions (id,campaign_id,current_location_id,session_flags) "
              "VALUES ('s1',1,1,?)", (json.dumps({"current_hex": {"q": 0, "r": 0}}),))
    c.commit()
    return c


def test_declared_move_resolves_to_placed_subloc(conn):
    from app.services.hex_travel_service import resolve_declared_move_target
    hit = resolve_declared_move_target("idę do kuźni", conn, 1)
    assert hit is not None
    assert hit[0] == "kuznia_na_skraju_wsi", hit


def test_declared_move_ruszam_also_works(conn):
    from app.services.hex_travel_service import resolve_declared_move_target
    hit = resolve_declared_move_target("ruszam do kuźni na skraju wsi", conn, 1)
    assert hit is not None and hit[0] == "kuznia_na_skraju_wsi"


def test_non_move_returns_none(conn):
    from app.services.hex_travel_service import resolve_declared_move_target
    assert resolve_declared_move_target("rozglądam się po rynku", conn, 1) is None


def test_synthesize_move_intent(conn):
    from app.api.turns import _synthesize_move_intent_from_text
    intent = _synthesize_move_intent_from_text(conn, 1, "idę do kuźni")
    assert intent is not None
    assert intent.action == "move"
    assert intent.target_key == "kuznia_na_skraju_wsi"


def test_synthesize_none_for_non_move(conn):
    from app.api.turns import _synthesize_move_intent_from_text
    assert _synthesize_move_intent_from_text(conn, 1, "co tu słychać?") is None


def test_clear_stale_travel_plan_removes_it(conn):
    from app.api.turns import _clear_stale_travel_plan
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE id = 's1'",
        (json.dumps({
            "current_hex": {"q": 0, "r": 0},
            "travel_plan": {"interrupt_reason": "encounter_prompted",
                            "destination_hex": {"q": 5, "r": 5}},
        }),),
    )
    conn.commit()
    _clear_stale_travel_plan(conn, "s1")
    sf = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE id='s1'").fetchone()["session_flags"])
    assert "travel_plan" not in sf
