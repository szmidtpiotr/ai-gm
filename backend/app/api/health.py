from fastapi import APIRouter, Request
import os
import httpx

router = APIRouter()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "10"))


@router.get("/health")
async def health(request: Request):
    ollama_base_url = request.headers.get("X-Ollama-Base-Url", OLLAMA_BASE_URL)

    ollama = {
        "reachable": False,
        "base_url": ollama_base_url,
        "model_count": 0,
        "models": [],
    }

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            resp = await client.get(f"{ollama_base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = data.get("models", []) or []

        ollama = {
            "reachable": True,
            "base_url": ollama_base_url,
            "model_count": len(models),
            "models": [m.get("name") for m in models if m.get("name")],
        }
    except Exception as e:
        ollama["error"] = str(e)

    return {
        "status": "ok",
        "ollama": ollama,
    }