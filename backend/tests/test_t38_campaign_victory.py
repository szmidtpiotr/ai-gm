"""TDD: T38 (#1009) — deterministic campaign finale-gate spinacz.

Victory condition = all acts/scenes traversed (every act.completed) AND 0 active
quests — UNCHANGED 1:1 from #1009. #1097 changed the ACTION on that transition:
instead of flipping campaigns.status directly, it now sets the sticky
campaigns.finale_available=1 flag (status stays 'active'); quest_suggest_needed
is still cleared. The actual status='completed' flip moved to the player-triggered
finish_campaign() (see test_issue1097_finale_gate.py). [CAMPAIGN_END] narrator tag
still closes the campaign directly (separate code path, untouched by #1097) and
quest-title completion stays case/whitespace-insensitive.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.campaign_plan_runtime import is_plan_complete, maybe_complete_campaign
from app.services.xp_sources import process_narrative_xp_tags


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'active',
            gm_plan_json TEXT,
            ended_at TEXT,
            finale_available INTEGER NOT NULL DEFAULT 0
        );
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
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            session_flags TEXT DEFAULT '{}'
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            sheet_json TEXT DEFAULT '{}',
            visited_location_keys TEXT
        );
        CREATE TABLE character_xp_grants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, campaign_id INTEGER, amount INTEGER,
            reason TEXT, source TEXT, source_key TEXT, turn_number INTEGER,
            granted_by_user_id INTEGER DEFAULT 0
        );
        CREATE TABLE game_config_xp_rewards (
            key TEXT PRIMARY KEY, xp_amount INTEGER, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, turn_number INTEGER, created_at TEXT
        );
        """
    )
    conn.execute("INSERT INTO game_config_xp_rewards VALUES ('campaign.side_quest', 50, 1)")
    conn.execute("INSERT INTO game_config_xp_rewards VALUES ('campaign.campaign_ending', 100, 1)")
    conn.execute("INSERT INTO characters (id, sheet_json) VALUES (42, '{}')")
    conn.commit()
    return conn


def _plan(*completed_flags):
    return json.dumps({"acts": [{"completed": bool(f), "key_beats": []} for f in completed_flags]})


def _seed_campaign(conn, cid=7, status="active", plan=None, flags=None):
    conn.execute(
        "INSERT INTO campaigns (id, status, gm_plan_json) VALUES (?,?,?)",
        (cid, status, plan),
    )
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?,?)",
        (cid, json.dumps(flags or {})),
    )
    conn.commit()


def _insert_quest(conn, cid, title, status="active", character_id=42):
    conn.execute(
        "INSERT INTO character_quests (character_id, campaign_id, title, status, created_turn) VALUES (?,?,?,?,1)",
        (character_id, cid, title, status),
    )
    conn.commit()


def _status(conn, cid=7):
    return conn.execute("SELECT status FROM campaigns WHERE id=?", (cid,)).fetchone()["status"]


def _finale_available(conn, cid=7):
    return bool(conn.execute("SELECT finale_available FROM campaigns WHERE id=?", (cid,)).fetchone()[0])


# ─── is_plan_complete ─────────────────────────────────────────────────────────

def test_is_plan_complete_variants():
    assert is_plan_complete(None) is False
    assert is_plan_complete({}) is False
    assert is_plan_complete({"acts": []}) is False
    assert is_plan_complete(json.loads(_plan(True, False))) is False
    assert is_plan_complete(json.loads(_plan(True, True))) is True


# ─── maybe_complete_campaign ──────────────────────────────────────────────────

def test_victory_fires_when_all_acts_done_and_no_quests():
    conn = _make_db()
    _seed_campaign(conn, plan=_plan(True, True), flags={"quest_suggest_needed": {"x": 1}})
    fired = maybe_complete_campaign(7, 42, 12, conn)
    assert fired is True
    # #1097: gate opens, status stays 'active' — player finishes manually via /finish.
    assert _status(conn) == "active"
    assert _finale_available(conn) is True
    # quest_suggest_needed must be cleared so narrator isn't nudged for a new quest
    sf = json.loads(
        conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=7").fetchone()["session_flags"]
    )
    assert "quest_suggest_needed" not in sf


def test_victory_blocked_by_active_quest():
    conn = _make_db()
    _seed_campaign(conn, plan=_plan(True, True))
    _insert_quest(conn, 7, "Odbij twierdzę", status="active")
    assert maybe_complete_campaign(7, 42, 5, conn) is False
    assert _status(conn) == "active"
    assert _finale_available(conn) is False


def test_victory_blocked_by_incomplete_act():
    conn = _make_db()
    _seed_campaign(conn, plan=_plan(True, False))
    assert maybe_complete_campaign(7, 42, 5, conn) is False
    assert _status(conn) == "active"
    assert _finale_available(conn) is False


def test_victory_idempotent_on_terminal_status():
    conn = _make_db()
    _seed_campaign(conn, status="ended", plan=_plan(True, True))
    assert maybe_complete_campaign(7, 42, 5, conn) is False
    assert _status(conn) == "ended"


def test_victory_blocked_when_no_plan():
    conn = _make_db()
    _seed_campaign(conn, plan=None)
    assert maybe_complete_campaign(7, 42, 5, conn) is False
    assert _status(conn) == "active"


# ─── integration via process_narrative_xp_tags ────────────────────────────────

def test_completing_last_quest_triggers_victory_case_insensitive():
    """Narrator restates title with different case/spaces — quest still completes,
    then the spinacz opens the finale gate (all acts already done). #1097: status
    stays 'active' — only finale_available flips; player finishes manually."""
    conn = _make_db()
    _seed_campaign(conn, plan=_plan(True, True))
    _insert_quest(conn, 7, "Nocna przesyłka", status="active")

    narrative = "Zadanie wypełnione. [QUEST_COMPLETE:  nocna PRZESYŁKA ] Świt wstaje nad Kresami."
    process_narrative_xp_tags(narrative, conn, character_id=42, campaign_id=7, turn_number=40)

    q = conn.execute(
        "SELECT status FROM character_quests WHERE campaign_id=7 AND character_id=42"
    ).fetchone()
    assert q["status"] == "completed", f"quest not completed (silent no-op?): {q['status']}"
    assert _status(conn) == "active", "campaign must stay active in the finale grace window"
    assert _finale_available(conn) is True, "spinacz did not open the gate after last quest completed"


def test_campaign_end_tag_closes_campaign():
    conn = _make_db()
    _seed_campaign(conn, plan=_plan(False))  # plan NOT complete — tag must still close
    narrative = "Mrok pierzcha. [CAMPAIGN_END:dobry_koniec] Bohater wraca do domu."
    process_narrative_xp_tags(narrative, conn, character_id=42, campaign_id=7, turn_number=99)
    assert _status(conn) == "completed"
