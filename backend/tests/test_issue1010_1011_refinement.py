"""TDD: Issues #1010 + #1011 refinement (razem) — critical/optional beats and
main/side quests vs. campaign victory.

#1010 refinement — critical-path act completion:
  • beat flag `optional: true` (default false = legacy behavior)
  • act closes once all *critical* (non-optional) beats are visited; optional beats
    don't block
  • on act close, unvisited beats → `skipped: true` (NOT `visited`) — honest telemetry
  • guard: an all-optional act falls back to "every beat required" so it can't close empty
  • find_orphan_beats: an *optional* beat without objective_type is NOT an orphan

#1011 refinement — quests vs. victory (depends on the optional/critical model):
  • maybe_complete_campaign blocks only on active *main* quests; side quests never block
  • a quest pinned to a skipped beat (beat_key link) is auto-cancelled → status 'skipped'
"""
import json
import sqlite3
import pytest

from app.services.campaign_plan_runtime import (
    get_plan, save_plan, mark_beat_visited,
    find_orphan_beats, maybe_complete_campaign,
)
from app.services.quest_persist_service import cancel_quests_for_skipped_beats


# ── Plan with an optional beat + a critical narrative beat ───────────────────

def _plan_with_optional():
    return {
        "title": "Refinement Campaign",
        "active_act": 1,
        "acts": [
            {
                "number": 1, "title": "Act 1", "completed": False,
                "key_beats": [
                    # critical — must be done to close the act
                    {"beat_key": "main_fight", "title": "Main fight", "visited": False,
                     "objective_type": "kill_enemy", "objective_value": "baron"},
                    # optional side scene — may be skipped, must NOT block the act
                    {"beat_key": "side_chat", "title": "Optional chat", "visited": False,
                     "optional": True},
                ],
            },
            {
                "number": 2, "title": "Act 2", "completed": False,
                "key_beats": [
                    {"beat_key": "finale", "title": "Finale", "visited": False},
                ],
            },
        ],
    }


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY, status TEXT DEFAULT 'active', gm_plan_json TEXT DEFAULT '{}', finale_available INTEGER NOT NULL DEFAULT 0)")
    conn.execute(
        "CREATE TABLE character_quests ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, campaign_id INTEGER, "
        "quest_type TEXT DEFAULT 'main', title TEXT, narrative TEXT DEFAULT '', "
        "status TEXT DEFAULT 'active', beat_key TEXT, "
        "created_turn INTEGER, completed_turn INTEGER, "
        "objective_type TEXT, objective_value TEXT, updated_at TEXT)"
    )
    conn.commit()
    yield conn
    conn.close()


def _seed_plan(db, plan):
    db.execute("INSERT INTO campaigns (id, status, gm_plan_json) VALUES (1, 'active', ?)",
               (json.dumps(plan),))
    db.commit()


# ─── #1010: optional beats don't block act close ─────────────────────────────

def test_optional_beat_does_not_block_act_close(db):
    """Closing only the critical beat advances the act; the optional beat is left behind."""
    _seed_plan(db, _plan_with_optional())
    # visit ONLY the critical beat — optional 'side_chat' stays unvisited
    mark_beat_visited(1, "main_fight", 5, db)
    plan = get_plan(1, db)
    act1 = plan["acts"][0]
    assert act1.get("completed") is True, "critical-only completion should close the act"
    assert plan.get("active_act") == 2, "act pointer should advance past the optional beat"


def test_skipped_beat_marked_skipped_not_visited(db):
    """Unvisited beats at act close are tagged skipped — never silently visited."""
    _seed_plan(db, _plan_with_optional())
    mark_beat_visited(1, "main_fight", 5, db)
    plan = get_plan(1, db)
    side = next(b for b in plan["acts"][0]["key_beats"] if b["beat_key"] == "side_chat")
    assert side.get("skipped") is True, "skipped optional beat must be marked skipped"
    assert side.get("visited") is not True, "skipped beat must NOT be marked visited"


def test_all_optional_act_does_not_close_empty(db):
    """An act whose every beat is optional falls back to 'all required' — no empty close."""
    plan = {
        "title": "All-optional", "active_act": 1,
        "acts": [{
            "number": 1, "title": "Act 1", "completed": False,
            "key_beats": [
                {"beat_key": "opt_a", "title": "A", "visited": False, "optional": True,
                 "objective_type": "kill_enemy", "objective_value": "wilk"},
                {"beat_key": "opt_b", "title": "B", "visited": False, "optional": True},
            ],
        }],
    }
    _seed_plan(db, plan)
    mark_beat_visited(1, "opt_a", 3, db)  # one optional done, one still open
    got = get_plan(1, db)
    assert got["acts"][0].get("completed") is not True, \
        "all-optional act must require every beat (fallback), not close on one"


