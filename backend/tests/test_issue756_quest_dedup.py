"""TDD: Issue #756 — quest dedup by normalized objective + context block injection."""
import sqlite3
import sys

sys.path.insert(0, "/app")

import pytest
from app.services.quest_persist_service import persist_quest_to_character_quests


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE character_quests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        character_id INTEGER NOT NULL,
        campaign_id INTEGER NOT NULL,
        quest_type TEXT DEFAULT 'main',
        title TEXT NOT NULL,
        narrative TEXT,
        status TEXT DEFAULT 'active',
        created_turn INTEGER,
        completed_turn INTEGER,
        updated_at TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    conn.execute("""CREATE TABLE campaign_turns (
        id INTEGER PRIMARY KEY,
        campaign_id INTEGER,
        turn_number INTEGER
    )""")
    conn.commit()
    return conn


# ─── Test 1: core bug — same objective, different title → rejected ─────────────

def test_dedup_by_normalized_objective():
    """Same goal (75% word overlap), different title → second insert rejected."""
    conn = make_conn()
    q1 = {"title": "Nocna przesyłka", "objective": "Zanieś paczkę pod starą kapliczkę za chatami"}
    q2 = {"title": "Posłaniec po zmroku", "objective": "Zanieś pergamin pod starą kapliczkę za chatami"}

    r1 = persist_quest_to_character_quests(conn, 1, 1, q1, turn_number=8)
    r2 = persist_quest_to_character_quests(conn, 1, 1, q2, turn_number=12)

    assert r1 is True, "First quest should be inserted"
    assert r2 is False, "Similar-objective quest (75% Jaccard) should be rejected as duplicate"

    count = conn.execute(
        "SELECT COUNT(*) FROM character_quests WHERE character_id=1 AND campaign_id=1 AND status='active'"
    ).fetchone()[0]
    assert count == 1, f"Expected 1 quest in DB, got {count}"


# ─── Test 2: backward compat — exact title still deduped ──────────────────────

def test_dedup_exact_title_still_works():
    """Exact title match still rejected (no regression)."""
    conn = make_conn()
    q = {"title": "Nocna przesyłka", "objective": "Dostarcz list do Marty"}

    r1 = persist_quest_to_character_quests(conn, 1, 1, q, turn_number=1)
    r2 = persist_quest_to_character_quests(conn, 1, 1, q, turn_number=2)

    assert r1 is True
    assert r2 is False


# ─── Test 3: genuinely different quests both inserted ─────────────────────────

def test_different_objectives_both_inserted():
    """Low word overlap → both quests inserted."""
    conn = make_conn()
    q1 = {"title": "Odnaleźć syna", "objective": "Przeszukaj las na zachód od wioski znajdź syna Marela"}
    q2 = {"title": "Zadanie kupca", "objective": "Przynieś beczkę wina z piwnicy zamku górującego nad miastem"}

    r1 = persist_quest_to_character_quests(conn, 1, 1, q1, turn_number=1)
    r2 = persist_quest_to_character_quests(conn, 1, 1, q2, turn_number=2)

    assert r1 is True, "First quest should be inserted"
    assert r2 is True, "Different-objective quest should also be inserted"


# ─── Test 4: build_quest_context_block returns non-empty when quests exist ────

def test_quest_context_block_built():
    """build_quest_context_block returns block with title when active quests exist."""
    from app.services.quest_persist_service import build_quest_context_block

    conn = make_conn()
    q = {"title": "Nocna przesyłka", "objective": "Zanieś paczkę pod kapliczkę"}
    persist_quest_to_character_quests(conn, 10, 5, q, turn_number=1)

    block = build_quest_context_block(conn, character_id=10, campaign_id=5)

    assert block, "Block should not be empty when active quests exist"
    assert "Nocna przesyłka" in block, "Block should contain quest title"
    assert "QUESTY" in block.upper(), "Block should have QUESTY header"


# ─── Test 5: empty block when no active quests ────────────────────────────────

def test_quest_context_block_empty_when_no_quests():
    """build_quest_context_block returns '' when no active quests."""
    from app.services.quest_persist_service import build_quest_context_block

    conn = make_conn()
    block = build_quest_context_block(conn, character_id=99, campaign_id=99)

    assert block == "", "Should return empty string with no active quests"


# ─── Test 6: completed quests ignored in objective dedup ─────────────────────

def test_completed_quest_not_counted_in_dedup():
    """Completed quest with same objective → new insert accepted."""
    conn = make_conn()
    q1 = {"title": "Nocna przesyłka", "objective": "Zanieś paczkę pod starą kapliczkę za chatami"}
    persist_quest_to_character_quests(conn, 1, 1, q1, turn_number=1)
    conn.execute("UPDATE character_quests SET status='completed' WHERE character_id=1 AND campaign_id=1")
    conn.commit()

    q2 = {"title": "Nocna przesyłka II", "objective": "Zanieś paczkę pod starą kapliczkę za chatami"}
    r2 = persist_quest_to_character_quests(conn, 1, 1, q2, turn_number=5)

    assert r2 is True, "Completed quest should not block re-insert of same objective"
