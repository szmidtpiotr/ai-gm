"""TDD #790 — G6: Team hex-move voting (majority wins, tie → host decides, host has no veto)."""
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
    db_path = str(tmp_path / "test_790.db")
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
            lobby_status TEXT NOT NULL DEFAULT 'started',
            party_hex_q INTEGER DEFAULT NULL,
            party_hex_r INTEGER DEFAULT NULL
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
        CREATE TABLE IF NOT EXISTS campaign_move_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            target_q INTEGER NOT NULL,
            target_r INTEGER NOT NULL,
            voted_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(campaign_id, user_id)
        );
    """)
    conn.commit()
    return db_path, conn


def _raw_conn(db_path):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


def _setup_campaign(conn, host_id=1, n_players=3):
    """Insert campaign + N accepted members (user IDs 1..n_players, host = host_id)."""
    for uid in range(1, max(n_players, 4) + 1):
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (uid, f"user{uid}")
        )
    conn.execute(
        "INSERT INTO campaigns (id, title, owner_user_id, host_user_id, mode) "
        "VALUES (1, 'TestCamp', ?, ?, 'multiplayer')",
        (host_id, host_id),
    )
    for uid in range(1, n_players + 1):
        conn.execute(
            "INSERT INTO campaign_members (campaign_id, user_id, status) VALUES (1, ?, 'accepted')",
            (uid,),
        )
    conn.commit()


# ── App factory ───────────────────────────────────────────────────────────────

def _make_client(monkeypatch, db_path: str):
    """TestClient with _db patched in both API and service modules."""
    import app.api.multiplayer as mp
    import app.services.multiplayer_round_service as svc

    importlib.reload(svc)
    importlib.reload(mp)

    def _test_db():
        return _raw_conn(db_path)

    monkeypatch.setattr(mp, "_db", _test_db)
    monkeypatch.setattr(svc, "_db", _test_db)

    app_inst = FastAPI()
    app_inst.include_router(mp.router, prefix="/api")
    return TestClient(app_inst, raise_server_exceptions=False)


# ── TESTS ─────────────────────────────────────────────────────────────────────

class TestMoveVoteMajority:
    """3 players: 2 vote for (5,3), 1 for (2,2) → (5,3) wins even if host voted for (2,2)."""

    def test_majority_wins_over_host(self, tmp_path, monkeypatch):
        db_path, conn = _make_test_db(tmp_path)
        _setup_campaign(conn, host_id=1, n_players=3)
        conn.close()

        client = _make_client(monkeypatch, db_path)

        # Host (user 1) votes for (2, 2)
        r = client.post("/api/campaigns/1/move-vote", json={"target_q": 2, "target_r": 2}, params={"user_id": 1})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["resolved"] is False, "Should not resolve until all voted"

        # Player 2 votes for (5, 3)
        r = client.post("/api/campaigns/1/move-vote", json={"target_q": 5, "target_r": 3}, params={"user_id": 2})
        assert r.status_code == 200, r.text

        # Player 3 votes for (5, 3) — now 2 vs 1 → resolved
        r = client.post("/api/campaigns/1/move-vote", json={"target_q": 5, "target_r": 3}, params={"user_id": 3})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["resolved"] is True
        assert data["winner_q"] == 5
        assert data["winner_r"] == 3

        # Verify campaigns.party_hex updated
        c = _raw_conn(db_path)
        camp = c.execute("SELECT party_hex_q, party_hex_r FROM campaigns WHERE id=1").fetchone()
        assert camp["party_hex_q"] == 5
        assert camp["party_hex_r"] == 3
        c.close()

    def test_host_cannot_veto_majority(self, tmp_path, monkeypatch):
        """Host's vote for minority hex does not override majority."""
        db_path, conn = _make_test_db(tmp_path)
        _setup_campaign(conn, host_id=1, n_players=3)
        conn.close()

        client = _make_client(monkeypatch, db_path)

        # Both non-host players vote for (9, 1)
        client.post("/api/campaigns/1/move-vote", json={"target_q": 9, "target_r": 1}, params={"user_id": 2})
        client.post("/api/campaigns/1/move-vote", json={"target_q": 9, "target_r": 1}, params={"user_id": 3})
        # Host votes for (0, 0) LAST — still should lose
        r = client.post("/api/campaigns/1/move-vote", json={"target_q": 0, "target_r": 0}, params={"user_id": 1})
        data = r.json()
        assert data["resolved"] is True
        assert data["winner_q"] == 9
        assert data["winner_r"] == 1


class TestMoveVoteTie:
    """2 players: tie 1:1 → host's vote wins."""

    def test_tie_host_decides(self, tmp_path, monkeypatch):
        db_path, conn = _make_test_db(tmp_path)
        _setup_campaign(conn, host_id=1, n_players=2)
        conn.close()

        client = _make_client(monkeypatch, db_path)

        # Player 2 votes for (3, 4)
        client.post("/api/campaigns/1/move-vote", json={"target_q": 3, "target_r": 4}, params={"user_id": 2})
        # Host (user 1) votes for (7, 2) — tie 1:1 → host wins
        r = client.post("/api/campaigns/1/move-vote", json={"target_q": 7, "target_r": 2}, params={"user_id": 1})
        data = r.json()
        assert data["resolved"] is True
        assert data["winner_q"] == 7
        assert data["winner_r"] == 2


class TestMoveVoteStatus:
    """GET /campaigns/{id}/move-vote returns current state."""

    def test_get_vote_status_partial(self, tmp_path, monkeypatch):
        db_path, conn = _make_test_db(tmp_path)
        _setup_campaign(conn, host_id=1, n_players=3)
        conn.close()

        client = _make_client(monkeypatch, db_path)

        client.post("/api/campaigns/1/move-vote", json={"target_q": 2, "target_r": 2}, params={"user_id": 1})

        r = client.get("/api/campaigns/1/move-vote", params={"user_id": 1})
        assert r.status_code == 200
        data = r.json()
        assert data["votes_cast"] == 1
        assert data["total_players"] == 3
        assert data["resolved"] is False

    def test_player_can_change_vote(self, tmp_path, monkeypatch):
        """Re-submitting replaces previous vote."""
        db_path, conn = _make_test_db(tmp_path)
        _setup_campaign(conn, host_id=1, n_players=2)
        conn.close()

        client = _make_client(monkeypatch, db_path)

        client.post("/api/campaigns/1/move-vote", json={"target_q": 1, "target_r": 1}, params={"user_id": 1})
        # Change vote
        client.post("/api/campaigns/1/move-vote", json={"target_q": 5, "target_r": 5}, params={"user_id": 1})
        # Now player 2 votes same as host's NEW vote → resolves to (5,5)
        r = client.post("/api/campaigns/1/move-vote", json={"target_q": 5, "target_r": 5}, params={"user_id": 2})
        data = r.json()
        assert data["resolved"] is True
        assert data["winner_q"] == 5
        assert data["winner_r"] == 5


class TestMoveVoteGuards:
    """Non-member cannot vote."""

    def test_non_member_rejected(self, tmp_path, monkeypatch):
        db_path, conn = _make_test_db(tmp_path)
        _setup_campaign(conn, host_id=1, n_players=2)
        conn.execute("INSERT INTO users (id, username) VALUES (99, 'outsider')")
        conn.commit()
        conn.close()

        client = _make_client(monkeypatch, db_path)

        r = client.post("/api/campaigns/1/move-vote", json={"target_q": 1, "target_r": 1}, params={"user_id": 99})
        assert r.status_code == 403
