from fastapi import APIRouter, Query

from app.services.llm_service import get_health
from app.services.user_llm_settings import get_user_llm_settings_full

router = APIRouter()

@router.get("/health")
async def health(user_id: int | None = Query(default=None)):
    llm = get_health(get_user_llm_settings_full(user_id) if user_id else None)
    return {
        "status": "ok",
        "llm": llm,
        # Backward-compatible key used by existing frontend code.
        "ollama": llm,
    }