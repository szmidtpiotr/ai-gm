"""Notification preferences + Telegram linking — Issue #602 (N0/N1/N2).

Player (JWT-gated):
    GET    /api/users/notify-prefs         — channel prefs (no secrets leaked)
    PUT    /api/users/notify-prefs          — set web_push_enabled / email / order
    POST   /api/users/telegram/link-token   — mint easy-click deep-link + QR data
    GET    /api/users/telegram/status       — {connected} for the UI poll
    DELETE /api/users/telegram              — unlink Telegram

Telegram (bot):
    POST   /api/telegram/webhook            — /start <token> → bind chat_id

Admin / test (unauthenticated read):
    GET    /api/admin/notify/preview/{user_id}  — dry-run channel selection
"""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from app.core.jwt_auth import require_current_user
from app.core.logging import get_logger
from app.services import notification_service as ns
from app.services import telegram_link_service as tls

logger = get_logger(__name__)
router = APIRouter()


def _uid(authorization: Optional[str]) -> int:
    payload = require_current_user(authorization)
    uid = int(payload.get("sub") or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="invalid_token")
    return uid


# ─── Preferences ─────────────────────────────────────────────────────────────

class NotifyPrefsReq(BaseModel):
    web_push_enabled: Optional[bool] = None
    email: Optional[str] = None
    channel_order: Optional[str] = None


def _public_prefs(uid: int) -> dict:
    """Shape sent to the client — telegram exposed as a bool, never the chat_id."""
    p = ns.get_prefs(uid)
    return {
        "web_push_enabled": bool(p.get("web_push_enabled")),
        "telegram_connected": bool(p.get("telegram_chat_id")),
        "email": p.get("email"),
        "channel_order": p.get("channel_order") or ns.DEFAULT_CHANNEL_ORDER,
    }


@router.get("/users/notify-prefs")
def get_notify_prefs(authorization: Optional[str] = Header(default=None)):
    return _public_prefs(_uid(authorization))


@router.put("/users/notify-prefs")
def put_notify_prefs(req: NotifyPrefsReq, authorization: Optional[str] = Header(default=None)):
    uid = _uid(authorization)
    fields: dict = {}
    if req.web_push_enabled is not None:
        fields["web_push_enabled"] = 1 if req.web_push_enabled else 0
    if req.email is not None:
        fields["email"] = req.email.strip() or None
    if req.channel_order is not None:
        # Keep only known channels, preserve order, dedupe.
        seen: list = []
        for c in req.channel_order.split(","):
            c = c.strip()
            if c in ns._VALID_CHANNELS and c not in seen:
                seen.append(c)
        if seen:
            fields["channel_order"] = ",".join(seen)
    if fields:
        ns.set_prefs(uid, **fields)
    return _public_prefs(uid)


# ─── Telegram linking (N1) ───────────────────────────────────────────────────

@router.post("/users/telegram/link-token")
def create_telegram_link(authorization: Optional[str] = Header(default=None)):
    uid = _uid(authorization)
    return tls.create_link_token(uid)


@router.get("/users/telegram/status")
def telegram_status(authorization: Optional[str] = Header(default=None)):
    uid = _uid(authorization)
    return {"connected": tls.is_connected(uid), "configured": tls.is_configured()}


@router.delete("/users/telegram")
def telegram_unlink(authorization: Optional[str] = Header(default=None)):
    uid = _uid(authorization)
    tls.unlink(uid)
    return {"connected": False}


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
):
    """Bot webhook. When a webhook secret is configured it MUST match; the bot is
    set up with the same secret so spoofed calls are rejected."""
    secret = tls.webhook_secret()
    if secret and x_telegram_bot_api_secret_token != secret:
        raise HTTPException(status_code=403, detail="bad_secret")
    try:
        update = await request.json()
    except Exception:  # noqa: BLE001
        update = {}
    result = tls.handle_update(update)
    # Always 200 so Telegram does not retry-storm on our side.
    return {"ok": True, **result}


# ─── Admin preview (N0/N2) ───────────────────────────────────────────────────

@router.get("/admin/notify/preview/{user_id}")
def admin_notify_preview(user_id: int):
    """Dry-run: which channel WOULD fire for this player. No send, no log."""
    return ns.preview_channel(user_id)
