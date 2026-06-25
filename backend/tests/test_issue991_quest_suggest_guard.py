"""TDD: Issue #991 — quest suggest guard + arc advance after quest completion."""
import json
import sqlite3
import sys
import os

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/app")

import pytest


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def mem_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS character_quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            campaign_id INTEGER,
            quest_type TEXT DEFAULT 'main',
            title TEXT,
            narrative TEXT,
            status TEXT DEFAULT 'active',
            created_turn INTEGER,
            completed_turn INTEGER,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER UNIQUE,
            session_flags TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gm_plan_json TEXT
        );
    """)
    yield conn
    conn.close()


def _insert_quest(conn, character_id, campaign_id, title, status="active"):
    conn.execute(
        "INSERT INTO character_quests (character_id, campaign_id, title, status, created_turn) VALUES (?,?,?,?,1)",
        (character_id, campaign_id, title, status),
    )
    conn.commit()


def _insert_session(conn, campaign_id, flags=None):
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?,?)",
        (campaign_id, json.dumps(flags or {})),
    )
    conn.commit()


# ─── Test 1: flag set when quest completes and no active quests remain ────────

def test_quest_suggest_needed_set_when_no_active_quests(mem_db):
    """After last active quest completes, flag quest_suggest_needed in session_flags."""
    from app.services.quest_persist_service import check_and_set_quest_suggest_needed

    character_id, campaign_id = 10, 20
    _insert_quest(mem_db, character_id, campaign_id, "Nocna przesyłka", status="completed")
    _insert_session(mem_db, campaign_id)

    result = check_and_set_quest_suggest_needed(mem_db, character_id, campaign_id, "Nocna przesyłka")
    assert result is True, "Should return True when no active quests remain"

    row = mem_db.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=?", (campaign_id,)).fetchone()
    sf = json.loads(row["session_flags"])
    assert "quest_suggest_needed" in sf, "Flag not written to session_flags"
    assert sf["quest_suggest_needed"]["last_completed"] == "Nocna przesyłka"


# ─── Test 2: flag NOT set when active quests still exist ─────────────────────

def test_quest_suggest_needed_not_set_when_active_quests_remain(mem_db):
    """Flag must not be set if character still has active quests."""
    from app.services.quest_persist_service import check_and_set_quest_suggest_needed

    character_id, campaign_id = 10, 21
    _insert_quest(mem_db, character_id, campaign_id, "Nocna przesyłka", status="completed")
    _insert_quest(mem_db, character_id, campaign_id, "Ślad bandytów", status="active")
    _insert_session(mem_db, campaign_id)

    result = check_and_set_quest_suggest_needed(mem_db, character_id, campaign_id, "Nocna przesyłka")
    assert result is False, "Should return False when active quests remain"

    row = mem_db.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=?", (campaign_id,)).fetchone()
    sf = json.loads(row["session_flags"])
    assert "quest_suggest_needed" not in sf, "Flag must not appear when active quest exists"


# ─── Test 3: tutorial arc advances to next arc ────────────────────────────────

def test_advance_gm_plan_arc_from_tutorial(mem_db):
    """arc_tutorial → next arc when quest completes."""
    from app.services.gm_plan_schema import advance_gm_plan_arc

    raw_plan = json.dumps({
        "schema_version": 2,
        "active_arc_id": "arc_tutorial",
        "arcs": {
            "arc_tutorial": {"id": "arc_tutorial", "title": "Tutorial", "status": "active", "scene_goals": ["Dostarcz paczkę"]},
            "arc_slad": {"id": "arc_slad", "title": "Ślad Jednookiego", "status": "draft", "scene_goals": ["Znajdź bandytów"]},
        },
        "engine_private": {},
    })

    new_plan, did_advance = advance_gm_plan_arc(raw_plan)
    assert did_advance is True, "Should advance from tutorial arc"
    assert new_plan["active_arc_id"] == "arc_slad", f"Expected arc_slad, got {new_plan['active_arc_id']}"
    assert new_plan["arcs"]["arc_tutorial"]["status"] == "closed"
    assert new_plan["arcs"]["arc_slad"]["status"] == "active"


# ─── Test 4: non-tutorial arc not auto-advanced ───────────────────────────────

def test_advance_gm_plan_arc_no_change_for_non_tutorial(mem_db):
    """Non-tutorial arcs should not be auto-advanced."""
    from app.services.gm_plan_schema import advance_gm_plan_arc

    raw_plan = json.dumps({
        "schema_version": 2,
        "active_arc_id": "arc_main_story",
        "arcs": {
            "arc_main_story": {"id": "arc_main_story", "title": "Główna historia", "status": "active", "scene_goals": []},
            "arc_finale": {"id": "arc_finale", "title": "Finał", "status": "draft", "scene_goals": []},
        },
        "engine_private": {},
    })

    new_plan, did_advance = advance_gm_plan_arc(raw_plan)
    assert did_advance is False, "Non-tutorial arc should not auto-advance"
    assert new_plan["active_arc_id"] == "arc_main_story"


# ─── Test 5: directive contains expected keywords ─────────────────────────────

def test_build_quest_suggest_directive_content(mem_db):
    """Directive injected into LLM context must contain QUEST_SUGGEST and key info."""
    from app.services.quest_persist_service import build_quest_suggest_directive

    directive = build_quest_suggest_directive(last_completed="Nocna przesyłka", turns_waiting=1)
    assert "QUEST_SUGGEST" in directive, "Directive must mention QUEST_SUGGEST tag"
    assert "Nocna przesyłka" in directive
    assert "quest" in directive.lower() or "zadanie" in directive.lower() or "cel" in directive.lower()


def test_build_quest_suggest_directive_urgent_after_n_turns(mem_db):
    """After N turns without quest, directive must escalate urgency."""
    from app.services.quest_persist_service import build_quest_suggest_directive

    directive_late = build_quest_suggest_directive(last_completed="Nocna przesyłka", turns_waiting=5)
    directive_early = build_quest_suggest_directive(last_completed="Nocna przesyłka", turns_waiting=1)
    # Late directive must be stronger (PILNE or urgency marker)
    assert len(directive_late) > len(directive_early) or "PILNE" in directive_late or "MUSI" in directive_late


# ─── Test 6: backward compat — existing quest_persist_service functions unchanged ──

def test_existing_quest_functions_still_work(mem_db):
    """persist_quest_to_character_quests and complete_quest_in_character_quests unchanged."""
    from app.services.quest_persist_service import (
        persist_quest_to_character_quests,
        complete_quest_in_character_quests,
    )

    character_id, campaign_id = 99, 99
    quest = {"title": "Test Quest", "objective": "Do something", "reward": "50 gold", "status": "active"}
    inserted = persist_quest_to_character_quests(mem_db, character_id, campaign_id, quest, turn_number=1)
    assert inserted is True

    completed = complete_quest_in_character_quests(mem_db, character_id, campaign_id, "Test Quest", completed_turn=5)
    assert completed is True

    row = mem_db.execute(
        "SELECT status, completed_turn FROM character_quests WHERE character_id=? AND campaign_id=? AND title=?",
        (character_id, campaign_id, "Test Quest"),
    ).fetchone()
    assert row["status"] == "completed"
    assert row["completed_turn"] == 5
