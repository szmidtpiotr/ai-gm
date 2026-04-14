import json
import os
from typing import Generator

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


def generatechat_stream(
    model: str, messages: list[dict], base_url: str | None = None
) -> Generator[str, None, None]:
    """
    Streams the LLM response token by token as Server-Sent Events (SSE).
    Yields SSE-formatted strings: 'data: <token>\\n\\n'
    Sends 'data: [DONE]\\n\\n' when finished.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    ollama_base_url = resolve_ollama_base_url(base_url)

    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            with client.stream("POST", f"{ollama_base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = (chunk.get("message") or {}).get("content", "")
                    if token:
                        # Escape newlines so SSE stays valid
                        safe = token.replace("\n", "\\n")
                        yield f"data: {safe}\n\n"
                    if chunk.get("done"):
                        break
        yield "data: [DONE]\n\n"
    except httpx.TimeoutException as e:
        yield f"data: [ERROR] Ollama timeout: {e}\n\n"
    except httpx.HTTPStatusError as e:
        detail = e.response.text if e.response is not None else str(e)
        yield f"data: [ERROR] Ollama HTTP error: {detail}\n\n"
    except httpx.RequestError as e:
        yield f"data: [ERROR] Ollama connection error: {e}\n\n"
