"""Stage 10 A3 — FastAPI dependency for DB-backed session token auth (#256).

`get_current_user`: extracts Bearer token → validates via user_sessions table →
sets request.state.user_id → returns user_id. Raises 401 on missing/invalid token.

Use as `Depends(get_current_user)` on player-facing endpoints once migrated off
the legacy `?user_id=` query param (see #259).

The existing jwt_auth.py helpers remain for admin routes and the JWT migration
window. This dependency is the target for the player-facing auth path.
"""

from __future__ import annotations

import sqlite3

from fastapi import Header, HTTPException, Request

from app.core.db_runtime import resolve_db_path
from app.services.jwt_service import get_csrf_token_for_session, validate_session_token


def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> int:
    """Validate Authorization: Bearer <opaque-session-token>.

    Returns the authenticated user_id and writes it to request.state.user_id.
    Raises 401 when the token is absent/expired, 403 on CSRF mismatch for POST.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization: Bearer <token>")

    raw_token = authorization[7:].strip()
    if not raw_token:
        raise HTTPException(status_code=401, detail="Empty token")

    conn = sqlite3.connect(resolve_db_path())
    try:
        user_id = validate_session_token(raw_token, conn)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        # Stage 10 A6 — CSRF validation on state-changing requests (#260).
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            stored_csrf = get_csrf_token_for_session(raw_token, conn)
            if stored_csrf and (not x_csrf_token or x_csrf_token != stored_csrf):
                raise HTTPException(status_code=403, detail="CSRF validation failed")
    finally:
        conn.close()

    request.state.user_id = user_id
    return user_id


def get_current_user_optional(
    request: Request,
    authorization: str | None = Header(default=None),
) -> int | None:
    """Like get_current_user but returns None instead of raising 401.

    Useful during the migration window where some endpoints still accept
    the legacy ?user_id= query param as a fallback. No CSRF check (read-only safe).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None

    raw_token = authorization[7:].strip()
    if not raw_token:
        return None

    conn = sqlite3.connect(resolve_db_path())
    try:
        user_id = validate_session_token(raw_token, conn)
    finally:
        conn.close()

    if user_id:
        request.state.user_id = user_id
    return user_id
