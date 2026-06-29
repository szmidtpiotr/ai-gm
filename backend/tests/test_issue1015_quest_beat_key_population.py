"""TDD: Issue #1015 — populate `character_quests.beat_key` when spawning a side
quest from a scene, so the #1011 auto-cancel loop (skipped beat → skipped quest)
actually fires in a live playthrough.

Source of truth (decided here): a quest spawned at runtime (QUEST_SUGGEST) is
pinned to the *current active beat* — the first unvisited key_beat of the active
act, i.e. "the scene the player is in". Template/Forge spawn paths may pass an
explicit beat_key instead. Quests with no link (beat_key=NULL) behave as today.

Infra already in place (#1011): the `beat_key` column and
`cancel_quests_for_skipped_beats()`. What was missing: nothing populated
`beat_key`, so auto-cancel never fired in practice.
"""
import json
import sqlite3
import pytest

from app.services.quest_persist_service import (
    persist_quest_to_character_quests,
    cancel_quests_for_skipped_beats,
)
from app.services.campaign_plan_runtime import (
    get_current_beat_key,
    get_plan,
    mark_beat_visited,
)


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
        "quest_type TEXT DEFAULT 'main', title TEXT, narrative TEXT DEFAULT '', "
        "status TEXT DEFAULT 'active', beat_key TEXT, "
        "created_turn INTEGER, completed_turn INTEGER, "
        "objective_type TEXT, objective_value TEXT, updated_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE campaign_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "campaign_id INTEGER, turn_number INTEGER)"
    )
    conn.commit()
    yield conn
    conn.close()


def _plan_two_critical_one_optional():
    """Act 1 with critical→optional→critical so the optional beat is the 'current'
    scene after the first critical beat, yet still gets skipped on act close."""
    return {
        "title": "Loop Campaign", "active_act": 1,
        "acts": [{
            "number": 1, "title": "Act 1", "completed": False,
            "key_beats": [
                {"beat_key": "A_intro", "title": "Intro fight", "visited": False,
                 "objective_type": "kill_enemy", "objective_value": "baron"},
                {"beat_key": "B_side", "title": "Optional side scene", "visited": False,
                 "optional": True},
                {"beat_key": "C_finale", "title": "Finale", "visited": False,
                 "objective_type": "visit_location", "objective_value": "wieza"},
            ],
        }],
    }


def _seed_plan(db, plan):
    db.execute("INSERT INTO campaigns (id, status, gm_plan_json) VALUES (1, 'active', ?)",
               (json.dumps(plan),))
    db.commit()


# ─── Main behavior: persist writes beat_key ──────────────────────────────────

def test_persist_quest_writes_beat_key(db):
    """persist_quest_to_character_quests(beat_key=...) stores it on the row."""
    quest = {"title": "Zbadaj kapliczke", "objective": "Sprawdz, kto zostawia ofiary"}
    inserted = persist_quest_to_character_quests(
        db, character_id=7, campaign_id=1, quest=quest, turn_number=3, beat_key="B_side"
    )
    assert inserted is True
    row = db.execute(
        "SELECT beat_key FROM character_quests WHERE title='Zbadaj kapliczke'"
    ).fetchone()
    assert row["beat_key"] == "B_side", "beat_key of the spawning scene must be stored"


def test_get_current_beat_key_returns_first_unvisited(db):
    """Current scene = first unvisited beat of the active act."""
    _seed_plan(db, _plan_two_critical_one_optional())
    assert get_current_beat_key(get_plan(1, db)) == "A_intro"
    mark_beat_visited(1, "A_intro", 1, db)
    assert get_current_beat_key(get_plan(1, db)) == "B_side", \
        "after the intro beat, the optional side scene is the current beat"


def test_get_current_beat_key_none_for_planless(db):
    """Planless / empty plan → no current beat (so nothing is mis-pinned)."""
    assert get_current_beat_key(None) is None
    assert get_current_beat_key({}) is None
    assert get_current_beat_key({"acts": []}) is None


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_persist_quest_without_beat_key_leaves_null(db):
    """Old call (no beat_key) still works and leaves beat_key NULL — no auto-cancel."""
    quest = {"title": "Wolny quest", "objective": "Bez powiazania ze scena"}
    inserted = persist_quest_to_character_quests(
        db, character_id=7, campaign_id=1, quest=quest, turn_number=2
    )
    assert inserted is True
    row = db.execute(
        "SELECT beat_key FROM character_quests WHERE title='Wolny quest'"
    ).fetchone()
    assert row["beat_key"] is None, "unlinked quest must keep beat_key NULL"


# ─── Integration: full beat → quest → skip loop ──────────────────────────────

def test_spawn_quest_pinned_to_current_beat_cancels_on_skip(db, monkeypatch):
    """End-to-end: a quest spawned during an optional scene is pinned to that beat;
    when the act closes via the critical path the optional scene is skipped and the
    pinned quest auto-cancels (status 'skipped')."""
    import app.services.campaign_plan_runtime as cpr
    monkeypatch.setattr(cpr, "write_game_event", lambda *a, **k: None)
    _seed_plan(db, _plan_two_critical_one_optional())

    # 1) Player clears the intro critical beat → optional B_side becomes current.
    mark_beat_visited(1, "A_intro", 1, db)
    current = get_current_beat_key(get_plan(1, db))
    assert current == "B_side"

    # 2) Narrator spawns a side quest during that scene → pinned to current beat.
    persist_quest_to_character_quests(
        db, character_id=7, campaign_id=1,
        quest={"title": "Poboczny watek", "objective": "Pomoz wiesniakom"},
        turn_number=2, beat_key=current,
    )

    # 3) Player heads straight to the finale, skipping B_side → act closes,
    #    B_side marked skipped, mark_beat_visited fires cancel_quests_for_skipped.
    mark_beat_visited(1, "C_finale", 3, db)

    plan = get_plan(1, db)
    b_side = next(b for b in plan["acts"][0]["key_beats"] if b["beat_key"] == "B_side")
    assert b_side.get("skipped") is True, "optional beat must be skipped on act close"
    status = db.execute(
        "SELECT status FROM character_quests WHERE title='Poboczny watek'"
    ).fetchone()["status"]
    assert status == "skipped", "quest pinned to the skipped beat must auto-cancel"


def test_unpinned_quest_survives_skip(db, monkeypatch):
    """A quest with no beat_key is never touched by the skip-cancel sweep."""
    import app.services.campaign_plan_runtime as cpr
    monkeypatch.setattr(cpr, "write_game_event", lambda *a, **k: None)
    _seed_plan(db, _plan_two_critical_one_optional())
    persist_quest_to_character_quests(
        db, character_id=7, campaign_id=1,
        quest={"title": "Wolny", "objective": "Bez beatu"}, turn_number=1,
    )
    mark_beat_visited(1, "A_intro", 1, db)
    mark_beat_visited(1, "C_finale", 2, db)  # closes act → B_side skipped
    status = db.execute(
        "SELECT status FROM character_quests WHERE title='Wolny'"
    ).fetchone()["status"]
    assert status == "active", "unlinked quest must stay active through a skip"
