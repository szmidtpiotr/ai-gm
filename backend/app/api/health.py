from fastapi import APIRouter

from app.services.llm_service import get_health

router = APIRouter()

@router.get("/health")
async def health():
    llm = get_health()
    return {
        "status": "ok",
        "llm": llm,
        # Backward-compatible key used by existing frontend code.
        "ollama": llm,
    }