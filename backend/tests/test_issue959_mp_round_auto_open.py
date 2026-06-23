"""TDD: Issue #959 — submit_action auto-opens next collecting round after 'done'."""
import importlib
import sqlite3
import sys
import os

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest

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
    db_path = str(tmp_path / "test_959.db")
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
        (campaign_id, "TestCampMP", user_ids[0]),
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


# ── P0-A: auto-open next round after 'done' ───────────────────────────────────

def test_submit_after_done_round_opens_next_collecting(tmp_path, monkeypatch):
    """After round 1 is 'done', submit_action must auto-create round 2 'collecting'
    and record the action — NOT return round_closed."""
    db_path, conn = _make_test_db(tmp_path)
    _seed_campaign(conn)
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status)"
        " VALUES (1, 1, 1, 'done')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    result = svc.submit_action(
        campaign_id=1,
        user_id=101,
        character_id=100,
        character_name="Hero101",
        action_text="Ruszam naprzód!",
    )

    assert result.get("error") != "round_closed", (
        f"submit_action blocked with round_closed after 'done' round — expected auto-open. Got: {result}"
    )
    assert "error" not in result, f"Unexpected error: {result}"

    # Verify round 2 was created and action stored
    verify_conn = sqlite3.connect(db_path)
    verify_conn.row_factory = sqlite3.Row
    rounds = verify_conn.execute(
        "SELECT * FROM campaign_rounds WHERE campaign_id=1 ORDER BY round_number"
    ).fetchall()
    verify_conn.close()

    assert len(rounds) == 2, f"Expected 2 rounds (1 done + 1 collecting), got {len(rounds)}"
    assert rounds[1]["round_number"] == 2
    assert rounds[1]["status"] == "collecting"


def test_submit_after_done_stores_action_in_new_round(tmp_path, monkeypatch):
    """Action submitted after 'done' round lands in the new collecting round (round 2)."""
    db_path, conn = _make_test_db(tmp_path)
    _seed_campaign(conn)
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status)"
        " VALUES (1, 1, 1, 'done')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    svc.submit_action(
        campaign_id=1,
        user_id=101,
        character_id=100,
        character_name="Hero101",
        action_text="Ataduję orka!",
    )

    verify_conn = sqlite3.connect(db_path)
    verify_conn.row_factory = sqlite3.Row
    action = verify_conn.execute(
        "SELECT a.*, r.round_number FROM campaign_round_actions a"
        " JOIN campaign_rounds r ON a.round_id=r.id"
        " WHERE a.campaign_id=1 AND a.user_id=101"
    ).fetchone()
    verify_conn.close()

    assert action is not None, "Action was not stored in DB"
    assert action["round_number"] == 2, (
        f"Action should be in round 2, got round {action['round_number']}"
    )


# ── P0-A backward compat: narrating still blocks ──────────────────────────────

def test_submit_blocked_when_narrating_still_blocks(tmp_path, monkeypatch):
    """narrating round must still return round_closed (backward compat for G24)."""
    db_path, conn = _make_test_db(tmp_path)
    _seed_campaign(conn)
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status)"
        " VALUES (1, 1, 1, 'narrating')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    result = svc.submit_action(
        campaign_id=1,
        user_id=101,
        character_id=100,
        character_name="Hero101",
        action_text="Próbuję!",
    )
    assert result.get("error") == "round_closed", (
        f"narrating round should still block. Got: {result}"
    )


def test_submit_collecting_unchanged(tmp_path, monkeypatch):
    """collecting round still accepts actions normally (backward compat)."""
    db_path, conn = _make_test_db(tmp_path)
    _seed_campaign(conn)
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status)"
        " VALUES (1, 1, 2, 'collecting')"
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
    assert "error" not in result, f"collecting round should not block. Got: {result}"
