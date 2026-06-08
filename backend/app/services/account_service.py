"""Account profile updates — D8 (#383).

Single validated entry point for editing the current user's account fields
(username, display name, EMAIL, avatar). Email editing is new in D8 — with
format validation + uniqueness. Raises ValueError(code) on validation failure
so the router can map codes to HTTP statuses.
"""
from __future__ import annotations

import re
import sqlite3

_USERNAME_RE = re.compile(r"^[a-z0-9_]+$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def update_account(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    username: str | None = None,
    display_name: str | None = None,
    email: str | None = None,
    avatar_url: str | None = None,
) -> dict:
    """Update any provided account fields (None = leave unchanged).

    Raises ValueError with one of: username_empty, username_invalid_chars,
    username_too_short, username_taken, invalid_email, email_taken.
    """
    uid = int(user_id)

    if username is not None:
        uname = username.strip().lower()[:30]
        if not uname:
            raise ValueError("username_empty")
        if not _USERNAME_RE.match(uname):
            raise ValueError("username_invalid_chars")
        if len(uname) < 3:
            raise ValueError("username_too_short")
        taken = conn.execute(
            "SELECT id FROM users WHERE username = ? AND id != ? LIMIT 1", (uname, uid)
        ).fetchone()
        if taken:
            raise ValueError("username_taken")
        conn.execute("UPDATE users SET username = ? WHERE id = ?", (uname, uid))

    if display_name is not None:
        name = display_name.strip()[:40] or None
        conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (name, uid))

    if email is not None:
        em = email.strip().lower()[:120]
        if not _EMAIL_RE.match(em):
            raise ValueError("invalid_email")
        taken = conn.execute(
            "SELECT id FROM users WHERE lower(email) = ? AND id != ? LIMIT 1", (em, uid)
        ).fetchone()
        if taken:
            raise ValueError("email_taken")
        conn.execute("UPDATE users SET email = ? WHERE id = ?", (em, uid))

    if avatar_url is not None:
        url = avatar_url.strip() or None
        try:
            conn.execute("UPDATE users SET avatar_url = ? WHERE id = ?", (url, uid))
        except sqlite3.OperationalError:
            pass

    conn.commit()
    row = conn.execute(
        "SELECT username, display_name, email, avatar_url FROM users WHERE id = ?", (uid,)
    ).fetchone()
    avatar = None
    try:
        avatar = row["avatar_url"]
    except Exception:
        pass
    return {
        "ok": True,
        "username": row["username"],
        "display_name": row["display_name"],
        "email": row["email"],
        "avatar_url": avatar,
    }
