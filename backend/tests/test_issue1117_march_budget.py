"""TDD: Issue #1117 — PT7 Budżet dzienny marszu: 8h baza, 12h max, zmierzch pyta, nocny marsz ryzykowny."""
import sys
import json
import sqlite3
import pytest

sys.path.insert(0, "/app")

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER NOT NULL, r INTEGER NOT NULL,
    hex_type TEXT NOT NULL DEFAULT 'plains',
    label TEXT, atmosphere TEXT,
    encounter_chance REAL NOT NULL DEFAULT 0.0,
    encounter_pool TEXT NOT NULL DEFAULT '[]',
    location_key TEXT, region TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    map_level INTEGER NOT NULL DEFAULT 0,
    created_by_gm INTEGER NOT NULL DEFAULT 0,
    parent_hex_id INTEGER
);
CREATE TABLE IF NOT EXISTS hex_type_config (
    hex_type TEXT PRIMARY KEY,
    travel_hours REAL NOT NULL DEFAULT 1.0,
    encounter_base_chance REAL NOT NULL DEFAULT 0.0,
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
CREATE TABLE IF NOT EXISTS game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL, label TEXT NOT NULL,
    canonical INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    ai_generated INTEGER NOT NULL DEFAULT 0,
    world_hex_q INTEGER, world_hex_r INTEGER,
    location_type TEXT DEFAULT 'macro',
    map_icon TEXT, review_status TEXT DEFAULT 'permanent',
    safe_for_rest INTEGER NOT NULL DEFAULT 0,
    temporary INTEGER NOT NULL DEFAULT 0,
    description TEXT DEFAULT '',
    parent_key TEXT DEFAULT NULL,
    created_by TEXT DEFAULT 'seed'
);
CREATE TABLE IF NOT EXISTS game_sessions (
    id TEXT PRIMARY KEY, campaign_id INTEGER,
    current_location_id INTEGER,
    session_flags TEXT NOT NULL DEFAULT '{}',
    ingame_hours INTEGER DEFAULT 9
);
CREATE TABLE IF NOT EXISTS campaign_hex_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    hex_q INTEGER NOT NULL, hex_r INTEGER NOT NULL,
    discovered INTEGER NOT NULL DEFAULT 0,
    encounter_cleared INTEGER NOT NULL DEFAULT 0,
    UNIQUE(campaign_id, hex_q, hex_r)
);
CREATE TABLE IF NOT EXISTS world_regions (
    key TEXT PRIMARY KEY, label TEXT, status TEXT DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS active_combat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER UNIQUE, status TEXT DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER, sheet_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS character_xp_grants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER, campaign_id INTEGER,
    amount INTEGER, reason TEXT, source TEXT, granted_by_user_id INTEGER
);
"""


@pytest.fixture
def conn():
    """10 forest hexes (0,0)→(9,0). Forest = 2h each. No encounters."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)

    c.execute("INSERT INTO hex_type_config (hex_type, travel_hours, encounter_base_chance) VALUES ('forest', 2.0, 0.0)")
    c.execute("INSERT INTO hex_type_config (hex_type, travel_hours, encounter_base_chance) VALUES ('plains', 1.0, 0.0)")

    for q in range(10):
        c.execute(
            "INSERT INTO world_hexes (q, r, hex_type, label, encounter_chance, encounter_pool, is_active, map_level)"
            " VALUES (?, 0, 'forest', ?, 0.0, '[]', 1, 0)",
            (q, f"Las-{q}"),
        )

    c.execute(
        "INSERT INTO game_sessions (id, campaign_id, session_flags, ingame_hours) VALUES ('s1', 1, ?, 9)",
        (json.dumps({"current_hex": {"q": 0, "r": 0}, "ingame_hours": 9}),),
    )
    c.commit()
    return c


# ── Test 1: Dusk interrupt at 8h ─────────────────────────────────────────────

