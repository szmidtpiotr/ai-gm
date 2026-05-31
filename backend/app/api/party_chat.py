"""Party chat — out-of-character player messaging within a multiplayer campaign."""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.core.db_runtime import resolve_db_path
from app.core.jwt_auth import resolve_authed_user_id
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


class ChatMessageReq(BaseModel):
    message: str
    character_name: str


@router.get("/multiplayer/campaigns/{campaign_id}/chat")
def get_party_chat(
    campaign_id: int,
    since_id: Optional[int] = Query(default=None),
    authorization: Optional[str] = Header(default=None),
    user_id: Optional[int] = Query(default=None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    conn = _db()
    try:
        member = conn.execute(
            "SELECT 1 FROM campaign_members WHERE campaign_id=? AND user_id=? AND status='accepted'",
            (campaign_id, uid),
        ).fetchone()
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this campaign")

        if since_id:
            rows = conn.execute(
                "SELECT id, user_id, character_name, message, created_at "
                "FROM party_messages WHERE campaign_id=? AND id>? ORDER BY id ASC LIMIT 50",
                (campaign_id, since_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, user_id, character_name, message, created_at "
                "FROM party_messages WHERE campaign_id=? ORDER BY id DESC LIMIT 50",
                (campaign_id,),
            ).fetchall()
            rows = list(reversed(rows))

        return {
            "messages": [
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "character_name": r["character_name"],
                    "message": r["message"],
                    "created_at": r["created_at"],
                    "is_mine": r["user_id"] == uid,
                }
                for r in rows
            ]
        }
    finally:
        conn.close()


@router.post("/multiplayer/campaigns/{campaign_id}/chat", status_code=201)
def post_party_chat(
    campaign_id: int,
    req: ChatMessageReq,
    authorization: Optional[str] = Header(default=None),
    user_id: Optional[int] = Query(default=None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")
    if len(req.message) > 500:
        raise HTTPException(status_code=400, detail="Message too long (max 500 chars)")
    if len(req.character_name) > 100:
        raise HTTPException(status_code=400, detail="character_name too long (max 100 chars)")

    conn = _db()
    try:
        member = conn.execute(
            "SELECT 1 FROM campaign_members WHERE campaign_id=? AND user_id=? AND status='accepted'",
            (campaign_id, uid),
        ).fetchone()
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this campaign")

        row = conn.execute(
            "INSERT INTO party_messages (campaign_id, user_id, character_name, message) VALUES (?, ?, ?, ?) RETURNING id, created_at",
            (campaign_id, uid, req.character_name, req.message.strip()),
        ).fetchone()
        conn.commit()
        msg_id = int(row["id"])
        created_at = row["created_at"]
    finally:
        conn.close()

    import threading
    from app.services.push_notification_service import send_push_to_campaign_players
    threading.Thread(
        target=send_push_to_campaign_players,
        args=(campaign_id, f"{req.character_name} 💬", req.message.strip()[:80]),
        kwargs={"url": "/", "exclude_user_id": uid},
        daemon=True,
    ).start()

    return {"id": msg_id, "created_at": created_at}
