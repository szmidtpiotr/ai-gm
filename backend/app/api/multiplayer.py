"""Multiplayer round API — submit actions, poll status, fetch narration."""

import threading
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.core.jwt_auth import resolve_authed_user_id
from app.core.logging import get_logger
from app.services import multiplayer_round_service as svc

router = APIRouter(tags=["multiplayer"])
logger = get_logger(__name__)


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
        round_id = result["round_id"]
        threading.Thread(
            target=svc.trigger_narration,
            args=(round_id,),
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
