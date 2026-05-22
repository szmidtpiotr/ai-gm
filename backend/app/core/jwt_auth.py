"""Stage 10 A2/A3 — FastAPI dependencies for JWT-based auth.

Two helpers:

- `current_user_optional`: returns the decoded JWT payload when Authorization
  header is present and valid, else None. Used during the 10-B transition where
  endpoints still accept `?user_id=X` query param — this dependency just makes
  JWT auth available without forcing it.

- `require_current_user`: same logic but raises HTTPException(401) when the
  token is missing/expired/invalid. Use this on endpoints that have been
  migrated to JWT-only (Sub-phase 10-C territory).

Helper `verify_request_user_matches(payload, query_user_id)` is used during the
overlap window to detect frontend code that still sends `?user_id=` AND a JWT —
ensures the two agree, prevents the JWT path from being silently spoofed by a
mismatched query param.
"""

from __future__ import annotations

from typing import Any

from fastapi import Header, HTTPException

from app.services.jwt_service import JWTError, verify_token


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def current_user_optional(
    authorization: str | None = Header(default=None),
) -> dict[str, Any] | None:
    """Returns the JWT payload when a valid Bearer token is present, else None.

    Used during the parallel-auth phase — endpoints that haven't migrated yet
    can still fall back to `?user_id=` query param when this returns None.
    """
    token = _extract_bearer(authorization)
    if not token:
        return None
    try:
        return verify_token(token, expected_type="access")
    except JWTError:
        return None


def require_current_user(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Returns the JWT payload; raises 401 when missing/invalid.

    Use on endpoints that are fully JWT-gated (10-C).
    """
    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization: Bearer <token>")
    try:
        return verify_token(token, expected_type="access")
    except JWTError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None


def verify_request_user_matches(payload: dict | None, query_user_id: int | None) -> None:
    """During the overlap window, if BOTH a JWT and a `?user_id=` are sent and
    they disagree, reject — prevents accidental spoofing through inconsistent
    request shape. No-op when one or both are absent.
    """
    if not payload or query_user_id is None:
        return
    try:
        jwt_uid = int(payload.get("sub") or 0)
    except (TypeError, ValueError):
        jwt_uid = 0
    if jwt_uid and int(query_user_id) != jwt_uid:
        raise HTTPException(
            status_code=400,
            detail=f"user_id query param ({query_user_id}) does not match JWT subject ({jwt_uid})",
        )