def test_dusk_interrupt_at_8h(conn):
    """PT7 RED: 10 forest hexes (2h each), fresh budget → interrupt after 4 hexes (8h)."""
    from app.services.hex_travel_service import resolve_chain_travel

    result = resolve_chain_travel(
        campaign_id=1, character_id=None,
        from_hex=(0, 0), to_hex=(9, 0),
        character_sheet={}, conn=conn,
    )

    assert result.get("ok") is True, f"Travel must succeed: {result}"
    assert result.get("encounter") is None, "No encounter expected (encounter_chance=0.0)"

    arrived = result.get("arrived_hex")
    assert arrived == {"q": 4, "r": 0}, (
        f"Expected dusk stop at (4,0) after 4×2h=8h, got arrived_hex={arrived}"
    )

    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1"
    ).fetchone()[0])
    assert "travel_plan" in flags, (
        f"travel_plan must be saved after dusk interrupt, keys={list(flags.keys())}"
    )
    tp = flags["travel_plan"]
    assert tp.get("interrupt_reason") == "dusk", (
        f"interrupt_reason must be 'dusk', got: {tp.get('interrupt_reason')}"
    )
    assert tp.get("destination_hex") == {"q": 9, "r": 0}, (
        f"destination_hex must be (9,0), got: {tp.get('destination_hex')}"
    )
    assert float(flags.get("hours_marched_today", 0)) == pytest.approx(8.0), (
        f"hours_marched_today must be 8.0, got: {flags.get('hours_marched_today')}"
    )


# ── Test 2: Forced camp at 12h ────────────────────────────────────────────────

def test_forced_camp_at_12h(conn):
    """PT7 RED: 10h already marched + night_march=True → next forest hex (2h) → forced camp at 12h."""
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({
            "current_hex": {"q": 0, "r": 0},
            "ingame_hours": 19,
            "hours_marched_today": 10.0,
            "night_march": True,
        }),),
    )
    conn.commit()

    from app.services.hex_travel_service import resolve_chain_travel

    result = resolve_chain_travel(
        campaign_id=1, character_id=None,
        from_hex=(0, 0), to_hex=(9, 0),
        character_sheet={}, conn=conn,
    )

    assert result.get("ok") is True

    arrived = result.get("arrived_hex")
    assert arrived == {"q": 1, "r": 0}, (
        f"Expected forced camp at (1,0) after 10+2h=12h, got: {arrived}"
    )

    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1"
    ).fetchone()[0])
    tp = flags.get("travel_plan", {})
    assert tp.get("interrupt_reason") == "forced_camp", (
        f"interrupt_reason must be 'forced_camp', got: {tp.get('interrupt_reason')}"
    )
    # night_march stays True (marks night march for PT9)
    assert flags.get("night_march") is True, (
        f"night_march must remain True after forced_camp (PT9 needs it), got: {flags.get('night_march')}"
    )


# ── Test 3: Budget carries over from session_flags ────────────────────────────

def test_budget_accumulates_from_session_flags(conn):
    """PT7 RED: 6h pre-marched + 1 forest hex (2h) = 8h → dusk interrupt at (1,0)."""
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({
            "current_hex": {"q": 0, "r": 0},
            "ingame_hours": 15,
            "hours_marched_today": 6.0,
        }),),
    )
    conn.commit()

    from app.services.hex_travel_service import resolve_chain_travel

    result = resolve_chain_travel(
        campaign_id=1, character_id=None,
        from_hex=(0, 0), to_hex=(9, 0),
        character_sheet={}, conn=conn,
    )

    arrived = result.get("arrived_hex")
    assert arrived == {"q": 1, "r": 0}, (
        f"Expected dusk at (1,0) after 6+2h=8h, got: {arrived}"
    )

    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1"
    ).fetchone()[0])
    assert float(flags.get("hours_marched_today", 0)) == pytest.approx(8.0), (
        f"hours_marched_today must be 8.0 (6+2), got: {flags.get('hours_marched_today')}"
    )


# ── Test 4: night_march=True skips 8h dusk cap ───────────────────────────────

def test_night_march_skips_dusk_interrupt(conn):
    """PT7 RED: night_march=True → 8h soft cap bypassed → arrives at destination."""
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({
            "current_hex": {"q": 0, "r": 0},
            "ingame_hours": 9,
            "hours_marched_today": 0.0,
            "night_march": True,
        }),),
    )
    conn.commit()

    from app.services.hex_travel_service import resolve_chain_travel

    # 4 hexes × 2h = 8h — exactly at soft cap, but night_march=True skips it
    result = resolve_chain_travel(
        campaign_id=1, character_id=None,
        from_hex=(0, 0), to_hex=(4, 0),
        character_sheet={}, conn=conn,
    )

    arrived = result.get("arrived_hex")
    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1"
    ).fetchone()[0])
    tp = flags.get("travel_plan")

    assert arrived == {"q": 4, "r": 0}, (
        f"night_march=True must allow full arrival at (4,0), got: {arrived}"
    )
    assert tp is None or tp.get("interrupt_reason") != "dusk", (
        f"night_march=True must skip dusk interrupt, travel_plan: {tp}"
    )


