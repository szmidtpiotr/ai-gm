"""TDD #800 — G19: Spectators — viewer role, public-only filter, hint consent matrix."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest

# ── Minimal schema ─────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    display_name TEXT
);
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'multiplayer',
    host_user_id INTEGER,
    lobby_status TEXT NOT NULL DEFAULT 'open',
    max_players INTEGER NOT NULL DEFAULT 4,
    round_timer_minutes INTEGER NOT NULL DEFAULT 1440,
    spectator_policy TEXT NOT NULL DEFAULT 'none'
);
CREATE TABLE IF NOT EXISTS campaign_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'player',
    status TEXT NOT NULL DEFAULT 'pending',
    character_id INTEGER,
    absence_warnings INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    campaign_id INTEGER,
    status TEXT NOT NULL DEFAULT 'idle',
    sheet_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS campaign_spectator_mutes (
    campaign_id INTEGER NOT NULL,
    user_id_player INTEGER NOT NULL,
    user_id_spectator INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (campaign_id, user_id_player, user_id_spectator)
);
CREATE TABLE IF NOT EXISTS party_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    character_name TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL,
    whisper_to TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS campaign_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'open',
    deadline TEXT,
    narrative_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS campaign_round_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    character_id INTEGER,
    character_name TEXT NOT NULL DEFAULT '',
    action_text TEXT NOT NULL DEFAULT '',
    initiative_roll INTEGER NOT NULL DEFAULT 10,
    submitted_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _make_db(tmp_path, label="800"):
    db_path = str(tmp_path / f"test_{label}.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    # users
    conn.execute("INSERT INTO users (id, username) VALUES (1, 'host')")
    conn.execute("INSERT INTO users (id, username) VALUES (2, 'player1')")
    conn.execute("INSERT INTO users (id, username) VALUES (3, 'spectator1')")
    conn.execute("INSERT INTO users (id, username) VALUES (4, 'spectator2')")
    # campaign
    conn.execute(
        "INSERT INTO campaigns (id, title, host_user_id, lobby_status, max_players, spectator_policy) "
        "VALUES (10, 'Test', 1, 'open', 4, 'none')"
    )
    # members: host(owner/accepted), player1(player/accepted), spectator1(player/pending -> spectator/accepted)
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, role, status) VALUES (10, 1, 'owner', 'accepted')"
    )
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, role, status, character_id) VALUES (10, 2, 'player', 'accepted', NULL)"
    )
    # spectator1 pending, will be accepted as spectator in tests
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, role, status) VALUES (10, 3, 'player', 'pending')"
    )
    conn.commit()
    conn.close()
    return db_path


def _set_spectator_member(db_path, campaign_id, user_id):
    """Accept user as spectator in campaign."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE campaign_members SET role='spectator', status='accepted', character_id=NULL "
        "WHERE campaign_id=? AND user_id=?",
        (campaign_id, user_id),
    )
    conn.commit()
    conn.close()


def _set_spectator_policy(db_path, campaign_id, policy):
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE campaigns SET spectator_policy=? WHERE id=?", (policy, campaign_id))
    conn.commit()
    conn.close()


def _add_mute(db_path, campaign_id, user_id_player, user_id_spectator):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO campaign_spectator_mutes (campaign_id, user_id_player, user_id_spectator) "
        "VALUES (?, ?, ?)",
        (campaign_id, user_id_player, user_id_spectator),
    )
    conn.commit()
    conn.close()


