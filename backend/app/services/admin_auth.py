import hashlib
import hmac
import secrets
import sqlite3
from datetime import UTC, datetime


DB_PATH = "/data/ai_gm.db"


def hash_admin_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def verify_admin_token(raw_token: str) -> bool:
    if not raw_token:
        return False

    token_hash = hash_admin_token(raw_token)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT token_hash
            FROM admin_tokens
            """
        ).fetchall()
    except sqlite3.OperationalError:
        # Table does not exist yet or DB is unavailable.
        return False
    finally:
        conn.close()

    for row in rows:
        stored = row["token_hash"] or ""
        if hmac.compare_digest(stored, token_hash):
            return True
    return False


def _verify_user_password(stored_password_hash: str, raw_password: str) -> bool:
    if not stored_password_hash or not raw_password:
        return False
    # Backward-compatible dev mode:
    # - accepts legacy plain-text seed values (e.g., "demo")
    # - accepts sha256 hash values
    if hmac.compare_digest(stored_password_hash, raw_password):
        return True
    return hmac.compare_digest(stored_password_hash, hash_admin_token(raw_password))


def issue_dev_admin_token(username: str, password: str) -> str:
    if not username or not password:
        raise ValueError("missing_credentials")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT id, username, password_hash, COALESCE(is_active, 1) AS is_active
            FROM users
            WHERE username = ?
            LIMIT 1
            """,
            (username,),
        ).fetchone()
        if not row:
            raise PermissionError("invalid_credentials")
        if int(row["is_active"] or 0) != 1:
            raise PermissionError("inactive_user")
        if not _verify_user_password(str(row["password_hash"] or ""), password):
            raise PermissionError("invalid_credentials")

        raw_token = secrets.token_urlsafe(32)
        token_hash = hash_admin_token(raw_token)
        label = f"dev-login:{username}:{datetime.now(UTC).isoformat()}"
        conn.execute(
            "INSERT INTO admin_tokens(token_hash, label) VALUES (?, ?)",
            (token_hash, label),
        )
        conn.commit()
        return raw_token
    finally:
        conn.close()
