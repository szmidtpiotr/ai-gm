"""TDD #805 — G24: edit/withdraw action only while round is collecting."""
import importlib
import sqlite3
import sys
import os

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest


# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA = """
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
    owner_user_id INTEGER NOT NULL DEFAULT 1,
    mode TEXT NOT NULL DEFAULT 'multiplayer',
    status TEXT NOT NULL DEFAULT 'active',
    round_timer_minutes INTEGER NOT NULL DEFAULT 1440,
    round_timer_hours INTEGER NOT NULL DEFAULT 24,
    max_players INTEGER NOT NULL DEFAULT 4,
    host_user_id INTEGER
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
    complete_push_sent INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS campaign_round_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    character_id INTEGER,
    character_name TEXT NOT NULL DEFAULT '',
    action_text TEXT NOT NULL DEFAULT '',
    initiative_roll INTEGER NOT NULL DEFAULT 10,
    submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
    client_action_id TEXT,
    UNIQUE(round_id, user_id)
);
"""


def _make_test_db(tmp_path):
    db_path = str(tmp_path / "test_805.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return db_path, conn


def _seed_campaign(conn, campaign_id=1, user_ids=(101, 102)):
    for uid in user_ids:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (uid, f"user{uid}")
        )
        conn.execute(
            "INSERT OR IGNORE INTO campaign_members (campaign_id, user_id, status) VALUES (?,?,'accepted')",
            (campaign_id, uid),
        )
    conn.execute(
        "INSERT OR IGNORE INTO campaigns (id, title, owner_user_id) VALUES (?,?,?)",
        (campaign_id, "TestCamp", user_ids[0]),
    )
    for i, uid in enumerate(user_ids):
        conn.execute(
            "INSERT OR IGNORE INTO characters (id, campaign_id, user_id, name, sheet_json) VALUES (?,?,?,?,?)",
            (100 + i, campaign_id, uid, f"Hero{uid}", '{"DEX": 10}'),
        )
    conn.commit()


def _load_svc(monkeypatch, db_path):
    monkeypatch.setenv("AI_TEST_DB_PATH", db_path)
    import app.services.multiplayer_round_service as svc
    importlib.reload(svc)
    monkeypatch.setattr(svc, "trigger_narration", lambda round_id: None)
    monkeypatch.setattr(svc, "send_push_to_campaign_players", lambda *a, **kw: None)
    return svc


# ── Tests: submit_action blocked when not collecting ─────────────────────────

def test_submit_blocked_when_narrating(tmp_path, monkeypatch):
    """submit_action must return error when round status is 'narrating'."""
    db_path, conn = _make_test_db(tmp_path)
    _seed_campaign(conn)
    # Insert a round already in narrating state
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status) VALUES (1, 1, 1, 'narrating')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    result = svc.submit_action(
        campaign_id=1,
        user_id=101,
        character_id=100,
        character_name="Hero101",
        action_text="Atakuję!",
    )
    assert result.get("error") == "round_closed", (
        f"Expected error='round_closed' but got: {result}"
    )


def test_submit_blocked_when_done(tmp_path, monkeypatch):
    """submit_action must return error when round status is 'done'."""
    db_path, conn = _make_test_db(tmp_path)
    _seed_campaign(conn)
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status) VALUES (1, 1, 1, 'done')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    result = svc.submit_action(
        campaign_id=1,
        user_id=101,
        character_id=100,
        character_name="Hero101",
        action_text="Atakuję!",
    )
    assert result.get("error") == "round_closed", (
        f"Expected error='round_closed' but got: {result}"
    )


def test_submit_allowed_when_collecting(tmp_path, monkeypatch):
    """submit_action still works when round is collecting (backward compat)."""
    db_path, conn = _make_test_db(tmp_path)
    _seed_campaign(conn)
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status) VALUES (1, 1, 1, 'collecting')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    result = svc.submit_action(
        campaign_id=1,
        user_id=101,
        character_id=100,
        character_name="Hero101",
        action_text="Atakuję!",
    )
    assert "error" not in result, f"Expected no error in collecting state, got: {result}"
    assert result["status"] in ("collecting", "narrating"), f"Unexpected status: {result}"


# ── Tests: withdraw_action ────────────────────────────────────────────────────

def test_withdraw_removes_action_in_collecting(tmp_path, monkeypatch):
    """withdraw_action deletes action and decrements submitted count when collecting."""
    db_path, conn = _make_test_db(tmp_path)
    _seed_campaign(conn)
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status) VALUES (1, 1, 1, 'collecting')"
    )
    # Pre-insert an action for user 101
    conn.execute(
        "INSERT INTO campaign_round_actions (round_id, campaign_id, user_id, character_name, action_text) "
        "VALUES (1, 1, 101, 'Hero101', 'Atakuję!')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    result = svc.withdraw_action(campaign_id=1, user_id=101)

    assert result.get("error") is None, f"Unexpected error: {result}"
    assert result["submitted"] == 0, f"Expected submitted=0 after withdraw, got: {result['submitted']}"
    assert result["withdrawn"] is True, f"Expected withdrawn=True, got: {result}"


def test_withdraw_blocked_when_narrating(tmp_path, monkeypatch):
    """withdraw_action must return error when round is narrating (already closed)."""
    db_path, conn = _make_test_db(tmp_path)
    _seed_campaign(conn)
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status) VALUES (1, 1, 1, 'narrating')"
    )
    conn.execute(
        "INSERT INTO campaign_round_actions (round_id, campaign_id, user_id, character_name, action_text) "
        "VALUES (1, 1, 101, 'Hero101', 'Atakuję!')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    result = svc.withdraw_action(campaign_id=1, user_id=101)

    assert result.get("error") == "round_closed", (
        f"Expected error='round_closed' but got: {result}"
    )


def test_withdraw_no_active_round_returns_error(tmp_path, monkeypatch):
    """withdraw_action when no collecting round exists returns error gracefully."""
    db_path, conn = _make_test_db(tmp_path)
    _seed_campaign(conn)
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    result = svc.withdraw_action(campaign_id=1, user_id=101)

    assert result.get("error") is not None, (
        f"Expected error when no active round, got: {result}"
    )


def test_edit_overwrites_action_in_collecting(tmp_path, monkeypatch):
    """Submitting again during collecting replaces previous action (UPSERT)."""
    db_path, conn = _make_test_db(tmp_path)
    _seed_campaign(conn)
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status) VALUES (1, 1, 1, 'collecting')"
    )
    conn.execute(
        "INSERT INTO campaign_round_actions (round_id, campaign_id, user_id, character_name, action_text) "
        "VALUES (1, 1, 101, 'Hero101', 'Stara akcja')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    result = svc.submit_action(
        campaign_id=1,
        user_id=101,
        character_id=100,
        character_name="Hero101",
        action_text="Nowa akcja",
    )
    assert "error" not in result

    # Verify DB has the new action
    verify_conn = sqlite3.connect(svc.resolve_db_path())
    verify_conn.row_factory = sqlite3.Row
    row = verify_conn.execute(
        "SELECT action_text FROM campaign_round_actions WHERE round_id=1 AND user_id=101"
    ).fetchone()
    verify_conn.close()
    assert row is not None
    assert row["action_text"] == "Nowa akcja", f"Expected 'Nowa akcja', got: {row['action_text']}"
