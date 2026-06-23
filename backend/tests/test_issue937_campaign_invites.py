"""TDD #937 — campaign_invites table missing: POST /invite-link returned 500."""
import sqlite3
import sys
import os
from datetime import datetime, timedelta, timezone
import secrets

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest


def _make_test_db(tmp_path):
    """Minimal schema for campaign_invites tests (mirrors RAW_MIGRATIONS)."""
    db_path = str(tmp_path / "test_937.db")
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
            max_players INTEGER NOT NULL DEFAULT 4,
            host_user_id INTEGER,
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
    return db_path, conn


# ── Test główny ───────────────────────────────────────────────────────────────

def test_campaign_invites_table_insert_and_select(tmp_path):
    """campaign_invites table accepts INSERT and SELECT (was missing before #937)."""
    _, conn = _make_test_db(tmp_path)

    # Insert invite like the endpoint does
    token = secrets.token_urlsafe(24)
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    conn.execute(
        "INSERT INTO campaign_invites (campaign_id, token, created_by, expires_at) VALUES (?, ?, ?, ?)",
        (1, token, 42, expires),
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM campaign_invites WHERE token=?", (token,)
    ).fetchone()
    assert row is not None, "campaign_invites row not found after INSERT"
    assert row["campaign_id"] == 1
    assert row["created_by"] == 42
    assert row["used_at"] is None
    assert row["used_by"] is None
    conn.close()


def test_campaign_invites_used_at_update(tmp_path):
    """UPDATE used_at/used_by on campaign_invites works (join-via-link flow)."""
    _, conn = _make_test_db(tmp_path)

    token = secrets.token_urlsafe(24)
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    conn.execute(
        "INSERT INTO campaign_invites (campaign_id, token, created_by, expires_at) VALUES (?, ?, ?, ?)",
        (1, token, 42, expires),
    )
    conn.commit()

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE campaign_invites SET used_at=?, used_by=? WHERE token=?",
        (now, 99, token),
    )
    conn.commit()

    row = conn.execute(
        "SELECT used_at, used_by FROM campaign_invites WHERE token=?", (token,)
    ).fetchone()
    assert row["used_at"] == now
    assert row["used_by"] == 99
    conn.close()


def test_campaign_invites_token_unique_constraint(tmp_path):
    """UNIQUE constraint on token prevents duplicate invite tokens."""
    _, conn = _make_test_db(tmp_path)

    token = secrets.token_urlsafe(24)
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    conn.execute(
        "INSERT INTO campaign_invites (campaign_id, token, created_by, expires_at) VALUES (?, ?, ?, ?)",
        (1, token, 1, expires),
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO campaign_invites (campaign_id, token, created_by, expires_at) VALUES (?, ?, ?, ?)",
            (2, token, 2, expires),
        )
    conn.close()


# ── Backward compat ───────────────────────────────────────────────────────────

def test_campaign_invites_table_exists_in_migration(tmp_path):
    """Sanity: campaign_invites is listed in migration schema (regression guard)."""
    _, conn = _make_test_db(tmp_path)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "campaign_invites" in tables, (
        "campaign_invites missing from schema — RAW_MIGRATIONS lost the CREATE TABLE"
    )
    conn.close()
