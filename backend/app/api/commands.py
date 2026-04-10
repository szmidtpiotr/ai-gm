from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.commands_service import execute_command_logic

router = APIRouter()


class CommandRequest(BaseModel):
    character_id: int
    text: str


@router.post("/commands/execute")
def execute_command(req: CommandRequest):
    try:
        result = execute_command_logic(req.character_id, req.text)
        return result.payload
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))