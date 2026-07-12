"""Push notification subscription management endpoints.

POST   /api/users/push-subscription    — register/update browser subscription
DELETE /api/users/push-subscription    — remove subscription
GET    /api/push/vapid-public-key      — return VAPID public key for frontend
"""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.jwt_auth import require_current_user
from app.core.logging import get_logger
from app.services.push_notification_service import (
    delete_subscription,
    get_diagnostics,
    get_vapid_public_key,
    save_subscription,
)

logger = get_logger(__name__)
router = APIRouter()


def _uid(authorization: str | None) -> int:
    payload = require_current_user(authorization)
    uid = int(payload.get("sub") or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="invalid_token")
    return uid


class PushSubscriptionReq(BaseModel):
    endpoint: str
    keys: dict


class DeleteSubscriptionReq(BaseModel):
    endpoint: str


@router.get("/push/vapid-public-key")
def vapid_public_key():
    key = get_vapid_public_key()
    if not key:
        raise HTTPException(status_code=503, detail="Push notifications not configured")
    return {"publicKey": key}


@router.get("/push/diagnostics")
def push_diagnostics():
    """Unauthenticated server-readiness check for the player-UI push panel.
    Exposes config presence/lengths/bools only — no secret material (#593)."""
    return get_diagnostics()


@router.post("/users/push-subscription", status_code=201)
def register_push_subscription(
    req: PushSubscriptionReq,
    authorization: str | None = Header(default=None),
):
    uid = _uid(authorization)
    try:
        save_subscription(uid, {"endpoint": req.endpoint, "keys": req.keys})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # N3 (#885): enable the web_push channel in the dispatcher now that a live
    # subscription exists — otherwise notify() would skip web_push entirely.
    try:
        from app.services import notification_service as ns
        ns.set_prefs(uid, web_push_enabled=1)
    except Exception:  # noqa: BLE001 — subscription itself already succeeded
        logger.warning("web_push_pref_enable_failed", user_id=uid)
    logger.info("push_subscription_registered", user_id=uid)
    return {"status": "ok"}


@router.delete("/users/push-subscription")
def remove_push_subscription(
    req: DeleteSubscriptionReq,
    authorization: str | None = Header(default=None),
):
    uid = _uid(authorization)
    delete_subscription(uid, req.endpoint)
    # N3 (#885): if that was the last subscription, disable the web_push channel
    # so the dispatcher stops choosing it and falls through to email.
    try:
        from app.services import notification_service as ns
        from app.services.push_notification_service import _db

        conn = _db()
        try:
            remaining = conn.execute(
                "SELECT COUNT(*) FROM user_push_subscriptions WHERE user_id = ?", (uid,)
            ).fetchone()[0]
        finally:
            conn.close()
        if not remaining:
            ns.set_prefs(uid, web_push_enabled=0)
    except Exception:  # noqa: BLE001
        logger.warning("web_push_pref_disable_failed", user_id=uid)
    logger.info("push_subscription_removed", user_id=uid)
    return {"status": "ok"}
