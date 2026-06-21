"""Multiplayer API — lobby creation, invites, round submission, narration."""

import json
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


def _send_invite_push(user_id: int, camp_title: str) -> None:
    try:
        from app.services.push_notification_service import send_push
        send_push(
            user_id,
            "Nowe zaproszenie ⚔",
            f"Zostałeś zaproszony do \"{camp_title}\". Otwórz Kampanie, aby dołączyć.",
            url="/",
        )
    except Exception as e:
        logger.warning("push_invite_failed", error=str(e)[:100])


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


# ── Lobby ─────────────────────────────────────────────────────────────────────

class CreateLobbyReq(BaseModel):
    title: str
    system_id: str = "fantasy"
    round_timer_minutes: int = 1440  # default 24h
    max_players: int = 4
    template_id: Optional[int] = None


class UpdateTimerReq(BaseModel):
    round_timer_minutes: int


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
    if body.round_timer_minutes < 1 or body.round_timer_minutes > 4320:
        raise HTTPException(status_code=400, detail="round_timer_minutes must be 1–4320")

    conn = _db()
    try:
        gm_plan_json = "{}"
        lobby_title = body.title.strip()
        template_id = body.template_id

        if template_id:
            tpl = conn.execute(
                "SELECT title, gm_plan_json FROM campaign_templates WHERE id=? AND status='published'",
                (template_id,),
            ).fetchone()
            if not tpl:
                raise HTTPException(status_code=404, detail="Template not found or not published")
            if tpl["gm_plan_json"] and tpl["gm_plan_json"].strip() not in ("", "{}"):
                gm_plan_json = tpl["gm_plan_json"]
            if not lobby_title:
                lobby_title = tpl["title"]

        cur = conn.execute(
            """INSERT INTO campaigns
               (title, system_id, owner_user_id, mode, status,
                round_timer_hours, round_timer_minutes, max_players, host_user_id, lobby_status,
                template_id, gm_plan_json)
               VALUES (?, ?, ?, 'multiplayer', 'active', ?, ?, ?, ?, 'open', ?, ?)""",
            (lobby_title, body.system_id, uid,
             max(1, body.round_timer_minutes // 60), body.round_timer_minutes,
             body.max_players, uid, template_id, gm_plan_json),
        )
        campaign_id = cur.lastrowid
        conn.execute(
            "INSERT INTO campaign_members (campaign_id, user_id, role, status) VALUES (?, ?, 'owner', 'accepted')",
            (campaign_id, uid),
        )
        conn.commit()
        return {"campaign_id": campaign_id, "title": lobby_title, "lobby_status": "open"}
    finally:
        conn.close()


@router.patch("/multiplayer/campaigns/{campaign_id}/timer")
def update_round_timer(
    campaign_id: int,
    body: UpdateTimerReq,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    if body.round_timer_minutes < 1 or body.round_timer_minutes > 4320:
        raise HTTPException(status_code=400, detail="round_timer_minutes must be 1–4320")
    conn = _db()
    try:
        camp = conn.execute(
            "SELECT host_user_id FROM campaigns WHERE id=? AND mode='multiplayer'",
            (campaign_id,),
        ).fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if camp["host_user_id"] != uid:
            raise HTTPException(status_code=403, detail="Only host can change timer")
        conn.execute(
            "UPDATE campaigns SET round_timer_minutes=?, round_timer_hours=? WHERE id=?",
            (body.round_timer_minutes, max(1, body.round_timer_minutes // 60), campaign_id),
        )
        conn.commit()
        return {"round_timer_minutes": body.round_timer_minutes}
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
            "SELECT id, title, system_id, round_timer_hours, "
            "COALESCE(round_timer_minutes, round_timer_hours*60) as round_timer_minutes, "
            "max_players, host_user_id, lobby_status "
            "FROM campaigns WHERE id=? AND mode='multiplayer'",
            (campaign_id,),
        ).fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Lobby not found")

        members = conn.execute(
            """SELECT m.user_id, u.username, u.display_name, m.role, m.status, m.character_id,
                      COALESCE(m.absence_warnings, 0) as absence_warnings,
                      COALESCE(m.autopilot_consent, 0) as autopilot_consent
               FROM campaign_members m JOIN users u ON u.id=m.user_id
               WHERE m.campaign_id=?""",
            (campaign_id,),
        ).fetchall()

        # G21 (#802) — heartbeat: update last_seen for polling user
        conn.execute(
            "UPDATE campaign_members SET last_seen=datetime('now') WHERE campaign_id=? AND user_id=?",
            (campaign_id, uid),
        )
        conn.commit()
        accepted = [m for m in members if m["status"] == "accepted"]
        vote_kick_suggested = any(int(m["absence_warnings"]) >= 3 for m in accepted)
        return {
            "campaign_id": campaign_id,
            "title": camp["title"],
            "system_id": camp["system_id"],
            "round_timer_hours": camp["round_timer_hours"],
            "round_timer_minutes": int(camp["round_timer_minutes"]),
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
                    "absence_warnings": int(m["absence_warnings"]),
                    "autopilot_consent": bool(int(m["autopilot_consent"])),
                }
                for m in members
            ],
            "accepted_count": len(accepted),
            "vote_kick_suggested": vote_kick_suggested,
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
        invited_uid = int(target["id"])
        username = target["username"]
        camp_title_row = conn.execute("SELECT title FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
        camp_title = camp_title_row["title"] if camp_title_row else "kampanii"
    finally:
        conn.close()

    if invited_uid:
        threading.Thread(
            target=_send_invite_push,
            args=(invited_uid, camp_title),
            daemon=True,
        ).start()
    return {"invited": username, "status": "pending"}


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


class AcceptInviteReq(BaseModel):
    character_id: Optional[int] = None
    as_spectator: bool = False


@router.post("/multiplayer/campaigns/{campaign_id}/accept")
def accept_invite(
    campaign_id: int,
    body: AcceptInviteReq = AcceptInviteReq(),
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

        # G19 #800 — spectator path: role='spectator', no character required
        if body.as_spectator:
            conn.execute(
                "UPDATE campaign_members SET status='accepted', role='spectator', character_id=NULL "
                "WHERE campaign_id=? AND user_id=?",
                (campaign_id, uid),
            )
            conn.commit()
            return {"status": "accepted", "role": "spectator"}

        character_id = body.character_id
        if character_id is not None:
            # Validate character belongs to this user
            char = conn.execute(
                "SELECT id, sheet_json FROM characters WHERE id=? AND user_id=?",
                (character_id, uid),
            ).fetchone()
            if not char:
                raise HTTPException(status_code=400, detail="Character not found or doesn't belong to you")
            # Check not already in this campaign as a different member
            already = conn.execute(
                "SELECT 1 FROM campaign_members WHERE campaign_id=? AND character_id=? AND user_id!=?",
                (campaign_id, character_id, uid),
            ).fetchone()
            if already:
                raise HTTPException(status_code=409, detail="This character is already in this campaign under a different player")
            conn.execute(
                "UPDATE campaign_members SET status='accepted', character_id=? WHERE campaign_id=? AND user_id=?",
                (character_id, campaign_id, uid),
            )
            # Create per-campaign battle state row
            from app.services.campaign_state_service import create_initial_state
            import json as _json
            sheet = _json.loads(char["sheet_json"] or "{}")
            create_initial_state(conn, campaign_id=campaign_id, character_id=character_id, sheet=sheet)
        else:
            conn.execute(
                "UPDATE campaign_members SET status='accepted' WHERE campaign_id=? AND user_id=?",
                (campaign_id, uid),
            )
        camp = conn.execute(
            "SELECT title, lobby_status FROM campaigns WHERE id=?", (campaign_id,)
        ).fetchone()
        joining_name = conn.execute(
            "SELECT display_name, username FROM users WHERE id=?", (uid,)
        ).fetchone()
        # G12 #798 — mark late joiner for intro only when character is already selected
        if camp and camp["lobby_status"] == "started" and character_id is not None:
            conn.execute(
                "UPDATE campaign_members SET pending_intro=1 WHERE campaign_id=? AND user_id=?",
                (campaign_id, uid),
            )
        conn.commit()
        if camp and camp["lobby_status"] == "started" and joining_name:
            new_name = joining_name["display_name"] or joining_name["username"]
            from app.services.push_notification_service import send_push_to_campaign_players
            threading.Thread(
                target=send_push_to_campaign_players,
                args=(campaign_id, f"{new_name} dołączył!", f"{new_name} pojawia się w kampanii \"{camp['title']}\"."),
                kwargs={"url": "/", "exclude_user_id": uid},
                daemon=True,
            ).start()
        return {"status": "accepted"}
    finally:
        conn.close()


# G19 #800 — Spectator policy (host only)

class SpectatorPolicyReq(BaseModel):
    policy: str  # 'none' | 'watch' | 'watch_hint'


@router.patch("/multiplayer/campaigns/{campaign_id}/spectator-policy")
def set_spectator_policy(
    campaign_id: int,
    body: SpectatorPolicyReq,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    if body.policy not in ("none", "watch", "watch_hint"):
        raise HTTPException(status_code=400, detail="policy must be 'none', 'watch', or 'watch_hint'")
    conn = _db()
    try:
        camp = conn.execute(
            "SELECT host_user_id FROM campaigns WHERE id=? AND mode='multiplayer'",
            (campaign_id,),
        ).fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if camp["host_user_id"] != uid:
            raise HTTPException(status_code=403, detail="Only host can change spectator policy")
        conn.execute(
            "UPDATE campaigns SET spectator_policy=? WHERE id=?",
            (body.policy, campaign_id),
        )
        conn.commit()
        return {"spectator_policy": body.policy}
    finally:
        conn.close()


# G22 #803 — Autopilot consent (per-player opt-in for safe hold action on absence)

class AutopilotConsentReq(BaseModel):
    consent: bool


@router.patch("/multiplayer/campaigns/{campaign_id}/autopilot")
def set_autopilot_consent(
    campaign_id: int,
    body: AutopilotConsentReq,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
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
        conn.execute(
            "UPDATE campaign_members SET autopilot_consent=? WHERE campaign_id=? AND user_id=?",
            (1 if body.consent else 0, campaign_id, uid),
        )
        conn.commit()
        return {"autopilot_consent": body.consent}
    finally:
        conn.close()


# G19 #800 — Per-player spectator mute

class SpectatorMuteReq(BaseModel):
    spectator_user_id: int


@router.post("/multiplayer/campaigns/{campaign_id}/spectator-mute", status_code=201)
def mute_spectator(
    campaign_id: int,
    body: SpectatorMuteReq,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    conn = _db()
    try:
        player_ok = conn.execute(
            "SELECT 1 FROM campaign_members WHERE campaign_id=? AND user_id=? AND status='accepted' AND role!='spectator'",
            (campaign_id, uid),
        ).fetchone()
        if not player_ok:
            raise HTTPException(status_code=403, detail="Only active players can mute spectators")
        spectator_ok = conn.execute(
            "SELECT 1 FROM campaign_members WHERE campaign_id=? AND user_id=? AND status='accepted' AND role='spectator'",
            (campaign_id, body.spectator_user_id),
        ).fetchone()
        if not spectator_ok:
            raise HTTPException(status_code=404, detail="Spectator not found in this campaign")
        conn.execute(
            "INSERT OR IGNORE INTO campaign_spectator_mutes (campaign_id, user_id_player, user_id_spectator) VALUES (?, ?, ?)",
            (campaign_id, uid, body.spectator_user_id),
        )
        conn.commit()
        return {"muted": body.spectator_user_id}
    finally:
        conn.close()


@router.delete("/multiplayer/campaigns/{campaign_id}/spectator-mute/{spectator_user_id}")
def unmute_spectator(
    campaign_id: int,
    spectator_user_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    conn = _db()
    try:
        player_ok = conn.execute(
            "SELECT 1 FROM campaign_members WHERE campaign_id=? AND user_id=? AND status='accepted'",
            (campaign_id, uid),
        ).fetchone()
        if not player_ok:
            raise HTTPException(status_code=403, detail="Not a member of this campaign")
        conn.execute(
            "DELETE FROM campaign_spectator_mutes WHERE campaign_id=? AND user_id_player=? AND user_id_spectator=?",
            (campaign_id, uid, spectator_user_id),
        )
        conn.commit()
        return {"unmuted": spectator_user_id}
    finally:
        conn.close()


@router.post("/multiplayer/campaigns/{campaign_id}/leave")
def leave_multiplayer_campaign(
    campaign_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    return svc.leave_campaign(campaign_id, uid)


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
        _execute_kick(conn, campaign_id, target_user_id)
        return {"kicked": target_user_id}
    finally:
        conn.close()


def _execute_kick(conn: sqlite3.Connection, campaign_id: int, target_user_id: int) -> None:
    """#787 G3 — mark player as kicked, free their hero, clean up pending votes."""
    conn.execute(
        "UPDATE campaign_members SET status='kicked' WHERE campaign_id=? AND user_id=?",
        (campaign_id, target_user_id),
    )
    conn.execute(
        "UPDATE characters SET campaign_id=NULL, status='idle' WHERE campaign_id=? AND user_id=?",
        (campaign_id, target_user_id),
    )
    conn.execute(
        "DELETE FROM campaign_kick_votes WHERE campaign_id=? AND target_user_id=?",
        (campaign_id, target_user_id),
    )
    conn.commit()


class KickVoteReq(BaseModel):
    target_user_id: int


@router.post("/multiplayer/campaigns/{campaign_id}/kick-vote")
def vote_to_kick(
    campaign_id: int,
    body: KickVoteReq,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    conn = _db()
    try:
        camp = conn.execute(
            "SELECT host_user_id FROM campaigns WHERE id=? AND mode='multiplayer'",
            (campaign_id,),
        ).fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Campaign not found")

        host_id = camp["host_user_id"]

        if body.target_user_id == host_id:
            raise HTTPException(status_code=403, detail="Host cannot be kicked")

        if uid == body.target_user_id:
            raise HTTPException(status_code=400, detail="Cannot vote to kick yourself")

        voter_ok = conn.execute(
            "SELECT 1 FROM campaign_members WHERE campaign_id=? AND user_id=? AND status='accepted'",
            (campaign_id, uid),
        ).fetchone()
        if not voter_ok:
            raise HTTPException(status_code=403, detail="Not an active member of this campaign")

        target_ok = conn.execute(
            "SELECT 1 FROM campaign_members WHERE campaign_id=? AND user_id=? AND status='accepted'",
            (campaign_id, body.target_user_id),
        ).fetchone()
        if not target_ok:
            raise HTTPException(status_code=404, detail="Target player not found in this campaign")

        others_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM campaign_members "
            "WHERE campaign_id=? AND status='accepted' AND user_id!=?",
            (campaign_id, body.target_user_id),
        ).fetchone()["cnt"]

        # 2-person game: only host can kick, immediately
        if others_count == 1:
            if uid != host_id:
                raise HTTPException(status_code=403, detail="Only host can kick in a 2-player game")
            _execute_kick(conn, campaign_id, body.target_user_id)
            return {"kicked": True, "target_user_id": body.target_user_id, "votes": 1, "required": 1}

        conn.execute(
            "INSERT OR IGNORE INTO campaign_kick_votes "
            "(campaign_id, target_user_id, voter_user_id) VALUES (?, ?, ?)",
            (campaign_id, body.target_user_id, uid),
        )
        conn.commit()

        vote_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM campaign_kick_votes "
            "WHERE campaign_id=? AND target_user_id=?",
            (campaign_id, body.target_user_id),
        ).fetchone()["cnt"]

        required = (others_count // 2) + 1
        kicked = vote_count >= required

        if kicked:
            _execute_kick(conn, campaign_id, body.target_user_id)

        return {
            "kicked": kicked,
            "target_user_id": body.target_user_id,
            "votes": vote_count,
            "required": required,
        }
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
            "SELECT host_user_id, lobby_status, title, COALESCE(gm_plan_json, '{}') as gm_plan_json FROM campaigns WHERE id=? AND mode='multiplayer'",
            (campaign_id,),
        ).fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Lobby not found")
        if camp["host_user_id"] != uid:
            raise HTTPException(status_code=403, detail="Only host can start")
        if camp["lobby_status"] != "open":
            raise HTTPException(status_code=400, detail="Already started")

        members = conn.execute(
            """SELECT u.display_name, u.username, c.name as char_name, c.sheet_json
               FROM campaign_members m
               JOIN users u ON u.id = m.user_id
               LEFT JOIN characters c ON c.id = m.character_id
               WHERE m.campaign_id=? AND m.status='accepted'""",
            (campaign_id,),
        ).fetchall()

        party_info = []
        for r in members:
            char_name = r["char_name"] or (r["display_name"] or r["username"])
            archetype, level = "", 1
            try:
                if r["sheet_json"]:
                    sheet = json.loads(r["sheet_json"])
                    archetype = sheet.get("archetype", "")
                    level = sheet.get("level", 1)
            except Exception:
                pass
            desc = char_name
            if archetype:
                desc += f" ({archetype}, poz. {level})"
            party_info.append(desc)

        player_names = [(r["display_name"] or r["username"]) for r in members]

        conn.execute(
            "UPDATE campaigns SET lobby_status='started' WHERE id=?", (campaign_id,)
        )
        # Reserve round 1 immediately (status='done', narrative_json=NULL).
        # Frontend polls status → sees 'done' → waits for narration.
        # LLM thread fills in narrative_json when ready.
        conn.execute(
            "INSERT OR IGNORE INTO campaign_rounds (campaign_id, round_number, status) VALUES (?, 1, 'done')",
            (campaign_id,),
        )
        opening_round = conn.execute(
            "SELECT id FROM campaign_rounds WHERE campaign_id=? AND round_number=1",
            (campaign_id,),
        ).fetchone()
        opening_round_id = int(opening_round["id"])
        conn.commit()

        threading.Thread(
            target=_narrate_opening,
            args=(campaign_id, opening_round_id, camp["title"], party_info, camp["gm_plan_json"]),
            daemon=True,
        ).start()

        from app.services.push_notification_service import send_push_to_campaign_players
        threading.Thread(
            target=send_push_to_campaign_players,
            args=(campaign_id, "Gra rozpoczęta! 🎲", f'Kampania "{camp["title"]}" ruszyła. Czas na przygodę!'),
            kwargs={"url": "/"},
            daemon=True,
        ).start()

        return {"campaign_id": campaign_id, "lobby_status": "started", "players": len(player_names)}
    finally:
        conn.close()


_OPENING_SYSTEM = (
    "Jesteś Mistrzem Gry w tekstowej grze RPG osadzonej w mrocznym świecie fantasy. "
    "Odpowiadasz WYŁĄCZNIE po polsku. Narruj w TRZECIEJ osobie. "
    'Odpowiedź MUSI być poprawnym JSON: {"narrative": "narracja otwierająca"}'
)


def _narrate_opening(campaign_id: int, round_id: int, title: str, players: list, gm_plan_json: str = "{}") -> None:
    from app.services import llm_service

    names = ", ".join(players) if players else "bohater"

    # Extract first-arc premise from pre-built template plan
    premise = ""
    try:
        plan = json.loads(gm_plan_json) if gm_plan_json and gm_plan_json.strip() not in ("", "{}") else {}
        arcs = plan.get("arcs") or []
        if arcs:
            first = arcs[0]
            premise = first.get("premise") or first.get("title") or ""
    except Exception:
        pass

    user_msg = (
        f"Kampania: {title}\n"
        f"Drużyna: {names}\n"
    )
    if premise:
        user_msg += f"Prolog przygody: {premise}\n"
    user_msg += (
        "\nNapisz narrację otwierającą sesję RPG (3-4 zdania). "
        "Opisz mroczne miejsce gdzie drużyna się znajduje — karczmę, ruiny, las, lochy — "
        "i nastrój sceny. Zaintryguj graczy, zasugeruj nadchodzące niebezpieczeństwo lub tajemnicę. "
        "Nie zadawaj pytań graczom — to opis sceny otwierającej."
    )
    try:
        cfg = llm_service.get_effective_config()
        provider = cfg["provider"]
        if provider == "openai":
            driver = llm_service.OpenAIDriver()
        elif provider == "azure":
            driver = llm_service.AzureDriver()
        else:
            driver = llm_service.OllamaDriver()
        raw = driver.generate_chat(
            base_url=cfg["base_url"],
            model=cfg["model"],
            messages=[
                {"role": "system", "content": _OPENING_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            api_key=cfg.get("api_key", ""),
        )
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(clean)
    except Exception as e:
        logger.error("opening_narration_failed", campaign_id=campaign_id, error=str(e)[:200])
        parsed = {"narrative": "Przygoda się zaczyna. Mroczny świat czeka na bohaterów."}

    conn = _db()
    try:
        conn.execute(
            "UPDATE campaign_rounds SET narrative_json=?, closed_at=datetime('now') WHERE id=?",
            (json.dumps(parsed, ensure_ascii=False), round_id),
        )
        conn.commit()
    finally:
        conn.close()
    logger.info("opening_narration_done", campaign_id=campaign_id)


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
    client_action_id: Optional[str] = None


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
        client_action_id=body.client_action_id,
    )

    if result.get("just_transitioned"):
        threading.Thread(
            target=svc.trigger_narration,
            args=(result["round_id"],),
            daemon=True,
        ).start()

    return result


@router.delete("/campaigns/{campaign_id}/round/action")
def withdraw_round_action(
    campaign_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    """G24 (#805) — player withdraws (deletes) their action from the current collecting round."""
    uid = resolve_authed_user_id(authorization, user_id)
    result = svc.withdraw_action(campaign_id=campaign_id, user_id=uid)
    if result.get("error") == "round_closed":
        raise HTTPException(status_code=409, detail=result["detail"])
    if result.get("error") == "no_active_round":
        raise HTTPException(status_code=404, detail=result["detail"])
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


@router.get("/campaigns/{campaign_id}/rounds/history")
def get_rounds_history(
    campaign_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    rounds = svc.get_rounds_history(campaign_id, uid)
    return {"rounds": rounds}


# ── G11 #797 — Catch-up po powrocie ──────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/catchup")
def get_catchup(
    campaign_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    return svc.get_catchup(campaign_id, uid)


# ── G23 #804 — Away recap (pętla zaangażowania) ───────────────────────────────

@router.get("/campaigns/{campaign_id}/away-recap")
def get_away_recap(
    campaign_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    return svc.get_away_recap(campaign_id, uid)


# ── G6 #790 — Party hex-move voting ───────────────────────────────────────────

class MoveVoteReq(BaseModel):
    target_q: int
    target_r: int


@router.post("/campaigns/{campaign_id}/move-vote")
def submit_move_vote(
    campaign_id: int,
    body: MoveVoteReq,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    return svc.submit_move_vote(campaign_id, uid, body.target_q, body.target_r)


@router.get("/campaigns/{campaign_id}/move-vote")
def get_move_vote_status(
    campaign_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    resolve_authed_user_id(authorization, user_id)
    return svc.get_move_vote_status(campaign_id)


# ── G7 (#791) — MP Combat endpoints ─────────────────────────────────────────


class MpCombatStartReq(BaseModel):
    enemy_keys: list


class MpCombatActionReq(BaseModel):
    action_type: str  # 'attack' | 'spell' | 'defense'
    character_id: int
    target_id: Optional[str] = None
    spell_key: Optional[str] = None
    raw_d20: Optional[int] = None
    roll_result: Optional[int] = None


@router.post("/campaigns/{campaign_id}/combat/start")
def start_mp_combat(
    campaign_id: int,
    body: MpCombatStartReq,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    """G7 (#791) — Start sequential MP combat for all campaign members."""
    uid = resolve_authed_user_id(authorization, user_id)
    try:
        return svc.start_mp_combat(campaign_id, body.enemy_keys)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/campaigns/{campaign_id}/combat/action")
def submit_mp_combat_action(
    campaign_id: int,
    body: MpCombatActionReq,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    """G7 (#791) — Player submits combat action (attack/spell/defense). Enemies auto-resolve after."""
    uid = resolve_authed_user_id(authorization, user_id)
    try:
        return svc.submit_mp_combat_action(
            campaign_id=campaign_id,
            user_id=uid,
            character_id=body.character_id,
            action_type=body.action_type,
            target_id=body.target_id,
            spell_key=body.spell_key,
            raw_d20=body.raw_d20,
            roll_result=body.roll_result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
