"""TDD #787 — G3: Vote-to-kick; majority vote removes player from campaign."""
import importlib
import sqlite3
import sys
import os

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ── DB helpers ────────────────────────────────────────────────────────────────

def _make_test_db(tmp_path):
    db_path = str(tmp_path / "test_787.db")
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
            lobby_status TEXT NOT NULL DEFAULT 'started'
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
            campaign_id INTEGER,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            system_id TEXT NOT NULL DEFAULT 'fantasy',
            sheet_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'idle'
        );
        CREATE TABLE IF NOT EXISTS campaign_kick_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            target_user_id INTEGER NOT NULL,
            voter_user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(campaign_id, target_user_id, voter_user_id)
        );
    """)
    conn.commit()
    return db_path, conn


def _conn(db_path):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


def _setup_3_player_campaign(conn):
    """host=101 (unkickable), player2=102, player3=103 (target)."""
    for uid, name in [(101, "host"), (102, "player2"), (103, "player3")]:
        conn.execute("INSERT INTO users (id, username) VALUES (?, ?)", (uid, name))
    conn.execute(
        "INSERT INTO campaigns (id, title, owner_user_id, host_user_id, mode) "
        "VALUES (1, 'TestCamp', 101, 101, 'multiplayer')"
    )
    for uid in [101, 102, 103]:
        conn.execute(
            "INSERT INTO campaign_members (campaign_id, user_id, status) VALUES (1, ?, 'accepted')",
            (uid,),
        )
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name, status) VALUES (13, 1, 103, 'Zara', 'active')"
    )
    conn.commit()


def _setup_2_player_campaign(conn):
    """host=101, player2=102 (target)."""
    for uid, name in [(101, "host"), (102, "player2")]:
        conn.execute("INSERT INTO users (id, username) VALUES (?, ?)", (uid, name))
    conn.execute(
        "INSERT INTO campaigns (id, title, owner_user_id, host_user_id, mode) "
        "VALUES (1, 'TwoPlayer', 101, 101, 'multiplayer')"
    )
    for uid in [101, 102]:
        conn.execute(
            "INSERT INTO campaign_members (campaign_id, user_id, status) VALUES (1, ?, 'accepted')",
            (uid,),
        )
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name, status) VALUES (12, 1, 102, 'Mira', 'active')"
    )
    conn.commit()


def _make_client(monkeypatch, db_path: str):
    """TestClient with _db patched to use test DB. Use ?user_id= for auth."""
    import app.api.multiplayer as mp
    importlib.reload(mp)

    def _test_db():
        return _conn(db_path)

    monkeypatch.setattr(mp, "_db", _test_db)

    app_inst = FastAPI()
    app_inst.include_router(mp.router)
    return TestClient(app_inst, raise_server_exceptions=False)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_minority_vote_does_not_kick(tmp_path, monkeypatch):
    """3 players; 1 vote is not majority (need 2) → kicked=False."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_3_player_campaign(conn)
    conn.close()

    client = _make_client(monkeypatch, db_path)
    r = client.post(
        "/multiplayer/campaigns/1/kick-vote?user_id=102",
        json={"target_user_id": 103},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kicked"] is False
    assert data["votes"] == 1
    assert data["required"] == 2

    check = _conn(db_path)
    member = check.execute(
        "SELECT status FROM campaign_members WHERE campaign_id=1 AND user_id=103"
    ).fetchone()
    assert member["status"] == "accepted", "Player must NOT be kicked on minority vote"
    check.close()


def test_majority_vote_kicks_player(tmp_path, monkeypatch):
    """3 players; 2 votes (majority) → player kicked, hero becomes idle."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_3_player_campaign(conn)
    conn.close()

    client = _make_client(monkeypatch, db_path)

    # First vote (player 102)
    r1 = client.post(
        "/multiplayer/campaigns/1/kick-vote?user_id=102",
        json={"target_user_id": 103},
    )
    assert r1.status_code == 200
    assert r1.json()["kicked"] is False

    # Second vote (host 101) — majority reached
    r2 = client.post(
        "/multiplayer/campaigns/1/kick-vote?user_id=101",
        json={"target_user_id": 103},
    )
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert data["kicked"] is True

    check = _conn(db_path)
    member = check.execute(
        "SELECT status FROM campaign_members WHERE campaign_id=1 AND user_id=103"
    ).fetchone()
    assert member["status"] == "kicked"
    hero = check.execute(
        "SELECT campaign_id, status FROM characters WHERE user_id=103"
    ).fetchone()
    assert hero["campaign_id"] is None, "Kicked hero campaign_id must be NULL"
    assert hero["status"] == "idle", "Kicked hero status must be idle"
    check.close()


def test_host_unkickable(tmp_path, monkeypatch):
    """Attempt to kick host → 403."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_3_player_campaign(conn)
    conn.close()

    client = _make_client(monkeypatch, db_path)
    r = client.post(
        "/multiplayer/campaigns/1/kick-vote?user_id=102",
        json={"target_user_id": 101},  # 101 is host
    )
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


def test_two_player_host_kicks_directly(tmp_path, monkeypatch):
    """2-person game: host votes → immediate kick, no vote count needed."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2_player_campaign(conn)
    conn.close()

    client = _make_client(monkeypatch, db_path)
    r = client.post(
        "/multiplayer/campaigns/1/kick-vote?user_id=101",
        json={"target_user_id": 102},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kicked"] is True
    assert data["votes"] == 1
    assert data["required"] == 1

    check = _conn(db_path)
    member = check.execute(
        "SELECT status FROM campaign_members WHERE campaign_id=1 AND user_id=102"
    ).fetchone()
    assert member["status"] == "kicked"
    check.close()


def test_two_player_non_host_cannot_kick(tmp_path, monkeypatch):
    """2-person game: non-host tries to kick → 403."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2_player_campaign(conn)
    conn.close()

    client = _make_client(monkeypatch, db_path)
    r = client.post(
        "/multiplayer/campaigns/1/kick-vote?user_id=102",
        json={"target_user_id": 101},  # trying to kick host — blocked by host-unkickable rule
    )
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


def test_kicked_hero_becomes_idle(tmp_path, monkeypatch):
    """After kick: campaign_members.status='kicked', characters.campaign_id=NULL, status='idle'."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2_player_campaign(conn)
    conn.close()

    client = _make_client(monkeypatch, db_path)
    r = client.post(
        "/multiplayer/campaigns/1/kick-vote?user_id=101",
        json={"target_user_id": 102},
    )
    assert r.status_code == 200
    assert r.json()["kicked"] is True

    check = _conn(db_path)
    m = check.execute(
        "SELECT status FROM campaign_members WHERE campaign_id=1 AND user_id=102"
    ).fetchone()
    assert m["status"] == "kicked", f"Expected kicked, got {m['status']}"

    hero = check.execute(
        "SELECT campaign_id, status FROM characters WHERE user_id=102"
    ).fetchone()
    assert hero["campaign_id"] is None, "Hero must be freed from campaign"
    assert hero["status"] == "idle", "Hero must be idle after kick"
    check.close()


def test_duplicate_vote_ignored(tmp_path, monkeypatch):
    """Same player voting twice counts only once."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_3_player_campaign(conn)
    conn.close()

    client = _make_client(monkeypatch, db_path)

    r1 = client.post(
        "/multiplayer/campaigns/1/kick-vote?user_id=102",
        json={"target_user_id": 103},
    )
    assert r1.status_code == 200
    assert r1.json()["votes"] == 1

    # Second identical vote — must not increment count
    r2 = client.post(
        "/multiplayer/campaigns/1/kick-vote?user_id=102",
        json={"target_user_id": 103},
    )
    assert r2.status_code == 200
    assert r2.json()["votes"] == 1, "Duplicate vote must not be counted twice"
    assert r2.json()["kicked"] is False
