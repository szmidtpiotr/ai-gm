"""Telegram easy-click linking — Issue #883 (Faza N1 of #602).

Two-tap opt-in: the player clicks a deep-link `https://t.me/<bot>?start=<token>`,
Telegram opens the chat pre-filled with `/start <token>`, one tap sends it, the
bot webhook redeems the token and binds the player's `telegram_chat_id`. From
then on the unified dispatcher (`notification_service.notify`) can DM them.

Flow:
    create_link_token(user_id)  -> one-time token (+ deep-link) shown as button/QR
    <player taps>               -> Telegram POSTs /start <token> to our webhook
    handle_update(update)       -> redeem_token() binds chat_id, sends confirm DM

Everything is testable without a live bot: `redeem_token` / `handle_update` take
plain dicts and never require network (the confirmation DM is best-effort).

Config (env, injected on the backend — never committed):
    TELEGRAM_BOT_TOKEN     — Bot API token (@BotFather). Delivery no-ops without it.
    TELEGRAM_BOT_USERNAME  — bot handle without @, for the deep-link / QR.
    TELEGRAM_WEBHOOK_SECRET — optional; matched against X-Telegram-Bot-Api-Secret-Token.

Table `telegram_link_tokens` DDL is mirrored in ADMIN_MIGRATIONS (migrations_admin.py).
"""
import os
import secrets
import sqlite3
from typing import Optional

from app.core.db_runtime import resolve_db_path
from app.core.logging import get_logger
from app.services import notification_service as ns

logger = get_logger(__name__)

# Tokens are single-use and short-lived; a stale link should not silently bind.
TOKEN_TTL_MINUTES = 15

# Mirrors the DDL appended to ADMIN_MIGRATIONS so unit tests can build the same
# schema on a throwaway DB without booting the app.
SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS telegram_link_tokens (
        token      TEXT PRIMARY KEY,
        user_id    INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        used_at    TEXT
    )
    """,
]


def _db(db_path: Optional[str] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def bot_token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "")


def bot_username() -> str:
    return os.getenv("TELEGRAM_BOT_USERNAME", "").lstrip("@")


def webhook_secret() -> str:
    return os.getenv("TELEGRAM_WEBHOOK_SECRET", "")


def is_configured() -> bool:
    """True once a bot exists — link buttons stay disabled otherwise."""
    return bool(bot_token() and bot_username())


def deep_link(token: str) -> Optional[str]:
    """`https://t.me/<bot>?start=<token>` — None until a bot username is set."""
    user = bot_username()
    if not user:
        return None
    return f"https://t.me/{user}?start={token}"


def create_link_token(user_id: int, db_path: Optional[str] = None) -> dict:
    """Mint a fresh one-time link token for a player.

    Drops the player's prior unused tokens first so only the latest link works.
    Returns {token, deep_link, bot_username, configured}.
    """
    token = secrets.token_urlsafe(24)
    conn = _db(db_path)
    try:
        conn.execute(
            "DELETE FROM telegram_link_tokens WHERE user_id = ? AND used_at IS NULL",
            (user_id,),
        )
        conn.execute(
            "INSERT INTO telegram_link_tokens (token, user_id) VALUES (?, ?)",
            (token, user_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "token": token,
        "deep_link": deep_link(token),
        "bot_username": bot_username() or None,
        "configured": is_configured(),
    }


def redeem_token(token: str, chat_id, db_path: Optional[str] = None) -> Optional[int]:
    """Validate + consume a token, binding `chat_id` to its player.

    Returns the bound user_id, or None if the token is unknown, already used, or
    expired. On success the player's `telegram_chat_id` pref is set (enabling the
    telegram channel) and the token is marked used.
    """
    if not token or chat_id in (None, ""):
        return None
    conn = _db(db_path)
    try:
        row = conn.execute(
            "SELECT user_id, used_at, "
            "  (created_at > datetime('now', ?)) AS fresh "
            "FROM telegram_link_tokens WHERE token = ?",
            (f"-{TOKEN_TTL_MINUTES} minutes", token),
        ).fetchone()
        if not row or row["used_at"] is not None or not row["fresh"]:
            return None
        user_id = int(row["user_id"])
        conn.execute(
            "UPDATE telegram_link_tokens SET used_at = datetime('now') WHERE token = ?",
            (token,),
        )
        conn.commit()
    finally:
        conn.close()

    ns.set_prefs(user_id, db_path=db_path, telegram_chat_id=str(chat_id))
    logger.info("telegram_linked", user_id=user_id)
    return user_id


def is_connected(user_id: int, db_path: Optional[str] = None) -> bool:
    return bool(ns.get_prefs(user_id, db_path=db_path).get("telegram_chat_id"))


def unlink(user_id: int, db_path: Optional[str] = None) -> None:
    ns.set_prefs(user_id, db_path=db_path, telegram_chat_id=None)
    logger.info("telegram_unlinked", user_id=user_id)


def _parse_start_command(update: dict) -> Optional[tuple]:
    """Extract (token, chat_id) from a Telegram `/start <token>` update, else None."""
    msg = (update or {}).get("message") or (update or {}).get("edited_message")
    if not isinstance(msg, dict):
        return None
    text = (msg.get("text") or "").strip()
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if not text.startswith("/start") or chat_id is None:
        return None
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        return None
    return parts[1].strip(), chat_id


def handle_update(update: dict, db_path: Optional[str] = None) -> dict:
    """Process one Telegram webhook update.

    Recognises `/start <token>`: redeems it, binds the chat, sends a best-effort
    confirmation DM. Returns {handled, linked, user_id}. Never raises.
    """
    try:
        parsed = _parse_start_command(update)
        if not parsed:
            return {"handled": False, "linked": False, "user_id": None}
        token, chat_id = parsed
        user_id = redeem_token(token, chat_id, db_path=db_path)
        if user_id is None:
            ns.send_telegram(chat_id, "AI-GM",
                             "Ten link wygasł lub został już użyty. Wygeneruj nowy w Ustawieniach.")
            return {"handled": True, "linked": False, "user_id": None}
        ns.send_telegram(chat_id, "AI-GM",
                         "✅ Połączono! Będziesz tu dostawać powiadomienia o swojej turze.")
        return {"handled": True, "linked": True, "user_id": user_id}
    except Exception as e:  # noqa: BLE001 — webhook must always 200
        logger.error("telegram_update_failed", error=str(e)[:160])
        return {"handled": False, "linked": False, "user_id": None}
