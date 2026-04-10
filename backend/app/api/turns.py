from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.turn_engine import run_narrative_turn
from app.services.commands_service import execute_command_logic, is_command

router = APIRouter()


class TurnRequest(BaseModel):
    character_id: int
    text: str
    system: str | None = None
    engine: str | None = None
    game_id: int | None = None


@router.post("/campaigns/{campaign_id}/turns")
def create_turn(campaign_id: int, req: TurnRequest):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text required")

    if is_command(text):
        try:
            result = execute_command_logic(req.character_id, text)
            return {
                "route": "command",
                **result.payload,
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))

    return run_narrative_turn(
        campaign_id=campaign_id,
        character_id=req.character_id,
        text=text,
        system=req.system,
        engine=req.engine,
        game_id=req.game_id,
    )