# ── Test 5: Long rest resets budget ──────────────────────────────────────────

def test_long_rest_resets_march_budget(conn):
    """PT7 RED: perform_long_rest → hours_marched_today=0, night_march=False."""
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({
            "current_hex": {"q": 0, "r": 0},
            "ingame_hours": 20,
            "hours_marched_today": 10.0,
            "night_march": True,
        }),),
    )
    conn.execute(
        "INSERT OR IGNORE INTO characters (id, campaign_id, sheet_json) VALUES (1, 1, ?)",
        (json.dumps({
            "current_hp": 10, "max_hp": 10, "current_mana": 0, "max_mana": 0,
            "pending_xp": 0, "xp_available": 0, "xp_lifetime_earned": 0,
            "level": 1, "short_rests_used": 0, "death_saves_failed": 0,
            "stats": {"CON": 10, "INT": 10}, "archetype": "warrior",
        }),),
    )
    conn.execute(
        "INSERT OR IGNORE INTO game_locations (key, label, is_active, canonical, safe_for_rest, world_hex_q, world_hex_r)"
        " VALUES ('camp_rest', 'Obóz', 1, 0, 1, 0, 0)"
    )
    conn.execute("UPDATE world_hexes SET location_key='camp_rest' WHERE q=0 AND r=0")
    conn.commit()

    from app.services.rest_service import perform_long_rest

    result = perform_long_rest(conn=conn, character_id=1, campaign_id=1)
    assert result.get("ok") is True, f"Long rest must succeed, got: {result}"

    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1"
    ).fetchone()[0])
    assert float(flags.get("hours_marched_today", 999)) == pytest.approx(0.0), (
        f"hours_marched_today must reset to 0 after long rest, got: {flags.get('hours_marched_today')}"
    )
    assert not flags.get("night_march"), (
        f"night_march must be False after long rest, got: {flags.get('night_march')}"
    )


# ── Test 6: pop_travel_plan_hint handles dusk ─────────────────────────────────

def test_dusk_hint_in_pop_travel_plan_hint(conn):
    """PT7 RED: travel_plan with interrupt_reason='dusk' → dusk hint returned."""
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({
            "current_hex": {"q": 4, "r": 0},
            "travel_plan": {
                "destination_hex": {"q": 9, "r": 0},
                "destination_label": "Wachstein",
                "path": [{"q": i, "r": 0} for i in range(10)],
                "step_index": 4,
                "hours_remaining": 5.0,
                "interrupt_reason": "dusk",
            },
        }),),
    )
    conn.commit()

    from app.services.turn_pipeline import pop_travel_plan_hint

    hint = pop_travel_plan_hint(conn, 1)

    assert hint is not None, "pop_travel_plan_hint must return dusk hint"
    assert "[SYSTEM:" in hint, f"Hint must be [SYSTEM:...] fact, got: {hint!r}"
    assert "zmierzch" in hint.lower() or "8h" in hint or "ciemno" in hint.lower(), (
        f"Dusk hint must mention dusk/zmierzch/8h, got: {hint!r}"
    )
    assert "Wachstein" in hint, f"Hint must mention destination Wachstein, got: {hint!r}"


# ── Test 7: pop_travel_plan_hint handles forced_camp ─────────────────────────

def test_forced_camp_hint_in_pop_travel_plan_hint(conn):
    """PT7 RED: travel_plan with interrupt_reason='forced_camp' → forced_camp hint returned."""
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({
            "current_hex": {"q": 1, "r": 0},
            "travel_plan": {
                "destination_hex": {"q": 9, "r": 0},
                "destination_label": "Vilnograd",
                "path": [{"q": i, "r": 0} for i in range(10)],
                "step_index": 1,
                "hours_remaining": 8.0,
                "interrupt_reason": "forced_camp",
            },
        }),),
    )
    conn.commit()

    from app.services.turn_pipeline import pop_travel_plan_hint

    hint = pop_travel_plan_hint(conn, 1)

    assert hint is not None, "pop_travel_plan_hint must return forced_camp hint"
    assert "[SYSTEM:" in hint, f"Hint must be [SYSTEM:...] fact, got: {hint!r}"
    assert "12h" in hint or "sił" in hint.lower() or "obóz" in hint.lower() or "wymuszon" in hint.lower(), (
        f"Forced camp hint must mention forced camp/exhaustion, got: {hint!r}"
    )