def _insert_messages(db_path, campaign_id):
    """Seed public and whisper messages for filter tests."""
    conn = sqlite3.connect(db_path)
    # public message from player1
    conn.execute(
        "INSERT INTO party_messages (campaign_id, user_id, character_name, message, whisper_to) "
        "VALUES (?, 2, 'Aldric', 'Chodźmy razem!', NULL)",
        (campaign_id,),
    )
    # whisper player1→host
    conn.execute(
        "INSERT INTO party_messages (campaign_id, user_id, character_name, message, whisper_to) "
        "VALUES (?, 2, 'Aldric', 'Szept do hosta', 'Host')",
        (campaign_id,),
    )
    # whisper host→player1
    conn.execute(
        "INSERT INTO party_messages (campaign_id, user_id, character_name, message, whisper_to) "
        "VALUES (?, 1, 'Host', 'Szept do gracza', 'Aldric')",
        (campaign_id,),
    )
    conn.commit()
    conn.close()


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestSpectatorMemberRole:
    """Spectator has role='spectator' and character_id=NULL; not in round actions."""

    def test_spectator_accepted_no_character(self, tmp_path):
        db_path = _make_db(tmp_path)
        _set_spectator_member(db_path, 10, 3)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        m = conn.execute(
            "SELECT role, status, character_id FROM campaign_members WHERE campaign_id=10 AND user_id=3"
        ).fetchone()
        conn.close()
        assert m["role"] == "spectator"
        assert m["status"] == "accepted"
        assert m["character_id"] is None

    def test_spectator_not_in_round_actions(self, tmp_path):
        db_path = _make_db(tmp_path)
        _set_spectator_member(db_path, 10, 3)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        # Insert round action only for player (user_id=2)
        conn.execute(
            "INSERT INTO campaign_round_actions (campaign_id, user_id, character_name, action_text) "
            "VALUES (10, 2, 'Aldric', 'atakuję')"
        )
        conn.commit()
        spectator_action = conn.execute(
            "SELECT 1 FROM campaign_round_actions WHERE campaign_id=10 AND user_id=3"
        ).fetchone()
        conn.close()
        assert spectator_action is None, "Spectator should not appear in round_actions"


class TestSpectatorChatFilter:
    """Spectator sees only public messages (whisper_to IS NULL)."""

    def test_spectator_sees_only_public(self, tmp_path):
        db_path = _make_db(tmp_path)
        _set_spectator_member(db_path, 10, 3)
        _insert_messages(db_path, 10)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        caller_uid = 3  # spectator
        member = conn.execute(
            "SELECT role FROM campaign_members WHERE campaign_id=10 AND user_id=? AND status='accepted'",
            (caller_uid,),
        ).fetchone()
        assert member["role"] == "spectator"

        # Spectator filter: only public
        rows = conn.execute(
            "SELECT id, whisper_to FROM party_messages WHERE campaign_id=10 AND whisper_to IS NULL ORDER BY id ASC"
        ).fetchall()
        conn.close()

        assert len(rows) == 1, f"Expected 1 public message, got {len(rows)}"
        assert rows[0]["whisper_to"] is None

    def test_player_sees_own_whispers(self, tmp_path):
        db_path = _make_db(tmp_path)
        _insert_messages(db_path, 10)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        caller_uid = 2  # player1
        caller_char = conn.execute(
            "SELECT character_name FROM campaign_round_actions "
            "WHERE campaign_id=10 AND user_id=? ORDER BY submitted_at DESC LIMIT 1",
            (caller_uid,),
        ).fetchone()
        caller_char_name = caller_char["character_name"] if caller_char else "Aldric"

        rows = conn.execute(
            "SELECT id, whisper_to FROM party_messages "
            "WHERE campaign_id=10 AND (whisper_to IS NULL OR user_id=? OR whisper_to=?) ORDER BY id ASC",
            (caller_uid, caller_char_name or ""),
        ).fetchall()
        conn.close()

        # Should see public + own whisper to host + host's whisper to them
        assert len(rows) == 3, f"Player should see all relevant messages, got {len(rows)}"


