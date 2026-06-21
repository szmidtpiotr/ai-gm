"""Notification preferences + dispatcher preview — Issue #602 (Faza N0/N2).

Player:
    GET  /api/users/notify-prefs        — read own channel prefs
    PUT  /api/users/notify-prefs        — update own channel prefs

Admin / test (unauthenticated, like other /api/admin/* read surfaces):
    GET  /api/admin/notify/preview/{user_id}  — dry-run channel selection (no send)
"""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.jwt_auth import require_current_user
from app.core.logging import get_logger
from app.services import notification_service as ns

logger = get_logger(__name__)
router = APIRouter()


def _uid(authorization: str | None) -> int:
    payload = require_current_user(authorization)
    uid = int(payload.get("sub") or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="invalid_token")
    return uid


class NotifyPrefsReq(BaseModel):
    web_push_enabled: int | None = None
    telegram_chat_id: str | None = None
    email: str | None = None
    channel_order: str | None = None


@router.get("/users/notify-prefs")
def get_notify_prefs(authorization: str | None = Header(default=None)):
    uid = _uid(authorization)
    return ns.get_prefs(uid)


@router.put("/users/notify-prefs")
def put_notify_prefs(
    req: NotifyPrefsReq,
    authorization: str | None = Header(default=None),
):
    uid = _uid(authorization)
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    ns.set_prefs(uid, **fields)
    logger.info("notify_prefs_updated", user_id=uid, fields=list(fields.keys()))
    return ns.get_prefs(uid)


@router.get("/admin/notify/preview/{user_id}")
def admin_notify_preview(user_id: int):
    """Dry-run: which channel WOULD fire for this player. No send, no log."""
    return ns.preview_channel(user_id)
