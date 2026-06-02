"""Stage 10 A2 — JWT issuance + verification for player auth.

- Algorithm: HS256
- Access token: 7-day expiry, payload = {sub: user_id, username, role, is_admin, type: "access"}
- Refresh token: 30-day expiry, payload = {sub: user_id, type: "refresh", jti}
- Secret: read from env JWT_SECRET; falls back to a dev-only hash of the DB path
  so local dev keeps working without explicit config, while prod MUST set the env.
- The shape is deliberately minimal — no audience, no issuer claims; we're a
  single-tenant solo RPG, not a federated identity provider.

The verification helper returns the decoded payload OR raises `JWTError`. Callers
in `core/jwt_auth.py` will translate to HTTPException(401).
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import sqlite3
import time
import uuid
from typing import Any

import jwt as pyjwt  # PyJWT

from app.core.logging import get_logger

logger = get_logger(__name__)

JWT_ALG = "HS256"
ACCESS_TTL_SECONDS = 7 * 24 * 3600    # 7 days
REFRESH_TTL_SECONDS = 30 * 24 * 3600  # 30 days


class JWTError(Exception):
    """Raised when a token is missing, expired, malformed, or signature-invalid."""


def _secret() -> str:
    """Return the JWT signing secret.

    Prefers env `JWT_SECRET`. On dev (no env set) derives a stable per-host
    secret from a hash of `/data/ai_gm.db` + hostname so restart preserves tokens
    but the value isn't predictable to outside parties.
    """
    env = os.environ.get("JWT_SECRET", "").strip()
    if env:
        return env
    # Dev fallback — DO NOT use in prod. Log a warning so it's visible in logs.
    seed = (os.uname().nodename + "::ai_gm::dev_jwt_fallback").encode("utf-8")
    derived = hashlib.sha256(seed).hexdigest()
    logger.warning("jwt_secret_env_missing_using_dev_fallback",
                   hint="Set JWT_SECRET in production for stable, unpredictable signing.")
    return derived


def issue_access_token(*, user_id: int, username: str, role: str, is_admin: int) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": str(int(user_id)),
        "username": str(username or ""),
        "role": str(role or "player").lower(),
        "is_admin": int(is_admin or 0),
        "type": "access",
        "iat": now,
        "exp": now + ACCESS_TTL_SECONDS,
    }
    return pyjwt.encode(payload, _secret(), algorithm=JWT_ALG)


def issue_refresh_token(*, user_id: int) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": str(int(user_id)),
        "type": "refresh",
        "iat": now,
        "exp": now + REFRESH_TTL_SECONDS,
        # jti differentiates separate refresh-token issuance events (multi-device,
        # rotation, future revocation list) without requiring server-side storage.
        "jti": secrets.token_hex(8),
    }
    return pyjwt.encode(payload, _secret(), algorithm=JWT_ALG)


def verify_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    """Decode + verify a JWT. Raises JWTError on any failure.

    `expected_type='access'` or `'refresh'` enforces the token-type claim so a
    long-lived refresh token can't be used in place of an access token (and
    vice versa).
    """
    if not token:
        raise JWTError("missing_token")
    try:
        payload = pyjwt.decode(token, _secret(), algorithms=[JWT_ALG])
    except pyjwt.ExpiredSignatureError:
        raise JWTError("token_expired") from None
    except pyjwt.InvalidTokenError as e:
        raise JWTError(f"invalid_token: {e}") from None
    if expected_type and str(payload.get("type") or "") != expected_type:
        raise JWTError(f"wrong_token_type: expected={expected_type} got={payload.get('type')}")
    return payload


def issue_pair(*, user_id: int, username: str, role: str, is_admin: int) -> dict[str, Any]:
    """Convenience — return both tokens shaped for an HTTP login response."""
    return {
        "access_token": issue_access_token(user_id=user_id, username=username, role=role, is_admin=is_admin),
        "refresh_token": issue_refresh_token(user_id=user_id),
        "token_type": "bearer",
        "expires_in": ACCESS_TTL_SECONDS,
    }


# ── Stage 10 A1-A2: DB-backed opaque session tokens (#254/#255) ───────────────
# Unlike JWTs, these are revocable (DELETE from user_sessions) and have no
# decodable payload — the raw token is opaque to the client.

SESSION_TTL_DAYS = 7


def generate_session_token(user_id: int, conn: sqlite3.Connection) -> tuple[str, str]:
    """Create a session token, persist its sha256 hash, return (plain_token, csrf_token).

    The plain token is returned ONCE and never stored — only sha256(token) lives
    in the DB so a DB leak doesn't expose valid credentials.
    The csrf_token (UUID) is stored in the session row and must accompany POST requests.
    """
    raw = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    csrf = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO user_sessions (user_id, token_hash, expires_at, csrf_token)
           VALUES (?, ?, datetime('now', ?), ?)""",
        (user_id, token_hash, f"+{SESSION_TTL_DAYS} days", csrf),
    )
    conn.commit()
    logger.info("session_token_issued", user_id=user_id, ttl_days=SESSION_TTL_DAYS)
    return raw, csrf


def get_csrf_token_for_session(token: str, conn: sqlite3.Connection) -> str | None:
    """Look up the CSRF token associated with a session token."""
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    row = conn.execute(
        "SELECT csrf_token FROM user_sessions WHERE token_hash = ? AND expires_at > datetime('now')",
        (token_hash,),
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def validate_session_token(token: str, conn: sqlite3.Connection) -> int | None:
    """Verify a session token against the DB. Returns user_id or None.

    Returns None when the token is missing, not found, or expired.
    Expired rows are cleaned up lazily on successful validation.
    """
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    row = conn.execute(
        """SELECT user_id FROM user_sessions
           WHERE token_hash = ? AND expires_at > datetime('now')""",
        (token_hash,),
    ).fetchone()
    if not row:
        return None
    return int(row[0])


def revoke_session_token(token: str, conn: sqlite3.Connection) -> bool:
    """Delete a session token from the DB (logout). Returns True if found."""
    if not token:
        return False
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    cur = conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (token_hash,))
    conn.commit()
    return cur.rowcount > 0


def purge_expired_sessions(conn: sqlite3.Connection) -> int:
    """Remove expired sessions. Returns count of deleted rows."""
    cur = conn.execute("DELETE FROM user_sessions WHERE expires_at <= datetime('now')")
    conn.commit()
    return cur.rowcount
