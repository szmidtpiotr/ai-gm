"""TDD: Issue #1071 — deleting a hero mid-combat must be blocked (live-lock), force=True ends combat first."""
import os
import sqlite3
import sys
import tempfile
from unittest import mock

import pytest

sys.path.insert(0, '/app')


def _make_conn():
    """Real sqlite conn on a temp file (not a generic stub, not :memory: — the code under
    test opens its own connection via sqlite3.connect() and closes it in a `finally`, so a
    temp file lets a second, post-close connection re-read the persisted state for
    assertions). A stub that returns the same truthy row for every execute() would
    false-positive the live-lock check regardless of query, so this uses real SQL against
    a real schema."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE characters (id INTEGER PRIMARY KEY, name TEXT, campaign_id INTEGER, user_id INTEGER)")
    conn.execute("CREATE TABLE campaign_turns (character_id INTEGER)")
    conn.execute("CREATE TABLE active_combat (campaign_id INTEGER, status TEXT)")
    return conn, path


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_delete_blocked_during_active_combat():
    """Character with active_combat for its campaign → 409 live_locked, row NOT deleted."""
    conn, path = _make_conn()
    conn.execute("INSERT INTO characters (id, name, campaign_id, user_id) VALUES (9911, 'Locked', 77, 42)")
    conn.execute("INSERT INTO active_combat (campaign_id, status) VALUES (77, 'active')")
    conn.commit()

    with mock.patch('sqlite3.connect', return_value=conn):
        from app.services.admin_character_recreate import delete_character_admin
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            delete_character_admin(9911)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["reason"] == "live_locked"
    assert exc_info.value.detail["lock_reason"] == "active_combat"

    check = sqlite3.connect(path)
    still_there = check.execute("SELECT 1 FROM characters WHERE id = 9911").fetchone()
    check.close()
    os.remove(path)
    assert still_there is not None


def test_delete_force_ends_combat_and_deletes():
    """force=True bypasses the block, ends the active combat, then deletes the hero."""
    conn, path = _make_conn()
    conn.execute("INSERT INTO characters (id, name, campaign_id, user_id) VALUES (9912, 'ForcedOut', 78, 42)")
    conn.execute("INSERT INTO active_combat (campaign_id, status) VALUES (78, 'active')")
    conn.commit()

    with mock.patch('sqlite3.connect', return_value=conn), \
         mock.patch('app.services.combat_service.end_combat') as mock_end_combat:
        from app.services.admin_character_recreate import delete_character_admin
        result = delete_character_admin(9912, force=True)

    mock_end_combat.assert_called_once()
    assert mock_end_combat.call_args[0][0] == 78

    assert result['ok'] is True
    assert result['deleted_id'] == 9912

    check = sqlite3.connect(path)
    gone = check.execute("SELECT 1 FROM characters WHERE id = 9912").fetchone()
    check.close()
    os.remove(path)
    assert gone is None


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_delete_without_active_combat_still_works():
    """Hero with no active combat: delete succeeds exactly as before (no force needed)."""
    conn, path = _make_conn()
    conn.execute("INSERT INTO characters (id, name, campaign_id, user_id) VALUES (9913, 'Free', 79, 42)")
    conn.commit()

    with mock.patch('sqlite3.connect', return_value=conn):
        from app.services.admin_character_recreate import delete_character_admin
        result = delete_character_admin(9913)

    os.remove(path)
    assert result['ok'] is True
    assert result['deleted_id'] == 9913
    assert result['campaign_id'] == 79
