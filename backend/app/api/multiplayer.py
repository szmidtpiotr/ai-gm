"""Multiplayer API — lobby creation, invites, round submission, narration."""

import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.core.db_runtime import resolve_db_path
from app.core.jwt_auth import resolve_authed_user_id
from app.core.logging import get_logger
from app.services import multiplayer_round_service as svc

router = APIRouter(tags=["multiplayer"])
logger = get_logger(__name__)

INVITE_TTL_DAYS = 7


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


# ── Lobby ─────────────────────────────────────────────────────────────────────

class CreateLobbyReq(BaseModel):
    title: str
    system_id: str = "fantasy"
    round_timer_hours: int = 24
    max_players: int = 4


@router.post("/multiplayer/campaigns")
def create_lobby(
    body: CreateLobbyReq,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="title required")
    if body.max_players < 2 or body.max_players > 4:
        raise HTTPException(status_code=400, detail="max_players must be 2-4")
    if body.round_timer_hours not in (12, 24, 48):
        raise HTTPException(status_code=400, detail="round_timer_hours must be 12, 24 or 48")

    conn = _db()
    try:
        cur = conn.execute(
            """INSERT INTO campaigns
               (title, system_id, owner_user_id, mode, status,
                round_timer_hours, max_players, host_user_id, lobby_status)
               VALUES (?, ?, ?, 'multiplayer', 'active', ?, ?, ?, 'open')""",
            (body.title.strip(), body.system_id, uid,
             body.round_timer_hours, body.max_players, uid),
        )
        campaign_id = cur.lastrowid
        conn.execute(
            "INSERT INTO campaign_members (campaign_id, user_id, role, status) VALUES (?, ?, 'owner', 'accepted')",
            (campaign_id, uid),
        )
        conn.commit()
        return {"campaign_id": campaign_id, "title": body.title.strip(), "lobby_status": "open"}
    finally:
        conn.close()