def test_legacy_plan_without_optional_still_closes_on_all_visited(db):
    """Backward compat: a plan with no `optional` flags closes exactly as before."""
    plan = {
        "title": "Legacy", "active_act": 1,
        "acts": [{
            "number": 1, "title": "Act 1", "completed": False,
            "key_beats": [
                {"beat_key": "b1", "title": "B1", "visited": False,
                 "objective_type": "kill_enemy", "objective_value": "ork"},
                {"beat_key": "b2", "title": "B2", "visited": False},
            ],
        }],
    }
    _seed_plan(db, plan)
    mark_beat_visited(1, "b1", 1, db)
    assert get_plan(1, db)["acts"][0].get("completed") is not True, "one of two visited → still open"
    mark_beat_visited(1, "b2", 2, db)
    assert get_plan(1, db)["acts"][0].get("completed") is True, "all visited → closes (legacy)"


# ─── #1010: orphan validator ignores optional beats ─────────────────────────

def test_optional_beat_without_objective_is_not_orphan(db):
    """An optional narrative beat is intentionally skippable — not an orphan."""
    plan = _plan_with_optional()
    orphans = find_orphan_beats(plan)
    assert "side_chat" not in orphans, "optional beat without objective must NOT be flagged orphan"


def test_critical_beat_without_objective_is_orphan():
    """A *critical* beat with no objective and no narrative_close still strands the act."""
    plan = {
        "acts": [{"key_beats": [
            {"beat_key": "dead_critical", "title": "X", "visited": False},  # critical, no path
        ]}],
    }
    assert "dead_critical" in find_orphan_beats(plan)


# ─── #1011: victory blocks only on MAIN quests ──────────────────────────────

def _complete_all_acts(db):
    """Drive the plan to every act completed so only quests gate victory."""
    mark_beat_visited(1, "main_fight", 1, db)   # closes act 1 (optional skipped)
    mark_beat_visited(1, "finale", 2, db)       # closes act 2


def test_active_side_quest_does_not_block_victory(db, monkeypatch):
    """A lingering side quest must not stop the campaign from completing."""
    import app.services.campaign_plan_runtime as cpr
    monkeypatch.setattr(cpr, "write_game_event", lambda *a, **k: None)
    _seed_plan(db, _plan_with_optional())
    _complete_all_acts(db)
    db.execute("INSERT INTO character_quests (character_id, campaign_id, quest_type, title, status) "
               "VALUES (7, 1, 'side', 'Pobocze', 'active')")
    db.commit()
    won = maybe_complete_campaign(1, 7, 10, db)
    assert won is True, "side quest active should NOT block victory"
    # #1097: gate opens (finale_available), status stays 'active' until /finish.
    row = db.execute("SELECT status, finale_available FROM campaigns WHERE id=1").fetchone()
    assert row["status"] == "active"
    assert row["finale_available"] == 1


def test_active_main_quest_blocks_victory(db):
    """A main quest still hard-blocks the finale."""
    _seed_plan(db, _plan_with_optional())
    _complete_all_acts(db)
    db.execute("INSERT INTO character_quests (character_id, campaign_id, quest_type, title, status) "
               "VALUES (7, 1, 'main', 'Glowny watek', 'active')")
    db.commit()
    won = maybe_complete_campaign(1, 7, 10, db)
    assert won is False, "active main quest must block victory"
    row = db.execute("SELECT status FROM campaigns WHERE id=1").fetchone()
    assert row["status"] == "active"


# ─── #1011: quest pinned to a skipped beat is auto-cancelled ────────────────

def test_quest_on_skipped_beat_is_cancelled(db):
    """A side quest pinned (beat_key) to a skipped optional beat → status 'skipped'."""
    _seed_plan(db, _plan_with_optional())
    db.execute("INSERT INTO character_quests (character_id, campaign_id, quest_type, title, status, beat_key) "
               "VALUES (7, 1, 'side', 'Quest poboczny', 'active', 'side_chat')")
    db.commit()
    cancelled = cancel_quests_for_skipped_beats(db, 1, ["side_chat"])
    assert "Quest poboczny" in cancelled
    status = db.execute("SELECT status FROM character_quests WHERE beat_key='side_chat'").fetchone()["status"]
    assert status == "skipped", "quest pinned to a skipped beat must be cancelled (skipped)"


def test_cancel_skipped_beats_ignores_unrelated_quests(db):
    """Cancelling skipped-beat quests must not touch quests pinned elsewhere."""
    _seed_plan(db, _plan_with_optional())
    db.execute("INSERT INTO character_quests (character_id, campaign_id, quest_type, title, status, beat_key) "
               "VALUES (7, 1, 'side', 'Inny', 'active', 'other_beat')")
    db.commit()
    cancel_quests_for_skipped_beats(db, 1, ["side_chat"])
    status = db.execute("SELECT status FROM character_quests WHERE beat_key='other_beat'").fetchone()["status"]
    assert status == "active", "unrelated quest must stay active"
