"""#1424 — ownership guards for gameplay routers.

Tests the shared helpers in core/jwt_auth.py that every mutating Tier A/B endpoint
now calls: a user may only act on their OWN character/campaign, and an anonymous
request (no JWT, fallback OFF) is rejected.
"""
import sqlite3

import pytest
from fastapi import HTTPException

from app.core import jwt_auth
from app.services import jwt_service


def _seed(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE characters (id INTEGER PRIMARY KEY, user_id INTEGER)")
        conn.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY, owner_user_id INTEGER)")
        conn.execute("INSERT INTO characters(id, user_id) VALUES (10, 1)")   # owned by user 1
        conn.execute("INSERT INTO campaigns(id, owner_user_id) VALUES (20, 1)")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "game.db"
    _seed(str(p))
    # _owner_conn() imports resolve_db_path lazily from app.core.db_runtime.
    import app.core.db_runtime as db_runtime
    monkeypatch.setattr(db_runtime, "resolve_db_path", lambda: str(p))
    monkeypatch.setenv("JWT_SECRET", "unit-test-secret-key-32-characters-long")
    monkeypatch.delenv("ALLOW_LEGACY_USERID", raising=False)
    return str(p)


def _row_conn(db_path):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


# ── pure helpers ──────────────────────────────────────────────────────────────

def test_require_character_owner_ok(db):
    conn = _row_conn(db)
    try:
        row = jwt_auth.require_character_owner(conn, 10, 1)
        assert int(row["id"]) == 10
    finally:
        conn.close()


def test_require_character_owner_cross_user_403(db):
    conn = _row_conn(db)
    try:
        with pytest.raises(HTTPException) as ei:
            jwt_auth.require_character_owner(conn, 10, 2)
        assert ei.value.status_code == 403
    finally:
        conn.close()


def test_require_character_owner_missing_404(db):
    conn = _row_conn(db)
    try:
        with pytest.raises(HTTPException) as ei:
            jwt_auth.require_character_owner(conn, 999, 1)
        assert ei.value.status_code == 404
    finally:
        conn.close()


def test_require_campaign_owner_cross_user_403(db):
    conn = _row_conn(db)
    try:
        with pytest.raises(HTTPException) as ei:
            jwt_auth.require_campaign_owner(conn, 20, 2)
        assert ei.value.status_code == 403
    finally:
        conn.close()


# ── end-to-end guards used by endpoints ───────────────────────────────────────

def _token(uid):
    return "Bearer " + jwt_service.issue_access_token(
        user_id=uid, username="u", role="player", is_admin=0
    )


def test_assert_character_owner_owner_ok(db):
    assert jwt_auth.assert_character_owner(10, _token(1)) == 1


def test_assert_character_owner_cross_user_rejected(db):
    with pytest.raises(HTTPException) as ei:
        jwt_auth.assert_character_owner(10, _token(2))
    assert ei.value.status_code == 403


def test_assert_character_owner_no_auth_rejected(db):
    with pytest.raises(HTTPException) as ei:
        jwt_auth.assert_character_owner(10, None)
    assert ei.value.status_code == 401


def test_assert_campaign_owner_cross_user_rejected(db):
    with pytest.raises(HTTPException) as ei:
        jwt_auth.assert_campaign_owner(20, _token(2))
    assert ei.value.status_code == 403


def test_assert_campaign_owner_no_auth_rejected(db):
    with pytest.raises(HTTPException) as ei:
        jwt_auth.assert_campaign_owner(20, None)
    assert ei.value.status_code == 401
