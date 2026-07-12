"""Issue #895 — public verification-link resend breaks the login-gate deadlock.

An onboarded, unverified user whose 72h link expired cannot log in (403
email_unverified, no token) and so cannot reach the authenticated
/auth/resend-verification. The public endpoint keyed by email fixes that:
always 200 (never reveals existence), rate-limited 1 per 120s, and it derives
recency from expires_at because the tokens table has no created_at column.
"""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app.api import auth
from app.api.auth import ResendVerificationPublicReq, resend_verification_public


def _mkdb(path):
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT, email_verified_at TEXT, is_active INTEGER DEFAULT 1
        )"""
    )
    conn.execute(
        """CREATE TABLE email_verification_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, token TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL, used_at TEXT
        )"""
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "t895.db")
    _mkdb(path)
    monkeypatch.setattr(auth, "_AUTH_DB", path)
    monkeypatch.setenv(auth.BASE_URL_ENV, "https://example.test")
    return path


@pytest.fixture()
def sent(monkeypatch):
    calls = []
    import app.services.email_service as es

    monkeypatch.setattr(es, "send_verification_email", lambda to, link: calls.append((to, link)))
    return calls


def _user(db, uid=1, email="gate@example.test", verified=None, active=1):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO users (id, email, email_verified_at, is_active) VALUES (?,?,?,?)",
        (uid, email, verified, active),
    )
    conn.commit()
    conn.close()


def _tokens(db, uid=1):
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT token, expires_at FROM email_verification_tokens WHERE user_id=?", (uid,)
    ).fetchall()
    conn.close()
    return rows


def test_unverified_user_gets_fresh_link(db, sent):
    _user(db, email="gate@example.test", verified=None)
    res = resend_verification_public(ResendVerificationPublicReq(email="GATE@example.test"))
    assert res["ok"] is True
    assert len(_tokens(db)) == 1, "a new verification token must be issued"
    assert len(sent) == 1 and sent[0][0] == "gate@example.test"
    assert "/graj/weryfikacja-email?token=" in sent[0][1]


def test_rate_limited_within_120s_no_second_token(db, sent):
    _user(db, verified=None)
    # A token issued ~30s ago: expires 72h from its creation → created = expires-72h.
    fresh_exp = (datetime.now(timezone.utc) + timedelta(hours=72) - timedelta(seconds=30)).isoformat()
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO email_verification_tokens (user_id, token, expires_at) VALUES (1,'x',?)",
        (fresh_exp,),
    )
    conn.commit()
    conn.close()
    res = resend_verification_public(ResendVerificationPublicReq(email="gate@example.test"))
    assert res["ok"] is True  # always 200
    assert len(_tokens(db)) == 1, "throttled — no new token"
    assert sent == [], "throttled — no email"


def test_stale_token_allows_resend(db, sent):
    _user(db, verified=None)
    old_exp = (datetime.now(timezone.utc) + timedelta(hours=72) - timedelta(hours=1)).isoformat()
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO email_verification_tokens (user_id, token, expires_at) VALUES (1,'old',?)",
        (old_exp,),
    )
    conn.commit()
    conn.close()
    resend_verification_public(ResendVerificationPublicReq(email="gate@example.test"))
    assert len(_tokens(db)) == 2, "prior token is >120s old → new one issued"
    assert len(sent) == 1


def test_already_verified_no_link(db, sent):
    _user(db, verified="2026-01-01T00:00:00+00:00")
    res = resend_verification_public(ResendVerificationPublicReq(email="gate@example.test"))
    assert res["ok"] is True
    assert _tokens(db) == [] and sent == []


def test_unknown_email_is_silent_200(db, sent):
    res = resend_verification_public(ResendVerificationPublicReq(email="nobody@example.test"))
    assert res["ok"] is True  # never reveal existence
    assert sent == []


def test_inactive_account_ignored(db, sent):
    _user(db, email="ban@example.test", verified=None, active=0)
    resend_verification_public(ResendVerificationPublicReq(email="ban@example.test"))
    assert sent == []
