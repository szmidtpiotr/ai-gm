"""TDD: Issue #776 — [QUEST_COMPLETE:title] must flip character_quests status AND grant XP."""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _fixtures_schema import table_sql

from app.services.xp_sources import process_narrative_xp_tags, _QUEST_RE


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE character_quests (
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
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            sheet_json TEXT DEFAULT '{}',
            visited_location_keys TEXT
        );
        CREATE TABLE character_xp_grants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            campaign_id INTEGER,
            amount INTEGER,
            reason TEXT,
            source TEXT,
            source_key TEXT,
            turn_number INTEGER,
            granted_by_user_id INTEGER DEFAULT 0
        );
        """ + table_sql("game_config_xp_rewards") + """
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            turn_number INTEGER,
            created_at TEXT
        );
    """)
    conn.execute("INSERT INTO game_config_xp_rewards VALUES ('campaign.side_quest', 50, 1)")
    conn.execute("INSERT INTO characters (id, sheet_json) VALUES (42, '{}')")
    conn.commit()
    return conn


def _insert_quest(conn, character_id, campaign_id, title, status="active"):
    conn.execute(
        "INSERT INTO character_quests (character_id, campaign_id, title, status, created_turn) VALUES (?,?,?,?,1)",
        (character_id, campaign_id, title, status),
    )
    conn.commit()


# ─── Test 1: QUEST_COMPLETE tag with spaces in title flips status AND grants XP ──

def test_quest_complete_tag_flips_status_and_grants_xp():
    """[QUEST_COMPLETE:Nocna przesyłka] must set status=completed AND grant XP."""
    conn = _make_db()
    _insert_quest(conn, 42, 7, "Nocna przesyłka")

    narrative = "Medali przekazany. [QUEST_COMPLETE:Nocna przesyłka] Strażnik kiwa głową z uznaniem."
    process_narrative_xp_tags(narrative, conn, character_id=42, campaign_id=7, turn_number=35)

    row = conn.execute(
        "SELECT status, completed_turn FROM character_quests WHERE character_id=42 AND title='Nocna przesyłka'"
    ).fetchone()
    assert row is not None, "Quest row missing"
    assert row["status"] == "completed", f"Expected status=completed, got {row['status']}"
    assert row["completed_turn"] is not None, "completed_turn must be set"

    xp_row = conn.execute(
        "SELECT amount FROM character_xp_grants WHERE character_id=42 AND source='campaign.side_quest'"
    ).fetchone()
    assert xp_row is not None, "XP grant not found"
    assert xp_row["amount"] == 50, f"Expected 50 XP, got {xp_row['amount']}"


# ─── Test 2: QUEST_COMPLETE regex allows spaces in title ──────────────────────

def test_quest_complete_regex_matches_title_with_spaces():
    """_QUEST_RE must match titles containing spaces."""
    narrative = "[QUEST_COMPLETE:Nocna przesyłka]"
    matches = list(_QUEST_RE.finditer(narrative))
    assert len(matches) == 1, f"Expected 1 match, got {len(matches)} — regex blocks spaces"
    assert matches[0].group(1).strip() == "Nocna przesyłka"


# ─── Test 3: QUEST_COMPLETE with simple key (no spaces) still works ───────────

def test_quest_complete_tag_simple_key_still_works():
    """Backward compat: single-word key continues to complete quest."""
    conn = _make_db()
    _insert_quest(conn, 42, 7, "kill_bandits")

    narrative = "Bandyci pokonani. [QUEST_COMPLETE:kill_bandits] Wioska bezpieczna."
    process_narrative_xp_tags(narrative, conn, character_id=42, campaign_id=7, turn_number=10)

    row = conn.execute(
        "SELECT status FROM character_quests WHERE character_id=42 AND title='kill_bandits'"
    ).fetchone()
    assert row["status"] == "completed", f"Simple-key quest not completed: {row['status']}"


# ─── Test 4: Already completed quest not double-processed ────────────────────

def test_quest_complete_tag_no_double_processing():
    """If quest already completed, a second QUEST_COMPLETE tag grants no extra XP."""
    conn = _make_db()
    _insert_quest(conn, 42, 7, "Nocna przesyłka", status="completed")

    narrative = "[QUEST_COMPLETE:Nocna przesyłka]"
    process_narrative_xp_tags(narrative, conn, character_id=42, campaign_id=7, turn_number=36)

    xp_rows = conn.execute(
        "SELECT count(*) as cnt FROM character_xp_grants WHERE character_id=42 AND source='campaign.side_quest'"
    ).fetchone()
    assert xp_rows["cnt"] == 0, "Double XP grant on already-completed quest"
