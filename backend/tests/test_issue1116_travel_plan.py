"""TDD: Issue #1116 — PT6 travel_plan: destination memory + post-combat resumption.

Before PT6: resolve_chain_travel interrupts on encounter and forgets destination.
            After combat, player stands on encounter hex with no prompt.
After PT6:  travel_plan saved to session_flags on interrupt; pop_travel_plan_hint
            injects narrator fact asking: continue / rest / camp.
            "idę dalej" resumption calls resolve_chain_travel from current hex.
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
"""


@pytest.fixture
def conn():
    """In-memory DB with a 5-hex path: (0,0)→(1,0)→(2,0)→(3,0)→(4,0).
    Hex (2,0) has encounter_chance=1.0 with enemy pool.
    Destination (4,0) has location 'vilnograd'.
    """
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)

    # Session: player starts at (0,0)
    c.execute(
        "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES ('s1', 1, ?)",
        (json.dumps({"current_hex": {"q": 0, "r": 0}}),),
    )

    # Hex path: (0,0) through (4,0) — all plains, flat row
    hexes = [
        (0, 0, "plains", "Start", 0.0, "[]", None),
        (1, 0, "plains", "Pole", 0.0, "[]", None),
        (2, 0, "plains", "Niebezpieczna Równina", 1.0, '["goblin_scout"]', None),  # GUARANTEED encounter
        (3, 0, "plains", "Droga", 0.0, "[]", None),
        (4, 0, "plains", "Vilnograd", 0.0, "[]", "vilnograd"),
    ]
    for q, r, htype, label, enc_chance, enc_pool, loc_key in hexes:
        c.execute(
            "INSERT INTO world_hexes (q, r, hex_type, label, encounter_chance, encounter_pool, location_key, is_active, map_level)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0)",
            (q, r, htype, label, enc_chance, enc_pool, loc_key),
        )

    # Location for destination
    c.execute(
        "INSERT INTO game_locations (key, label, canonical, is_active, world_hex_q, world_hex_r)"
        " VALUES ('vilnograd', 'Vilnograd', 1, 1, 4, 0)"
    )
    c.commit()
    return c


# ── RED 1: resolve_chain_travel saves travel_plan on encounter interrupt ──────

def test_travel_plan_saved_when_encounter_interrupts(conn):
    """#1116 RED: encounter on hex (2,0) → travel_plan in session_flags with destination."""
    from app.services.hex_travel_service import resolve_chain_travel

    result = resolve_chain_travel(
        campaign_id=1,
        character_id=None,
        from_hex=(0, 0),
        to_hex=(4, 0),
        character_sheet={},
        conn=conn,
    )

    assert result.get("encounter") is not None, "Expected encounter at hex (2,0)"
    assert result.get("arrived_hex") == {"q": 2, "r": 0}, f"Expected arrival at encounter hex, got {result.get('arrived_hex')}"

    flags = json.loads(
        conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0]
    )
    assert "travel_plan" in flags, (
        "session_flags must contain 'travel_plan' after encounter interrupt — "
        f"got keys: {list(flags.keys())}"
    )
    tp = flags["travel_plan"]
    assert tp["destination_hex"] == {"q": 4, "r": 0}, (
        f"travel_plan.destination_hex must be (4,0), got: {tp.get('destination_hex')}"
    )
    assert tp.get("interrupt_reason") == "encounter", (
        f"travel_plan.interrupt_reason must be 'encounter', got: {tp.get('interrupt_reason')}"
    )
    assert "path" in tp, "travel_plan must include path"
    assert tp.get("step_index") is not None, "travel_plan must include step_index"


# ── RED 2: resolve_chain_travel clears travel_plan on full arrival ────────────

def test_travel_plan_cleared_on_full_arrival(conn):
    """#1116 RED: travel with no encounter → travel_plan NOT saved (or cleared)."""
    from app.services.hex_travel_service import resolve_chain_travel
    # Put a pre-existing travel_plan to verify it gets cleared
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({
            "current_hex": {"q": 0, "r": 0},
            "travel_plan": {
                "destination_hex": {"q": 4, "r": 0},
                "interrupt_reason": "encounter",
            },
        }),),
    )
    conn.commit()

    # Travel from (3,0) to (4,0) — no encounter hex on this single-step path
    result = resolve_chain_travel(
        campaign_id=1,
        character_id=None,
        from_hex=(3, 0),
        to_hex=(4, 0),
        character_sheet={},
        conn=conn,
    )

    assert result.get("encounter") is None, "Expected no encounter on last hop"
    assert result.get("arrived_hex") == {"q": 4, "r": 0}

    flags = json.loads(
        conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0]
    )
    assert "travel_plan" not in flags or flags["travel_plan"] is None, (
        "travel_plan must be cleared after successful full arrival — "
        f"got: {flags.get('travel_plan')}"
    )


