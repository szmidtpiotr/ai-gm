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


# Stage 10-C — enforcement helpers.
# Routers use these to derive `user_id` from the JWT subject. Query-param
# fallback remains during the migration window so a missing token doesn't
# brick the player UI on the old cache-bust.

import logging as _stdlib_logging
from app.core.logging import get_logger as _get_logger

_logger = _get_logger(__name__)


def resolve_authed_user_id(
    authorization: str | None,
    user_id_query: int | None,
) -> int:
    """Derive the authenticated user_id from the request.

    Order of trust:
      1. `Authorization: Bearer <access_jwt>` (verified signature → payload.sub)
      2. `?user_id=N` query param (LEGACY — logged as deprecation warning)

    Raises:
      HTTPException 401 — neither JWT nor query param present
      HTTPException 401 — JWT present but invalid
      HTTPException 400 — JWT and query param both present but disagree

    During Stage 10-C this is THE auth point for player-facing endpoints. After
    the deprecation period the query-param branch can be removed (one-liner).
    """
    token = _extract_bearer(authorization)
    jwt_uid: int | None = None
    if token:
        try:
            payload = verify_token(token, expected_type="access")
            jwt_uid = int(payload.get("sub") or 0) or None
        except JWTError as e:
            raise HTTPException(status_code=401, detail=str(e)) from None

    if jwt_uid is not None:
        if user_id_query is not None and int(user_id_query) != jwt_uid:
            raise HTTPException(
                status_code=400,
                detail=f"user_id query param ({user_id_query}) does not match JWT subject ({jwt_uid})",
            )
        return jwt_uid

    if user_id_query is not None:
        _logger.warning(
            "legacy_query_param_auth",
            user_id=int(user_id_query),
            hint="Frontend should send Authorization: Bearer <access_token> — query param fallback is deprecated.",
        )
        return int(user_id_query)

    raise HTTPException(
        status_code=401,
        detail="Missing authentication (send Authorization: Bearer <access_token>)",
    )


def require_admin_role(
    authorization: str | None,
    user_id_query: int | None = None,
) -> int:
    """Stage 10-C A6 — require the request to come from an admin (JWT role=admin
    OR legacy query-param user_id whose users.is_admin=1).

    Returns the user_id when ok. Raises 403 otherwise.
    """
    # Need to verify JWT to know the role, OR fall back to DB lookup for legacy callers.
    token = _extract_bearer(authorization)
    if token:
        try:
            payload = verify_token(token, expected_type="access")
        except JWTError as e:
            raise HTTPException(status_code=401, detail=str(e)) from None
        if str(payload.get("role") or "").lower() == "admin" or int(payload.get("is_admin") or 0) == 1:
            uid = int(payload.get("sub") or 0)
            if user_id_query is not None and int(user_id_query) != uid:
                raise HTTPException(
                    status_code=400,
                    detail=f"user_id query param ({user_id_query}) does not match JWT subject ({uid})",
                )
            return uid
        raise HTTPException(status_code=403, detail="Admin role required")

    # Legacy query-param fallback — verify via DB lookup.
    if user_id_query is not None:
        import sqlite3
        from app.core.db_runtime import resolve_db_path
        conn = sqlite3.connect(resolve_db_path())
        try:
            row = conn.execute(
                "SELECT COALESCE(is_admin, 0) AS is_admin, COALESCE(role,'player') AS role FROM users WHERE id = ?",
                (int(user_id_query),),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            raise HTTPException(status_code=401, detail="User not found")
        if int(row[0] or 0) == 1 or str(row[1] or "").lower() == "admin":
            _logger.warning(
                "legacy_query_param_admin_auth",
                user_id=int(user_id_query),
                hint="Admin endpoint reached via legacy query-param fallback.",
            )
            return int(user_id_query)
        raise HTTPException(status_code=403, detail="Admin role required")

    raise HTTPException(
        status_code=401,
        detail="Missing authentication (send Authorization: Bearer <access_token>)",
    )


def assert_character_owner(jwt_payload: dict, character_id: int) -> None:
    """Raise 403 if the authenticated user does not own the character. Admins bypass."""
    if int(jwt_payload.get("is_admin") or 0) == 1 or str(jwt_payload.get("role") or "").lower() == "admin":
        return
    jwt_uid = int(jwt_payload.get("sub") or 0)
    if not jwt_uid:
        raise HTTPException(status_code=403, detail="Forbidden")
    import sqlite3 as _sqlite3
    from app.core.db_runtime import resolve_db_path as _resolve_db_path
    _conn = _sqlite3.connect(_resolve_db_path())
    try:
        row = _conn.execute(
            "SELECT user_id FROM characters WHERE id = ? AND is_active = 1",
            (character_id,),
        ).fetchone()
    finally:
        _conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Character not found")
    if int(row[0] or 0) != jwt_uid:
        raise HTTPException(status_code=403, detail="Forbidden")
