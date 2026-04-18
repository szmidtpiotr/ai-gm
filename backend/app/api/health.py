from typing import Any

import httpx
from fastapi import APIRouter, Query

from app.services.llm_service import get_health
from app.services.loki_settings import get_effective_loki_base, get_stored_loki_url
from app.services.user_llm_settings import get_user_llm_settings_full

router = APIRouter()


async def _loki_health() -> dict[str, Any]:
    """
    Probe Loki HTTP `/ready` using URL from SQLite (game_config_meta) or LOKI_URL env.
    """
    raw = get_effective_loki_base()
    if not raw:
        return {"configured": False, "reachable": None}
    base = raw.rstrip("/")
    src = "db" if get_stored_loki_url() else "env"
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            resp = await client.get(f"{base}/ready")
        ok = resp.status_code == 200
        out: dict[str, Any] = {
            "configured": True,
            "reachable": ok,
            "url": base,
            "source": src,
        }
        if not ok:
            out["http_status"] = resp.status_code
        return out
    except Exception as exc:
        return {
            "configured": True,
            "reachable": False,
            "url": base,
            "source": src,
            "error": str(exc),
        }


@router.get("/health")
async def health(user_id: int | None = Query(default=None)):
    llm = get_health(get_user_llm_settings_full(user_id) if user_id else None)
    loki = await _loki_health()
    return {
        "status": "ok",
        "llm": llm,
        # Backward-compatible key used by existing frontend code.
        "ollama": llm,
        "loki": loki,
    }