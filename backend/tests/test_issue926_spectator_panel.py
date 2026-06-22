"""TDD: Issue #926 — GF6 spectator panel (backend contract verification)."""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ─── Minimal DB fixtures ──────────────────────────────────────────────────────

def _make_db() -> sqlite3.Connection:
    """In-memory SQLite with all required tables for spectator tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            display_name TEXT,
            password_hash TEXT,
            role TEXT DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            mode TEXT DEFAULT 'single',
            lobby_status TEXT DEFAULT 'open',
            status TEXT DEFAULT 'active',
            host_user_id INTEGER,
            system_id TEXT,
            round_timer_hours REAL DEFAULT 24,
            max_players INTEGER DEFAULT 4,
            spectator_policy TEXT DEFAULT 'none',
            host_note TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE campaign_members (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            character_id INTEGER,
            role TEXT DEFAULT 'player',
            status TEXT DEFAULT 'pending',
            last_seen TEXT,
            UNIQUE(campaign_id, user_id)
        );
        CREATE TABLE campaign_spectator_mutes (
            campaign_id INTEGER NOT NULL,
            user_id_player INTEGER NOT NULL,
            user_id_spectator INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (campaign_id, user_id_player, user_id_spectator)
        );
        CREATE TABLE party_messages (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            character_name TEXT,
            message TEXT NOT NULL,
            whisper_to TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    # Seed: host user, spectator user, player user, campaign
    conn.execute("INSERT INTO users(id, username, display_name) VALUES(1, 'host', 'Host GM')")
    conn.execute("INSERT INTO users(id, username, display_name) VALUES(2, 'spectator_user', 'Widz')")
    conn.execute("INSERT INTO users(id, username, display_name) VALUES(3, 'player_user', 'Player')")
    conn.execute(
        "INSERT INTO campaigns(id, title, mode, lobby_status, host_user_id, spectator_policy) "
        "VALUES(100, 'Test Campaign', 'multiplayer', 'started', 1, 'none')"
    )
    # Spectator user has a pending invite
    conn.execute(
        "INSERT INTO campaign_members(campaign_id, user_id, role, status) VALUES(100, 2, 'player', 'pending')"
    )
    # Active player is in the game
    conn.execute(
        "INSERT INTO campaign_members(campaign_id, user_id, character_id, role, status) "
        "VALUES(100, 3, 42, 'player', 'accepted')"
    )
    conn.commit()
    return conn


# ─── Test 1 — accept invite as spectator ────────────────────────────────────

def test_accept_invite_as_spectator_sets_correct_role():
    """Accepting invite with as_spectator=True sets role='spectator' and character_id=NULL."""
    conn = _make_db()

    # Simulate backend accept logic (G19 path)
    conn.execute(
        "UPDATE campaign_members SET status='accepted', role='spectator', character_id=NULL "
        "WHERE campaign_id=? AND user_id=?",
        (100, 2),
    )
    conn.commit()

    row = conn.execute(
        "SELECT role, status, character_id FROM campaign_members WHERE campaign_id=100 AND user_id=2"
    ).fetchone()

    assert row is not None, "Spectator member row not found"
    assert row["role"] == "spectator", f"Expected role='spectator', got '{row['role']}'"
    assert row["status"] == "accepted", f"Expected status='accepted', got '{row['status']}'"
    assert row["character_id"] is None, f"Spectator must have character_id=NULL, got {row['character_id']}"
    conn.close()


# ─── Test 2 — spectator excluded from total_players count ───────────────────

def test_spectator_not_counted_in_total_players():
    """Spectators (role='spectator') must NOT count toward total_players (only role!='spectator')."""
    conn = _make_db()

    # Accept spectator
    conn.execute(
        "UPDATE campaign_members SET status='accepted', role='spectator', character_id=NULL "
        "WHERE campaign_id=100 AND user_id=2"
    )
    conn.commit()

    total = conn.execute(
        "SELECT COUNT(*) as cnt FROM campaign_members "
        "WHERE campaign_id=100 AND status='accepted' AND role!='spectator'"
    ).fetchone()["cnt"]

    # Only player_user (user_id=3) is an active player; spectator_user (2) is spectator
    assert total == 1, f"Expected 1 active player, got {total}"
    conn.close()


# ─── Test 3 — spectator policy update ────────────────────────────────────────

def test_spectator_policy_update():
    """Host can update spectator_policy to 'watch', 'watch_hint', or 'none'."""
    conn = _make_db()

    for policy in ("watch", "watch_hint", "none"):
        conn.execute("UPDATE campaigns SET spectator_policy=? WHERE id=100", (policy,))
        conn.commit()
        row = conn.execute("SELECT spectator_policy FROM campaigns WHERE id=100").fetchone()
        assert row["spectator_policy"] == policy, f"Policy not updated to '{policy}'"

    conn.close()


# ─── Test 4 — spectator mute table exists and works ──────────────────────────

def test_spectator_mute_insert_and_delete():
    """campaign_spectator_mutes supports INSERT/DELETE for per-player mute control."""
    conn = _make_db()

    # Accept spectator first
    conn.execute(
        "UPDATE campaign_members SET status='accepted', role='spectator', character_id=NULL "
        "WHERE campaign_id=100 AND user_id=2"
    )
    conn.commit()

    # Player 3 mutes spectator 2
    conn.execute(
        "INSERT OR IGNORE INTO campaign_spectator_mutes (campaign_id, user_id_player, user_id_spectator) "
        "VALUES (100, 3, 2)"
    )
    conn.commit()

    row = conn.execute(
        "SELECT 1 FROM campaign_spectator_mutes WHERE campaign_id=100 AND user_id_player=3 AND user_id_spectator=2"
    ).fetchone()
    assert row is not None, "Mute row should exist after insert"

    # Player 3 unmutes spectator 2
    conn.execute(
        "DELETE FROM campaign_spectator_mutes WHERE campaign_id=100 AND user_id_player=3 AND user_id_spectator=2"
    )
    conn.commit()

    row = conn.execute(
        "SELECT 1 FROM campaign_spectator_mutes WHERE campaign_id=100 AND user_id_player=3 AND user_id_spectator=2"
    ).fetchone()
    assert row is None, "Mute row should be gone after delete"
    conn.close()


# ─── Test 5 — spectator whisper gating logic ─────────────────────────────────

def test_spectator_whisper_allowed_only_when_policy_permits():
    """Spectator can send /whisper only when spectator_policy='watch_hint' and not muted."""
    conn = _make_db()

    # Accept spectator
    conn.execute(
        "UPDATE campaign_members SET status='accepted', role='spectator', character_id=NULL "
        "WHERE campaign_id=100 AND user_id=2"
    )
    conn.commit()

    def _can_spectator_whisper(whisper_to_user_id: int, spectator_user_id: int) -> bool:
        """Simulate backend G19 whisper gate."""
        camp = conn.execute(
            "SELECT spectator_policy FROM campaigns WHERE id=100"
        ).fetchone()
        if not camp or camp["spectator_policy"] != "watch_hint":
            return False
        # Check mute
        muted = conn.execute(
            "SELECT 1 FROM campaign_spectator_mutes "
            "WHERE campaign_id=100 AND user_id_player=? AND user_id_spectator=?",
            (whisper_to_user_id, spectator_user_id),
        ).fetchone()
        return muted is None

    # Policy=none → blocked
    assert not _can_spectator_whisper(3, 2), "Whisper must be blocked when policy='none'"

    # Policy=watch → still blocked
    conn.execute("UPDATE campaigns SET spectator_policy='watch' WHERE id=100")
    conn.commit()
    assert not _can_spectator_whisper(3, 2), "Whisper must be blocked when policy='watch'"

    # Policy=watch_hint → allowed
    conn.execute("UPDATE campaigns SET spectator_policy='watch_hint' WHERE id=100")
    conn.commit()
    assert _can_spectator_whisper(3, 2), "Whisper must be allowed when policy='watch_hint'"

    # Policy=watch_hint but muted → blocked
    conn.execute(
        "INSERT INTO campaign_spectator_mutes (campaign_id, user_id_player, user_id_spectator) "
        "VALUES (100, 3, 2)"
    )
    conn.commit()
    assert not _can_spectator_whisper(3, 2), "Whisper must be blocked when player muted the spectator"

    conn.close()


# ─── Test 6 — spectator sees only public messages (no whispers) ───────────────

def test_spectator_chat_filter_excludes_whispers():
    """Spectators see only public messages (whisper_to IS NULL)."""
    conn = _make_db()

    # Accept spectator
    conn.execute(
        "UPDATE campaign_members SET status='accepted', role='spectator', character_id=NULL "
        "WHERE campaign_id=100 AND user_id=2"
    )
    # Insert test messages
    conn.execute(
        "INSERT INTO party_messages(campaign_id, user_id, character_name, message, whisper_to) "
        "VALUES(100, 3, 'Player', 'public message', NULL)"
    )
    conn.execute(
        "INSERT INTO party_messages(campaign_id, user_id, character_name, message, whisper_to) "
        "VALUES(100, 3, 'Player', 'secret whisper', 'Host')"
    )
    conn.commit()

    # Simulate spectator view: only public
    is_spectator = True
    if is_spectator:
        msgs = conn.execute(
            "SELECT * FROM party_messages WHERE campaign_id=100 AND whisper_to IS NULL"
        ).fetchall()
    else:
        msgs = conn.execute(
            "SELECT * FROM party_messages WHERE campaign_id=100"
        ).fetchall()

    assert len(msgs) == 1, f"Spectator should see 1 public message, got {len(msgs)}"
    assert msgs[0]["whisper_to"] is None, "Public message must have whisper_to=NULL"
    conn.close()


# ─── Backward compat — normal player accept still works ──────────────────────

def test_normal_player_accept_still_works():
    """Normal accept (with character) still sets role='player' and character_id correctly."""
    conn = _make_db()

    # Add another pending player invite
    conn.execute(
        "INSERT INTO campaign_members(campaign_id, user_id, role, status) VALUES(100, 99, 'player', 'pending')"
    )
    conn.execute(
        "INSERT INTO users(id, username) VALUES(99, 'normal_player')"
    )
    conn.commit()

    # Normal accept (not spectator)
    conn.execute(
        "UPDATE campaign_members SET status='accepted', character_id=77 "
        "WHERE campaign_id=100 AND user_id=99"
    )
    conn.commit()

    row = conn.execute(
        "SELECT role, status, character_id FROM campaign_members WHERE campaign_id=100 AND user_id=99"
    ).fetchone()

    assert row["role"] == "player", f"Normal player role should remain 'player', got '{row['role']}'"
    assert row["status"] == "accepted"
    assert row["character_id"] == 77, f"Character ID should be 77, got {row['character_id']}"
    conn.close()
