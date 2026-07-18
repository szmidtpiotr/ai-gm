"""#1426 — kill the unsigned `?user_id=` fallback + fail-start on empty JWT_SECRET.

- resolve_authed_user_id: no JWT + only `?user_id=` → 401 (fallback OFF by default).
- require_admin_role: no JWT → 401 (legacy DB-lookup fallback OFF by default).
- jwt_service._secret: empty JWT_SECRET → RuntimeError (no predictable fallback key).
"""
import pytest
from fastapi import HTTPException

from app.core import jwt_auth
from app.services import jwt_service


def test_no_auth_header_rejected(monkeypatch):
    monkeypatch.delenv("ALLOW_LEGACY_USERID", raising=False)
    with pytest.raises(HTTPException) as ei:
        jwt_auth.resolve_authed_user_id(None, 4242)
    assert ei.value.status_code == 401


def test_legacy_userid_flag_reopens_fallback(monkeypatch):
    monkeypatch.setenv("ALLOW_LEGACY_USERID", "1")
    assert jwt_auth.resolve_authed_user_id(None, 4242) == 4242


def test_require_admin_role_no_token_rejected(monkeypatch):
    monkeypatch.delenv("ALLOW_LEGACY_USERID", raising=False)
    with pytest.raises(HTTPException) as ei:
        jwt_auth.require_admin_role(None, 1)
    assert ei.value.status_code == 401


def test_valid_jwt_still_resolves(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "unit-test-secret-key-32-characters-long")
    token = jwt_service.issue_access_token(user_id=77, username="u", role="player", is_admin=0)
    assert jwt_auth.resolve_authed_user_id(f"Bearer {token}", None) == 77


def test_missing_jwt_secret_fails(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        jwt_service._secret()
    # And any issuance path surfaces the same fail-start condition.
    with pytest.raises(RuntimeError):
        jwt_service.issue_access_token(user_id=1, username="u", role="player", is_admin=0)
