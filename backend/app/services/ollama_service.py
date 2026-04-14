import json
import os
import time
from typing import Generator

import httpx

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))


def resolve_ollama_base_url(base_url: str | None = None) -> str:
    value = (base_url or "").strip()
    return value or OLLAMA_BASE_URL


def generatechat(model: str, messages: list[dict], base_url: str | None = None, llm_params: dict | None = None) -> str:
    params = llm_params or {}
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": params.get("temperature", 0.8),
            "top_p": params.get("top_p", 0.9),
            "top_k": params.get("top_k", 40),
            "repeat_penalty": params.get("repeat_penalty", 1.1),
            "num_predict": params.get("max_tokens", 512),
        },
    }

    ollama_base_url = resolve_ollama_base_url(base_url)
    t_start = time.time()

    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            resp = client.post(f"{ollama_base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = (data.get("message") or {}).get("content", "").strip()
            if not content:
                raise RuntimeError("Ollama returned empty content")

        duration = round(time.time() - t_start, 2)
        _log_llm_io(model=model, messages=messages, response=content, duration=duration)
        return content
    except httpx.TimeoutException as e:
        raise RuntimeError(f"Ollama timeout: {e}") from e
    except httpx.HTTPStatusError as e:
        detail = e.response.text if e.response is not None else str(e)
        raise RuntimeError(f"Ollama HTTP error: {detail}") from e
    except httpx.RequestError as e:
        raise RuntimeError(f"Ollama connection error: {e}") from e


def generatechat_stream(
    model: str, messages: list[dict], base_url: str | None = None, llm_params: dict | None = None
) -> Generator[str, None, None]:
    """
    Streams the LLM response token by token as Server-Sent Events (SSE).
    Yields SSE-formatted strings: 'data: <token>\\n\\n'
    Sends 'data: [DONE]\\n\\n' when finished.
    """
    params = llm_params or {}
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": params.get("temperature", 0.8),
            "top_p": params.get("top_p", 0.9),
            "top_k": params.get("top_k", 40),
            "repeat_penalty": params.get("repeat_penalty", 1.1),
            "num_predict": params.get("max_tokens", 512),
        },
    }

    ollama_base_url = resolve_ollama_base_url(base_url)
    t_start = time.time()
    collected_tokens: list[str] = []

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
                        collected_tokens.append(token)
                        safe = token.replace("\n", "\\n")
                        yield f"data: {safe}\n\n"
                    if chunk.get("done"):
                        break

        full_response = "".join(collected_tokens)
        duration = round(time.time() - t_start, 2)
        _log_llm_io(model=model, messages=messages, response=full_response, duration=duration)
        yield "data: [DONE]\n\n"
    except httpx.TimeoutException as e:
        yield f"data: [ERROR] Ollama timeout: {e}\n\n"
    except httpx.HTTPStatusError as e:
        detail = e.response.text if e.response is not None else str(e)
        yield f"data: [ERROR] Ollama HTTP error: {detail}\n\n"
    except httpx.RequestError as e:
        yield f"data: [ERROR] Ollama connection error: {e}\n\n"


def _log_llm_io(model: str, messages: list[dict], response: str, duration: float) -> None:
    """
    Appends one JSON line to /data/llm_log.jsonl for later analysis.
    Format: {timestamp, model, input_tokens_approx, output_tokens_approx, duration_sec, response_preview}
    """
    try:
        log_path = os.getenv("LLM_LOG_PATH", "/data/llm_log.jsonl")
        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "model": model,
            "input_chars": prompt_chars,
            "output_chars": len(response),
            "duration_sec": duration,
            "response_preview": response[:120].replace("\n", " "),
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Never crash the game over a logging failure
