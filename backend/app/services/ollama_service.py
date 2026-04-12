import os
import httpx

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))


def resolve_ollama_base_url(base_url: str | None = None) -> str:
    value = (base_url or "").strip()
    return value or OLLAMA_BASE_URL


def generatechat(model: str, messages: list[dict], base_url: str | None = None) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }

    ollama_base_url = resolve_ollama_base_url(base_url)

    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            resp = client.post(f"{ollama_base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = (data.get("message") or {}).get("content", "").strip()
            if not content:
                raise RuntimeError("Ollama returned empty content")
            return content
    except httpx.TimeoutException as e:
        raise RuntimeError(f"Ollama timeout: {e}") from e
    except httpx.HTTPStatusError as e:
        detail = e.response.text if e.response is not None else str(e)
        raise RuntimeError(f"Ollama HTTP error: {detail}") from e
    except httpx.RequestError as e:
        raise RuntimeError(f"Ollama connection error: {e}") from e