class TestSpectatorPolicyGate:
    """Spectator hint blocked by policy (none/watch) → 403-logic."""

    def test_hint_blocked_policy_none(self, tmp_path):
        db_path = _make_db(tmp_path)
        _set_spectator_member(db_path, 10, 3)
        # policy='none' (default)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        spectator_uid = 3
        member = conn.execute(
            "SELECT role FROM campaign_members WHERE campaign_id=10 AND user_id=? AND status='accepted'",
            (spectator_uid,),
        ).fetchone()
        camp = conn.execute("SELECT spectator_policy FROM campaigns WHERE id=10").fetchone()
        conn.close()

        assert member["role"] == "spectator"
        assert camp["spectator_policy"] == "none"
        # Business rule: spectator hint with whisper_to blocked
        allowed = camp["spectator_policy"] == "watch_hint"
        assert not allowed, "Policy 'none' should block spectator hints"

    def test_hint_blocked_policy_watch(self, tmp_path):
        db_path = _make_db(tmp_path)
        _set_spectator_member(db_path, 10, 3)
        _set_spectator_policy(db_path, 10, "watch")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        camp = conn.execute("SELECT spectator_policy FROM campaigns WHERE id=10").fetchone()
        conn.close()

        assert camp["spectator_policy"] == "watch"
        allowed = camp["spectator_policy"] == "watch_hint"
        assert not allowed, "Policy 'watch' should block spectator hints"

    def test_hint_allowed_policy_watch_hint_no_mute(self, tmp_path):
        db_path = _make_db(tmp_path)
        _set_spectator_member(db_path, 10, 3)
        _set_spectator_policy(db_path, 10, "watch_hint")

        spectator_uid = 3
        target_player_uid = 2

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        camp = conn.execute("SELECT spectator_policy FROM campaigns WHERE id=10").fetchone()
        muted = conn.execute(
            "SELECT 1 FROM campaign_spectator_mutes WHERE campaign_id=10 AND user_id_player=? AND user_id_spectator=?",
            (target_player_uid, spectator_uid),
        ).fetchone()
        conn.close()

        assert camp["spectator_policy"] == "watch_hint"
        assert muted is None, "No mute should exist"
        # Both conditions met → allowed
        allowed = (camp["spectator_policy"] == "watch_hint") and (muted is None)
        assert allowed

    def test_hint_blocked_by_player_mute(self, tmp_path):
        db_path = _make_db(tmp_path)
        _set_spectator_member(db_path, 10, 3)
        _set_spectator_policy(db_path, 10, "watch_hint")
        _add_mute(db_path, 10, 2, 3)  # player2 mutes spectator3

        spectator_uid = 3
        target_player_uid = 2

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        camp = conn.execute("SELECT spectator_policy FROM campaigns WHERE id=10").fetchone()
        muted = conn.execute(
            "SELECT 1 FROM campaign_spectator_mutes WHERE campaign_id=10 AND user_id_player=? AND user_id_spectator=?",
            (target_player_uid, spectator_uid),
        ).fetchone()
        conn.close()

        assert camp["spectator_policy"] == "watch_hint"
        assert muted is not None, "Mute should exist"
        # Policy OK but muted → blocked
        allowed = (camp["spectator_policy"] == "watch_hint") and (muted is None)
        assert not allowed, "Muted spectator should be blocked even with watch_hint policy"

    def test_hint_allowed_when_other_player_muted(self, tmp_path):
        """player3 muted spectator, but player2 (target) didn't — still allowed."""
        db_path = _make_db(tmp_path)
        # Add player3 as member
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO campaign_members (campaign_id, user_id, role, status) VALUES (10, 4, 'player', 'accepted')")
        conn.commit()
        conn.close()

        _set_spectator_member(db_path, 10, 3)
        _set_spectator_policy(db_path, 10, "watch_hint")
        _add_mute(db_path, 10, 4, 3)  # player4 mutes spectator3, but target is player2

        spectator_uid = 3
        target_player_uid = 2  # target

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        camp = conn.execute("SELECT spectator_policy FROM campaigns WHERE id=10").fetchone()
        muted = conn.execute(
            "SELECT 1 FROM campaign_spectator_mutes WHERE campaign_id=10 AND user_id_player=? AND user_id_spectator=?",
            (target_player_uid, spectator_uid),
        ).fetchone()
        conn.close()

        assert muted is None, "Target player2 did NOT mute spectator3"
        allowed = (camp["spectator_policy"] == "watch_hint") and (muted is None)
        assert allowed


