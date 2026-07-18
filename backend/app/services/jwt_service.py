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

import os
import secrets
import time
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
    """Return the JWT signing secret from env `JWT_SECRET`.

    #1426 — the previous dev fallback derived the HS256 key from a *known
    constant* (`sha256("/data/ai_gm.db::ai_gm::dev_jwt_fallback")`, the DB path
    is public in CLAUDE.md) → anyone could forge a token with arbitrary
    `sub`/`is_admin:1`. There is no safe fallback: an empty secret is a
    fail-startup condition, not a warning. DEV/PROD compose and env.test all set
    JWT_SECRET explicitly.
    """
    env = os.environ.get("JWT_SECRET", "").strip()
    if not env:
        raise RuntimeError(
            "JWT_SECRET is not set — refusing to sign/verify tokens with a "
            "predictable fallback key. Set JWT_SECRET (compose env / .env)."
        )
    return env


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
