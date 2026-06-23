"""TDD #785 — G1: sweep_expired_rounds closes collecting rounds past deadline."""
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
    """Minimal schema for sweep tests (mirrors the RAW_MIGRATIONS schema)."""
    db_path = str(tmp_path / "test_785.db")
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
            template_id INTEGER,
            quiet_start TEXT,
            quiet_end TEXT,
            team_tz TEXT
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
            autopilot_consent INTEGER NOT NULL DEFAULT 0,
            last_seen TEXT,
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
            client_action_id TEXT,
            UNIQUE(round_id, user_id)
        );
    """)
    conn.commit()
    return db_path, conn


def _setup_campaign_with_2_players(conn, deadline_offset_seconds: int):
    """Insert campaign, 2 members, 2 characters, 1 round with given deadline."""
    conn.execute("INSERT INTO users (id, username) VALUES (101, 'player1')")
    conn.execute("INSERT INTO users (id, username) VALUES (102, 'player2')")
    conn.execute(
        "INSERT INTO campaigns (id, title, owner_user_id, host_user_id) VALUES (1, 'TestCamp', 101, 101)"
    )
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, status) VALUES (1, 101, 'accepted')"
    )
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, status) VALUES (1, 102, 'accepted')"
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
    """Point the service at our test DB and reload module to pick up fresh state."""
    monkeypatch.setenv("AI_TEST_DB_PATH", db_path)
    import app.services.multiplayer_round_service as svc
    importlib.reload(svc)
    monkeypatch.setattr(svc, "trigger_narration", lambda round_id: None)
    return svc


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_sweep_closes_expired_round_and_inserts_placeholder(tmp_path, monkeypatch):
    """Expired round → status='narrating', missing player gets [BRAK AKCJI]."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_campaign_with_2_players(conn, deadline_offset_seconds=-60)  # expired 1 min ago

    # Player 1 submitted action, player 2 did NOT
    conn.execute(
        "INSERT INTO campaign_round_actions "
        "(round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1, 1, 101, 11, 'Aldric', 'Atakuję smoka!')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    svc.sweep_expired_rounds()

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row

    round_row = check.execute("SELECT status, closed_at FROM campaign_rounds WHERE id=1").fetchone()
    assert round_row["status"] == "narrating", f"Expected 'narrating', got '{round_row['status']}'"
    assert round_row["closed_at"] is not None, "closed_at must be set"

    actions = check.execute(
        "SELECT user_id, action_text FROM campaign_round_actions WHERE round_id=1 ORDER BY user_id"
    ).fetchall()
    assert len(actions) == 2, f"Expected 2 actions (1 real + 1 placeholder), got {len(actions)}"

    player1_action = next(a for a in actions if a["user_id"] == 101)
    player2_action = next(a for a in actions if a["user_id"] == 102)

    assert player1_action["action_text"] == "Atakuję smoka!", "Player 1 action must be unchanged"
    assert player2_action["action_text"] == "[BRAK AKCJI]", \
        f"Player 2 must get placeholder, got: {player2_action['action_text']}"
    check.close()


def test_sweep_is_idempotent(tmp_path, monkeypatch):
    """Calling sweep twice on the same expired round must not duplicate actions."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_campaign_with_2_players(conn, deadline_offset_seconds=-60)
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    svc.sweep_expired_rounds()
    svc.sweep_expired_rounds()  # second call must be no-op

    check = sqlite3.connect(db_path)
    action_count = check.execute(
        "SELECT COUNT(*) FROM campaign_round_actions WHERE round_id=1"
    ).fetchone()[0]
    assert action_count == 2, f"Expected 2 [BRAK AKCJI] after 2 sweeps (idempotent), got {action_count}"

    round_count = check.execute(
        "SELECT COUNT(*) FROM campaign_rounds WHERE id=1 AND status='narrating'"
    ).fetchone()[0]
    assert round_count == 1, "Round status must remain 'narrating' after second sweep"
    check.close()


def test_sweep_ignores_future_deadline(tmp_path, monkeypatch):
    """Round with deadline in the future must NOT be closed by sweep."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_campaign_with_2_players(conn, deadline_offset_seconds=3600)  # 1h in future
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    svc.sweep_expired_rounds()

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    row = check.execute("SELECT status FROM campaign_rounds WHERE id=1").fetchone()
    assert row["status"] == "collecting", \
        f"Round with future deadline must stay 'collecting', got '{row['status']}'"
    check.close()


def test_sweep_ignores_done_rounds(tmp_path, monkeypatch):
    """Already completed rounds (status='done') must not be touched."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_campaign_with_2_players(conn, deadline_offset_seconds=-60)
    conn.execute("UPDATE campaign_rounds SET status='done', narrative_json='{}' WHERE id=1")
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    svc.sweep_expired_rounds()

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    row = check.execute("SELECT status FROM campaign_rounds WHERE id=1").fetchone()
    assert row["status"] == "done", \
        f"Done round must stay 'done', got '{row['status']}'"
    action_count = check.execute(
        "SELECT COUNT(*) FROM campaign_round_actions WHERE round_id=1"
    ).fetchone()[0]
    assert action_count == 0, "No actions should be inserted for done round"
    check.close()


def test_sweep_normal_round_not_touched(tmp_path, monkeypatch):
    """Round where ALL players submitted (status='narrating') must not be re-closed."""
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
    action_count = check.execute(
        "SELECT COUNT(*) FROM campaign_round_actions WHERE round_id=1"
    ).fetchone()[0]
    assert action_count == 2, \
        f"Narrating round must keep original 2 actions, got {action_count}"
    check.close()
