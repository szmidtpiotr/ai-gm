"""TDD: Issue #955 — is_tester flag not persisted via PATCH /admin/accounts."""
import sys
import os
import sqlite3
import tempfile

sys.path.insert(0, "/app")

import pytest


# ─── Helpers ────────────────────────────────────────────────────────────────

def _make_db(tmp_path):
    db = os.path.join(tmp_path, "test.db")
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL DEFAULT '',
            display_name TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            is_admin INTEGER NOT NULL DEFAULT 0,
            is_tester INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT,
            row_key TEXT,
            operation TEXT,
            old_values TEXT,
            new_values TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "INSERT INTO users (username, display_name, is_active, is_admin, is_tester) VALUES (?,?,?,?,?)",
        ("testuser", "Test User", 1, 0, 0),
    )
    conn.commit()
    conn.close()
    return db


# ─── Test główny — is_tester zapisuje się ───────────────────────────────────

def test_update_account_persists_is_tester(tmp_path, monkeypatch):
    """update_account must persist is_tester=1 and return it in the result."""
    db = _make_db(str(tmp_path))
    import app.services.admin_accounts as svc
    monkeypatch.setattr(svc, "DB_PATH", db)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    user_id = conn.execute("SELECT id FROM users WHERE username='testuser'").fetchone()["id"]
    conn.close()

    result = svc.update_account(
        user_id,
        display_name="Test User",
        is_active=1,
        is_admin=0,
        is_tester=1,
    )

    assert result.get("is_tester") == 1, (
        f"is_tester should be 1 after update, got {result.get('is_tester')}"
    )

    # Verify DB directly
    conn2 = sqlite3.connect(db)
    row = conn2.execute("SELECT is_tester FROM users WHERE id=?", (user_id,)).fetchone()
    conn2.close()
    assert row[0] == 1, f"DB should have is_tester=1, got {row[0]}"


def test_update_account_clears_is_tester(tmp_path, monkeypatch):
    """update_account must persist is_tester=0 (clear tester flag)."""
    db = _make_db(str(tmp_path))
    # Pre-set is_tester=1
    conn = sqlite3.connect(db)
    conn.execute("UPDATE users SET is_tester=1 WHERE username='testuser'")
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE username='testuser'").fetchone()[0]
    conn.close()

    import app.services.admin_accounts as svc
    monkeypatch.setattr(svc, "DB_PATH", db)

    result = svc.update_account(
        user_id,
        display_name="Test User",
        is_active=1,
        is_admin=0,
        is_tester=0,
    )

    assert result.get("is_tester") == 0, (
        f"is_tester should be 0 after clear, got {result.get('is_tester')}"
    )


# ─── Backward compatibility — is_tester=None leaves existing value ──────────

def test_update_account_is_tester_none_preserves_existing(tmp_path, monkeypatch):
    """When is_tester=None (not sent), existing DB value must be preserved."""
    db = _make_db(str(tmp_path))
    conn = sqlite3.connect(db)
    conn.execute("UPDATE users SET is_tester=1 WHERE username='testuser'")
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE username='testuser'").fetchone()[0]
    conn.close()

    import app.services.admin_accounts as svc
    monkeypatch.setattr(svc, "DB_PATH", db)

    result = svc.update_account(
        user_id,
        display_name="Test User",
        is_active=1,
        is_admin=0,
        # is_tester NOT passed → defaults to None
    )

    assert result.get("is_tester") == 1, (
        f"Existing is_tester=1 should be preserved when not passed, got {result.get('is_tester')}"
    )


def test_pydantic_model_accepts_is_tester():
    """AccountPatchReq must accept is_tester field without validation error."""
    from app.routers.admin import AccountPatchReq

    req = AccountPatchReq(display_name="X", is_active=1, is_admin=0, is_tester=1)
    assert req.is_tester == 1, f"AccountPatchReq.is_tester should be 1, got {req.is_tester}"

    req_none = AccountPatchReq(display_name="X", is_active=1, is_admin=0)
    assert req_none.is_tester is None
