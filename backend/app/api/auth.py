import hashlib
import hmac
import sqlite3
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.db_runtime import resolve_db_path
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


# Stage 10 A4 — Brute-force lockout config.
LOCKOUT_THRESHOLD = 10        # consecutive failed attempts before lock
LOCKOUT_DURATION_MIN = 15     # how long the lock holds (minutes)

# Stage 10 A1 — bcrypt cost factor for re-hash (matches existing $2b$12$ rows).
BCRYPT_COST = 12


class PlayerLoginReq(BaseModel):
    username: str
    password: str


def _verify_user_password(stored_password_hash: str, raw_password: str) -> tuple[bool, str]:
    """
    Backward-compatible password verification.

    Returns `(ok, kind)` where `kind` is one of 'bcrypt' | 'sha256' | 'plain' | ''.
    Used by the login handler to decide whether to re-hash (A1).

    Current seed uses plain-text `password_hash` (e.g. 'demo'), but older snapshots may
    store sha256(raw_password). Admin-created users use bcrypt. We accept all to avoid
    breaking existing deployments.
    """
    if not stored_password_hash or not raw_password:
        return False, ""
    stored = str(stored_password_hash)
    if stored.startswith("$2"):
        try:
            return bcrypt.checkpw(raw_password.encode("utf-8"), stored.encode("ascii")), "bcrypt"
        except (ValueError, TypeError):
            return False, ""
    if hmac.compare_digest(stored, raw_password):
        return True, "plain"
    sha = hashlib.sha256(raw_password.encode("utf-8")).hexdigest()
    if hmac.compare_digest(stored, sha):
        return True, "sha256"
    return False, ""


def _bcrypt_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_COST)).decode("ascii")


