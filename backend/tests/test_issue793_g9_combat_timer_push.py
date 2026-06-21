"""TDD #793 — G9: Timer walki 2 min + push 'Twoja kolej' per tura.

Acceptance criteria:
- COMBAT_TURN_TIMER_MINUTES == 2
- _push_combat_turn sets combat_turn_deadline (now+2min) on active_combat
- _push_combat_turn sends push to owner of player:{char_id} only (not broadcast)
- _push_combat_turn does NOT send push on enemy turn
- sweep_expired_combat_turns: expired player turn → apply_mp_default_defense + advance
- sweep_expired_combat_turns: enemy turn → skip (enemies never idle)
- sweep_expired_combat_turns: non-expired → skip
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest
from app.services import multiplayer_round_service as mrs


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_file_db(tmp_path):
    """Real file-based SQLite so connections can be re-opened after close."""
    db_path = str(tmp_path / "test_793.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS active_combat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL UNIQUE,
        character_id INTEGER NOT NULL DEFAULT 1,
        round INTEGER NOT NULL DEFAULT 1,
        turn_order TEXT NOT NULL DEFAULT '[]',
        current_turn TEXT NOT NULL DEFAULT '',
        combatants TEXT NOT NULL DEFAULT '[]',
        status TEXT NOT NULL DEFAULT 'active',
        ended_reason TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        combat_turn_deadline TEXT DEFAULT NULL
    );
    CREATE TABLE IF NOT EXISTS characters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        campaign_id INTEGER,
        name TEXT NOT NULL DEFAULT 'Hero',
        sheet_json TEXT NOT NULL DEFAULT '{}'
    );
    CREATE TABLE IF NOT EXISTS campaign_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        character_id INTEGER,
        status TEXT NOT NULL DEFAULT 'accepted'
    );
    INSERT INTO characters (id, user_id, campaign_id, name) VALUES (10, 101, 1, 'Aldric');
    INSERT INTO characters (id, user_id, campaign_id, name) VALUES (11, 102, 1, 'Mira');
    INSERT INTO campaign_members (campaign_id, user_id, character_id, status) VALUES (1, 101, 10, 'accepted');
    INSERT INTO campaign_members (campaign_id, user_id, character_id, status) VALUES (1, 102, 11, 'accepted');
    """)
    conn.commit()
    conn.close()
    return db_path


