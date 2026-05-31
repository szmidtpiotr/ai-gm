"""Web Push notification service — sends push messages to subscribed browsers.

Uses pywebpush + VAPID authentication. Subscriptions stored in
user_push_subscriptions table (created by migrations_admin).

Environment variables required:
    VAPID_PRIVATE_KEY   — base64url-encoded DER private key
    VAPID_PUBLIC_KEY    — base64url-encoded uncompressed EC public key (for frontend)
    VAPID_CLAIMS_EMAIL  — mailto: contact in VAPID claims
"""

import json
import os
import sqlite3
from typing import Optional

from app.core.db_runtime import resolve_db_path
from app.core.logging import get_logger

logger = get_logger(__name__)

_VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
_VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
_VAPID_EMAIL = os.getenv("VAPID_CLAIMS_EMAIL", "mailto:admin@example.com")


def get_vapid_public_key() -> str:
    return _VAPID_PUBLIC_KEY


def _is_configured() -> bool:
    return bool(_VAPID_PRIVATE_KEY and _VAPID_PUBLIC_KEY)


def _db():
    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def save_subscription(user_id: int, subscription: dict) -> None:
    endpoint = subscription.get("endpoint", "")
    keys = subscription.get("keys", {})
    p256dh = keys.get("p256dh", "")
    auth = keys.get("auth", "")

    if not endpoint or not p256dh or not auth:
        raise ValueError("Invalid subscription object — missing endpoint or keys")

    conn = _db()
    try:
        conn.execute(
            """
            INSERT INTO user_push_subscriptions (user_id, endpoint, p256dh, auth)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, endpoint) DO UPDATE SET
                p256dh = excluded.p256dh,
                auth = excluded.auth
            """,
            (user_id, endpoint, p256dh, auth),
        )
        conn.commit()
    finally:
        conn.close()


def delete_subscription(user_id: int, endpoint: str) -> None:
    conn = _db()
    try:
        conn.execute(
            "DELETE FROM user_push_subscriptions WHERE user_id = ? AND endpoint = ?",
            (user_id, endpoint),
        )
        conn.commit()
    finally:
        conn.close()


def _get_subscriptions_for_user(user_id: int, conn: sqlite3.Connection) -> list:
    return conn.execute(
        "SELECT endpoint, p256dh, auth FROM user_push_subscriptions WHERE user_id = ?",
        (user_id,),
    ).fetchall()


def send_push(
    user_id: int,
    title: str,
    body: str,
    url: str = "/",
    icon: Optional[str] = None,
    badge: Optional[str] = None,
    image: Optional[str] = None,
    vibrate: Optional[list] = None,
) -> None:
    if not _is_configured():
        logger.warning("push_not_configured", user_id=user_id)
        return

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.error("pywebpush_not_installed")
        return

    conn = _db()
    try:
        rows = _get_subscriptions_for_user(user_id, conn)
    finally:
        conn.close()

    if not rows:
        return

    data: dict = {"title": title, "body": body, "url": url}
    if icon:
        data["icon"] = icon
    if badge:
        data["badge"] = badge
    if image:
        data["image"] = image
    if vibrate:
        data["vibrate"] = vibrate
    payload = json.dumps(data)
    stale_endpoints = []

    for row in rows:
        subscription_info = {
            "endpoint": row["endpoint"],
            "keys": {"p256dh": row["p256dh"], "auth": row["auth"]},
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=_VAPID_PRIVATE_KEY,
                vapid_claims={"sub": _VAPID_EMAIL},
            )
            logger.info("push_sent", user_id=user_id, endpoint_prefix=row["endpoint"][:40])
        except Exception as e:
            err_str = str(e)
            if "410" in err_str or "404" in err_str:
                stale_endpoints.append(row["endpoint"])
                logger.info("push_subscription_stale", endpoint_prefix=row["endpoint"][:40])
            else:
                logger.warning("push_send_failed", user_id=user_id, error=err_str[:120])

    if stale_endpoints:
        conn = _db()
        try:
            for ep in stale_endpoints:
                conn.execute(
                    "DELETE FROM user_push_subscriptions WHERE endpoint = ?", (ep,)
                )
            conn.commit()
        finally:
            conn.close()


def send_push_to_campaign_players(
    campaign_id: int,
    title: str,
    body: str,
    url: str = "/",
    exclude_user_id: Optional[int] = None,
) -> None:
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT user_id FROM campaign_players WHERE campaign_id = ? AND status = 'accepted'",
            (campaign_id,),
        ).fetchall()
    finally:
        conn.close()

    for row in rows:
        uid = int(row["user_id"])
        if exclude_user_id and uid == exclude_user_id:
            continue
        send_push(uid, title, body, url)