# ── Test 8: Backward compat — short plains travel ────────────────────────────

def test_short_plains_travel_no_interrupt(conn):
    """PT7 COMPAT: 1 plains hex → arrives, budget updated, no travel_plan."""
    # Replace first two hexes with plains for this test
    conn.execute("UPDATE world_hexes SET hex_type='plains' WHERE q IN (0,1)")
    conn.commit()

    from app.services.hex_travel_service import resolve_chain_travel

    result = resolve_chain_travel(
        campaign_id=1, character_id=None,
        from_hex=(0, 0), to_hex=(1, 0),
        character_sheet={}, conn=conn,
    )

    assert result.get("ok") is True
    assert result.get("arrived_hex") == {"q": 1, "r": 0}

    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1"
    ).fetchone()[0])
    assert flags.get("travel_plan") is None, (
        f"Short travel must not create travel_plan, got: {flags.get('travel_plan')}"
    )
    # 1 plains hex = 1h marched today
    assert float(flags.get("hours_marched_today", 0)) == pytest.approx(1.0), (
        f"hours_marched_today must be 1.0 after 1 plains hex, got: {flags.get('hours_marched_today')}"
    )


# ── PT-F3 #1137: daily budget resets on a new day (end of "eternal dusk") ──────

def test_ptf3_budget_resets_on_new_day(conn):
    """PT-F3: hours_marched_today from a PRIOR day must reset at dawn.

    Bug: budget was only reset by a long rest, so a hero who hit 8h and kept playing
    got an immediate dusk-interrupt on every later trip. A new in-game day = fresh
    budget, so the trip should march a full 8h again (stop at hex 4), not stall at 0.
    """
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({
            "current_hex": {"q": 0, "r": 0},
            "ingame_hours": 25,          # day 2
            "hours_marched_today": 8.0,  # spent yesterday
            "march_day": 1,              # stamped on day 1
            "night_march": True,         # from yesterday's night march
        }),),
    )
    conn.commit()

    from app.services.hex_travel_service import resolve_chain_travel
    result = resolve_chain_travel(
        campaign_id=1, character_id=None,
        from_hex=(0, 0), to_hex=(9, 0),
        character_sheet={}, conn=conn,
    )
    assert result.get("ok") is True
    arrived = result.get("arrived_hex")
    assert arrived == {"q": 4, "r": 0}, (
        f"new day must reset budget -> full 8h march to hex 4, got {arrived} (stale budget bug)"
    )
    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1"
    ).fetchone()[0])
    assert flags.get("march_day") == 2, "march_day must advance to the current day"
    assert flags.get("night_march") is False, "night_march must clear on the new day"


def test_ptf3_forced_camp_arms_ambush_boost(conn):
    """PT-F3: a 12h forced collapse must set camp_encounter_boost so /rest rolls the ambush.

    Bug: forced_camp set night_march but not camp_encounter_boost, so rest_service
    skipped the whole ambush roll (boost==0) exactly when the hero is most exposed.
    """
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({
            "current_hex": {"q": 0, "r": 0},
            "ingame_hours": 19,
            "hours_marched_today": 10.0,
            "night_march": True,
        }),),
    )
    conn.commit()

    from app.services.hex_travel_service import resolve_chain_travel
    result = resolve_chain_travel(
        campaign_id=1, character_id=None,
        from_hex=(0, 0), to_hex=(9, 0),
        character_sheet={}, conn=conn,
    )
    assert result.get("ok") is True
    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1"
    ).fetchone()[0])
    assert flags.get("travel_plan", {}).get("interrupt_reason") == "forced_camp"
    boost = flags.get("camp_encounter_boost")
    assert boost is not None and boost > 0, "forced_camp must arm the ambush boost"
    # forest has no camp_encounter_boost configured -> 0.20 default + 0.10 night_march
    assert boost == pytest.approx(0.30), f"expected 0.20 base + 0.10 night_march = 0.30, got {boost}"
