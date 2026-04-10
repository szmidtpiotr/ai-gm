from fastapi import APIRouter, HTTPException
import httpx
import os

router = APIRouter()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "10"))


@router.get("/models")
async def list_models():
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = data.get("models", []) or []
            return [
                {"name": m.get("name"), "size": m.get("size", 0)}
                for m in models if m.get("name")
            ]
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama models fetch failed: {str(e)}"
        )