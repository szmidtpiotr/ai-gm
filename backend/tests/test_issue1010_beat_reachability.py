"""TDD: Issue #1010 — Beat reachability: teach [BEAT_COMPLETE], expose beat_keys
in turn context, warn on orphan beats, and close the live-tor mark-visited gap.

Three torn links in the beat-completion pipeline:
  1. narrator never told to emit [BEAT_COMPLETE]  → prompt edit (verified here as contract)
  2. turn context never lists active-act beat_keys → get_active_act_beat_keys / context block
  3. live tor parses the tag for XP only, never marks the beat visited → wiring (covered by
     mark_beat_visited still working + the live-tor hook checked separately)
"""
import json
import sqlite3
import pytest

from app.services.campaign_plan_runtime import (
    get_plan, save_plan, mark_beat_visited,
    get_active_act_beat_keys, get_beat_completion_context_block,
    find_orphan_beats, is_plan_complete,
)

SAMPLE_PLAN = {
    "title": "Test Campaign",
    "active_act": 1,
    "acts": [
        {
            "number": 1, "title": "Act 1", "summary": "The beginning.",
            "key_beats": [
                # narrative-only beat: no objective_type → only reachable via [BEAT_COMPLETE]
                {"beat_key": "confront_villain", "title": "Confront villain", "visited": False},
                # objective beat: auto-completes via event → not an orphan
                {"beat_key": "kill_boss", "title": "Kill boss", "visited": False,
                 "objective_type": "kill_enemy", "objective_value": "bandyta"},
            ],
            "completed": False,
        },
        {
            "number": 2, "title": "Act 2", "summary": "The end.",
            "key_beats": [
                {"beat_key": "epilogue", "title": "Epilogue", "visited": False},
            ],
            "completed": False,
        },
    ],
}


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY, gm_plan_json TEXT DEFAULT '{}')")
    conn.execute("INSERT INTO campaigns VALUES (1, ?)", (json.dumps(SAMPLE_PLAN),))
    conn.commit()
    yield conn
    conn.close()


# ─── Test główny: beat_keys aktywnego aktu ─────────────────────────────────

def test_get_active_act_beat_keys_lists_unvisited(db):
    """Active act exposes its unvisited beat_keys so the narrator knows what to close."""
    plan = get_plan(1, db)
    keys = get_active_act_beat_keys(plan)
    assert "confront_villain" in keys
    assert "kill_boss" in keys


def test_get_active_act_beat_keys_skips_visited(db):
    """A visited beat drops off the list — narrator should not re-close it."""
    mark_beat_visited(1, "kill_boss", 3, db)
    plan = get_plan(1, db)
    keys = get_active_act_beat_keys(plan)
    assert "kill_boss" not in keys
    assert "confront_villain" in keys


def test_get_active_act_beat_keys_follows_active_act_pointer(db):
    """After act 1 completes, beat_keys come from act 2, not act 1."""
    mark_beat_visited(1, "confront_villain", 1, db)
    mark_beat_visited(1, "kill_boss", 2, db)  # both visited → act advances to 2
    plan = get_plan(1, db)
    keys = get_active_act_beat_keys(plan)
    assert keys == ["epilogue"]


# ─── Context block dla narratora ────────────────────────────────────────────

def test_beat_completion_context_block_lists_keys_and_tag(db):
    """The narrator-facing block names every active beat_key and teaches the tag."""
    block = get_beat_completion_context_block(1, db)
    assert "confront_villain" in block
    assert "kill_boss" in block
    assert "[BEAT_COMPLETE" in block


def test_beat_completion_context_block_empty_when_no_beats(db):
    """No unvisited beats → empty block (nothing to nag the narrator about)."""
    mark_beat_visited(1, "confront_villain", 1, db)
    mark_beat_visited(1, "kill_boss", 2, db)
    mark_beat_visited(1, "epilogue", 3, db)
    assert get_beat_completion_context_block(1, db).strip() == ""


# ─── Walidator orphan-beatów ────────────────────────────────────────────────

def test_find_orphan_beats_flags_narrative_only_beat(db):
    """A beat with no objective_type and no narrative-close marker is an orphan."""
    plan = get_plan(1, db)
    orphans = find_orphan_beats(plan)
    assert "confront_villain" in orphans
    assert "epilogue" in orphans


def test_find_orphan_beats_objective_beat_not_orphan(db):
    """A beat with an objective_type can auto-complete → never an orphan."""
    plan = get_plan(1, db)
    orphans = find_orphan_beats(plan)
    assert "kill_boss" not in orphans


def test_find_orphan_beats_narrative_close_marker_not_orphan():
    """A beat explicitly flagged narrative-close is intentional, not an orphan."""
    plan = {
        "active_act": 1,
        "acts": [{"key_beats": [
            {"beat_key": "ritual", "objective_type": None, "narrative_close": True},
        ]}],
    }
    assert find_orphan_beats(plan) == []


# ─── Backward compatibility ─────────────────────────────────────────────────

def test_mark_beat_visited_still_works(db):
    """Existing beat-marking path is untouched."""
    assert mark_beat_visited(1, "confront_villain", 5, db) is True
    plan = get_plan(1, db)
    beat = plan["acts"][0]["key_beats"][0]
    assert beat["visited"] is True


def test_victory_chain_after_all_beats_marked(db):
    """Marking every beat via the tag path drives is_plan_complete True (#1009 link)."""
    for key in ("confront_villain", "kill_boss", "epilogue"):
        mark_beat_visited(1, key, 9, db)
    assert is_plan_complete(get_plan(1, db)) is True
