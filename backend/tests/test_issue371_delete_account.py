"""TDD: Issue #371 — hard delete account removes user permanently with cascade."""
import sqlite3
import sys
import os

sys.path.insert(0, "/app")

import pytest
from app.services.admin_accounts import (
    create_account_admin,
    hard_delete_account,
    list_accounts,
)
DB_PATH = "/data/ai_gm.db"


def _make_user(username: str) -> int:
    row = create_account_admin(username=username, password="testpass1", display_name=username)
    return row["id"]


def _user_in_db(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        return row is not None
    finally:
        conn.close()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_hard_delete_removes_user_from_db():
    """After hard_delete_account, user row is gone from DB."""
    uid = _make_user("tdd_del_371_a")
    assert _user_in_db(uid), "User must exist before delete"

    result = hard_delete_account(uid)

    assert not _user_in_db(uid), "User must be gone from DB after hard delete"


def test_hard_delete_returns_deleted_counts():
    """hard_delete_account returns dict with characters_deleted and campaigns_deleted."""
    uid = _make_user("tdd_del_371_b")

    result = hard_delete_account(uid)

    assert "characters_deleted" in result
    assert "campaigns_deleted" in result
    assert isinstance(result["characters_deleted"], int)
    assert isinstance(result["campaigns_deleted"], int)


def test_hard_delete_user_not_in_list_accounts():
    """After hard_delete_account, user does not appear in list_accounts()."""
    uid = _make_user("tdd_del_371_c")
    assert any(u["id"] == uid for u in list_accounts()), "User must be in list before delete"

    hard_delete_account(uid)

    assert not any(u["id"] == uid for u in list_accounts()), "User must NOT be in list after hard delete"


def test_hard_delete_nonexistent_raises_key_error():
    """hard_delete_account raises KeyError for missing user_id."""
    with pytest.raises(KeyError):
        hard_delete_account(999999999)


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_list_accounts_still_works():
    """list_accounts() returns a list of dicts with expected keys."""
    accounts = list_accounts()
    assert isinstance(accounts, list)
    if accounts:
        assert "id" in accounts[0]
        assert "username" in accounts[0]
        assert "is_active" in accounts[0]
