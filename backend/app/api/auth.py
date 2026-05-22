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

    conn = sqlite3.connect(_AUTH_DB)
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
                       lockout_until, email_verified_at, onboarded_at, email
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

        # Stage 11-C C6 — email verification gate on 2nd+ login
        # First session (onboarded_at IS NULL) is allowed through so new users
        # can complete onboarding before we enforce verification.
        try:
            email_verified = row["email_verified_at"]
            onboarded = row["onboarded_at"]
            user_email = row["email"]
        except (KeyError, IndexError):
            email_verified = None
            onboarded = None
            user_email = None

        # Only gate users who registered with an email AND haven't verified it yet.
        # Users without an email (legacy accounts, admin-created) are always allowed through.
        if not email_verified and onboarded and user_email:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "email_unverified",
                    "message": "Potwierdź swój adres email, aby kontynuować.",
                }
            )

        return {
            "ok": True,
            "user_id": int(row["id"]),
            "username": row["username"],
            "display_name": row["display_name"],
            "is_admin": is_admin_val,
            "role": role,
            "onboarded_at": onboarded,
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
    conn = sqlite3.connect(_AUTH_DB)
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


# ── Stage 11-C — Registration, invites, verification, password reset ──────────

import os
import re
import secrets
from datetime import datetime, timedelta, timezone

INVITE_EXPIRY_HOURS = 72
VERIFY_EXPIRY_HOURS = 72
RESET_EXPIRY_HOURS  = 2
BASE_URL_ENV        = "APP_BASE_URL"  # e.g. https://aigm-dev.studio-colorbox.com


def _base_url() -> str:
    return (os.getenv(BASE_URL_ENV) or "").rstrip("/")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expires_iso(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _is_expired(expires_at: str) -> bool:
    try:
        dt = datetime.fromisoformat(str(expires_at).replace(" ", "T"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > dt
    except Exception:
        return True


def _valid_username(username: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9_]{3,30}$', username))


_AUTH_DB = "/data/ai_gm.db"


@router.get("/auth/registration-status")
def registration_status():
    """Public — returns whether self-registration is open (controlled by admin)."""
    conn = sqlite3.connect(_AUTH_DB)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = 'registration_open' LIMIT 1"
        ).fetchone()
        open_val = str(row["value"] or "false").strip().lower() if row else "false"
        return {"open": open_val in ("true", "1", "yes")}
    finally:
        conn.close()


@router.get("/auth/invite/{code}")
def get_invite(code: str):
    """Validate an invite code and return inviter info (no auth required)."""
    conn = sqlite3.connect(_AUTH_DB)
    conn.row_factory = sqlite3.Row
    try:
        inv = conn.execute(
            "SELECT * FROM user_invites WHERE code = ? LIMIT 1", (code,)
        ).fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Zaproszenie nie istnieje")
        if inv["used_at"]:
            raise HTTPException(status_code=409, detail="Zaproszenie zostało już wykorzystane")
        if _is_expired(inv["expires_at"]):
            raise HTTPException(status_code=410, detail="Zaproszenie wygasło")

        inviter = conn.execute(
            "SELECT username, display_name FROM users WHERE id = ? LIMIT 1",
            (inv["created_by"],),
        ).fetchone()
        inviter_name = (inviter["display_name"] or inviter["username"]) if inviter else "Admin"

        return {
            "valid": True,
            "code": code,
            "email": inv["email"],
            "message": inv["message"],
            "inviter_name": inviter_name,
            "expires_at": inv["expires_at"],
        }
    finally:
        conn.close()


class RegisterReq(BaseModel):
    invite_code: str
    username: str
    password: str
    email: str | None = None  # required for open invites (where invite.email is NULL)


@router.post("/auth/register")
def register(req: RegisterReq):
    """Stage 11-C C4 — create a new player account via invite."""
    username  = (req.username or "").strip()
    password  = req.password or ""
    invite_code = (req.invite_code or "").strip()

    if not username or not password or not invite_code:
        raise HTTPException(status_code=400, detail="username, password, invite_code are required")
    if not _valid_username(username):
        raise HTTPException(status_code=400, detail="Nazwa użytkownika: 3-30 znaków, litery/cyfry/podkreślnik")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Hasło musi mieć minimum 8 znaków")

    conn = sqlite3.connect(_AUTH_DB)
    conn.row_factory = sqlite3.Row
    try:
        # Validate invite
        inv = conn.execute(
            "SELECT * FROM user_invites WHERE code = ? LIMIT 1", (invite_code,)
        ).fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Nieprawidłowy kod zaproszenia")
        if inv["used_at"]:
            raise HTTPException(status_code=409, detail="Zaproszenie zostało już wykorzystane")
        if _is_expired(inv["expires_at"]):
            raise HTTPException(status_code=410, detail="Zaproszenie wygasło")

        # Email: use locked email from invite (personalised) or provided email (open)
        invite_email = inv["email"]
        provided_email = (req.email or "").strip().lower()
        if invite_email:
            # Personalised — email must match
            if provided_email and provided_email != invite_email.lower():
                raise HTTPException(status_code=403, detail="Ten link zaproszenia jest przypisany do innego adresu email")
            final_email = invite_email
        else:
            # Open invite — email required from request
            if not provided_email or "@" not in provided_email:
                raise HTTPException(status_code=400, detail="Podaj prawidłowy adres email")
            final_email = provided_email

        # Check username uniqueness
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ? LIMIT 1", (username,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Nazwa użytkownika jest już zajęta")

        # Create user
        pw_hash = _bcrypt_hash(password)
        cursor = conn.execute(
            """
            INSERT INTO users (username, display_name, password_hash, email,
                               is_active, is_admin, role, invited_by_user_id, created_at)
            VALUES (?, ?, ?, ?, 1, 0, 'player', ?, ?)
            """,
            (username, username, pw_hash, final_email, inv["created_by"], _now_iso()),
        )
        new_user_id = cursor.lastrowid
        conn.commit()

        # Mark invite used
        conn.execute(
            "UPDATE user_invites SET accepted_by = ?, used_at = ? WHERE code = ?",
            (new_user_id, _now_iso(), invite_code),
        )
        conn.commit()

        # Send verification email
        verify_token = secrets.token_hex(32)
        conn.execute(
            "INSERT INTO email_verification_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
            (new_user_id, verify_token, _expires_iso(VERIFY_EXPIRY_HOURS)),
        )
        conn.commit()

        verify_link = f"{_base_url()}/verify-email?token={verify_token}"
        inviter = conn.execute(
            "SELECT username, display_name FROM users WHERE id = ? LIMIT 1",
            (inv["created_by"],),
        ).fetchone()
        inviter_name = (inviter["display_name"] or inviter["username"]) if inviter else "Admin"

        from app.services.email_service import send_verification_email
        send_verification_email(final_email, verify_link)

        # Issue JWT
        from app.services.jwt_service import issue_pair
        token_pair = issue_pair(user_id=new_user_id, username=username, role="player", is_admin=0)

        logger.info("user_registered", user_id=new_user_id, username=username, invited_by=inv["created_by"])
        return {
            "ok": True,
            "user_id": new_user_id,
            "username": username,
            "is_admin": 0,
            "role": "player",
            "onboarded_at": None,
            "inviter_name": inviter_name,
            "inviter_message": inv["message"],
            **token_pair,
        }
    finally:
        conn.close()


@router.post("/auth/verify-email")
def verify_email(body: dict):
    """Stage 11-C C6 — confirm email address via token from verification email."""
    token = (body.get("token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="token is required")

    conn = sqlite3.connect(_AUTH_DB)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM email_verification_tokens WHERE token = ? LIMIT 1", (token,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Nieprawidłowy link weryfikacyjny")
        if row["used_at"]:
            raise HTTPException(status_code=409, detail="Link weryfikacyjny został już użyty")
        if _is_expired(row["expires_at"]):
            raise HTTPException(status_code=410, detail="Link weryfikacyjny wygasł")

        user_id = row["user_id"]
        now = _now_iso()
        conn.execute(
            "UPDATE users SET email_verified_at = ? WHERE id = ?", (now, user_id)
        )
        conn.execute(
            "UPDATE email_verification_tokens SET used_at = ? WHERE token = ?", (now, token)
        )
        conn.commit()

        user = conn.execute(
            "SELECT username, COALESCE(role,'player') as role, COALESCE(is_admin,0) as is_admin FROM users WHERE id = ? LIMIT 1",
            (user_id,),
        ).fetchone()
        from app.services.jwt_service import issue_pair
        token_pair = issue_pair(user_id=user_id, username=user["username"], role=user["role"], is_admin=int(user["is_admin"]))
        return {"ok": True, **token_pair}
    finally:
        conn.close()


@router.post("/auth/resend-verification")
def resend_verification(authorization: str | None = Header(default=None)):
    """Stage 11-C C6 — resend verification email (rate-limited: 1 per 2 minutes)."""
    from app.core.jwt_auth import require_current_user
    payload = require_current_user(authorization)
    user_id = int(payload.get("sub") or 0)

    conn = sqlite3.connect(_AUTH_DB)
    conn.row_factory = sqlite3.Row
    try:
        user = conn.execute(
            "SELECT email, email_verified_at FROM users WHERE id = ? LIMIT 1", (user_id,)
        ).fetchone()
        if not user or user["email_verified_at"]:
            return {"ok": True, "message": "Już zweryfikowany"}

        # Rate limit: 1 per 2 minutes
        recent = conn.execute(
            """
            SELECT created_at FROM email_verification_tokens
            WHERE user_id = ? AND used_at IS NULL
            ORDER BY id DESC LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if recent:
            created = datetime.fromisoformat(str(recent["created_at"]).replace(" ", "T"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - created).total_seconds()
            if elapsed < 120:
                wait = int(120 - elapsed)
                raise HTTPException(
                    status_code=429,
                    detail={"error": "rate_limited", "retry_after_seconds": wait}
                )

        token = secrets.token_hex(32)
        conn.execute(
            "INSERT INTO email_verification_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, _expires_iso(VERIFY_EXPIRY_HOURS)),
        )
        conn.commit()

        verify_link = f"{_base_url()}/verify-email?token={token}"
        from app.services.email_service import send_verification_email
        send_verification_email(user["email"], verify_link)
        return {"ok": True}
    finally:
        conn.close()


class ForgotPasswordReq(BaseModel):
    email: str


@router.post("/auth/forgot-password")
def forgot_password(req: ForgotPasswordReq):
    """Stage 11-C C7 — send password reset email (always 200, never reveals existence)."""
    email = (req.email or "").strip().lower()
    conn = sqlite3.connect(_AUTH_DB)
    conn.row_factory = sqlite3.Row
    try:
        user = conn.execute(
            "SELECT id FROM users WHERE LOWER(email) = ? AND is_active = 1 LIMIT 1", (email,)
        ).fetchone()
        if user:
            token = secrets.token_hex(32)
            conn.execute(
                "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
                (user["id"], token, _expires_iso(RESET_EXPIRY_HOURS)),
            )
            conn.commit()
            reset_link = f"{_base_url()}/reset-password?token={token}"
            from app.services.email_service import send_password_reset_email
            send_password_reset_email(email, reset_link)
        # Always 200 — never reveal whether email exists
        return {"ok": True, "message": "Jeśli ten adres istnieje w systemie, wyślemy link resetujący."}
    finally:
        conn.close()


class ResetPasswordReq(BaseModel):
    token: str
    password: str


@router.post("/auth/reset-password")
def reset_password(req: ResetPasswordReq):
    """Stage 11-C C7 — set new password via reset token, auto-login on success."""
    token = (req.token or "").strip()
    password = req.password or ""
    if not token or len(password) < 8:
        raise HTTPException(status_code=400, detail="token i hasło (min 8 znaków) są wymagane")

    conn = sqlite3.connect(_AUTH_DB)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM password_reset_tokens WHERE token = ? LIMIT 1", (token,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Nieprawidłowy link resetujący")
        if row["used_at"]:
            raise HTTPException(status_code=409, detail="Link resetujący został już użyty")
        if _is_expired(row["expires_at"]):
            raise HTTPException(status_code=410, detail="Link resetujący wygasł")

        user_id = row["user_id"]
        now = _now_iso()
        pw_hash = _bcrypt_hash(password)
        conn.execute("UPDATE users SET password_hash = ?, failed_login_count = 0, lockout_until = NULL WHERE id = ?", (pw_hash, user_id))
        conn.execute("UPDATE password_reset_tokens SET used_at = ? WHERE token = ?", (now, token))
        conn.commit()

        user = conn.execute(
            "SELECT username, COALESCE(role,'player') as role, COALESCE(is_admin,0) as is_admin FROM users WHERE id = ? LIMIT 1",
            (user_id,),
        ).fetchone()
        from app.services.jwt_service import issue_pair
        token_pair = issue_pair(user_id=user_id, username=user["username"], role=user["role"], is_admin=int(user["is_admin"]))
        return {"ok": True, **token_pair}
    finally:
        conn.close()



class ChangePasswordReq(BaseModel):
    current_password: str
    new_password: str


@router.post("/auth/change-password")
def change_password(
    req: ChangePasswordReq,
    authorization: str | None = Header(default=None),
):
    """Change password for the currently logged-in user (no email needed)."""
    from app.core.jwt_auth import require_current_user
    payload = require_current_user(authorization)
    user_id = int(payload.get("sub") or 0)

    if len(req.new_password) < 8:
        raise HTTPException(status_code=422, detail="Hasło musi mieć minimum 8 znaków")

    conn = sqlite3.connect(_AUTH_DB)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ? LIMIT 1", (user_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        ok, _ = _verify_user_password(str(row["password_hash"] or ""), req.current_password)
        if not ok:
            raise HTTPException(status_code=403, detail="Nieprawidłowe obecne hasło")

        pw_hash = _bcrypt_hash(req.new_password)
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
