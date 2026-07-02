"""TDD: Issue #1022 — delete idle hero (NULL campaign_id) must return 200, not 500."""
import sys
import pytest
from unittest import mock

sys.path.insert(0, '/app')


class _Row(dict):
    """sqlite3.Row stand-in: supports dict item access."""
    def __getitem__(self, k):
        return super().__getitem__(k)
    def __bool__(self):
        return True


class _Cursor:
    def __init__(self, row=None):
        self._row = row
    def fetchone(self):
        return self._row


class _Conn:
    """SQL-aware stub. #1071 added a live-lock check that queries `campaign_id FROM
    characters` (row[0]) then `active_combat`/`game_sessions` — a query-blind stub
    that always returned the fixture character row would false-positive the lock
    (and mis-index row[0]) here, breaking these backward-compat cases."""
    def __init__(self, row):
        self._row = row
        self.row_factory = None
    def execute(self, sql='', params=()):
        if 'campaign_id FROM characters' in sql:
            cid = self._row['campaign_id'] if self._row else None
            return _Cursor((cid,) if self._row else None)
        if 'FROM characters' in sql:
            return _Cursor(self._row)
        return _Cursor(None)
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


# ─── Test główny — Bug 1 ────────────────────────────────────────────────────

def test_delete_idle_hero_returns_ok_campaign_id_none():
    """Idle hero (campaign_id=NULL) delete must return ok=True, campaign_id=None — not TypeError."""
    row = _Row(id=9901, name='TestIdle', campaign_id=None, user_id=42)
    conn = _Conn(row)

    with mock.patch('sqlite3.connect', return_value=conn):
        from app.services.admin_character_recreate import delete_character_admin
        result = delete_character_admin(9901)

    assert result['ok'] is True
    assert result['deleted_id'] == 9901
    assert result['campaign_id'] is None  # NOT int(None) → TypeError


def test_delete_active_hero_campaign_id_is_int():
    """Hero in campaign: campaign_id must survive as int (backward compat)."""
    row = _Row(id=9902, name='TestActive', campaign_id=55, user_id=42)
    conn = _Conn(row)

    with mock.patch('sqlite3.connect', return_value=conn):
        from app.services.admin_character_recreate import delete_character_admin
        result = delete_character_admin(9902)

    assert result['ok'] is True
    assert result['campaign_id'] == 55
    assert isinstance(result['campaign_id'], int)


def test_delete_missing_hero_raises_keyerror():
    """Non-existent hero must raise KeyError (router converts to 404)."""
    conn = _Conn(None)

    with mock.patch('sqlite3.connect', return_value=conn):
        from app.services.admin_character_recreate import delete_character_admin
        with pytest.raises(KeyError, match='character_not_found'):
            delete_character_admin(0)
