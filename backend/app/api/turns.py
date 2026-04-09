from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.commands_service import is_command, run_command

router = APIRouter(prefix="/api/campaigns", tags=["turns"])


class TurnRequest(BaseModel):
    character_id: int
    text: str
    system: str | None = None
    engine: str | None = None
    game_id: int | None = None


@router.post("/{campaign_id}/turns")
def create_turn(campaign_id: int, req: TurnRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    if is_command(text):
        result = run_command(db=db, character_id=req.character_id, text=text)
        if not result.ok:
            raise HTTPException(status_code=400, detail=result.error)
        return {
            "route": result.route,
            "command": result.command,
            "result": result.result,
        }

    return {
        "route": "narrative",
        "result": {
            "message": "LLM narrative path not implemented yet",
            "campaign_id": campaign_id,
            "character_id": req.character_id,
            "text": text,
            "system": req.system,
            "engine": req.engine,
            "game_id": req.game_id,
        },
    }