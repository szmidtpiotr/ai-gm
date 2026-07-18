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

import os
from typing import Any

from fastapi import Header, HTTPException

from app.services.jwt_service import JWTError, verify_token


def _legacy_userid_allowed() -> bool:
    """#1426 — the `?user_id=` fallback is a spoofable, unsigned identity claim.

    The Stage 10-C migration window is over; the ŻAR frontend sends
    `Authorization: Bearer <access_token>`. The fallback is OFF by default and
    only re-enabled by explicitly setting `ALLOW_LEGACY_USERID=1` (escape hatch
    for a migration emergency, never in normal operation).
    """
    return os.environ.get("ALLOW_LEGACY_USERID", "0").strip().lower() in ("1", "true", "yes", "on")


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

    # #1426 — legacy `?user_id=` fallback: OFF by default (spoofable identity).
    if user_id_query is not None and _legacy_userid_allowed():
        _logger.warning(
            "legacy_query_param_auth",
            user_id=int(user_id_query),
            hint="ALLOW_LEGACY_USERID is enabled — unsigned query-param identity accepted. Disable in production.",
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

    # #1426 — legacy query-param admin fallback (DB lookup on a spoofable
    # user_id): OFF by default. Anyone knowing an admin's small integer id could
    # otherwise reach /api/admin/* by passing ?user_id= and no token.
    if user_id_query is not None and _legacy_userid_allowed():
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
                hint="ALLOW_LEGACY_USERID is enabled — admin endpoint reached via unsigned query-param fallback.",
            )
            return int(user_id_query)
        raise HTTPException(status_code=403, detail="Admin role required")

    raise HTTPException(
        status_code=401,
        detail="Missing authentication (send Authorization: Bearer <access_token>)",
    )


# --------------------------------------------------------------------------
# #1424 — shared ownership guards for gameplay routers (Tier A/B).
#
# Pattern lifted from characters.py:3488-3492 / campaigns.py:592. Each mutating
# endpoint must, after resolving the authed user_id, prove that the target
# character/campaign actually BELONGS to that user — the id comes from the
# path/body but the owner is verified against the DB. Prevents an authenticated
# user from acting on someone else's hero/campaign by guessing a small integer.
#
# NOTE: ownership alone does NOT close self-cheat on your OWN character (gold
# #1437, dice #1427, sheet #1434) — those are separate fixes. This is the auth
# layer only.
# --------------------------------------------------------------------------

def require_character_owner(conn, character_id: int, user_id: int):
    """Return the character row if it belongs to `user_id`, else raise.

    404 when the character does not exist, 403 when it belongs to someone else.
    `conn` may or may not have a Row factory — owner is read positionally.
    """
    row = conn.execute(
        "SELECT id, user_id FROM characters WHERE id = ?", (int(character_id),)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="character not found")
    owner = row["user_id"] if hasattr(row, "keys") else row[1]
    if int(owner) != int(user_id):
        raise HTTPException(status_code=403, detail="not your hero")
    return row


def require_campaign_owner(conn, campaign_id: int, user_id: int):
    """Return the campaign row if it belongs to `user_id`, else raise.

    404 when the campaign does not exist, 403 when it belongs to someone else.
    """
    row = conn.execute(
        "SELECT id, owner_user_id FROM campaigns WHERE id = ?", (int(campaign_id),)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="campaign not found")
    owner = row["owner_user_id"] if hasattr(row, "keys") else row[1]
    if int(owner) != int(user_id):
        raise HTTPException(status_code=403, detail="not your campaign")
    return row


def require_authenticated(authorization: str | None = Header(default=None)) -> int:
    """FastAPI dependency — require a valid JWT, return the user_id.

    Usable as `Depends(require_authenticated)` for a router-level auth gate.
    Raises 401 when no valid token (legacy `?user_id=` fallback is off by
    default, see #1426).
    """
    return resolve_authed_user_id(authorization, None)


def _owner_conn():
    import sqlite3
    from app.core.db_runtime import resolve_db_path
    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def assert_character_owner(character_id: int, authorization: str | None, user_id_query: int | None = None) -> int:
    """One-liner guard for character-scoped endpoints (#1424).

    Resolves the authed user from the JWT, verifies the character belongs to
    them, and returns the user_id. Opens/closes its own short-lived connection.
    """
    uid = resolve_authed_user_id(authorization, user_id_query)
    conn = _owner_conn()
    try:
        require_character_owner(conn, character_id, uid)
    finally:
        conn.close()
    return uid


def assert_campaign_owner(campaign_id: int, authorization: str | None, user_id_query: int | None = None) -> int:
    """One-liner guard for campaign-scoped endpoints (#1424).

    Resolves the authed user from the JWT, verifies the campaign belongs to
    them, and returns the user_id. Opens/closes its own short-lived connection.
    """
    uid = resolve_authed_user_id(authorization, user_id_query)
    conn = _owner_conn()
    try:
        require_campaign_owner(conn, campaign_id, uid)
    finally:
        conn.close()
    return uid