# ── RED 3: pop_travel_plan_hint returns SYSTEM fact after encounter ────────────

def test_pop_travel_plan_hint_returns_fact(conn):
    """#1116 RED: travel_plan with interrupt_reason='encounter', no active combat → hint returned."""
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({
            "current_hex": {"q": 2, "r": 0},
            "travel_plan": {
                "destination_hex": {"q": 4, "r": 0},
                "destination_label": "Vilnograd",
                "path": [{"q": 0, "r": 0}, {"q": 1, "r": 0}, {"q": 2, "r": 0}, {"q": 3, "r": 0}, {"q": 4, "r": 0}],
                "step_index": 2,
                "interrupt_reason": "encounter",
                # PT-F1 #1135: combat already happened and ended -> hint may fire now
                "combat_seen": True,
            },
        }),),
    )
    conn.commit()

    from app.services.turn_pipeline import pop_travel_plan_hint

    hint = pop_travel_plan_hint(conn, 1)

    assert hint is not None, "pop_travel_plan_hint must return a fact when travel was interrupted"
    assert "[SYSTEM:" in hint, f"Hint must be a [SYSTEM:...] narrator fact, got: {hint!r}"
    assert "Vilnograd" in hint or "vilnograd" in hint.lower(), (
        f"Hint must mention destination name, got: {hint!r}"
    )
    assert any(kw in hint.lower() for kw in ["kontynuujesz", "kontynuuje", "odpocz", "obóz", "zapytaj"]), (
        f"Hint must ask about continue/rest/camp, got: {hint!r}"
    )


# ── RED 4: pop_travel_plan_hint returns None while combat still active ─────────

def test_pop_travel_plan_hint_none_while_combat_active(conn):
    """#1116 RED: travel_plan exists but combat still active → None (don't prompt during fight)."""
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({
            "travel_plan": {
                "destination_hex": {"q": 4, "r": 0},
                "interrupt_reason": "encounter",
            },
        }),),
    )
    conn.execute(
        "INSERT INTO active_combat (campaign_id, status) VALUES (1, 'active')"
    )
    conn.commit()

    from app.services.turn_pipeline import pop_travel_plan_hint

    hint = pop_travel_plan_hint(conn, 1)
    assert hint is None, "Must not prompt while combat is still active"


# ── RED 5: pop_travel_plan_hint fires exactly once ────────────────────────────

def test_pop_travel_plan_hint_fires_once(conn):
    """#1116 RED: hint returned on first call, None on second (one-shot prompt)."""
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({
            "travel_plan": {
                "destination_hex": {"q": 4, "r": 0},
                "destination_label": "Vilnograd",
                "path": [{"q": 0, "r": 0}, {"q": 1, "r": 0}, {"q": 2, "r": 0}, {"q": 3, "r": 0}, {"q": 4, "r": 0}],
                "step_index": 2,
                "interrupt_reason": "encounter",
                # PT-F1 #1135: combat already happened and ended -> one-shot may fire
                "combat_seen": True,
            },
        }),),
    )
    conn.commit()

    from app.services.turn_pipeline import pop_travel_plan_hint

    first = pop_travel_plan_hint(conn, 1)
    second = pop_travel_plan_hint(conn, 1)

    assert first is not None, "First call must return the hint"
    assert second is None, "Second call must return None (hint already consumed)"


# ── RED 6: detect_travel_continuation keyword detection ──────────────────────

def test_detect_travel_continuation_positive():
    """#1116 RED: continuation phrases detected."""
    from app.services.turn_pipeline import detect_travel_continuation

    positive = [
        "kontynuuję podróż",
        "idę dalej",
        "ruszam dalej",
        "tak, lecę dalej",
        "kontynuuj",
        "tak, kontynuuję",
        "wróćmy na szlak",
        "resume travel",
    ]
    for phrase in positive:
        assert detect_travel_continuation(phrase), (
            f"Expected continuation detected for: {phrase!r}"
        )


