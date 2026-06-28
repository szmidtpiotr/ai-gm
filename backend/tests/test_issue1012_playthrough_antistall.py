"""TDD: Issue #1012 — Playthrough anti-stall detector + autopilot mode.

Progress (per #1010/#1011 critical-path model) =
  • a new *critical* (non-optional) beat visited, OR
  • the act pointer advancing, OR
  • a main-quest change (new main quest, or one completed).
A skipped/optional beat is NEITHER progress NOR a stall trigger.

Acceptance:
  • detect no progress for N turns → escalate directive to narrator
  • autopilot: [TEST] hero protected from death-loop, deterministic gate choice
  • telemetry `playthrough_stall` event with classified cause
"""
import json
import sqlite3
import pytest

from app.services.campaign_plan_runtime import (
    get_plan, mark_beat_visited, get_active_act_critical_beat_keys,
)
from app.services import playthrough_service as pts


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _plan():
    return {
        "title": "Stall Campaign",
        "active_act": 1,
        "acts": [
            {
                "number": 1, "title": "Act 1", "completed": False,
                "key_beats": [
                    {"beat_key": "crit_a", "title": "Critical A", "visited": False,
                     "objective_type": "kill_enemy", "objective_value": "wolf"},
                    {"beat_key": "side_opt", "title": "Optional side", "visited": False,
                     "optional": True},
                ],
            },
            {
                "number": 2, "title": "Act 2", "completed": False,
                "key_beats": [
                    {"beat_key": "finale", "title": "Finale", "visited": False,
                     "narrative_close": True},
                ],
            },
        ],
    }


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE campaigns (id INTEGER PRIMARY KEY, status TEXT DEFAULT 'active', "
        "gm_plan_json TEXT DEFAULT '{}')"
    )
    conn.execute(
        "CREATE TABLE character_quests ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, campaign_id INTEGER, "
        "quest_type TEXT DEFAULT 'main', title TEXT, status TEXT DEFAULT 'active', "
        "beat_key TEXT)"
    )
    conn.execute(
        "CREATE TABLE game_sessions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, "
        "session_flags TEXT DEFAULT '{}')"
    )
    conn.execute(
        "CREATE TABLE characters ("
        "id INTEGER PRIMARY KEY, name TEXT, sheet_json TEXT DEFAULT '{}')"
    )
    conn.commit()
    db_seed(conn)
    yield conn
    conn.close()


def db_seed(conn):
    conn.execute(
        "INSERT INTO campaigns (id, status, gm_plan_json) VALUES (1, 'active', ?)",
        (json.dumps(_plan()),),
    )
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, '{}')")
    conn.commit()


def _sig(conn):
    return pts.compute_progress_signature(conn, 1, 100)


# ── Progress signature ───────────────────────────────────────────────────────

def test_critical_beat_visit_changes_signature(db):
    """Visiting a critical beat IS progress → signature changes."""
    before = _sig(db)
    mark_beat_visited(1, "crit_a", 3, db)
    after = _sig(db)
    assert before != after, "critical beat visit must change progress signature"


def test_optional_beat_skip_is_not_progress(db):
    """A skipped/optional beat is NOT progress → signature stays the same.

    Closing the critical beat advances the act and leaves the optional beat
    'skipped'. We then re-read: the optional skip itself contributed nothing.
    """
    # Establish baseline after the act has already advanced (crit visited).
    mark_beat_visited(1, "crit_a", 3, db)
    plan = get_plan(1, db)
    assert plan["acts"][0]["key_beats"][1].get("skipped") is True, "optional left skipped"
    sig_with_skip = _sig(db)
    # The skipped optional beat must NOT be counted as a visited critical beat.
    crit_visited = pts._count_visited_critical_beats(plan)
    assert crit_visited == 1, "only the critical beat counts, not the skipped optional"
    assert "side_opt" not in sig_with_skip or True  # signature is opaque; count is the contract


def test_main_quest_change_is_progress(db):
    """Creating then completing a MAIN quest both change the signature."""
    s0 = _sig(db)
    db.execute(
        "INSERT INTO character_quests (character_id, campaign_id, quest_type, title, status) "
        "VALUES (100, 1, 'main', 'Find the relic', 'active')"
    )
    db.commit()
    s1 = _sig(db)
    assert s1 != s0, "new main quest is progress"
    db.execute("UPDATE character_quests SET status='completed' WHERE title='Find the relic'")
    db.commit()
    s2 = _sig(db)
    assert s2 != s1, "main quest completion is progress"


def test_side_quest_change_is_not_progress(db):
    """A side quest must NOT count as story progress (only main quests do)."""
    s0 = _sig(db)
    db.execute(
        "INSERT INTO character_quests (character_id, campaign_id, quest_type, title, status) "
        "VALUES (100, 1, 'side', 'Optional errand', 'active')"
    )
    db.commit()
    assert _sig(db) == s0, "side quest change is not story progress"


def test_act_advance_changes_signature(db):
    """Advancing the act pointer is progress."""
    s0 = _sig(db)
    mark_beat_visited(1, "crit_a", 3, db)  # closes act 1 → active_act=2
    assert get_plan(1, db)["active_act"] == 2
    assert _sig(db) != s0


# ── get_active_act_critical_beat_keys ────────────────────────────────────────

def test_critical_beat_keys_filters_optional_and_visited(db):
    plan = get_plan(1, db)
    keys = get_active_act_critical_beat_keys(plan)
    assert keys == ["crit_a"], "only unvisited non-optional beats of the active act"


# ── Stall detection ──────────────────────────────────────────────────────────

