"""POST /helpme — doradca OOC; zapis route=helpme (poza kontekstem narracyjnym)."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.turns import (
    create_turn_log,
    get_campaign_or_404,
    get_character_or_404,
    get_db,
    resolve_model_name,
)
from app.services.helpme_advisor_service import run_helpme_advisor
from app.services.user_llm_settings import get_user_llm_settings_full

router = APIRouter()


class HelpmeBody(BaseModel):
    character_id: int = Field(..., ge=1)
    """Opcjonalne pytanie (bez prefiksu /helpme)."""
    topic: str = Field(default="", max_length=8000)
    user_line: str | None = Field(
        default=None,
        description="Pełna linia z czatu (np. '/helpme Co mogę zrobić?') do zapisu w turze.",
    )


@router.post("/campaigns/{campaign_id}/helpme")
def post_helpme(
    campaign_id: int,
    body: HelpmeBody,
    user_id: int = Query(..., description="Właściciel kampanii — spójnie z LLM."),
):
    conn = get_db()
    try:
        camp = get_campaign_or_404(conn, campaign_id)
        if str(camp["status"] or "").lower() == "ended":
            raise HTTPException(status_code=410, detail="This campaign has ended.")
        if int(camp["owner_user_id"]) != int(user_id):
            raise HTTPException(status_code=403, detail="user_id must match campaign owner")
        character = get_character_or_404(conn, campaign_id, body.character_id)
        llm_config = get_user_llm_settings_full(user_id)
        model = resolve_model_name(
            requested_model=None,
            campaign_model=camp["model_id"],
            llm_config=llm_config,
        )

        try:
            out = run_helpme_advisor(
                conn=conn,
                campaign=camp,
                character=character,
                topic=body.topic.strip(),
                user_id=user_id,
                model=model,
            )
        except RuntimeError as e:
            if str(e) == "empty_helpme_response":
                raise HTTPException(status_code=502, detail="Empty /helpme response") from None
            raise HTTPException(status_code=502, detail=str(e)) from None

        msg = (out.get("message") or "").strip()
        user_text = (body.user_line or "").strip()
        if not user_text:
            t = (body.topic or "").strip()
            user_text = f"/helpme {t}".strip() if t else "/helpme"

        log = create_turn_log(
            conn=conn,
            campaign_id=campaign_id,
            character_id=body.character_id,
            user_text=user_text,
            assistant_text=msg,
            route="helpme",
        )
        return {
            "answer": msg,
            "id": log["id"],
            "campaign_id": campaign_id,
            "turn_number": log["turn_number"],
            "created_at": log["created_at"],
            "route": "helpme",
            "ooc": True,
        }
    finally:
        conn.close()
