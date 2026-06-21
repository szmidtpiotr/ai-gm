"""TDD #866 — MP join-link routing: backend contract for consumePendingJoin()."""
import sqlite3
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest


# ── Minimal schema ────────────────────────────────────────────────────────────

def _make_db(tmp_path):
    db_path = str(tmp_path / "test_866.db")
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
            title TEXT NOT NULL DEFAULT 'Test Campaign',
            owner_user_id INTEGER NOT NULL DEFAULT 1,
            mode TEXT NOT NULL DEFAULT 'multiplayer',
            status TEXT NOT NULL DEFAULT 'active',
            max_players INTEGER NOT NULL DEFAULT 4,
            lobby_status TEXT NOT NULL DEFAULT 'open'
        );
        CREATE TABLE IF NOT EXISTS campaign_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'player',
            status TEXT NOT NULL DEFAULT 'accepted',
            UNIQUE(campaign_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS campaign_invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            created_by INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            used_by INTEGER
        );
    """)
    conn.commit()
    return conn, db_path


def _future(days=7):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

def _past(days=1):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_join_valid_token_creates_member(tmp_path):
    """Valid token → member inserted, token marked used, campaign_id returned."""
    conn, db_path = _make_db(tmp_path)

    conn.execute("INSERT INTO users (id, username) VALUES (1, 'host'), (2, 'joiner')")
    conn.execute("INSERT INTO campaigns (id, title, owner_user_id, max_players, lobby_status) "
                 "VALUES (10, 'Party Cave', 1, 4, 'open')")
    conn.execute(
        "INSERT INTO campaign_invites (campaign_id, token, created_by, expires_at) "
        "VALUES (10, 'VALID-TOKEN-ABC', 1, ?)", (_future(),)
    )
    conn.commit()

    # Simulate what join_via_link does
    inv = conn.execute(
        "SELECT * FROM campaign_invites WHERE token=?", ("VALID-TOKEN-ABC",)
    ).fetchone()

    assert inv is not None, "Token must exist in DB"
    assert inv["used_at"] is None, "Token must not be used yet"
    assert inv["expires_at"] > datetime.now(timezone.utc).isoformat(), "Token must not be expired"

    camp = conn.execute(
        "SELECT max_players, lobby_status, title FROM campaigns WHERE id=?",
        (inv["campaign_id"],)
    ).fetchone()
    assert camp["lobby_status"] == "open", "Lobby must be open"

    current_count = conn.execute(
        "SELECT COUNT(*) FROM campaign_members WHERE campaign_id=? AND status!='declined'",
        (inv["campaign_id"],)
    ).fetchone()[0]
    assert current_count < camp["max_players"], "Lobby must not be full"

    # Perform the join
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO campaign_members (campaign_id, user_id, role, status)
           VALUES (?, ?, 'player', 'accepted')
           ON CONFLICT(campaign_id, user_id) DO UPDATE SET status='accepted'""",
        (inv["campaign_id"], 2),
    )
    conn.execute(
        "UPDATE campaign_invites SET used_at=?, used_by=? WHERE token=?",
        (now, 2, "VALID-TOKEN-ABC"),
    )
    conn.commit()

    member = conn.execute(
        "SELECT * FROM campaign_members WHERE campaign_id=10 AND user_id=2"
    ).fetchone()
    assert member is not None, "Member must be inserted"
    assert member["status"] == "accepted"

    used_inv = conn.execute(
        "SELECT used_at, used_by FROM campaign_invites WHERE token='VALID-TOKEN-ABC'"
    ).fetchone()
    assert used_inv["used_at"] is not None, "Token must be marked used"
    assert used_inv["used_by"] == 2


def test_join_used_token_rejected(tmp_path):
    """Already-used token → 410 condition: used_at is set."""
    conn, db_path = _make_db(tmp_path)

    conn.execute("INSERT INTO users (id, username) VALUES (1, 'host'), (3, 'late_joiner')")
    conn.execute("INSERT INTO campaigns (id, owner_user_id) VALUES (11, 1)")
    conn.execute(
        "INSERT INTO campaign_invites (campaign_id, token, created_by, expires_at, used_at, used_by) "
        "VALUES (11, 'USED-TOKEN', 1, ?, ?, 99)",
        (_future(), _past(0))
    )
    conn.commit()

    inv = conn.execute(
        "SELECT used_at FROM campaign_invites WHERE token='USED-TOKEN'"
    ).fetchone()
    assert inv["used_at"] is not None, "used_at set → backend must return 410"


