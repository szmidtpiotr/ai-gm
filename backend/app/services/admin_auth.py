import hashlib
import hmac
import sqlite3


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
