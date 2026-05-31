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
        cur = conn.execute(
            """INSERT INTO campaigns
               (title, system_id, owner_user_id, mode, status,
                round_timer_hours, round_timer_minutes, max_players, host_user_id, lobby_status)
               VALUES (?, ?, ?, 'multiplayer', 'active', ?, ?, ?, ?, 'open')""",
            (body.title.strip(), body.system_id, uid,
             max(1, body.round_timer_minutes // 60), body.round_timer_minutes,
             body.max_players, uid),
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
        camp = conn.execute(
            "SELECT title, lobby_status FROM campaigns WHERE id=?", (campaign_id,)
        ).fetchone()
        joining_name = conn.execute(
            "SELECT display_name, username FROM users WHERE id=?", (uid,)
        ).fetchone()
        existing = conn.execute(
            """SELECT u.display_name, u.username FROM campaign_members m
               JOIN users u ON u.id = m.user_id
               WHERE m.campaign_id=? AND m.user_id!=? AND m.status='accepted'""",
            (campaign_id, uid),
        ).fetchall()
        conn.commit()
        # Fire arrival narration if joining a started campaign
        if camp and camp["lobby_status"] == "started" and joining_name:
            new_name = joining_name["display_name"] or joining_name["username"]
            existing_names = [(r["display_name"] or r["username"]) for r in existing]
            campaign_title = camp["title"]
            threading.Thread(
                target=_narrate_arrival,
                args=(campaign_id, new_name, existing_names, campaign_title),
                daemon=True,
            ).start()
        return {"status": "accepted"}
    finally:
        conn.close()


_ARRIVAL_SYSTEM = (
    "Jesteś Mistrzem Gry w tekstowej grze RPG osadzonej w mrocznym świecie fantasy. "
    "Odpowiadasz WYŁĄCZNIE po polsku. Narruj w TRZECIEJ osobie. "
    'Odpowiedź MUSI być poprawnym JSON: {"narrative": "narracja przybycia postaci"}'
)


def _narrate_arrival(campaign_id: int, new_player: str, existing: list, title: str) -> None:
    from app.services import llm_service

    others = ", ".join(existing) if existing else "grupą podróżnych"
    user_msg = (
        f"Kampania: {title}\n"
        f"Drużyna w grze: {others}\n"
        f"Dołącza nowy gracz: {new_player}\n\n"
        "Napisz krótką narrację (2-3 zdania) opisującą jak ta postać dołącza do drużyny — "
        "przypadkowe spotkanie na drodze, w karczmie, otwarcie celi więziennej, wspólna ucieczka itp. "
        "Narruj naturalnie, jakby to był zbieg okoliczności lub przeznaczenie."
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
                {"role": "system", "content": _ARRIVAL_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            api_key=cfg.get("api_key", ""),
        )
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(clean)
    except Exception as e:
        logger.error("arrival_narration_failed", campaign_id=campaign_id, error=str(e)[:200])
        parsed = {"narrative": f"{new_player} dołącza do drużyny, gotowy na nadchodzące przygody."}

    conn = _db()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO campaign_rounds (campaign_id, round_number, status, narrative_json, closed_at)
               VALUES (?, (SELECT COALESCE(MAX(round_number), 0)+1 FROM campaign_rounds WHERE campaign_id=?),
                       'done', ?, datetime('now'))""",
            (campaign_id, campaign_id, json.dumps(parsed, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()
    logger.info("arrival_narration_done", campaign_id=campaign_id, new_player=new_player)


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
            "SELECT host_user_id, lobby_status, title FROM campaigns WHERE id=? AND mode='multiplayer'",
            (campaign_id,),
        ).fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Lobby not found")
        if camp["host_user_id"] != uid:
            raise HTTPException(status_code=403, detail="Only host can start")
        if camp["lobby_status"] != "open":
            raise HTTPException(status_code=400, detail="Already started")

        players = conn.execute(
            """SELECT u.display_name, u.username FROM campaign_members m
               JOIN users u ON u.id = m.user_id
               WHERE m.campaign_id=? AND m.status='accepted'""",
            (campaign_id,),
        ).fetchall()
        player_names = [(r["display_name"] or r["username"]) for r in players]

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
            args=(campaign_id, opening_round_id, camp["title"], player_names),
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


def _narrate_opening(campaign_id: int, round_id: int, title: str, players: list) -> None:
    from app.services import llm_service

    names = ", ".join(players) if players else "bohater"
    user_msg = (
        f"Kampania: {title}\n"
        f"Drużyna: {names}\n\n"
        "Napisz narrację otwierającą sesję RPG (3-4 zdania). "
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

    if result.get("just_transitioned"):
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


@router.get("/campaigns/{campaign_id}/rounds/history")
def get_rounds_history(
    campaign_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
):
    uid = resolve_authed_user_id(authorization, user_id)
    rounds = svc.get_rounds_history(campaign_id, uid)
    return {"rounds": rounds}
