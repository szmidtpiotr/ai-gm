"""#1425 — /api/admin/dev-login must not mint an admin token for a regular player.

issue_dev_admin_token verified login+password+is_active but never is_admin/role,
so any user with valid credentials escalated to superadmin.
"""
import sqlite3

import bcrypt
import pytest

from app.services import admin_auth


def _seed_users(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password_hash TEXT,
                is_active INTEGER DEFAULT 1,
                is_admin INTEGER DEFAULT 0,
                role TEXT DEFAULT 'player'
            )
            """
        )
        conn.execute("CREATE TABLE admin_tokens (id INTEGER PRIMARY KEY, token_hash TEXT, label TEXT)")
        pw = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode("ascii")
        conn.execute(
            "INSERT INTO users(username, password_hash, is_active, is_admin, role) VALUES (?,?,1,0,'player')",
            ("player_joe", pw),
        )
        conn.execute(
            "INSERT INTO users(username, password_hash, is_active, is_admin, role) VALUES (?,?,1,1,'admin')",
            ("boss", pw),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    db = tmp_path / "auth.db"
    _seed_users(str(db))
    monkeypatch.setattr(admin_auth, "DB_PATH", str(db))
    return str(db)


def test_dev_login_rejects_non_admin(temp_db):
    with pytest.raises(PermissionError) as ei:
        admin_auth.issue_dev_admin_token("player_joe", "secret")
    assert str(ei.value) == "not_admin"


def test_dev_login_allows_admin(temp_db):
    token = admin_auth.issue_dev_admin_token("boss", "secret")
    assert isinstance(token, str) and len(token) > 10


def test_dev_login_wrong_password_still_invalid(temp_db):
    with pytest.raises(PermissionError) as ei:
        admin_auth.issue_dev_admin_token("boss", "wrong")
    assert str(ei.value) == "invalid_credentials"
