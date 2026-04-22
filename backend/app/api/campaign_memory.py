"""POST /mem — odpowiedzi z campaign_ai_summaries bez wpływu na narrację (route=memory)."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.turns import (
    create_turn_log,
    get_campaign_or_404,
    get_db,
    log_memory_turn_structured,
)
from app.services.client_ui_config import is_slash_command_enabled
from app.services.memory_qa_service import answer_from_summaries

router = APIRouter()


class MemoryAskBody(BaseModel):
    character_id: int = Field(..., ge=1)
    question: str = Field(..., min_length=1)
    """Treść pytania (bez prefiksu /mem)."""
    user_line: str | None = Field(
        default=None,
        description="Pełna linia z czatu (np. '/mem Kto był w karczmie?') do zapisu w turze.",
    )


@router.post("/campaigns/{campaign_id}/memory/ask")
def post_memory_ask(
    campaign_id: int,
    body: MemoryAskBody,
    user_id: int = Query(..., description="Właściciel kampanii — spójnie z LLM."),
):
    if not is_slash_command_enabled("/mem [pytanie]"):
        raise HTTPException(
            status_code=403,
            detail="Komenda /mem jest wyłączona przez administratora.",
        )

    conn = get_db()
    try:
        camp = get_campaign_or_404(conn, campaign_id)
        if int(camp["owner_user_id"]) != int(user_id):
            raise HTTPException(status_code=403, detail="user_id must match campaign owner")
    finally:
        conn.close()

    try:
        out = answer_from_summaries(
            campaign_id=campaign_id,
            user_id=user_id,
            question=body.question.strip(),
            model=str(camp["model_id"] or "").strip() or None,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None
    except Exception as e:
        # JSON decode, bugs, etc. — always return JSON detail (avoids generic HTTP 500 + empty body)
        raise HTTPException(status_code=502, detail=f"Memory QA failed: {e}") from None

    user_text = (body.user_line or "").strip() or f"/mem {body.question.strip()}"

    conn = get_db()
    try:
        # Sprawdź, że postać należy do kampanii
        ch = conn.execute(
            "SELECT id FROM characters WHERE id = ? AND campaign_id = ?",
            (body.character_id, campaign_id),
        ).fetchone()
        if not ch:
            raise HTTPException(status_code=404, detail="Character not found in this campaign")

        log = create_turn_log(
            conn=conn,
            campaign_id=campaign_id,
            character_id=body.character_id,
            user_text=user_text,
            assistant_text=out["answer"],
            route="memory",
        )
        log_memory_turn_structured(
            campaign_id=campaign_id,
            character_id=body.character_id,
            turn_row=log,
            user_text=user_text,
            assistant_text=out["answer"],
        )
    finally:
        conn.close()

    return {
        "answer": out["answer"],
        "source": out.get("source"),
        "used_llm": out.get("used_llm", False),
        "id": log["id"],
        "campaign_id": campaign_id,
        "turn_number": log["turn_number"],
        "created_at": log["created_at"],
        "route": "memory",
    }