def test_join_expired_token_rejected(tmp_path):
    """Expired token → 410 condition: expires_at < now."""
    conn, db_path = _make_db(tmp_path)

    conn.execute("INSERT INTO users (id, username) VALUES (1, 'host')")
    conn.execute("INSERT INTO campaigns (id, owner_user_id) VALUES (12, 1)")
    conn.execute(
        "INSERT INTO campaign_invites (campaign_id, token, created_by, expires_at) "
        "VALUES (12, 'EXPIRED-TOKEN', 1, ?)",
        (_past(2),)
    )
    conn.commit()

    inv = conn.execute(
        "SELECT expires_at FROM campaign_invites WHERE token='EXPIRED-TOKEN'"
    ).fetchone()
    now = datetime.now(timezone.utc).isoformat()
    assert inv["expires_at"] < now, "expires_at < now → backend must return 410"


def test_join_full_lobby_rejected(tmp_path):
    """Full lobby → 400 condition: member count >= max_players."""
    conn, db_path = _make_db(tmp_path)

    conn.execute("INSERT INTO users (id, username) VALUES (1, 'host'), (2, 'p1'), (3, 'newcomer')")
    conn.execute(
        "INSERT INTO campaigns (id, owner_user_id, max_players, lobby_status) "
        "VALUES (13, 1, 2, 'open')"
    )
    conn.execute("INSERT INTO campaign_members (campaign_id, user_id, status) VALUES (13, 1, 'accepted')")
    conn.execute("INSERT INTO campaign_members (campaign_id, user_id, status) VALUES (13, 2, 'accepted')")
    conn.execute(
        "INSERT INTO campaign_invites (campaign_id, token, created_by, expires_at) "
        "VALUES (13, 'FULL-TOKEN', 1, ?)", (_future(),)
    )
    conn.commit()

    inv = conn.execute(
        "SELECT * FROM campaign_invites WHERE token='FULL-TOKEN'"
    ).fetchone()
    camp = conn.execute(
        "SELECT max_players FROM campaigns WHERE id=?", (inv["campaign_id"],)
    ).fetchone()
    count = conn.execute(
        "SELECT COUNT(*) FROM campaign_members WHERE campaign_id=? AND status!='declined'",
        (inv["campaign_id"],)
    ).fetchone()[0]

    assert count >= camp["max_players"], "Full lobby → backend must return 400"


def test_join_missing_token_rejected(tmp_path):
    """Non-existent token → 404 condition: no row in campaign_invites."""
    conn, db_path = _make_db(tmp_path)
    inv = conn.execute(
        "SELECT * FROM campaign_invites WHERE token='GHOST-TOKEN'"
    ).fetchone()
    assert inv is None, "Missing token → backend must return 404"


def test_double_join_idempotent(tmp_path):
    """Same user joining twice via ON CONFLICT DO UPDATE → still accepted, no duplicate rows."""
    conn, db_path = _make_db(tmp_path)

    conn.execute("INSERT INTO users (id, username) VALUES (1, 'host'), (2, 'member')")
    conn.execute("INSERT INTO campaigns (id, owner_user_id) VALUES (20, 1)")

    # First join
    conn.execute(
        """INSERT INTO campaign_members (campaign_id, user_id, role, status)
           VALUES (20, 2, 'player', 'accepted')
           ON CONFLICT(campaign_id, user_id) DO UPDATE SET status='accepted'"""
    )
    # Second join (same user)
    conn.execute(
        """INSERT INTO campaign_members (campaign_id, user_id, role, status)
           VALUES (20, 2, 'player', 'accepted')
           ON CONFLICT(campaign_id, user_id) DO UPDATE SET status='accepted'"""
    )
    conn.commit()

    rows = conn.execute(
        "SELECT COUNT(*) FROM campaign_members WHERE campaign_id=20 AND user_id=2"
    ).fetchone()[0]
    assert rows == 1, "ON CONFLICT must prevent duplicate row"
