"""AUDIT #1446 (P0) — submit_action / submit_mp_combat_action require membership + ownership.

Outsiders must not inject into a party's shared round, and no authenticated user may
drive a combat turn for a character they don't own.
"""
import importlib
import os
import sqlite3
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest
from fastapi import HTTPException

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
    mode TEXT NOT NULL DEFAULT 'multiplayer',
    status TEXT NOT NULL DEFAULT 'active',
    round_timer_minutes INTEGER NOT NULL DEFAULT 1440,
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
    absence_warnings INTEGER NOT NULL DEFAULT 0,
    UNIQUE(campaign_id, user_id)
);
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
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


def _make_db(tmp_path):
    db_path = str(tmp_path / "test_1446.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    # user 101 owns char 100; user 102 owns char 101
    conn.execute("INSERT INTO users (id, username) VALUES (101,'u101'),(102,'u102'),(999,'outsider')")
    conn.execute("INSERT INTO campaigns (id, title, host_user_id) VALUES (1,'MP',101)")
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, role, status, character_id) "
        "VALUES (1,101,'player','accepted',100),(1,102,'player','accepted',101)"
    )
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name, sheet_json) "
        "VALUES (100,1,101,'Aldric','{\"current_hp\":20}'),(101,1,102,'Mira','{\"current_hp\":18}')"
    )
    conn.execute("INSERT INTO campaign_rounds (id, campaign_id, round_number, status) VALUES (1,1,1,'collecting')")
    conn.commit()
    conn.close()
    return db_path


def _load_svc(monkeypatch, db_path):
    monkeypatch.setenv("AI_TEST_MODE", "1")
    monkeypatch.setenv("AI_TEST_DB_PATH", db_path)
    import app.services.multiplayer_round_service as svc
    importlib.reload(svc)
    monkeypatch.setattr(svc, "trigger_narration", lambda *a, **k: None)
    monkeypatch.setattr(svc, "send_push_to_campaign_players", lambda *a, **k: None)
    return svc


def test_mp_submit_requires_membership(tmp_path, monkeypatch):
    """A non-member (user 999) cannot submit a round action → 403."""
    db_path = _make_db(tmp_path)
    svc = _load_svc(monkeypatch, db_path)
    with pytest.raises(HTTPException) as exc:
        svc.submit_action(
            campaign_id=1, user_id=999, character_id=100,
            character_name="Aldric", action_text="Wchodzę i psuję narrację",
        )
    assert exc.value.status_code == 403


def test_mp_submit_rejects_foreign_character(tmp_path, monkeypatch):
    """A member cannot submit an action AS a character they don't own → 403."""
    db_path = _make_db(tmp_path)
    svc = _load_svc(monkeypatch, db_path)
    # user 101 tries to act as char 101 (owned by 102)
    with pytest.raises(HTTPException) as exc:
        svc.submit_action(
            campaign_id=1, user_id=101, character_id=101,
            character_name="Mira", action_text="Impersonacja",
        )
    assert exc.value.status_code == 403


def test_mp_combat_action_ownership(tmp_path, monkeypatch):
    """user A submitting a combat action for character B (owned by B) → 403,
    before any combat state is touched."""
    db_path = _make_db(tmp_path)
    svc = _load_svc(monkeypatch, db_path)
    # user 101 tries to drive char 101 (owned by 102)
    with pytest.raises(HTTPException) as exc:
        svc.submit_mp_combat_action(
            campaign_id=1, user_id=101, character_id=101, action_type="attack",
        )
    assert exc.value.status_code == 403


def test_mp_submit_member_owner_passes_gate(tmp_path, monkeypatch):
    """Sanity: a legit member acting as their own assigned character is NOT blocked."""
    db_path = _make_db(tmp_path)
    svc = _load_svc(monkeypatch, db_path)
    result = svc.submit_action(
        campaign_id=1, user_id=101, character_id=100,
        character_name="Aldric", action_text="Legalna akcja",
    )
    assert result.get("round_id") == 1
    assert "error" not in result or result.get("error") != "round_closed"
