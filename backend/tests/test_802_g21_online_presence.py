"""TDD #802 — G21: last_seen heartbeat, online flag in round/status, push 'Drużyna w komplecie'."""
import importlib
import sqlite3
import sys
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

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
        pending_intro INTEGER NOT NULL DEFAULT 0,
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
        complete_push_sent INTEGER NOT NULL DEFAULT 0,
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
"""


def _make_test_db(tmp_path, db_name="test_802.db"):
    db_path = str(tmp_path / db_name)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return db_path, conn


def _setup_2_player_campaign(conn, deadline_offset_seconds=3600):
    conn.execute("INSERT INTO users (id, username, display_name) VALUES (101, 'player1', 'Gracz 1')")
    conn.execute("INSERT INTO users (id, username, display_name) VALUES (102, 'player2', 'Gracz 2')")
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
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status, deadline, complete_push_sent) "
        "VALUES (1, 1, 1, 'collecting', ?, 0)",
        (deadline,),
    )
    conn.commit()


def _load_svc(monkeypatch, db_path: str):
    monkeypatch.setenv("AI_TEST_MODE", "1")
    monkeypatch.setenv("AI_TEST_DB_PATH", db_path)
    import app.services.multiplayer_round_service as svc
    importlib.reload(svc)
    monkeypatch.setattr(svc, "trigger_narration", lambda round_id: None)
    return svc


# ── RED: online flag in get_round_status ─────────────────────────────────────

def test_online_flag_fresh_last_seen(tmp_path, monkeypatch):
    """Member with recent last_seen appears as online=True in round/status members list."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2_player_campaign(conn)
    # Set player 101 as recently seen
    conn.execute(
        "UPDATE campaign_members SET last_seen=datetime('now') WHERE campaign_id=1 AND user_id=101"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    status = svc.get_round_status(campaign_id=1, user_id=101)

    assert status is not None
    assert "members" in status, "get_round_status must return 'members' field"
    members_by_uid = {m["user_id"]: m for m in status["members"]}
    assert 101 in members_by_uid, "Player 101 must appear in members"
    assert members_by_uid[101]["online"] is True, (
        f"Player with fresh last_seen must be online=True, got {members_by_uid[101]}"
    )


def test_online_flag_stale_last_seen(tmp_path, monkeypatch):
    """Member with last_seen older than 60s appears as online=False."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2_player_campaign(conn)
    conn.execute(
        "UPDATE campaign_members SET last_seen=datetime('now', '-120 seconds') "
        "WHERE campaign_id=1 AND user_id=102"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    status = svc.get_round_status(campaign_id=1, user_id=101)

    assert "members" in status
    members_by_uid = {m["user_id"]: m for m in status["members"]}
    assert members_by_uid[102]["online"] is False, (
        f"Player with stale last_seen (120s ago) must be online=False, got {members_by_uid[102]}"
    )


def test_online_flag_null_last_seen(tmp_path, monkeypatch):
    """Member with NULL last_seen (never polled) appears as online=False."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2_player_campaign(conn)
    # last_seen stays NULL (default)
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    status = svc.get_round_status(campaign_id=1, user_id=101)

    assert "members" in status
    members_by_uid = {m["user_id"]: m for m in status["members"]}
    assert members_by_uid[102]["online"] is False, (
        f"Player with NULL last_seen must be online=False, got {members_by_uid[102]}"
    )


def test_last_seen_updated_on_round_status_call(tmp_path, monkeypatch):
    """Calling get_round_status updates last_seen for the calling user."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2_player_campaign(conn)
    # Ensure last_seen is NULL before call
    initial = conn.execute(
        "SELECT last_seen FROM campaign_members WHERE campaign_id=1 AND user_id=101"
    ).fetchone()
    assert initial["last_seen"] is None, "Precondition: last_seen must be NULL before test"
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    svc.get_round_status(campaign_id=1, user_id=101)

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    row = check.execute(
        "SELECT last_seen FROM campaign_members WHERE campaign_id=1 AND user_id=101"
    ).fetchone()
    check.close()

    assert row["last_seen"] is not None, "get_round_status must update last_seen for calling user"
    # Verify it's recent (within last 5 seconds)
    last_seen_dt = datetime.fromisoformat(row["last_seen"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    diff = abs((now - last_seen_dt.replace(tzinfo=timezone.utc) if last_seen_dt.tzinfo is None else (now - last_seen_dt)).total_seconds())
    assert diff <= 5, f"last_seen should be within 5s of now, got diff={diff}s"


# ── RED: complete push on full submit ─────────────────────────────────────────

def test_complete_push_sent_once_on_full_submit(tmp_path, monkeypatch):
    """When all players submit → push 'Drużyna w komplecie' fires exactly once, complete_push_sent=1."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2_player_campaign(conn)
    conn.close()

    push_calls = []

    svc = _load_svc(monkeypatch, db_path)
    monkeypatch.setattr(
        svc, "send_push_to_campaign_players",
        lambda campaign_id, title, body, url="/": push_calls.append((campaign_id, title, body))
    )

    # Player 1 submits
    svc.submit_action(
        campaign_id=1, user_id=101, character_id=11,
        character_name="Aldric", action_text="Atakuję smoka!"
    )
    assert len(push_calls) == 0, "Push must NOT fire after first player submits"

    # Player 2 submits — round complete
    svc.submit_action(
        campaign_id=1, user_id=102, character_id=12,
        character_name="Mira", action_text="Rzucam zaklęcie!"
    )

    assert len(push_calls) == 1, f"Push must fire exactly 1 time on full submit, fired {len(push_calls)} times"
    assert push_calls[0][1] == "Drużyna w komplecie", f"Push title wrong: {push_calls[0][1]}"

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    row = check.execute("SELECT complete_push_sent FROM campaign_rounds WHERE id=1").fetchone()
    check.close()
    assert row["complete_push_sent"] == 1, "complete_push_sent must be 1 after full submit"


def test_complete_push_not_duplicated_on_repoll(tmp_path, monkeypatch):
    """After round complete, calling get_round_status again must NOT re-send the push."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2_player_campaign(conn)
    # Manually mark round as already complete with push sent
    conn.execute(
        "UPDATE campaign_rounds SET status='narrating', complete_push_sent=1 WHERE id=1"
    )
    conn.execute(
        "INSERT INTO campaign_round_actions (round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1, 1, 101, 11, 'Aldric', 'Atakuję!')"
    )
    conn.execute(
        "INSERT INTO campaign_round_actions (round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1, 1, 102, 12, 'Mira', 'Czaruję!')"
    )
    conn.commit()
    conn.close()

    push_calls = []
    svc = _load_svc(monkeypatch, db_path)
    monkeypatch.setattr(
        svc, "send_push_to_campaign_players",
        lambda campaign_id, title, body, url="/": push_calls.append((campaign_id, title, body))
    )

    # Poll round status multiple times
    svc.get_round_status(campaign_id=1, user_id=101)
    svc.get_round_status(campaign_id=1, user_id=101)

    assert len(push_calls) == 0, (
        f"get_round_status must NOT send push again after complete_push_sent=1, got {len(push_calls)} calls"
    )


def test_sweep_timeout_does_not_set_complete_push_sent(tmp_path, monkeypatch):
    """force_sweep closing round by timeout must NOT set complete_push_sent=1."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2_player_campaign(conn, deadline_offset_seconds=-60)  # expired 1 min ago
    # Only player 1 submitted — round expires before player 2
    conn.execute(
        "INSERT INTO campaign_round_actions "
        "(round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1, 1, 101, 11, 'Aldric', 'Atakuję!')"
    )
    conn.commit()
    conn.close()

    push_calls = []
    svc = _load_svc(monkeypatch, db_path)
    monkeypatch.setattr(
        svc, "send_push_to_campaign_players",
        lambda campaign_id, title, body, url="/": push_calls.append((campaign_id, title, body))
    )

    svc.force_sweep()

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    row = check.execute("SELECT complete_push_sent, status FROM campaign_rounds WHERE id=1").fetchone()
    check.close()

    assert row["status"] == "narrating", "Sweep must close round to narrating"
    assert row["complete_push_sent"] == 0, (
        f"Sweep (timeout) must NOT set complete_push_sent, got {row['complete_push_sent']}"
    )
    # Push 'Drużyna w komplecie' must not fire on sweep timeout
    complete_pushes = [c for c in push_calls if "Drużyna w komplecie" in c[1]]
    assert len(complete_pushes) == 0, (
        f"Sweep must NOT send 'Drużyna w komplecie' push, got {complete_pushes}"
    )


def test_all_present_submitted_returns_true_all_online_submitted(tmp_path, monkeypatch):
    """all_present_submitted → True when all online members have real actions."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2_player_campaign(conn)
    # Both players online and submitted
    conn.execute(
        "UPDATE campaign_members SET last_seen=datetime('now') WHERE campaign_id=1"
    )
    conn.execute(
        "INSERT INTO campaign_round_actions (round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1, 1, 101, 11, 'Aldric', 'Atakuję!')"
    )
    conn.execute(
        "INSERT INTO campaign_round_actions (round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1, 1, 102, 12, 'Mira', 'Czaruję!')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    inner_conn = sqlite3.connect(db_path)
    inner_conn.row_factory = sqlite3.Row
    result = svc.all_present_submitted(round_id=1, campaign_id=1, conn=inner_conn)
    inner_conn.close()

    assert result is True, "All online members submitted real actions → must return True"


def test_all_present_submitted_false_when_online_player_missing(tmp_path, monkeypatch):
    """all_present_submitted → False when an online member has no action."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2_player_campaign(conn)
    # Both players online
    conn.execute(
        "UPDATE campaign_members SET last_seen=datetime('now') WHERE campaign_id=1"
    )
    # Only player 101 submitted
    conn.execute(
        "INSERT INTO campaign_round_actions (round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1, 1, 101, 11, 'Aldric', 'Atakuję!')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    inner_conn = sqlite3.connect(db_path)
    inner_conn.row_factory = sqlite3.Row
    result = svc.all_present_submitted(round_id=1, campaign_id=1, conn=inner_conn)
    inner_conn.close()

    assert result is False, "Online member has no action → must return False"


def test_all_present_submitted_ignores_offline_players(tmp_path, monkeypatch):
    """all_present_submitted → True when offline player hasn't submitted but online one has."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2_player_campaign(conn)
    # Player 101 online, player 102 offline (stale last_seen)
    conn.execute(
        "UPDATE campaign_members SET last_seen=datetime('now') WHERE campaign_id=1 AND user_id=101"
    )
    conn.execute(
        "UPDATE campaign_members SET last_seen=datetime('now', '-120 seconds') WHERE campaign_id=1 AND user_id=102"
    )
    # Only player 101 submitted
    conn.execute(
        "INSERT INTO campaign_round_actions (round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1, 1, 101, 11, 'Aldric', 'Atakuję!')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    inner_conn = sqlite3.connect(db_path)
    inner_conn.row_factory = sqlite3.Row
    result = svc.all_present_submitted(round_id=1, campaign_id=1, conn=inner_conn)
    inner_conn.close()

    assert result is True, "Offline player not submitted, but all ONLINE players submitted → must return True"