def _insert_active_combat(db_path, campaign_id=1, current_turn="player:10", status="active",
                           turn_order=None, combat_turn_deadline=None):
    if turn_order is None:
        turn_order = ["player:10", "player:11", "goblin_1"]
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO active_combat (campaign_id, character_id, current_turn, turn_order, combatants, status, combat_turn_deadline)
           VALUES (?, 10, ?, ?, '[]', ?, ?)""",
        (campaign_id, current_turn, json.dumps(turn_order), status, combat_turn_deadline)
    )
    conn.commit()
    conn.close()


def _make_mock_conn_for_push(char_user_map=None):
    """MagicMock connection that returns user_id for characters query."""
    if char_user_map is None:
        char_user_map = {10: 101, 11: 102}

    mock_conn = MagicMock()
    deadline_calls = []

    def execute_side(sql, *args, **kwargs):
        result = MagicMock()
        result.fetchone.return_value = None
        result.fetchall.return_value = []

        if "UPDATE active_combat" in sql and "combat_turn_deadline" in sql:
            deadline_calls.append(args[0] if args else ())

        elif "SELECT user_id FROM characters" in sql:
            char_id = args[0][0] if args and args[0] else 0
            uid = char_user_map.get(int(char_id))
            if uid:
                row = MagicMock()
                row.__getitem__ = lambda self, k: {"user_id": uid}.get(k)
                result.fetchone.return_value = row

        return result

    mock_conn.execute.side_effect = execute_side
    mock_conn._deadline_calls = deadline_calls
    return mock_conn


# ─── Test 1: Stała timera walki = 2 min ───────────────────────────────────────

def test_combat_turn_timer_minutes_is_2():
    """COMBAT_TURN_TIMER_MINUTES must be 2 (starting value per G9 policy)."""
    assert mrs.COMBAT_TURN_TIMER_MINUTES == 2


# ─── Test 2: _push_combat_turn ustawia deadline na active_combat ──────────────

def test_push_combat_turn_sets_deadline_on_active_combat(tmp_path):
    """_push_combat_turn must set combat_turn_deadline to now+2min on active_combat."""
    db_path = _make_file_db(tmp_path)
    _insert_active_combat(db_path, current_turn="player:10")

    before = datetime.now(timezone.utc)

    def make_conn():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        return c

    with patch("app.services.multiplayer_round_service._db", side_effect=make_conn), \
         patch("app.services.multiplayer_round_service.send_push"):
        mrs._push_combat_turn(1, "player:10")

    # Verify deadline persisted in file DB
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT combat_turn_deadline FROM active_combat WHERE campaign_id=1").fetchone()
    conn.close()

    assert row is not None, "combat_turn_deadline not set"
    dl = datetime.fromisoformat(row["combat_turn_deadline"].replace("Z", "+00:00"))
    expected_min = before + timedelta(minutes=2)
    expected_max = before + timedelta(minutes=3)
    assert expected_min <= dl <= expected_max, f"deadline {dl} not in expected range"


# ─── Test 3: push wysłany do właściwego gracza (nie broadcast) ────────────────

def test_push_combat_turn_sends_to_player_owner_only():
    """_push_combat_turn sends push to user_id owning character_id, not broadcast."""
    mock_conn = _make_mock_conn_for_push()

    with patch("app.services.multiplayer_round_service._db", return_value=mock_conn), \
         patch("app.services.multiplayer_round_service.send_push") as mock_push:
        mrs._push_combat_turn(1, "player:10")

    # should send to user_id=101 (owner of char 10), NOT to 102
    assert mock_push.call_count == 1
    called_user_id = mock_push.call_args[0][0]
    assert called_user_id == 101, f"push sent to {called_user_id}, expected 101"


# ─── Test 4: Brak push na turze wroga ────────────────────────────────────────

def test_push_combat_turn_no_push_on_enemy_turn():
    """_push_combat_turn must NOT send push when actor is an enemy, only sets deadline."""
    mock_conn = _make_mock_conn_for_push()

    with patch("app.services.multiplayer_round_service._db", return_value=mock_conn), \
         patch("app.services.multiplayer_round_service.send_push") as mock_push:
        mrs._push_combat_turn(1, "goblin_1")

    assert mock_push.call_count == 0, "push sent on enemy turn (should not happen)"
    # Deadline UPDATE should still have been called
    deadline_calls = mock_conn._deadline_calls
    assert len(deadline_calls) == 1, "deadline not updated for enemy turn"


# ─── Test 5: sweep pomija turę wroga ─────────────────────────────────────────

def test_sweep_expired_combat_turns_skips_enemy_turn(tmp_path):
    """sweep_expired_combat_turns does nothing when current_turn is an enemy actor."""
    db_path = _make_file_db(tmp_path)
    expired = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    _insert_active_combat(db_path, current_turn="goblin_1", combat_turn_deadline=expired)

    def make_conn():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        return c

    with patch("app.services.multiplayer_round_service._db", side_effect=make_conn), \
         patch("app.services.multiplayer_round_service.apply_mp_default_defense") as mock_def:
        mrs.sweep_expired_combat_turns()

    assert mock_def.call_count == 0, "default_defense called on enemy turn"


# ─── Test 6: sweep pomija niewyekspirowną turę ───────────────────────────────

def test_sweep_expired_combat_turns_skips_non_expired(tmp_path):
    """sweep_expired_combat_turns does nothing when deadline is in the future."""
    db_path = _make_file_db(tmp_path)
    future = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
    _insert_active_combat(db_path, current_turn="player:10", combat_turn_deadline=future)

    def make_conn():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        return c

    with patch("app.services.multiplayer_round_service._db", side_effect=make_conn), \
         patch("app.services.multiplayer_round_service.apply_mp_default_defense") as mock_def:
        mrs.sweep_expired_combat_turns()

    assert mock_def.call_count == 0, "default_defense called before deadline"


# ─── Test 7: sweep stosuje domyślną obronę po upłynięciu timera ──────────────

def test_sweep_expired_combat_turns_applies_defense_and_advances(tmp_path):
    """sweep_expired_combat_turns: expired player turn → apply_mp_default_defense called."""
    db_path = _make_file_db(tmp_path)
    expired = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    _insert_active_combat(db_path, current_turn="player:10", combat_turn_deadline=expired)

    mock_defense_result = {"ok": True, "actor": "player:10", "combat_state": None}

    def make_conn():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        return c

    with patch("app.services.multiplayer_round_service._db", side_effect=make_conn), \
         patch("app.services.multiplayer_round_service.apply_mp_default_defense",
               return_value=mock_defense_result) as mock_def, \
         patch("app.services.multiplayer_round_service._push_combat_turn"):
        mrs.sweep_expired_combat_turns()

    # apply_mp_default_defense called with (campaign_id=1, character_id=10)
    assert mock_def.call_count == 1
    args = mock_def.call_args[0]
    assert args[0] == 1    # campaign_id
    assert args[1] == 10   # character_id


# ─── Test 8: push NOT broadcast (send_push_to_campaign_players not called) ────

def test_push_combat_turn_does_not_use_broadcast():
    """_push_combat_turn uses send_push (per-user), NOT send_push_to_campaign_players."""
    mock_conn = _make_mock_conn_for_push()

    with patch("app.services.multiplayer_round_service._db", return_value=mock_conn), \
         patch("app.services.multiplayer_round_service.send_push") as mock_push, \
         patch("app.services.multiplayer_round_service.send_push_to_campaign_players") as mock_broadcast:
        mrs._push_combat_turn(1, "player:10")

    assert mock_broadcast.call_count == 0, "broadcast send_push_to_campaign_players was called (must NOT)"
    assert mock_push.call_count == 1, "per-user send_push was not called"


# ─── Backward compat: sweep_expired_rounds untouched ─────────────────────────

def test_sweep_expired_rounds_still_exists():
    """sweep_expired_rounds still callable — G9 adds new function, doesn't replace."""
    assert callable(mrs.sweep_expired_rounds)
