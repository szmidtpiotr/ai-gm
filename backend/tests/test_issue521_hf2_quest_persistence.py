"""TDD: Issue #524 / HF-2 — Quest persistence to character_quests table.

QUEST_SUGGEST tag previously only wrote to session_flags.active_quests (JSON blob).
After fix: persist_quest_to_character_quests() and complete_quest_in_character_quests()
from quest_persist_service are called from turns.py, ensuring DB row exists.
"""
import sqlite3
import pytest
import sys

sys.path.insert(0, "/app")


# ── Schema helper ─────────────────────────────────────────────────────────────

def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE character_quests (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id         INTEGER NOT NULL,
            campaign_id          INTEGER NOT NULL,
            quest_type           TEXT NOT NULL DEFAULT 'main',
            title                TEXT NOT NULL,
            narrative            TEXT NOT NULL DEFAULT '',
            status               TEXT NOT NULL DEFAULT 'active',
            resolution           TEXT DEFAULT NULL,
            resolution_narrative TEXT DEFAULT NULL,
            created_turn         INTEGER,
            completed_turn       INTEGER DEFAULT NULL,
            created_at           TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE campaign_turns (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id  INTEGER NOT NULL,
            turn_number  INTEGER NOT NULL DEFAULT 1,
            user_text    TEXT DEFAULT '',
            assistant_text TEXT DEFAULT ''
        );
    """)
    return conn


# ── RED: these import from a module that doesn't exist yet ────────────────────

def test_persist_quest_inserts_into_character_quests():
    """persist_quest_to_character_quests() must INSERT row with status=active."""
    from app.services.quest_persist_service import persist_quest_to_character_quests

    conn = _make_db()
    quest = {"title": "Zabij bandytę", "objective": "Wróg czeka w lesie", "reward": "50 XP"}

    inserted = persist_quest_to_character_quests(conn, character_id=42, campaign_id=7, quest=quest)

    assert inserted is True
    row = conn.execute(
        "SELECT * FROM character_quests WHERE character_id=42 AND campaign_id=7 AND title=?",
        ("Zabij bandytę",),
    ).fetchone()
    assert row is not None, "quest must exist in character_quests"
    assert row["status"] == "active"
    assert row["narrative"] == "Wróg czeka w lesie"
    assert row["quest_type"] == "main"


def test_duplicate_quest_not_inserted_twice():
    """Same title + character + campaign: second call returns False, only 1 row."""
    from app.services.quest_persist_service import persist_quest_to_character_quests

    conn = _make_db()
    quest = {"title": "Znajdź ziele", "objective": "W lesie", "reward": "30 XP"}

    persist_quest_to_character_quests(conn, 42, 7, quest)
    second = persist_quest_to_character_quests(conn, 42, 7, quest)

    assert second is False
    count = conn.execute(
        "SELECT COUNT(*) FROM character_quests WHERE character_id=42 AND campaign_id=7 AND title=?",
        ("Znajdź ziele",),
    ).fetchone()[0]
    assert count == 1


def test_multiple_quests_all_inserted():
    """Batch insert: all quests end up in character_quests."""
    from app.services.quest_persist_service import persist_quest_to_character_quests

    conn = _make_db()
    quests = [
        {"title": "Quest A", "objective": "Cel A", "reward": "10 XP"},
        {"title": "Quest B", "objective": "Cel B", "reward": "20 XP"},
        {"title": "Quest C", "objective": "Cel C", "reward": "30 XP"},
    ]
    for q in quests:
        persist_quest_to_character_quests(conn, 42, 7, q)

    count = conn.execute(
        "SELECT COUNT(*) FROM character_quests WHERE character_id=42 AND campaign_id=7",
    ).fetchone()[0]
    assert count == 3


def test_persist_quest_uses_next_turn_number():
    """created_turn = MAX(turn_number)+1 from campaign_turns."""
    from app.services.quest_persist_service import persist_quest_to_character_quests

    conn = _make_db()
    for i in range(1, 4):
        conn.execute("INSERT INTO campaign_turns (campaign_id, turn_number) VALUES (?,?)", (7, i))
    conn.commit()

    quest = {"title": "Turn quest", "objective": "Sprawdź turę", "reward": "0 XP"}
    persist_quest_to_character_quests(conn, 42, 7, quest)

    row = conn.execute(
        "SELECT created_turn FROM character_quests WHERE title='Turn quest'",
    ).fetchone()
    assert row["created_turn"] == 4, f"expected turn 4 (3+1), got {row['created_turn']}"


def test_complete_quest_updates_status_and_turn():
    """complete_quest_in_character_quests() sets status=completed and completed_turn."""
    from app.services.quest_persist_service import (
        persist_quest_to_character_quests,
        complete_quest_in_character_quests,
    )

    conn = _make_db()
    quest = {"title": "Zabij bandytę", "objective": "bandyta", "reward": "50 XP"}
    persist_quest_to_character_quests(conn, 42, 7, quest)

    complete_quest_in_character_quests(conn, character_id=42, campaign_id=7, title="Zabij bandytę", completed_turn=5)

    row = conn.execute(
        "SELECT status, completed_turn FROM character_quests WHERE character_id=42 AND campaign_id=7 AND title=?",
        ("Zabij bandytę",),
    ).fetchone()
    assert row["status"] == "completed"
    assert row["completed_turn"] == 5


# ── Backward compat: parsers still work ──────────────────────────────────────

def test_quest_suggest_parser_still_works():
    """parse_quest_suggest output still has title/objective/reward."""
    from app.services.quest_suggest_parser import parse_quest_suggest

    text = "[QUEST_SUGGEST: Zabij smoka | Pokonaj smoka w jaskini | 200 XP]"
    quests = parse_quest_suggest(text)

    assert len(quests) == 1
    assert quests[0]["title"] == "Zabij smoka"
    assert quests[0]["objective"] == "Pokonaj smoka w jaskini"
    assert quests[0]["status"] == "active"


def test_quest_checker_still_works():
    """check_kill_quest still returns completed quests correctly."""
    from app.services.quest_checker import check_kill_quest

    active = [
        {"title": "Zabij bandytę", "objective": "bandyta", "reward": "50 XP", "status": "active"},
    ]
    updated, completed = check_kill_quest(active, "Stary bandyta z lasu")

    assert len(completed) == 1
    assert completed[0]["status"] == "completed"