@router.get("/multiplayer/campaigns/{campaign_id}/lobby")
def get_lobby(
    campaign_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    conn = _db()
    try:
        camp = conn.execute(
            "SELECT id, title, system_id, round_timer_hours, max_players, host_user_id, lobby_status "
            "FROM campaigns WHERE id=? AND mode='multiplayer'",
            (campaign_id,),
        ).fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Lobby not found")

        members = conn.execute(
            """SELECT m.user_id, u.username, u.display_name, m.role, m.status, m.character_id
               FROM campaign_members m JOIN users u ON u.id=m.user_id
               WHERE m.campaign_id=?""",
            (campaign_id,),
        ).fetchall()

        return {
            "campaign_id": campaign_id,
            "title": camp["title"],
            "system_id": camp["system_id"],
            "round_timer_hours": camp["round_timer_hours"],
            "max_players": camp["max_players"],
            "host_user_id": camp["host_user_id"],
            "lobby_status": camp["lobby_status"],
            "is_host": uid == camp["host_user_id"],
            "members": [
                {
                    "user_id": m["user_id"],
                    "username": m["username"],
                    "display_name": m["display_name"] or m["username"],
                    "role": m["role"],
                    "status": m["status"],
                    "character_id": m["character_id"],
                }
                for m in members
            ],
            "accepted_count": sum(1 for m in members if m["status"] == "accepted"),
        }
    finally:
        conn.close()


# ── Invites ────────────────────────────────────────────────────────────────────

class InviteUsernameReq(BaseModel):
    username: str


@router.post("/multiplayer/campaigns/{campaign_id}/invite/username")
def invite_by_username(
    campaign_id: int,
    body: InviteUsernameReq,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    conn = _db()
    try:
        camp = conn.execute(
            "SELECT host_user_id, max_players, lobby_status FROM campaigns WHERE id=? AND mode='multiplayer'",
            (campaign_id,),
        ).fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Lobby not found")
        if camp["host_user_id"] != uid:
            raise HTTPException(status_code=403, detail="Only host can invite")
        if camp["lobby_status"] != "open":
            raise HTTPException(status_code=400, detail="Lobby already started")

        target = conn.execute(
            "SELECT id, username FROM users WHERE username=?", (body.username.strip(),)
        ).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        current_count = int(conn.execute(
            "SELECT COUNT(*) FROM campaign_members WHERE campaign_id=? AND status!='declined'",
            (campaign_id,),
        ).fetchone()[0])
        if current_count >= camp["max_players"]:
            raise HTTPException(status_code=400, detail="Lobby full")

        conn.execute(
            """INSERT INTO campaign_members (campaign_id, user_id, role, status)
               VALUES (?, ?, 'player', 'pending')
               ON CONFLICT(campaign_id, user_id) DO UPDATE SET status='pending'""",
            (campaign_id, target["id"]),
        )
        conn.commit()
        return {"invited": target["username"], "status": "pending"}
    finally:
        conn.close()


@router.post("/multiplayer/campaigns/{campaign_id}/invite-link")
def generate_invite_link(
    campaign_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    conn = _db()
    try:
        camp = conn.execute(
            "SELECT host_user_id, lobby_status FROM campaigns WHERE id=? AND mode='multiplayer'",
            (campaign_id,),
        ).fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Lobby not found")
        if camp["host_user_id"] != uid:
            raise HTTPException(status_code=403, detail="Only host can generate links")
        if camp["lobby_status"] != "open":
            raise HTTPException(status_code=400, detail="Lobby already started")

        token = secrets.token_urlsafe(24)
        expires = (datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)).isoformat()
        conn.execute(
            "INSERT INTO campaign_invites (campaign_id, token, created_by, expires_at) VALUES (?, ?, ?, ?)",
            (campaign_id, token, uid, expires),
        )
        conn.commit()
        return {"token": token, "expires_at": expires}
    finally:
        conn.close()


@router.get("/multiplayer/join/{token}")
def join_via_link(
    token: str,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    conn = _db()
    try:
        inv = conn.execute(
            "SELECT * FROM campaign_invites WHERE token=?", (token,)
        ).fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Invite link not found")
        if inv["used_at"]:
            raise HTTPException(status_code=410, detail="Invite link already used")
        now = datetime.now(timezone.utc).isoformat()
        if inv["expires_at"] < now:
            raise HTTPException(status_code=410, detail="Invite link expired")

        campaign_id = inv["campaign_id"]
        camp = conn.execute(
            "SELECT max_players, lobby_status, title FROM campaigns WHERE id=?",
            (campaign_id,),
        ).fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if camp["lobby_status"] != "open":
            raise HTTPException(status_code=400, detail="This lobby has already started")

        current_count = int(conn.execute(
            "SELECT COUNT(*) FROM campaign_members WHERE campaign_id=? AND status!='declined'",
            (campaign_id,),
        ).fetchone()[0])
        if current_count >= camp["max_players"]:
            raise HTTPException(status_code=400, detail="Lobby is full")

        conn.execute(
            """INSERT INTO campaign_members (campaign_id, user_id, role, status)
               VALUES (?, ?, 'player', 'accepted')
               ON CONFLICT(campaign_id, user_id) DO UPDATE SET status='accepted'""",
            (campaign_id, uid),
        )
        conn.execute(
            "UPDATE campaign_invites SET used_at=?, used_by=? WHERE token=?",
            (now, uid, token),
        )
        conn.commit()
        return {"campaign_id": campaign_id, "title": camp["title"], "status": "accepted"}
    finally:
        conn.close()


@router.post("/multiplayer/campaigns/{campaign_id}/accept")
def accept_invite(
    campaign_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    conn = _db()
    try:
        member = conn.execute(
            "SELECT status FROM campaign_members WHERE campaign_id=? AND user_id=?",
            (campaign_id, uid),
        ).fetchone()
        if not member:
            raise HTTPException(status_code=404, detail="Not invited to this lobby")
        conn.execute(
            "UPDATE campaign_members SET status='accepted' WHERE campaign_id=? AND user_id=?",
            (campaign_id, uid),
        )
        conn.commit()
        return {"status": "accepted"}
    finally:
        conn.close()


@router.post("/multiplayer/campaigns/{campaign_id}/decline")
def decline_invite(
    campaign_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    conn = _db()
    try:
        conn.execute(
            "UPDATE campaign_members SET status='declined' WHERE campaign_id=? AND user_id=?",
            (campaign_id, uid),
        )
        conn.commit()
        return {"status": "declined"}
    finally:
        conn.close()


@router.delete("/multiplayer/campaigns/{campaign_id}/players/{target_user_id}")
def kick_player(
    campaign_id: int,
    target_user_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    conn = _db()
    try:
        camp = conn.execute(
            "SELECT host_user_id, lobby_status FROM campaigns WHERE id=?", (campaign_id,)
        ).fetchone()
        if not camp or camp["host_user_id"] != uid:
            raise HTTPException(status_code=403, detail="Only host can kick players")
        if camp["lobby_status"] != "open":
            raise HTTPException(status_code=400, detail="Cannot kick after game started")
        conn.execute(
            "UPDATE campaign_members SET status='removed' WHERE campaign_id=? AND user_id=?",
            (campaign_id, target_user_id),
        )
        conn.commit()
        return {"removed": target_user_id}
    finally:
        conn.close()


@router.post("/multiplayer/campaigns/{campaign_id}/start")
def start_lobby(
    campaign_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    conn = _db()
    try:
        camp = conn.execute(
            "SELECT host_user_id, lobby_status FROM campaigns WHERE id=? AND mode='multiplayer'",
            (campaign_id,),
        ).fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Lobby not found")
        if camp["host_user_id"] != uid:
            raise HTTPException(status_code=403, detail="Only host can start")
        if camp["lobby_status"] != "open":
            raise HTTPException(status_code=400, detail="Already started")

        accepted = int(conn.execute(
            "SELECT COUNT(*) FROM campaign_members WHERE campaign_id=? AND status='accepted'",
            (campaign_id,),
        ).fetchone()[0])
        if accepted < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 accepted players to start")

        conn.execute(
            "UPDATE campaigns SET lobby_status='started' WHERE id=?", (campaign_id,)
        )
        conn.commit()
        return {"campaign_id": campaign_id, "lobby_status": "started", "players": accepted}
    finally:
        conn.close()


# ── My pending invites ────────────────────────────────────────────────────────

@router.get("/multiplayer/my-invites")
def my_pending_invites(
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    conn = _db()
    try:
        rows = conn.execute(
            """SELECT c.id as campaign_id, c.title, c.system_id, c.round_timer_hours,
                      c.max_players, c.host_user_id, u.username as host_username,
                      m.status
               FROM campaign_members m
               JOIN campaigns c ON c.id=m.campaign_id
               JOIN users u ON u.id=c.host_user_id
               WHERE m.user_id=? AND c.mode='multiplayer' AND m.status='pending'""",
            (uid,),
        ).fetchall()
        return {"invites": [dict(r) for r in rows]}
    finally:
        conn.close()


# ── My active lobbies ─────────────────────────────────────────────────────────

@router.get("/multiplayer/my-lobbies")
def my_active_lobbies(
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    conn = _db()
    try:
        rows = conn.execute(
            """SELECT c.id as campaign_id, c.title, c.system_id, c.round_timer_hours,
                      c.max_players, c.host_user_id, u.username as host_username,
                      m.status, m.role,
                      (SELECT COUNT(*) FROM campaign_members cm WHERE cm.campaign_id=c.id AND cm.status='accepted') as accepted_count
               FROM campaign_members m
               JOIN campaigns c ON c.id=m.campaign_id
               JOIN users u ON u.id=c.host_user_id
               WHERE m.user_id=? AND c.mode='multiplayer'
                 AND m.status='accepted' AND c.lobby_status='open'""",
            (uid,),
        ).fetchall()
        return {"lobbies": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.get("/multiplayer/my-active-games")
def my_active_games(
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    conn = _db()
    try:
        rows = conn.execute(
            """SELECT c.id as campaign_id, c.title, c.system_id, c.round_timer_hours,
                      c.max_players, c.host_user_id, u.username as host_username, m.role,
                      (SELECT COUNT(*) FROM campaign_members cm WHERE cm.campaign_id=c.id AND cm.status='accepted') as player_count
               FROM campaign_members m
               JOIN campaigns c ON c.id=m.campaign_id
               JOIN users u ON u.id=c.host_user_id
               WHERE m.user_id=? AND c.mode='multiplayer'
                 AND m.status='accepted' AND c.lobby_status='started'""",
            (uid,),
        ).fetchall()
        return {"games": [dict(r) for r in rows]}
    finally:
        conn.close()


# ── Round endpoints ────────────────────────────────────────────────────────────

class SubmitActionReq(BaseModel):
    action_text: str
    character_id: int
    character_name: str


@router.post("/campaigns/{campaign_id}/round/submit")
def submit_round_action(
    campaign_id: int,
    body: SubmitActionReq,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    if not body.action_text.strip():
        raise HTTPException(status_code=400, detail="action_text cannot be empty")

    result = svc.submit_action(
        campaign_id=campaign_id,
        user_id=uid,
        character_id=body.character_id,
        character_name=body.character_name,
        action_text=body.action_text.strip(),
    )

    if result["status"] == "narrating":
        threading.Thread(
            target=svc.trigger_narration,
            args=(result["round_id"],),
            daemon=True,
        ).start()

    return result


@router.get("/campaigns/{campaign_id}/round/status")
def get_round_status(
    campaign_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    status = svc.get_round_status(campaign_id, uid)
    if status is None:
        return {"round_number": 0, "status": "none", "submitted_count": 0, "total_players": 0, "my_submitted": False}
    return status


@router.get("/campaigns/{campaign_id}/round/narration")
def get_round_narration(
    campaign_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    narration = svc.get_round_narration(campaign_id, uid)
    if narration is None:
        raise HTTPException(status_code=404, detail="No completed narration available")
    return narration