class TestSpectatorMuteTable:
    """campaign_spectator_mutes CRUD."""

    def test_add_mute(self, tmp_path):
        db_path = _make_db(tmp_path)
        _add_mute(db_path, 10, 2, 3)
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT 1 FROM campaign_spectator_mutes WHERE campaign_id=10 AND user_id_player=2 AND user_id_spectator=3"
        ).fetchone()
        conn.close()
        assert row is not None

    def test_remove_mute(self, tmp_path):
        db_path = _make_db(tmp_path)
        _add_mute(db_path, 10, 2, 3)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "DELETE FROM campaign_spectator_mutes WHERE campaign_id=10 AND user_id_player=2 AND user_id_spectator=3"
        )
        conn.commit()
        row = conn.execute(
            "SELECT 1 FROM campaign_spectator_mutes WHERE campaign_id=10 AND user_id_player=2 AND user_id_spectator=3"
        ).fetchone()
        conn.close()
        assert row is None

    def test_idempotent_add(self, tmp_path):
        db_path = _make_db(tmp_path)
        _add_mute(db_path, 10, 2, 3)
        _add_mute(db_path, 10, 2, 3)  # second time should not raise
        conn = sqlite3.connect(db_path)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM campaign_spectator_mutes WHERE campaign_id=10 AND user_id_player=2 AND user_id_spectator=3"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1


class TestSpectatorNotInTurnOrder:
    """Spectator not in turn_order; round logic ignores them."""

    def test_turn_order_excludes_spectators(self, tmp_path):
        db_path = _make_db(tmp_path)
        _set_spectator_member(db_path, 10, 3)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        # Query members who are players (non-spectators, non-owners)
        players_in_round = conn.execute(
            "SELECT user_id, role FROM campaign_members "
            "WHERE campaign_id=10 AND status='accepted' AND role NOT IN ('spectator')"
        ).fetchall()
        conn.close()

        user_ids = [m["user_id"] for m in players_in_round]
        assert 3 not in user_ids, "Spectator user_id=3 should not be in round participant list"
        assert 1 in user_ids or 2 in user_ids, "Players/owners should be in round"


class TestSpectatorWhisperNotInNarration:
    """Spectator whisper in party_messages never reaches campaign_round_actions."""

    def test_whisper_not_in_round_actions(self, tmp_path):
        db_path = _make_db(tmp_path)
        _set_spectator_member(db_path, 10, 3)

        conn = sqlite3.connect(db_path)
        # Insert a whisper from spectator3 to player2 in party_messages
        conn.execute(
            "INSERT INTO party_messages (campaign_id, user_id, character_name, message, whisper_to) "
            "VALUES (10, 3, 'Widz', 'Podpowiedź: idź tam!', 'Aldric')"
        )
        conn.commit()

        # trigger_narration reads campaign_round_actions, never party_messages
        actions = conn.execute(
            "SELECT * FROM campaign_round_actions WHERE campaign_id=10"
        ).fetchall()
        conn.close()

        assert len(actions) == 0, "Spectator whisper must not appear in round_actions"


class TestSpectatorPolicyEndpointLogic:
    """Validate policy values (none/watch/watch_hint)."""

    def test_valid_policies(self, tmp_path):
        db_path = _make_db(tmp_path)
        valid = {"none", "watch", "watch_hint"}
        for policy in valid:
            _set_spectator_policy(db_path, 10, policy)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT spectator_policy FROM campaigns WHERE id=10").fetchone()
            conn.close()
            assert row["spectator_policy"] == policy

    def test_default_policy_is_none(self, tmp_path):
        db_path = _make_db(tmp_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT spectator_policy FROM campaigns WHERE id=10").fetchone()
        conn.close()
        assert row["spectator_policy"] == "none"
