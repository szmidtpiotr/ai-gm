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
    whisper_to: Optional[str] = None


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
            "SELECT role FROM campaign_members WHERE campaign_id=? AND user_id=? AND status='accepted'",
            (campaign_id, uid),
        ).fetchone()
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this campaign")

        # G19 #800 — spectators see only public messages (no whispers, no private notes)
        is_spectator = member["role"] == "spectator"
        if is_spectator:
            whisper_filter = "whisper_to IS NULL"
            params_extra: tuple = ()
        else:
            # Resolve caller's character name (needed to show whispers addressed to them)
            # 1. Most recent submitted action (most reliable in-game name)
            caller_char = conn.execute(
                "SELECT character_name FROM campaign_round_actions "
                "WHERE campaign_id=? AND user_id=? "
                "ORDER BY submitted_at DESC LIMIT 1",
                (campaign_id, uid),
            ).fetchone()
            caller_char_name = caller_char["character_name"] if caller_char else None

            # 2. Fallback: character assigned to this user for this campaign
            if not caller_char_name:
                char_row = conn.execute(
                    "SELECT c.name FROM characters c "
                    "JOIN campaign_members cm ON cm.character_id = c.id "
                    "WHERE cm.campaign_id=? AND cm.user_id=? AND cm.status='accepted' LIMIT 1",
                    (campaign_id, uid),
                ).fetchone()
                caller_char_name = char_row["name"] if char_row else None

            # 3. Fallback: any character owned by this user active in this campaign
            if not caller_char_name:
                char_row = conn.execute(
                    "SELECT name FROM characters WHERE user_id=? AND campaign_id=? LIMIT 1",
                    (uid, campaign_id),
                ).fetchone()
                caller_char_name = char_row["name"] if char_row else None

            # 4. Broadest fallback: any character owned by this user (handles new players with no actions yet)
            if not caller_char_name:
                char_row = conn.execute(
                    "SELECT name FROM characters WHERE user_id=? ORDER BY id DESC LIMIT 1",
                    (uid,),
                ).fetchone()
                caller_char_name = char_row["name"] if char_row else None

            whisper_filter = "(whisper_to IS NULL OR user_id=? OR whisper_to=?)"
            params_extra = (uid, caller_char_name or "")

        if since_id:
            rows = conn.execute(
                "SELECT id, user_id, character_name, message, created_at, whisper_to "
                "FROM party_messages WHERE campaign_id=? AND id>? AND " + whisper_filter + " ORDER BY id ASC LIMIT 50",
                (campaign_id, since_id) + params_extra,
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, user_id, character_name, message, created_at, whisper_to "
                "FROM party_messages WHERE campaign_id=? AND " + whisper_filter + " ORDER BY id DESC LIMIT 50",
                (campaign_id,) + params_extra,
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
                    "whisper_to": r["whisper_to"],
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
            "SELECT role FROM campaign_members WHERE campaign_id=? AND user_id=? AND status='accepted'",
            (campaign_id, uid),
        ).fetchone()
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this campaign")

        # #963 — normalize whisper_to: accept username OR char name, store as char name
        normalized_whisper_to = req.whisper_to
        if req.whisper_to:
            # 1. Check if it's already a valid character name in this campaign
            char_match = conn.execute(
                "SELECT name FROM characters WHERE name=? AND campaign_id=? LIMIT 1",
                (req.whisper_to, campaign_id),
            ).fetchone()
            if not char_match:
                # 2. Try as username → resolve to character name via campaign_members
                user_row = conn.execute(
                    "SELECT id FROM users WHERE username=?", (req.whisper_to,)
                ).fetchone()
                if user_row:
                    target_uid = int(user_row["id"])
                    # Prefer most recent round action (most reliable in-game name)
                    char_action = conn.execute(
                        "SELECT character_name FROM campaign_round_actions "
                        "WHERE campaign_id=? AND user_id=? ORDER BY submitted_at DESC LIMIT 1",
                        (campaign_id, target_uid),
                    ).fetchone()
                    if char_action:
                        normalized_whisper_to = char_action["character_name"]
                    else:
                        # Fallback: campaign_members.character_id → characters.name
                        char_row = conn.execute(
                            "SELECT c.name FROM characters c "
                            "JOIN campaign_members cm ON cm.character_id = c.id "
                            "WHERE cm.campaign_id=? AND cm.user_id=? AND cm.status='accepted' LIMIT 1",
                            (campaign_id, target_uid),
                        ).fetchone()
                        if char_row:
                            normalized_whisper_to = char_row["name"]
                        else:
                            raise HTTPException(
                                status_code=400,
                                detail="whisper_to: recipient not found in campaign",
                            )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="whisper_to: recipient not found in campaign",
                    )

        # G19 #800 — spectator hint guard: whisper from spectator requires policy + no mute
        if member["role"] == "spectator" and req.whisper_to:
            camp = conn.execute(
                "SELECT spectator_policy FROM campaigns WHERE id=?", (campaign_id,)
            ).fetchone()
            if not camp or camp["spectator_policy"] != "watch_hint":
                raise HTTPException(status_code=403, detail="Spectator hints not allowed (policy)")

            # Resolve target player's user_id from their character name
            target_action = conn.execute(
                "SELECT user_id FROM campaign_round_actions WHERE campaign_id=? AND character_name=? "
                "ORDER BY submitted_at DESC LIMIT 1",
                (campaign_id, req.whisper_to),
            ).fetchone()
            if target_action:
                target_uid = int(target_action["user_id"])
                muted = conn.execute(
                    "SELECT 1 FROM campaign_spectator_mutes "
                    "WHERE campaign_id=? AND user_id_player=? AND user_id_spectator=?",
                    (campaign_id, target_uid, uid),
                ).fetchone()
                if muted:
                    raise HTTPException(status_code=403, detail="Spectator muted by this player")

        row = conn.execute(
            "INSERT INTO party_messages (campaign_id, user_id, character_name, message, whisper_to, created_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now')) RETURNING id, created_at",
            (campaign_id, uid, req.character_name, req.message.strip(), normalized_whisper_to),
        ).fetchone()
        conn.commit()
        msg_id = int(row["id"])
        created_at = row["created_at"]
    finally:
        conn.close()

    import threading
    from app.services.push_notification_service import send_push_to_campaign_players, send_push

    if normalized_whisper_to:
        _whisper_target = normalized_whisper_to

        def _push_whisper():
            from app.core.db_runtime import resolve_db_path
            import sqlite3 as _sqlite3
            conn2 = _sqlite3.connect(resolve_db_path())
            conn2.row_factory = _sqlite3.Row
            try:
                target = conn2.execute(
                    "SELECT user_id FROM campaign_round_actions WHERE campaign_id=? AND character_name=? "
                    "ORDER BY submitted_at DESC LIMIT 1",
                    (campaign_id, _whisper_target),
                ).fetchone()
                if not target:
                    # Fallback: campaign_members with character_id
                    target = conn2.execute(
                        "SELECT cm.user_id FROM campaign_members cm "
                        "JOIN characters c ON cm.character_id = c.id "
                        "WHERE cm.campaign_id=? AND c.name=? AND cm.status='accepted' LIMIT 1",
                        (campaign_id, _whisper_target),
                    ).fetchone()
                if target:
                    send_push(int(target["user_id"]), f"🤫 Szept od {req.character_name}", req.message.strip()[:80], url="/")
            finally:
                conn2.close()
        threading.Thread(target=_push_whisper, daemon=True).start()
    else:
        threading.Thread(
            target=send_push_to_campaign_players,
            args=(campaign_id, f"{req.character_name} 💬", req.message.strip()[:80]),
            kwargs={"url": "/", "exclude_user_id": uid},
            daemon=True,
        ).start()

    return {"id": msg_id, "created_at": created_at}