def test_detect_travel_continuation_negative():
    """#1116 RED: non-continuation phrases not detected."""
    from app.services.turn_pipeline import detect_travel_continuation

    negative = [
        "chcę odpocząć",
        "rozbijam obóz",
        "atakuję goblin",
        "wchodzę do karczmy",
        "idę na północ",
    ]
    for phrase in negative:
        assert not detect_travel_continuation(phrase), (
            f"Expected no continuation for: {phrase!r}"
        )


# ── RED 7: travel_plan backward-compat (single-hex travel unchanged) ──────────

def test_single_hex_travel_no_travel_plan(conn):
    """#1116 COMPAT: single-hop travel (no encounter) → no travel_plan saved."""
    result = resolve_chain_travel_import(conn, from_hex=(3, 0), to_hex=(4, 0))
    assert result.get("ok") is True

    flags = json.loads(
        conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0]
    )
    assert "travel_plan" not in flags or flags["travel_plan"] is None, (
        f"Single-hop travel must not create travel_plan: {flags.get('travel_plan')}"
    )


def resolve_chain_travel_import(conn, from_hex, to_hex):
    from app.services.hex_travel_service import resolve_chain_travel
    return resolve_chain_travel(
        campaign_id=1,
        character_id=None,
        from_hex=from_hex,
        to_hex=to_hex,
        character_sheet={},
        conn=conn,
    )


# ── PT-F1 #1135: encounter hint must be DEFERRED until combat happened+ended ───

def _set_encounter_plan(conn, extra=None):
    tp = {
        "destination_hex": {"q": 4, "r": 0},
        "destination_label": "Vilnograd",
        "path": [{"q": 0, "r": 0}, {"q": 1, "r": 0}, {"q": 2, "r": 0}],
        "step_index": 1,
        "interrupt_reason": "encounter",
        "combat_seen": False,
        "wait_turns": 0,
    }
    if extra:
        tp.update(extra)
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({"current_hex": {"q": 2, "r": 0}, "travel_plan": tp}),),
    )
    conn.commit()


def test_ptf1_hint_deferred_on_encounter_turn(conn):
    """PT-F1: on the encounter turn combat has not spawned yet (post-LLM) -> no hint.

    The old P0 bug fired the continue/rest/camp prompt here, consuming the one-shot
    before the real combat, so it never appeared afterwards.
    """
    _set_encounter_plan(conn)
    from app.services.turn_pipeline import pop_travel_plan_hint
    assert pop_travel_plan_hint(conn, 1) is None, "must not prompt on the encounter turn (combat not yet spawned)"


def test_ptf1_hint_fires_after_combat_ended(conn):
    """PT-F1: combat became active (combat_seen) then ended -> hint fires exactly then."""
    _set_encounter_plan(conn)
    from app.services.turn_pipeline import pop_travel_plan_hint

    # turn 1: encounter turn, no combat yet -> deferred
    assert pop_travel_plan_hint(conn, 1) is None

    # combat spawns
    conn.execute("INSERT INTO active_combat (campaign_id, status) VALUES (1, active_val)".replace("active_val", "'active'"))
    conn.commit()
    assert pop_travel_plan_hint(conn, 1) is None, "no prompt while combat active"

    # combat ends
    conn.execute("UPDATE active_combat SET status='ended' WHERE campaign_id=1")
    conn.commit()
    hint = pop_travel_plan_hint(conn, 1)
    assert hint is not None and "[SYSTEM:" in hint, "hint must fire once combat has ended"
    assert pop_travel_plan_hint(conn, 1) is None, "one-shot: no second hint"


def test_ptf1_fizzle_guard_fires_if_no_combat(conn):
    """PT-F1: if the narrator never turns the encounter into combat, fire after fizzle turns."""
    _set_encounter_plan(conn)
    from app.services.turn_pipeline import pop_travel_plan_hint
    assert pop_travel_plan_hint(conn, 1) is None      # wait_turns 1
    hint = pop_travel_plan_hint(conn, 1)              # wait_turns 2 -> fire
    assert hint is not None, "fizzle guard must fire the prompt when combat never happened"


def test_ptf1_prompted_plan_expires_via_ttl(conn):
    """PT-F1: a plan stuck in *_prompted state is dropped after the TTL."""
    _set_encounter_plan(conn, extra={"interrupt_reason": "encounter_prompted", "age": 0})
    from app.services.turn_pipeline import pop_travel_plan_hint, _PLAN_TTL_TURNS
    for _ in range(_PLAN_TTL_TURNS + 1):
        pop_travel_plan_hint(conn, 1)
    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    assert json.loads(row[0]).get("travel_plan") is None, "stale prompted plan must be dropped by TTL"
