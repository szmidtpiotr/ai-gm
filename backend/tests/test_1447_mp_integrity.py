"""AUDIT #1447 (P1) — MP integrity: no rejoin-after-kick, capacity re-check, combat
turn-lock (TOCTOU), server-derived chat name, and membership gate on read endpoints.
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
    lobby_status TEXT NOT NULL DEFAULT 'open',
    round_timer_minutes INTEGER NOT NULL DEFAULT 1440,
    max_players INTEGER NOT NULL DEFAULT 4,
    host_user_id INTEGER,
    host_note TEXT,
    spectator_policy TEXT
);
CREATE TABLE IF NOT EXISTS campaign_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'player',
    status TEXT NOT NULL DEFAULT 'accepted',
    character_id INTEGER,
    absence_warnings INTEGER NOT NULL DEFAULT 0,
    pending_intro INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT,
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
CREATE TABLE IF NOT EXISTS party_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    character_name TEXT,
    message TEXT NOT NULL,
    whisper_to TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _make_db(tmp_path):
    db_path = str(tmp_path / "test_1447.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.execute("INSERT INTO users (id, username, display_name) VALUES "
                 "(101,'u101','Player101'),(102,'u102','Player102'),(103,'u103','Player103'),(999,'out','Out')")
    conn.execute("INSERT INTO campaigns (id, title, host_user_id, max_players, lobby_status) "
                 "VALUES (1,'MP',101,2,'open')")
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, role, status, character_id) "
        "VALUES (1,101,'player','accepted',100),(1,102,'player','accepted',101)"
    )
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name, sheet_json) "
        "VALUES (100,1,101,'Aldric','{}'),(101,1,102,'Mira','{}')"
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


def _load_multiplayer(monkeypatch, db_path, caller_uid):
    monkeypatch.setenv("AI_TEST_MODE", "1")
    monkeypatch.setenv("AI_TEST_DB_PATH", db_path)
    import app.api.multiplayer as mp
    importlib.reload(mp)
    monkeypatch.setattr(mp, "resolve_authed_user_id", lambda *a, **k: caller_uid)
    return mp


def _load_party_chat(monkeypatch, db_path, caller_uid):
    monkeypatch.setenv("AI_TEST_MODE", "1")
    monkeypatch.setenv("AI_TEST_DB_PATH", db_path)
    import app.api.party_chat as pc
    importlib.reload(pc)
    monkeypatch.setattr(pc, "resolve_authed_user_id", lambda *a, **k: caller_uid)
    return pc


# ── 1. rejoin-after-kick ─────────────────────────────────────────────────────

def test_kicked_player_cannot_rejoin(tmp_path, monkeypatch):
    db_path = _make_db(tmp_path)
    # mark user 102 kicked
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE campaign_members SET status='kicked' WHERE campaign_id=1 AND user_id=102")
    conn.commit()
    conn.close()

    mp = _load_multiplayer(monkeypatch, db_path, caller_uid=102)
    with pytest.raises(HTTPException) as exc:
        mp.accept_invite(campaign_id=1, body=mp.AcceptInviteReq(character_id=101),
                         authorization=None, user_id=102)
    assert exc.value.status_code == 403


def test_accept_rechecks_max_players(tmp_path, monkeypatch):
    """Lobby max_players=2 already has 2 accepted players → a pending 3rd accept → 409."""
    db_path = _make_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO campaign_members (campaign_id, user_id, role, status) "
                 "VALUES (1,103,'player','pending')")
    conn.commit()
    conn.close()

    mp = _load_multiplayer(monkeypatch, db_path, caller_uid=103)
    with pytest.raises(HTTPException) as exc:
        mp.accept_invite(campaign_id=1, body=mp.AcceptInviteReq(),
                         authorization=None, user_id=103)
    assert exc.value.status_code == 409


# ── 2. combat turn-lock (TOCTOU) ─────────────────────────────────────────────

def test_mp_combat_double_action_locked(tmp_path, monkeypatch):
    """A second concurrent combat action for the same character is refused with 409
    while the per-(campaign, character) turn_lock is held."""
    db_path = _make_db(tmp_path)
    svc = _load_svc(monkeypatch, db_path)
    # Simulate the first request holding the lock for (campaign 1, char 100).
    key = svc.turn_lock.acquire(1, 100)
    try:
        with pytest.raises(HTTPException) as exc:
            svc.submit_mp_combat_action(
                campaign_id=1, user_id=101, character_id=100, action_type="attack",
            )
        assert exc.value.status_code == 409
    finally:
        svc.turn_lock.release(key)


# ── 3. server-derived chat name ──────────────────────────────────────────────

def test_chat_name_server_derived(tmp_path, monkeypatch):
    """Client-supplied character_name is ignored; the stored name comes from the
    caller's assigned character."""
    db_path = _make_db(tmp_path)
    pc = _load_party_chat(monkeypatch, db_path, caller_uid=101)
    # party_chat imports push helpers lazily inside the function → patch at source module.
    import app.services.push_notification_service as pns
    monkeypatch.setattr(pns, "send_push_to_campaign_players", lambda *a, **k: None)
    monkeypatch.setattr(pns, "send_push", lambda *a, **k: None)

    pc.post_party_chat(
        campaign_id=1,
        req=pc.ChatMessageReq(message="siema", character_name="IMPOSTOR-Mira"),
        authorization=None, user_id=101,
    )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT character_name FROM party_messages WHERE user_id=101").fetchone()
    conn.close()
    assert row is not None
    assert row["character_name"] == "Aldric"  # server-derived, not the client's IMPOSTOR value


# ── 4. read-endpoint membership gate ─────────────────────────────────────────

def test_round_read_requires_membership(tmp_path, monkeypatch):
    db_path = _make_db(tmp_path)
    svc = _load_svc(monkeypatch, db_path)
    with pytest.raises(HTTPException) as exc:
        svc.get_round_status(campaign_id=1, user_id=999)
    assert exc.value.status_code == 403


def test_round_read_member_ok(tmp_path, monkeypatch):
    db_path = _make_db(tmp_path)
    svc = _load_svc(monkeypatch, db_path)
    status = svc.get_round_status(campaign_id=1, user_id=101)
    assert status is not None
    assert status.get("status") == "collecting"
