"""Unified multichannel notification dispatcher — Issue #602, Faza N2.

`notify(user_id, event, payload)` picks the most reliable channel the player has
enabled, walking their `channel_order` (default ``telegram > web_push > email``)
and falling through to the next channel when one is unavailable or its send
fails. Every attempt is recorded in ``notify_delivery_log``.

Channel availability:
    telegram   — a ``telegram_chat_id`` is stored (Faza N1 link).
    web_push   — ``web_push_enabled`` flag set + a live VAPID config / subscription.
    email      — an ``email`` address is stored.

The dispatcher never raises: a failing channel logs + falls through; an empty
preference set returns ``{"delivered": False, "channel": None}``.

Tables (``player_notify_prefs`` = Faza N0 foundation) are created by
``migrations_admin.run_admin_migrations`` — ``SCHEMA_SQL`` mirrors that DDL so
unit tests can spin the same schema on a throwaway DB.
"""
import os
import sqlite3
import sys
from typing import Optional

from app.core.db_runtime import resolve_db_path
from app.core.logging import get_logger

logger = get_logger(__name__)

_TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

DEFAULT_CHANNEL_ORDER = "telegram,web_push,email"
_VALID_CHANNELS = ("telegram", "web_push", "email")

# Mirrors the DDL appended to ADMIN_MIGRATIONS in migrations_admin.py so tests
# can build the same schema without booting the app.
SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS player_notify_prefs (
        user_id           INTEGER PRIMARY KEY,
        web_push_enabled  INTEGER NOT NULL DEFAULT 0,
        telegram_chat_id  TEXT,
        email             TEXT,
        channel_order     TEXT NOT NULL DEFAULT 'telegram,web_push,email',
        updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notify_delivery_log (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        event      TEXT NOT NULL,
        channel    TEXT NOT NULL,
        status     TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
]


def _db(db_path: Optional[str] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


# ─── Preferences (Faza N0 surface) ───────────────────────────────────────────

def get_prefs(user_id: int, db_path: Optional[str] = None) -> dict:
    """Return the player's notification prefs, or telegram-first defaults."""
    conn = _db(db_path)
    try:
        row = conn.execute(
            "SELECT user_id, web_push_enabled, telegram_chat_id, email, channel_order "
            "FROM player_notify_prefs WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return {
            "user_id": user_id,
            "web_push_enabled": 0,
            "telegram_chat_id": None,
            "email": None,
            "channel_order": DEFAULT_CHANNEL_ORDER,
        }
    d = dict(row)
    if not d.get("channel_order"):
        d["channel_order"] = DEFAULT_CHANNEL_ORDER
    return d


def set_prefs(user_id: int, db_path: Optional[str] = None, **fields) -> None:
    """Upsert a player's prefs. Only known columns are written."""
    allowed = ("web_push_enabled", "telegram_chat_id", "email", "channel_order")
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return

    conn = _db(db_path)
    try:
        names = ["user_id"] + list(cols.keys())
        placeholders = ", ".join("?" for _ in names)
        updates = ", ".join(f"{c} = excluded.{c}" for c in cols)
        conn.execute(
            f"INSERT INTO player_notify_prefs ({', '.join(names)}, updated_at) "
            f"VALUES ({placeholders}, datetime('now')) "
            f"ON CONFLICT(user_id) DO UPDATE SET {updates}, updated_at = datetime('now')",
            [user_id] + list(cols.values()),
        )
        conn.commit()
    finally:
        conn.close()


# ─── Channel senders ─────────────────────────────────────────────────────────

def send_telegram(chat_id, title: str, body: str) -> bool:
    """Send a Telegram DM via the Bot API. False (no raise) if unconfigured."""
    if not _TELEGRAM_BOT_TOKEN or not chat_id:
        logger.warning("telegram_not_configured", has_token=bool(_TELEGRAM_BOT_TOKEN),
                       has_chat=bool(chat_id))
        return False
    try:
        import requests

        text = f"*{title}*\n{body}" if title else body
        resp = requests.post(
            f"https://api.telegram.org/bot{_TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        ok = resp.status_code == 200 and bool(resp.json().get("ok"))
        if ok:
            logger.info("telegram_sent", chat_id=str(chat_id))
        else:
            logger.warning("telegram_send_rejected", status=resp.status_code)
        return ok
    except Exception as e:  # noqa: BLE001 — never break the turn loop
        logger.error("telegram_send_failed", error=str(e)[:120])
        return False


def _deliver_telegram(user_id, prefs, title, body, url) -> bool:
    chat_id = prefs.get("telegram_chat_id")
    if not chat_id:
        return False
    return send_telegram(chat_id, title, body)


def _deliver_web_push(user_id, prefs, title, body, url) -> bool:
    if not prefs.get("web_push_enabled"):
        return False
    from app.services import push_notification_service as pns

    if not pns._is_configured():
        return False
    conn = _db(prefs.get("__db_path"))
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM user_push_subscriptions WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
    except sqlite3.OperationalError:
        n = 0
    finally:
        conn.close()
    if not n:
        return False
    # Real send result → dispatcher falls through to email if no push lands.
    return bool(pns.send_push(user_id, title, body, url))


def _deliver_email(user_id, prefs, title, body, url) -> bool:
    email = prefs.get("email")
    if not email:
        return False
    from app.services.email_service import send_email

    html = f"<p>{body}</p>"
    return send_email(email, title or "AI-GM", html)


def _dispatch_one(channel, user_id, prefs, title, body, url) -> bool:
    """Route to the per-channel deliverer (looked up by name so tests can patch)."""
    fn_name = {
        "telegram": "_deliver_telegram",
        "web_push": "_deliver_web_push",
        "email": "_deliver_email",
    }.get(channel)
    if not fn_name:
        return False
    fn = getattr(sys.modules[__name__], fn_name)
    return bool(fn(user_id, prefs, title, body, url))


# ─── Delivery log ────────────────────────────────────────────────────────────

def _log_delivery(user_id, event, channel, status, db_path=None) -> None:
    try:
        conn = _db(db_path)
        try:
            conn.execute(
                "INSERT INTO notify_delivery_log (user_id, event, channel, status) "
                "VALUES (?, ?, ?, ?)",
                (user_id, event, channel, status),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001 — logging must never break dispatch
        logger.warning("notify_log_failed", error=str(e)[:120])


# ─── Dispatcher ──────────────────────────────────────────────────────────────

def _parse_order(raw: Optional[str]) -> list:
    if not raw:
        return list(_VALID_CHANNELS)
    order = [c.strip() for c in raw.split(",") if c.strip() in _VALID_CHANNELS]
    return order or list(_VALID_CHANNELS)


def notify(user_id: int, event: str, payload: dict,
           prefs: Optional[dict] = None, db_path: Optional[str] = None) -> dict:
    """Deliver ``event`` to ``user_id`` over the first working preferred channel.

    Returns ``{"delivered": bool, "channel": str|None, "attempts": [...]}``.
    """
    if prefs is None:
        prefs = get_prefs(user_id, db_path=db_path)
    if db_path:
        prefs = {**prefs, "__db_path": db_path}

    title = payload.get("title", "")
    body = payload.get("body", "")
    url = payload.get("url", "/")

    attempts = []
    delivered_channel = None
    for ch in _parse_order(prefs.get("channel_order")):
        if not _channel_enabled(ch, prefs):
            # Channel not enabled for this user — skip silently, no log noise.
            continue
        ok = _dispatch_one(ch, user_id, prefs, title, body, url)
        attempts.append({"channel": ch, "ok": ok})
        _log_delivery(user_id, event, ch, "delivered" if ok else "failed", db_path=db_path)
        if ok:
            delivered_channel = ch
            break

    if delivered_channel is None:
        _log_delivery(user_id, event, "none", "undelivered", db_path=db_path)

    return {
        "delivered": delivered_channel is not None,
        "channel": delivered_channel,
        "attempts": attempts,
    }


# ─── Campaign fan-out (Faza N2b, #884) ───────────────────────────────────────

# Seconds since last_seen under which a member counts as "online" (in-session).
# Online members are skipped — they already see the game, no need to ping.
# Starting value; tune per #884 Numbers Policy.
ONLINE_WINDOW_SECONDS = 60


def _campaign_in_quiet_window(campaign_id: int, conn: sqlite3.Connection) -> bool:
    """Best-effort quiet-window suppression, parity with push fan-out (G27 #808).
    No-ops if the campaigns row / helper is unavailable (e.g. unit test DB)."""
    try:
        camp = conn.execute(
            "SELECT quiet_start, quiet_end, team_tz FROM campaigns WHERE id=?",
            (campaign_id,),
        ).fetchone()
        if not camp:
            return False
        from datetime import datetime, timezone as _tz

        from app.services.quiet_window import _in_quiet_window

        return _in_quiet_window(
            datetime.now(_tz.utc), camp["quiet_start"], camp["quiet_end"], camp["team_tz"]
        )
    except Exception:  # noqa: BLE001 — never block a notification on quiet-window
        return False


def notify_campaign_players(
    campaign_id: int,
    event: str,
    title: str,
    body: str,
    url: str = "/",
    exclude_online: bool = True,
    exclude_user_ids: Optional[list] = None,
    db_path: Optional[str] = None,
) -> dict:
    """Fan a game event out to a campaign's accepted members via `notify()`.

    Anti-spam: members active within ``ONLINE_WINDOW_SECONDS`` (and any in
    ``exclude_user_ids``, e.g. the acting player) are skipped. Each remaining
    member is dispatched over their preferred channel with per-attempt logging.
    Returns {"targeted": [uid...], "delivered": [uid...], "skipped_online": n}.
    """
    excluded = set(int(u) for u in (exclude_user_ids or []))
    conn = _db(db_path)
    try:
        if _campaign_in_quiet_window(campaign_id, conn):
            logger.info("notify_quiet_window_suppressed", campaign_id=campaign_id, event=event)
            return {"targeted": [], "delivered": [], "skipped_online": 0, "quiet": True}
        members = conn.execute(
            "SELECT user_id FROM campaign_members WHERE campaign_id=? AND status='accepted'",
            (campaign_id,),
        ).fetchall()
        online_ids: set = set()
        if exclude_online:
            online = conn.execute(
                "SELECT user_id FROM campaign_members "
                "WHERE campaign_id=? AND status='accepted' AND last_seen IS NOT NULL "
                "AND datetime(last_seen) > datetime('now', ?)",
                (campaign_id, f"-{ONLINE_WINDOW_SECONDS} seconds"),
            ).fetchall()
            online_ids = {int(r["user_id"]) for r in online}
    finally:
        conn.close()

    payload = {"title": title, "body": body, "url": url}
    targeted, delivered = [], []
    for row in members:
        uid = int(row["user_id"])
        if uid in excluded or uid in online_ids:
            continue
        targeted.append(uid)
        res = notify(uid, event, payload, db_path=db_path)
        if res.get("delivered"):
            delivered.append(uid)
    return {
        "targeted": targeted,
        "delivered": delivered,
        "skipped_online": len(online_ids),
    }


def preview_channel(user_id: int, prefs: Optional[dict] = None,
                    db_path: Optional[str] = None) -> dict:
    """Dry-run: which channel WOULD be chosen for this user — no send, no log.

    Deterministic surface for the admin panel / Playwright: returns the first
    enabled channel in the player's order, plus the full enabled set.
    """
    if prefs is None:
        prefs = get_prefs(user_id, db_path=db_path)
    order = _parse_order(prefs.get("channel_order"))
    enabled = [ch for ch in order if _channel_enabled(ch, prefs)]
    return {
        "user_id": user_id,
        "channel": enabled[0] if enabled else None,
        "enabled_channels": enabled,
        "channel_order": ",".join(order),
    }


def _channel_enabled(channel, prefs) -> bool:
    """Whether the player has the channel set up (a False send is then a real
    delivery failure, not an unavailable channel). Keeps the log free of noise."""
    if channel == "telegram":
        return bool(prefs.get("telegram_chat_id"))
    if channel == "web_push":
        return bool(prefs.get("web_push_enabled"))
    if channel == "email":
        return bool(prefs.get("email"))
    return False
