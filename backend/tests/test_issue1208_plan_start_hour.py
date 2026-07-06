"""TDD: Issue #1208 — plan kampanii deklaruje godzinę startową (start_hour).

- init_clock_from_plan ustawia świeży zegar z gm_plan_json.start_hour,
- nigdy nie cofa chodzącego zegara (ingame_hours / clock_history w flags),
- waliduje zakres 0-23 i typ,
- hook w resolve_starting_hex ustawia zegar przy starcie kampanii,
- prompt Kuźni zawiera pole i zasadę,
- konteksty sceny otwarcia niosą porę dnia.
"""
import json
import sys
import sqlite3

sys.path.insert(0, "/app")


def _make_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, owner_user_id INTEGER,
            source_template_id INTEGER, template_id INTEGER,
            gm_plan_json TEXT
        );
        CREATE TABLE campaign_templates (
            id INTEGER PRIMARY KEY, start_hex_q INTEGER, start_hex_r INTEGER,
            gm_plan_json TEXT
        );
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER, r INTEGER, hex_type TEXT DEFAULT 'plains', label TEXT,
            map_level INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            location_key TEXT, encounter_chance REAL DEFAULT 0,
            encounter_pool TEXT DEFAULT '[]', created_by_gm INTEGER DEFAULT 0,
            created_by_campaign_id INTEGER, discovered_in_campaign_id INTEGER
        );
        CREATE TABLE campaign_hex_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, hex_q INTEGER, hex_r INTEGER,
            campaign_label TEXT, discovered INTEGER DEFAULT 0,
            UNIQUE(campaign_id, hex_q, hex_r)
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, session_flags TEXT DEFAULT '{}',
            current_location_id INTEGER, ingame_hours INTEGER DEFAULT 9,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT, label TEXT, description TEXT,
            parent_id INTEGER, parent_key TEXT, location_type TEXT,
            world_hex_q INTEGER, world_hex_r INTEGER,
            canonical INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            review_status TEXT DEFAULT 'permanent', safe_for_rest INTEGER DEFAULT 0,
            created_by TEXT, approved INTEGER DEFAULT 1, ai_generated INTEGER DEFAULT 0,
            source_campaign_id INTEGER, location_subtype TEXT, biome TEXT,
            created_at TEXT DEFAULT (datetime('now')), updated_at TEXT
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
            status TEXT DEFAULT 'active', sheet_json TEXT DEFAULT '{}'
        );
    """)
    return db


def _campaign(db, cid=1, start_hour=19, flags="{}"):
    plan = {"title": "T", "acts": []}
    if start_hour is not None:
        plan["start_hour"] = start_hour
    db.execute(
        "INSERT INTO campaigns (id, owner_user_id, gm_plan_json) VALUES (?,1,?)",
        (cid, json.dumps(plan)),
    )
    db.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?,?)",
        (cid, flags),
    )
    db.commit()


# ─── init_clock_from_plan ─────────────────────────────────────────────────────

def test_sets_fresh_clock_from_plan():
    from app.services.clock_service import init_clock_from_plan
    db = _make_db()
    _campaign(db, start_hour=19)

    assert init_clock_from_plan(1, conn=db) == 19

    row = db.execute("SELECT session_flags, ingame_hours FROM game_sessions WHERE campaign_id=1").fetchone()
    flags = json.loads(row["session_flags"])
    assert flags["ingame_hours"] == 19
    assert row["ingame_hours"] == 19
    assert flags["clock_history"][0]["reason"] == "plan_start_hour"


def test_never_rewinds_running_clock():
    from app.services.clock_service import init_clock_from_plan
    db = _make_db()
    _campaign(db, start_hour=19, flags='{"ingame_hours": 34, "clock_history": [{"from": 9, "to": 34}]}')

    assert init_clock_from_plan(1, conn=db) is None
    flags = json.loads(db.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1"
    ).fetchone()["session_flags"])
    assert flags["ingame_hours"] == 34, "chodzący zegar nietknięty"


def test_invalid_or_missing_start_hour_is_noop():
    from app.services.clock_service import init_clock_from_plan
    db = _make_db()
    _campaign(db, cid=1, start_hour=None)   # no field
    _campaign(db, cid=2, start_hour=25)     # out of range
    db.execute("UPDATE campaigns SET gm_plan_json=? WHERE id=2",
               (json.dumps({"start_hour": 25}),))
    _campaign(db, cid=3, start_hour="wieczorem")  # wrong type
    db.commit()

    assert init_clock_from_plan(1, conn=db) is None
    assert init_clock_from_plan(2, conn=db) is None
    assert init_clock_from_plan(3, conn=db) is None
    for cid in (1, 2, 3):
        flags = json.loads(db.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id=?", (cid,)
        ).fetchone()["session_flags"])
        assert "ingame_hours" not in flags


def test_noop_without_session():
    from app.services.clock_service import init_clock_from_plan
    db = _make_db()
    db.execute("INSERT INTO campaigns (id, owner_user_id, gm_plan_json) VALUES (9,1,?)",
               (json.dumps({"start_hour": 20}),))
    db.commit()
    assert init_clock_from_plan(9, conn=db) is None


def test_midnight_zero_is_valid():
    from app.services.clock_service import init_clock_from_plan
    db = _make_db()
    _campaign(db, start_hour=0)
    assert init_clock_from_plan(1, conn=db) == 0


# ─── hook w resolve_starting_hex ──────────────────────────────────────────────

def test_resolve_starting_hex_applies_plan_start_hour():
    from app.services.hex_travel_service import resolve_starting_hex
    db = _make_db()
    db.execute("INSERT INTO world_hexes (q,r,hex_type,label) VALUES (5,5,'town','Osada')")
    plan = {"title": "T", "start_hour": 21, "acts": []}
    db.execute("INSERT INTO campaigns (id,owner_user_id,gm_plan_json) VALUES (100,1,?)",
               (json.dumps(plan),))
    db.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (100,'{}')")
    db.commit()

    resolve_starting_hex(100, 999, "Osada", db)

    flags = json.loads(db.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=100"
    ).fetchone()["session_flags"])
    assert flags["ingame_hours"] == 21, "start kampanii ma ustawić zegar z planu"


# ─── prompty ──────────────────────────────────────────────────────────────────

def test_forge_plan_prompt_contains_start_hour():
    from app.routers.adventure_forge import _build_generate_plan_system_prompt
    prompt = _build_generate_plan_system_prompt(3)
    assert '"start_hour"' in prompt
    assert "PORA STARTOWA" in prompt


def test_opening_context_includes_time_of_day():
    from app.services.opening_context import build_opening_plan_context
    plan = json.dumps({
        "arcs": {"default": {"title": "Wątek", "hooks": {"locations": ["Karczma"]}}},
        "active_arc_id": "default",
        "start_hour": 19,
    })
    ctx = build_opening_plan_context(plan)
    assert "Pora startowa" in ctx
    assert "19:00" in ctx
    assert "Wieczór" in ctx


def test_opening_context_without_start_hour_unchanged():
    from app.services.opening_context import build_opening_plan_context
    plan = json.dumps({
        "arcs": {"default": {"title": "Wątek", "hooks": {"locations": ["Karczma"]}}},
        "active_arc_id": "default",
    })
    ctx = build_opening_plan_context(plan)
    assert "Pora startowa" not in ctx
    assert "Tytuł wątku" in ctx
