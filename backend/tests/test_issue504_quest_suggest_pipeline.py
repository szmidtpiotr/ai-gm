"""TDD: Issue #504 — C10 QUEST_SUGGEST full pipeline: parse → world_state → snapshot.

Tests the INTEGRATION path, not just the parser in isolation:
  1. parse_quest_suggest finds tags in JSON-wrapped streaming narrative
  2. set_world_state_flags persists to game_sessions.active_quests
  3. build_snapshot includes active_quests (i.e., World State tab shows quests)
  4. Deduplication: same quest not added twice
  5. Tag stripped from clean_text before storing

The unit tests in test_issue364_quest_suggest.py only verify the parser functions.
These tests verify the DB round-trip that the streaming path performs in turns.py (C10 block).
"""
import sys
import os
import json
import sqlite3
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.quest_suggest_parser import parse_quest_suggest, strip_quest_suggest_tags
from app.services.world_state_service import (
    get_world_state_flags,
    set_world_state_flags,
    build_snapshot,
)
from app.api.turns import _extract_narrative_for_cues, _repack_narrative

DB_PATH = "/data/ai_gm.db"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_test_session(campaign_id: int) -> None:
    """Ensure a clean game_sessions row exists for the test campaign."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "DELETE FROM game_sessions WHERE campaign_id = ?", (campaign_id,)
        )
        conn.execute(
            "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (?, ?, '{}')",
            (f"test-{campaign_id}", campaign_id),
        )
        conn.commit()
    finally:
        conn.close()


def _cleanup_test_session(campaign_id: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (campaign_id,))
        conn.execute("DELETE FROM world_state_snapshots WHERE campaign_id = ?", (campaign_id,))
        conn.commit()
    finally:
        conn.close()


# ── Test 1: full C10 pipeline on plain-text narrative ────────────────────────

def test_c10_saves_quest_plain_text():
    """C10 pipeline: parse tag → save to game_sessions → visible in get_world_state_flags."""
    CAMP = 999900
    _make_test_session(CAMP)
    try:
        narrative = (
            "Strażnik leży w rowie, ledwo żywy.\n"
            "[QUEST_SUGGEST: Ranny strażnik | Pomóż rannemu lub wysłuchaj go | Wiedza o kaplicy]\n"
            "Możesz mu pomóc lub iść dalej."
        )

        # Simulate C10 block from turns.py
        quests = parse_quest_suggest(narrative)
        assert len(quests) == 1, "parser must find 1 quest in plain-text narrative"
        existing = get_world_state_flags(CAMP).get("active_quests", [])
        seen = {q.get("title", "") for q in existing}
        to_add = [q for q in quests if q["title"] not in seen]
        assert len(to_add) == 1
        set_world_state_flags(CAMP, active_quests=existing + to_add)

        # Verify DB was updated
        result = get_world_state_flags(CAMP).get("active_quests", [])
        assert len(result) == 1
        assert result[0]["title"] == "Ranny strażnik"
        assert result[0]["objective"] == "Pomóż rannemu lub wysłuchaj go"
        assert result[0]["reward"] == "Wiedza o kaplicy"
        assert result[0]["status"] == "active"
    finally:
        _cleanup_test_session(CAMP)


# ── Test 2: full C10 pipeline on JSON-wrapped streaming narrative ─────────────

def test_c10_saves_quest_json_wrapped():
    """C10 pipeline with JSON-mode LLM response (default streaming format)."""
    CAMP = 999901
    _make_test_session(CAMP)
    try:
        # LLM typically returns JSON with narrative field
        response_json = json.dumps({
            "narrative": (
                "Opuszczasz kaplicę.\n"
                "[QUEST_SUGGEST: Ranny z traktu | Pomóż rannemu strażnikowi | Wiedza o wydarzeniach]\n"
                "Widzisz dym na horyzoncie."
            ),
            "location_intent": None,
            "suggested_actions": [{"label": "Idź do dymu", "action": "TRAVEL:camp", "enabled": True}],
        }, ensure_ascii=False)

        # Simulate what turns.py streaming path does with clean_text
        _narr_qs, _pjson_qs = _extract_narrative_for_cues(response_json)
        assert "QUEST_SUGGEST" in _narr_qs, "_extract_narrative_for_cues must expose tag in narrative"

        # C10 save
        quests = parse_quest_suggest(_narr_qs)
        assert len(quests) == 1
        existing = get_world_state_flags(CAMP).get("active_quests", [])
        seen = {q.get("title", "") for q in existing}
        to_add = [q for q in quests if q["title"] not in seen]
        set_world_state_flags(CAMP, active_quests=existing + to_add)

        # C10 strip
        clean_text = _repack_narrative(response_json, strip_quest_suggest_tags(_narr_qs), _pjson_qs)

        # Tag must be gone from clean_text
        assert "QUEST_SUGGEST" not in clean_text, "tag must be stripped before storing"

        # Quest must be in DB
        result = get_world_state_flags(CAMP).get("active_quests", [])
        assert len(result) == 1
        assert result[0]["title"] == "Ranny z traktu"
    finally:
        _cleanup_test_session(CAMP)


# ── Test 3: build_snapshot includes active_quests (World State tab source) ────

def test_snapshot_includes_quest_after_c10():
    """After C10 saves quest to game_sessions, build_snapshot reflects it."""
    CAMP = 999902
    _make_test_session(CAMP)
    # Insert a minimal campaign_turns row so turn_number resolves to 1
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO campaign_turns (campaign_id, character_id, user_text, route, assistant_text, turn_number) "
            "VALUES (?, 0, 'test', 'narrative', 'test', 1)",
            (CAMP,),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        # Simulate C10 saving quest
        quests = [{"title": "Test Quest", "objective": "Idź do zamku", "reward": "100 XP", "status": "active"}]
        set_world_state_flags(CAMP, active_quests=quests)

        # Build snapshot (what auto_save_snapshot calls)
        snap = build_snapshot(CAMP)
        assert "active_quests" in snap, "snapshot must have active_quests key"
        assert len(snap["active_quests"]) == 1, "snapshot must contain the saved quest"
        assert snap["active_quests"][0]["title"] == "Test Quest"
    finally:
        conn2 = sqlite3.connect(DB_PATH)
        try:
            conn2.execute("DELETE FROM campaign_turns WHERE campaign_id=?", (CAMP,))
            conn2.commit()
        finally:
            conn2.close()
        _cleanup_test_session(CAMP)


# ── Test 4: deduplication — same quest not added twice ───────────────────────

def test_c10_deduplication():
    """If quest with same title already exists, C10 must not add a duplicate."""
    CAMP = 999903
    _make_test_session(CAMP)
    try:
        existing_quest = {"title": "Ranny z traktu", "objective": "Pomóż", "reward": "Wiedza", "status": "active"}
        set_world_state_flags(CAMP, active_quests=[existing_quest])

        # Simulate C10 finding the same quest again
        narrative = "[QUEST_SUGGEST: Ranny z traktu | Pomóż rannemu | Wiedza i wdzięczność]"
        quests = parse_quest_suggest(narrative)
        existing = get_world_state_flags(CAMP).get("active_quests", [])
        seen = {q.get("title", "") for q in existing}
        to_add = [q for q in quests if q["title"] not in seen]
        assert len(to_add) == 0, "duplicate quest must not be added"

        # DB must still have only 1 quest
        result = get_world_state_flags(CAMP).get("active_quests", [])
        assert len(result) == 1
    finally:
        _cleanup_test_session(CAMP)


# ── Backward compat: non-quest narrative unchanged ───────────────────────────

def test_no_quest_tag_no_change():
    """Narrative without QUEST_SUGGEST tag: no quests added, clean_text unchanged."""
    CAMP = 999904
    _make_test_session(CAMP)
    try:
        narrative = "Strażnik kiwa głową i odchodzi bez słowa."
        assert parse_quest_suggest(narrative) == []
        assert strip_quest_suggest_tags(narrative) == narrative

        # DB must stay empty
        set_world_state_flags(CAMP, active_quests=[])  # ensure baseline
        quests = parse_quest_suggest(narrative)
        assert quests == []
        result = get_world_state_flags(CAMP).get("active_quests", [])
        assert result == []
    finally:
        _cleanup_test_session(CAMP)