@router.post("/auth/login")
def player_login(req: PlayerLoginReq):
    username = (req.username or "").strip()
    password = req.password or ""
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password are required")

    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    try:
        # Read user with all Stage 10 columns; gracefully fall back if any are
        # missing on an old DB snapshot (the migration creates them at startup).
        try:
            row = conn.execute(
                """
                SELECT id, username, password_hash, display_name,
                       COALESCE(is_active, 1) AS is_active,
                       COALESCE(is_admin, 0) AS is_admin,
                       COALESCE(role, 'player') AS role,
                       COALESCE(failed_login_count, 0) AS failed_login_count,
                       lockout_until
                FROM users WHERE username = ? LIMIT 1
                """,
                (username,),
            ).fetchone()
        except sqlite3.OperationalError:
            row = conn.execute(
                """
                SELECT id, username, password_hash, display_name,
                       COALESCE(is_active, 1) AS is_active,
                       COALESCE(is_admin, 0) AS is_admin
                FROM users WHERE username = ? LIMIT 1
                """,
                (username,),
            ).fetchone()

        if not row:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if int(row["is_active"] or 0) != 1:
            raise HTTPException(status_code=403, detail="User is inactive")

        # Stage 10 A4 — Brute-force lockout gate.
        lockout_until_raw = None
        try:
            lockout_until_raw = row["lockout_until"]
        except (KeyError, IndexError):
            lockout_until_raw = None
        if lockout_until_raw:
            try:
                lockout_until = datetime.fromisoformat(str(lockout_until_raw).replace(" ", "T"))
                if lockout_until.tzinfo is None:
                    lockout_until = lockout_until.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < lockout_until:
                    remaining = int((lockout_until - datetime.now(timezone.utc)).total_seconds() / 60) + 1
                    logger.warning("login_locked", username=username, minutes_remaining=remaining)
                    raise HTTPException(
                        status_code=423,
                        detail={
                            "error": "account_locked",
                            "message": f"Konto tymczasowo zablokowane. Spróbuj za {remaining} min.",
                            "minutes_remaining": remaining,
                            "lockout_until": lockout_until.isoformat(),
                        },
                    )
            except (ValueError, TypeError):
                pass  # corrupt timestamp — fail open rather than locking forever

        ok, kind = _verify_user_password(str(row["password_hash"] or ""), password)

        if not ok:
            # Stage 10 A4 — bump failed-login counter; lock if threshold hit.
            try:
                new_count = int(row["failed_login_count"] or 0) + 1
            except (KeyError, IndexError):
                new_count = 1
            lock_until = None
            if new_count >= LOCKOUT_THRESHOLD:
                lock_until = (datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MIN)).isoformat()
                logger.warning("login_lockout_triggered", username=username, count=new_count)
            try:
                conn.execute(
                    """
                    UPDATE users SET failed_login_count = ?, lockout_until = ? WHERE id = ?
                    """,
                    (new_count, lock_until, int(row["id"])),
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass  # columns missing on old DB — skip silently
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # SUCCESS — clear counter, maybe re-hash to bcrypt (A1).
        try:
            updates = ["failed_login_count = 0", "lockout_until = NULL"]
            params: list = []
            if kind in ("plain", "sha256"):
                new_hash = _bcrypt_hash(password)
                updates.append("password_hash = ?")
                params.append(new_hash)
                logger.info("password_rehashed_to_bcrypt", user_id=int(row["id"]), from_kind=kind)
            params.append(int(row["id"]))
            conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # columns missing on old DB — skip silently

        # Role: prefer the explicit role column when present, else derive from is_admin.
        is_admin_val = int(row["is_admin"] or 0)
        try:
            role = str(row["role"] or "").strip().lower() or ("admin" if is_admin_val else "player")
        except (KeyError, IndexError):
            role = "admin" if is_admin_val else "player"

        # Stage 10 A2 — emit JWT pair so the client can switch to Bearer auth.
        # Returned alongside the legacy `user_id`/`is_admin`/`role` fields so
        # existing clients keep working unchanged during the overlap window.
        from app.services.jwt_service import issue_pair
        token_pair = issue_pair(
            user_id=int(row["id"]),
            username=str(row["username"] or ""),
            role=role,
            is_admin=is_admin_val,
        )

        return {
            "ok": True,
            "user_id": int(row["id"]),
            "username": row["username"],
            "display_name": row["display_name"],
            "is_admin": is_admin_val,
            "role": role,
            **token_pair,
        }
    except sqlite3.OperationalError:
        raise HTTPException(status_code=500, detail="DB is not initialized") from None
    finally:
        conn.close()


class RefreshTokenReq(BaseModel):
    refresh_token: str


@router.post("/auth/refresh")
def refresh_access_token(req: RefreshTokenReq):
    """Stage 10 A2 — exchange a refresh token for a new access token.

    Refresh token itself is NOT rotated (would require storing jti server-side).
    A future hardening pass can swap to refresh-token rotation when we're ready
    to accept the storage cost.
    """
    from app.services.jwt_service import (
        JWTError,
        issue_access_token,
        verify_token,
        ACCESS_TTL_SECONDS,
    )
    try:
        payload = verify_token(req.refresh_token, expected_type="refresh")
    except JWTError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None
    uid = int(payload.get("sub") or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="invalid_refresh_subject")
    # Re-fetch current role/is_admin in case the user was promoted/demoted since the refresh was issued.
    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, username, COALESCE(is_admin,0) AS is_admin, COALESCE(role,'player') AS role, COALESCE(is_active,1) AS is_active FROM users WHERE id = ?",
            (uid,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="user_not_found")
    if int(row["is_active"] or 0) != 1:
        raise HTTPException(status_code=403, detail="user_inactive")
    access = issue_access_token(
        user_id=int(row["id"]),
        username=str(row["username"] or ""),
        role=str(row["role"] or "player"),
        is_admin=int(row["is_admin"] or 0),
    )
    return {
        "access_token": access,
        "token_type": "bearer",
        "expires_in": ACCESS_TTL_SECONDS,
    }


@router.get("/auth/me")
def get_me(authorization: str | None = Header(default=None)):
    """Stage 10 A2 — return the current user payload when a valid access token
    is present. Useful for the frontend to validate the token at boot.
    """
    from app.core.jwt_auth import require_current_user
    payload = require_current_user(authorization)
    return {
        "user_id": int(payload.get("sub") or 0),
        "username": payload.get("username") or "",
        "role": payload.get("role") or "player",
        "is_admin": int(payload.get("is_admin") or 0),
    }

