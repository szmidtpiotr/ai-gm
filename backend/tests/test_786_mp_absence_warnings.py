"""TDD #786 — G2: Absence warnings counter; vote_kick_suggested after 3 misses."""
import importlib
import sqlite3
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_test_db(tmp_path):
    """Minimal schema for absence-warnings tests, including absence_warnings column."""
    db_path = str(tmp_path / "test_786.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL DEFAULT '',
            display_name TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            system_id TEXT NOT NULL DEFAULT 'fantasy',
            model_id TEXT NOT NULL DEFAULT 'gpt-4',
            owner_user_id INTEGER NOT NULL,
            mode TEXT NOT NULL DEFAULT 'multiplayer',
            status TEXT NOT NULL DEFAULT 'active',
            round_timer_minutes INTEGER NOT NULL DEFAULT 1440,
            round_timer_hours INTEGER NOT NULL DEFAULT 24,
            max_players INTEGER NOT NULL DEFAULT 4,
            host_user_id INTEGER,
            lobby_status TEXT NOT NULL DEFAULT 'open',
            host_note TEXT,
            template_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS campaign_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'player',
            status TEXT NOT NULL DEFAULT 'accepted',
            character_id INTEGER,
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            absence_warnings INTEGER NOT NULL DEFAULT 0,
            UNIQUE(campaign_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            system_id TEXT NOT NULL DEFAULT 'fantasy',
            sheet_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS campaign_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'collecting',
            deadline TEXT,
            closed_at TEXT,
            narrative_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS campaign_round_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER NOT NULL,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            character_id INTEGER,
            character_name TEXT NOT NULL,
            action_text TEXT NOT NULL,
            submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
            initiative_roll INTEGER NOT NULL DEFAULT 0,
            UNIQUE(round_id, user_id)
        );
    """)
    conn.commit()
    return db_path, conn


def _setup_campaign_with_2_players(conn, deadline_offset_seconds: int):
    conn.execute("INSERT INTO users (id, username) VALUES (101, 'player1')")
    conn.execute("INSERT INTO users (id, username) VALUES (102, 'player2')")
    conn.execute(
        "INSERT INTO campaigns (id, title, owner_user_id, host_user_id) VALUES (1, 'TestCamp', 101, 101)"
    )
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, status, absence_warnings) VALUES (1, 101, 'accepted', 0)"
    )
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, status, absence_warnings) VALUES (1, 102, 'accepted', 0)"
    )
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name) VALUES (11, 1, 101, 'Aldric')"
    )
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name) VALUES (12, 1, 102, 'Mira')"
    )
    deadline = (
        datetime.now(timezone.utc) + timedelta(seconds=deadline_offset_seconds)
    ).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status, deadline) "
        "VALUES (1, 1, 1, 'collecting', ?)",
        (deadline,),
    )
    conn.commit()


def _load_svc(monkeypatch, db_path: str):
    monkeypatch.setenv("AI_TEST_DB_PATH", db_path)
    import app.services.multiplayer_round_service as svc
    importlib.reload(svc)
    monkeypatch.setattr(svc, "trigger_narration", lambda round_id: None)
    return svc


def _add_round(conn, campaign_id: int, round_id: int, round_num: int, deadline_offset_seconds: int):
    """Helper to insert an additional round."""
    deadline = (
        datetime.now(timezone.utc) + timedelta(seconds=deadline_offset_seconds)
    ).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status, deadline) "
        "VALUES (?, ?, ?, 'collecting', ?)",
        (round_id, campaign_id, round_num, deadline),
    )
    conn.commit()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_sweep_increments_absence_warnings_for_missing_player(tmp_path, monkeypatch):
    """Player missing expired round → absence_warnings goes from 0 to 1."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_campaign_with_2_players(conn, deadline_offset_seconds=-60)

    # Player 1 submitted, player 2 did NOT
    conn.execute(
        "INSERT INTO campaign_round_actions "
        "(round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1, 1, 101, 11, 'Aldric', 'Atakuję!')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    svc.sweep_expired_rounds()

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row

    p1 = check.execute("SELECT absence_warnings FROM campaign_members WHERE campaign_id=1 AND user_id=101").fetchone()
    p2 = check.execute("SELECT absence_warnings FROM campaign_members WHERE campaign_id=1 AND user_id=102").fetchone()

    assert p1["absence_warnings"] == 0, "Player who submitted must NOT get warning"
    assert p2["absence_warnings"] == 1, f"Player who missed round must get 1 warning, got {p2['absence_warnings']}"
    check.close()


def test_sweep_no_warning_for_player_who_submitted(tmp_path, monkeypatch):
    """All players submit → no absence_warnings incremented."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_campaign_with_2_players(conn, deadline_offset_seconds=-60)

    conn.execute(
        "INSERT INTO campaign_round_actions "
        "(round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1, 1, 101, 11, 'Aldric', 'Atakuję!')"
    )
    conn.execute(
        "INSERT INTO campaign_round_actions "
        "(round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1, 1, 102, 12, 'Mira', 'Czaruję!')"
    )
    conn.execute("UPDATE campaign_rounds SET status='narrating' WHERE id=1")
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    svc.sweep_expired_rounds()

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    for uid in (101, 102):
        row = check.execute(
            "SELECT absence_warnings FROM campaign_members WHERE campaign_id=1 AND user_id=?", (uid,)
        ).fetchone()
        assert row["absence_warnings"] == 0, f"User {uid} submitted — must have 0 warnings"
    check.close()


def test_absence_warnings_accumulate_across_rounds(tmp_path, monkeypatch):
    """Three missed rounds → warnings 0→1→2→3."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_campaign_with_2_players(conn, deadline_offset_seconds=-60)
    conn.close()

    svc = _load_svc(monkeypatch, db_path)

    for round_id, round_num in [(1, 1), (2, 2), (3, 3)]:
        conn2 = sqlite3.connect(db_path)
        conn2.row_factory = sqlite3.Row
        if round_id > 1:
            _add_round(conn2, campaign_id=1, round_id=round_id, round_num=round_num, deadline_offset_seconds=-60)
        # Player 101 submits, player 102 does not
        conn2.execute(
            "INSERT OR IGNORE INTO campaign_round_actions "
            "(round_id, campaign_id, user_id, character_id, character_name, action_text) "
            "VALUES (?, 1, 101, 11, 'Aldric', 'Atakuję!')",
            (round_id,),
        )
        conn2.commit()
        conn2.close()
        svc.sweep_expired_rounds()

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    p2 = check.execute("SELECT absence_warnings FROM campaign_members WHERE campaign_id=1 AND user_id=102").fetchone()
    assert p2["absence_warnings"] == 3, f"Expected 3 warnings after 3 misses, got {p2['absence_warnings']}"
    check.close()


def test_real_submit_resets_absence_warnings(tmp_path, monkeypatch):
    """Player with 2 warnings submits a real action → warnings reset to 0."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_campaign_with_2_players(conn, deadline_offset_seconds=3600)  # future deadline
    # Pre-set player 102 to have 2 warnings
    conn.execute(
        "UPDATE campaign_members SET absence_warnings=2 WHERE campaign_id=1 AND user_id=102"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    svc.submit_action(
        campaign_id=1,
        user_id=102,
        character_id=12,
        character_name="Mira",
        action_text="Rzucam zaklęcie!",
    )

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    p2 = check.execute("SELECT absence_warnings FROM campaign_members WHERE campaign_id=1 AND user_id=102").fetchone()
    assert p2["absence_warnings"] == 0, f"Submit must reset absence_warnings to 0, got {p2['absence_warnings']}"
    check.close()


def test_vote_kick_suggested_after_3_warnings(tmp_path, monkeypatch):
    """Player with absence_warnings >= 3 triggers vote_kick_suggested in get_round_status."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_campaign_with_2_players(conn, deadline_offset_seconds=3600)
    # Pre-set player 102 to 3 warnings
    conn.execute(
        "UPDATE campaign_members SET absence_warnings=3 WHERE campaign_id=1 AND user_id=102"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    status = svc.get_round_status(campaign_id=1, user_id=101)

    assert status is not None, "get_round_status must return data"
    assert status.get("vote_kick_suggested") is True, \
        f"vote_kick_suggested must be True when a player has >=3 warnings, got: {status.get('vote_kick_suggested')}"


def test_vote_kick_not_suggested_below_threshold(tmp_path, monkeypatch):
    """Player with 2 absence_warnings → vote_kick_suggested must be False."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_campaign_with_2_players(conn, deadline_offset_seconds=3600)
    conn.execute(
        "UPDATE campaign_members SET absence_warnings=2 WHERE campaign_id=1 AND user_id=102"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    status = svc.get_round_status(campaign_id=1, user_id=101)

    assert status is not None
    assert not status.get("vote_kick_suggested"), \
        "vote_kick_suggested must be False when no player has >=3 warnings"


def test_absence_warnings_per_member_in_round_status(tmp_path, monkeypatch):
    """get_round_status exposes absence_warnings_by_player dict keyed by user_id."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_campaign_with_2_players(conn, deadline_offset_seconds=3600)
    conn.execute(
        "UPDATE campaign_members SET absence_warnings=1 WHERE campaign_id=1 AND user_id=101"
    )
    conn.execute(
        "UPDATE campaign_members SET absence_warnings=3 WHERE campaign_id=1 AND user_id=102"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    status = svc.get_round_status(campaign_id=1, user_id=101)

    assert status is not None
    assert "absence_warnings_by_player" in status, "Must include absence_warnings_by_player dict"
    w = status["absence_warnings_by_player"]
    assert w.get(101) == 1, f"User 101 must have 1 warning, got {w.get(101)}"
    assert w.get(102) == 3, f"User 102 must have 3 warnings, got {w.get(102)}"
