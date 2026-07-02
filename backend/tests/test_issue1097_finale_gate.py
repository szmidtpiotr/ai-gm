"""TDD: Issue #1097 — soft finale gate (player-triggered campaign completion).

#1009's spinacz still detects victory deterministically (all acts + 0 active main
quests), but instead of flipping campaigns.status it now sets a sticky
finale_available flag. The player pulls the actual completion trigger via
finish_campaign() (POST /campaigns/{id}/finish). This file covers the parts that
changed relative to #1009 (see test_t38_campaign_victory.py):
  - the gate is STICKY (never re-closes once open)
  - finish_campaign() is host-guarded and idempotent
  - quest_suggest_needed is never re-set while the gate is open
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.campaign_plan_runtime import finish_campaign, maybe_complete_campaign
from app.services.quest_persist_service import check_and_set_quest_suggest_needed


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
            finale_available INTEGER NOT NULL DEFAULT 0,
            owner_user_id INTEGER,
            host_user_id INTEGER
        );
        CREATE TABLE character_quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            campaign_id INTEGER,
            quest_type TEXT DEFAULT 'main',
            title TEXT,
            status TEXT DEFAULT 'active',
            created_turn INTEGER
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            session_flags TEXT DEFAULT '{}'
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            sheet_json TEXT DEFAULT '{}'
        );
        """
    )
    conn.execute("INSERT INTO characters (id, sheet_json) VALUES (42, '{}')")
    conn.commit()
    return conn


def _plan(*completed_flags):
    return json.dumps({"acts": [{"completed": bool(f), "key_beats": []} for f in completed_flags]})


def _seed_campaign(conn, cid=7, status="active", plan=None, owner=1013, host=None, finale=0):
    conn.execute(
        "INSERT INTO campaigns (id, status, gm_plan_json, owner_user_id, host_user_id, finale_available) "
        "VALUES (?,?,?,?,?,?)",
        (cid, status, plan, owner, host, finale),
    )
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?,?)",
        (cid, json.dumps({})),
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


# ─── sticky gate ──────────────────────────────────────────────────────────────

def test_gate_is_sticky_does_not_reclose_when_new_main_quest_accepted():
    conn = _make_db()
    _seed_campaign(conn, plan=_plan(True, True))
    assert maybe_complete_campaign(7, 42, 1, conn) is True
    assert _finale_available(conn) is True

    # Player accepts a new main quest during the grace window.
    _insert_quest(conn, 7, "Nowy wątek", status="active")
    # Spinacz runs again next turn — must stay open, not re-close.
    fired_again = maybe_complete_campaign(7, 42, 2, conn)
    assert fired_again is False, "gate must not fire twice"
    assert _finale_available(conn) is True, "sticky gate must not close when a new quest appears"
    assert _status(conn) == "active"


# ─── finish_campaign() ────────────────────────────────────────────────────────

def test_finish_blocked_when_gate_not_open():
    conn = _make_db()
    _seed_campaign(conn, plan=_plan(True, True), finale=0)
    result = finish_campaign(7, 42, 1013, 5, conn)
    assert result == {"ok": False, "error": "finale_not_available"}
    assert _status(conn) == "active"


def test_finish_blocked_for_non_host_in_multiplayer():
    conn = _make_db()
    _seed_campaign(conn, plan=_plan(True, True), owner=1013, host=1013, finale=1)
    result = finish_campaign(7, 42, 9999, 5, conn)
    assert result == {"ok": False, "error": "not_host"}
    assert _status(conn) == "active"


def test_finish_flips_completed_and_stamps_ended_at():
    conn = _make_db()
    _seed_campaign(conn, plan=_plan(True, True), owner=1013, finale=1)
    result = finish_campaign(7, 42, 1013, 12, conn)
    assert result["ok"] is True
    assert result["already_completed"] is False
    assert result["ended_at"]
    assert _status(conn) == "completed"


def test_finish_idempotent_when_already_completed():
    conn = _make_db()
    _seed_campaign(conn, status="completed", plan=_plan(True, True), owner=1013, finale=1)
    result = finish_campaign(7, 42, 1013, 12, conn)
    assert result == {"ok": True, "already_completed": True, "ended_at": None}


def test_finish_allowed_for_solo_owner_with_no_host_column_set():
    """Solo campaigns never set host_user_id — owner alone must pass the guard."""
    conn = _make_db()
    _seed_campaign(conn, plan=_plan(True, True), owner=1013, host=None, finale=1)
    result = finish_campaign(7, 42, 1013, 5, conn)
    assert result["ok"] is True


# ─── quest_suggest_needed guard during grace window ───────────────────────────

def test_quest_suggest_needed_not_set_while_finale_available():
    conn = _make_db()
    _seed_campaign(conn, plan=_plan(True, True), finale=1)
    fired = check_and_set_quest_suggest_needed(conn, 42, 7, "Ostatni quest")
    assert fired is False
    sf = json.loads(
        conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=7").fetchone()["session_flags"]
    )
    assert "quest_suggest_needed" not in sf
