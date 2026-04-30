import hashlib
import hmac
import sqlite3

import bcrypt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.db_runtime import resolve_db_path

router = APIRouter()


class PlayerLoginReq(BaseModel):
    username: str
    password: str


def _verify_user_password(stored_password_hash: str, raw_password: str) -> bool:
    """
    Backward-compatible password verification.

    Current seed uses plain-text `password_hash` (e.g. 'demo'), but older snapshots may
    store sha256(raw_password). Admin-created users use bcrypt. We accept all to avoid
    breaking existing deployments.
    """
    if not stored_password_hash or not raw_password:
        return False
    if hmac.compare_digest(stored_password_hash, raw_password):
        return True
    sha = hashlib.sha256(raw_password.encode("utf-8")).hexdigest()
    if hmac.compare_digest(stored_password_hash, sha):
        return True
    stored = str(stored_password_hash)
    if stored.startswith("$2"):
        try:
            return bcrypt.checkpw(raw_password.encode("utf-8"), stored.encode("ascii"))
        except (ValueError, TypeError):
            return False
    return False


@router.post("/auth/login")
def player_login(req: PlayerLoginReq):
    username = (req.username or "").strip()
    password = req.password or ""
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password are required")

    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    is_admin_val = 0
    try:
        try:
            row = conn.execute(
                """
                SELECT id, username, password_hash, display_name,
                       COALESCE(is_active, 1) AS is_active,
                       COALESCE(is_admin, 0) AS is_admin
                FROM users
                WHERE username = ?
                LIMIT 1
                """,
                (username,),
            ).fetchone()
            if row:
                is_admin_val = int(row["is_admin"] or 0)
        except sqlite3.OperationalError:
            # Older DB snapshots without `is_admin` column.
            row = conn.execute(
                """
                SELECT id, username, password_hash, display_name,
                       COALESCE(is_active, 1) AS is_active
                FROM users
                WHERE username = ?
                LIMIT 1
                """,
                (username,),
            ).fetchone()
    except sqlite3.OperationalError:
        raise HTTPException(status_code=500, detail="DB is not initialized") from None
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if int(row["is_active"] or 0) != 1:
        raise HTTPException(status_code=403, detail="User is inactive")

    if not _verify_user_password(str(row["password_hash"] or ""), password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "ok": True,
        "user_id": int(row["id"]),
        "username": row["username"],
        "display_name": row["display_name"],
        "is_admin": is_admin_val,
    }

