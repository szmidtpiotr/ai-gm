from fastapi import APIRouter, HTTPException, Query

from app.services.llm_service import get_health
from app.services.user_llm_settings import get_user_llm_settings_full

router = APIRouter()


def _curate_narration_models(provider: str, models: list[str]) -> list[str]:
    if not models:
        return []

    preferred_openai_order = [
        "OpenEuro-Polish",
        "gpt-4o",
        "gpt-4.1",
        "claude-sonnet-4-5",
        "claude-sonnet-4",
        "gemini-2.5-pro",
        "mistral-large-latest",
        "qwen-max",
        "qwen3-32b",
        "llama-3.3-70b-instruct",
    ]
    if provider == "openai":
        lower_map = {m.lower(): m for m in models}
        curated: list[str] = []
        for preferred in preferred_openai_order:
            key = preferred.lower()
            if key in lower_map and lower_map[key] not in curated:
                curated.append(lower_map[key])
        keyword_hits = [
            m
            for m in models
            if any(
                kw in m.lower()
                for kw in ("polish", "openeuro", "gpt-4o", "gpt-4.1", "claude-sonnet", "gemini-2.5-pro")
            )
        ]
        for m in keyword_hits:
            if m not in curated:
                curated.append(m)
        return curated[:20] if curated else models[:20]

    # For Ollama keep raw model list as-is (no curation/filtering).
    return models


@router.get("/models")
async def list_models(show_all: bool = Query(default=False), user_id: int | None = Query(default=None)):
    try:
        llm = get_health(get_user_llm_settings_full(user_id) if user_id else None)
        provider = str(llm.get("provider") or "ollama").lower()
        model_names = llm.get("models") or []
        if not model_names and llm.get("model"):
            model_names = [llm["model"]]
        clean_names = [name for name in model_names if name]
        if show_all:
            curated = clean_names
        else:
            curated = _curate_narration_models(provider, clean_names)
        return [{"name": name, "size": 0} for name in curated]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Models fetch failed: {str(e)}")