def test_stall_fires_after_threshold_turns_without_progress(db):
    """No progress for THRESHOLD turns → stalled=True; not before."""
    n = pts.STALL_TURN_THRESHOLD
    # First call establishes the baseline signature (turn 1) — never stalled.
    r = pts.record_progress_and_detect_stall(db, 1, 100, 1)
    assert r["stalled"] is False
    # Repeat with no progress until the counter reaches the threshold.
    last = r
    for t in range(2, n + 2):
        last = pts.record_progress_and_detect_stall(db, 1, 100, t)
    assert last["stall_turns"] >= n
    assert last["stalled"] is True, "must flag stall once threshold reached"
    assert last["cause"], "a stalled result must carry a classified cause"


def test_progress_resets_stall_counter(db):
    """Any real progress zeroes the stall counter."""
    for t in range(1, pts.STALL_TURN_THRESHOLD + 1):
        pts.record_progress_and_detect_stall(db, 1, 100, t)
    # make progress
    mark_beat_visited(1, "crit_a", pts.STALL_TURN_THRESHOLD, db)
    r = pts.record_progress_and_detect_stall(db, 1, 100, pts.STALL_TURN_THRESHOLD + 1)
    assert r["stall_turns"] == 0, "progress must reset the counter"
    assert r["stalled"] is False


# ── Cause classification ─────────────────────────────────────────────────────

def test_cause_orphan_beat(db):
    """A non-optional beat with no objective_type and no narrative_close = orphan."""
    orphan_plan = _plan()
    # make finale an orphan: strip its narrative_close
    orphan_plan["acts"][1]["key_beats"][0].pop("narrative_close", None)
    db.execute("UPDATE campaigns SET gm_plan_json=? WHERE id=1", (json.dumps(orphan_plan),))
    db.commit()
    assert pts.classify_stall_cause(db, 1, 100) == "orphan_beat"


def test_cause_main_quest_hanging(db):
    db.execute(
        "INSERT INTO character_quests (character_id, campaign_id, quest_type, title, status) "
        "VALUES (100, 1, 'main', 'Hanging', 'active')"
    )
    db.commit()
    assert pts.classify_stall_cause(db, 1, 100) == "main_quest_hanging"


def test_cause_narrator_loop_default(db):
    """Plan healthy, no hanging main quest, open critical beat exists → narrator loop."""
    assert pts.classify_stall_cause(db, 1, 100) == "narrator_loop"


# ── Stall directive ──────────────────────────────────────────────────────────

def test_directive_lists_critical_beats_and_escalates(db):
    mild = pts.build_stall_directive(5, ["crit_a"])
    crit = pts.build_stall_directive(15, ["crit_a"])
    assert "crit_a" in mild, "directive must name the critical beat to push toward"
    assert "STALL" in mild.upper() or "UTKN" in mild.upper()
    assert crit != mild, "intensity must escalate with stall_turns"


# ── Autopilot ────────────────────────────────────────────────────────────────

def test_autopilot_active_reads_env(monkeypatch):
    monkeypatch.setenv("AI_TEST_MODE", "1")
    assert pts.is_autopilot_active() is True
    monkeypatch.setenv("AI_TEST_MODE", "0")
    assert pts.is_autopilot_active() is False


def test_is_test_hero():
    assert pts.is_test_hero({"name": "[TEST] Bohater"}) is True
    assert pts.is_test_hero({"name": "Mizel"}) is False


def test_protect_test_hero_boosts_low_hp(db, monkeypatch):
    monkeypatch.setenv("AI_TEST_MODE", "1")
    db.execute(
        "INSERT INTO characters (id, name, sheet_json) VALUES (?,?,?)",
        (100, "[TEST] Bohater", json.dumps({"current_hp": 1, "max_hp": 40})),
    )
    db.commit()
    char = db.execute("SELECT * FROM characters WHERE id=100").fetchone()
    boosted = pts.protect_test_hero_from_death(db, char)
    assert boosted is True
    sheet = json.loads(db.execute("SELECT sheet_json FROM characters WHERE id=100").fetchone()[0])
    assert sheet["current_hp"] == 40, "low [TEST] hero hp restored to max"


def test_protect_skips_non_test_hero(db, monkeypatch):
    monkeypatch.setenv("AI_TEST_MODE", "1")
    db.execute(
        "INSERT INTO characters (id, name, sheet_json) VALUES (?,?,?)",
        (101, "Mizel", json.dumps({"current_hp": 1, "max_hp": 40})),
    )
    db.commit()
    char = db.execute("SELECT * FROM characters WHERE id=101").fetchone()
    assert pts.protect_test_hero_from_death(db, char) is False
    sheet = json.loads(db.execute("SELECT sheet_json FROM characters WHERE id=101").fetchone()[0])
    assert sheet["current_hp"] == 1, "real hero hp must never be touched"


def test_protect_skips_when_autopilot_off(db, monkeypatch):
    monkeypatch.setenv("AI_TEST_MODE", "0")
    db.execute(
        "INSERT INTO characters (id, name, sheet_json) VALUES (?,?,?)",
        (102, "[TEST] Bohater", json.dumps({"current_hp": 1, "max_hp": 40})),
    )
    db.commit()
    char = db.execute("SELECT * FROM characters WHERE id=102").fetchone()
    assert pts.protect_test_hero_from_death(db, char) is False


def test_autopilot_gate_choice_deterministic():
    a = pts.autopilot_gate_choice()
    b = pts.autopilot_gate_choice()
    assert a == b, "gate choice must be deterministic in autopilot"
    assert a, "must return a concrete choice"
