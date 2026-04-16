import os
import re
import json
from typing import Any, Generator

import httpx

_runtime_config: dict[str, str] = {
    "provider": "",
    "base_url": "",
    "model": "",
    "api_key": "",
}


def set_runtime_config(provider: str, base_url: str, model: str, api_key: str) -> None:
    _runtime_config["provider"] = (provider or "").strip().lower()
    _runtime_config["base_url"] = (base_url or "").strip()
    _runtime_config["model"] = (model or "").strip()
    _runtime_config["api_key"] = (api_key or "").strip()


def get_runtime_config(mask_api_key: bool = False) -> dict[str, str]:
    api_key = _runtime_config["api_key"]
    if mask_api_key and api_key:
        shown = f"{api_key[:6]}..." if len(api_key) > 6 else f"{api_key}..."
    else:
        shown = api_key
    return {
        "provider": _runtime_config["provider"],
        "base_url": _runtime_config["base_url"],
        "model": _runtime_config["model"],
        "api_key": shown,
    }


def get_effective_config() -> dict[str, str]:
    provider = _runtime_config["provider"] or os.getenv("LLM_PROVIDER", "ollama")
    base_url = _runtime_config["base_url"] or os.getenv("LLM_BASE_URL", "http://localhost:11434")
    model = _runtime_config["model"] or os.getenv("LLM_MODEL", "gemma4:e4b")
    api_key = _runtime_config["api_key"] or os.getenv("LLM_API_KEY", "")
    normalized_provider = provider.strip().lower()
    return {
        "provider": normalized_provider,
        "base_url": _normalize_base_url(base_url.strip(), normalized_provider),
        "model": model.strip(),
        "api_key": api_key.strip(),
    }


def _build_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _normalize_base_url(base_url: str, provider: str) -> str:
    value = (base_url or "").strip().rstrip("/")
    if not value:
        return value
    if provider == "openai":
        value = re.sub(r"/v1/chat/completions/?$", "", value, flags=re.I)
        value = re.sub(r"/chat/completions/?$", "", value, flags=re.I)
        value = re.sub(r"/v1/models/?$", "", value, flags=re.I)
        value = re.sub(r"/v1/?$", "", value, flags=re.I)
    elif provider == "ollama":
        value = re.sub(r"/api/chat/?$", "", value, flags=re.I)
        value = re.sub(r"/api/tags/?$", "", value, flags=re.I)
        value = re.sub(r"/api/?$", "", value, flags=re.I)
    return value.rstrip("/")


class OllamaDriver:
    @staticmethod
    def generate_chat(base_url: str, model: str, messages: list[dict], api_key: str) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.8, "top_k": 40},
        }
        with httpx.Client(timeout=float(os.getenv("OLLAMA_TIMEOUT", "120"))) as client:
            resp = client.post(
                f"{base_url}/api/chat",
                json=payload,
                headers=_build_headers(api_key),
            )
            resp.raise_for_status()
            data = resp.json()
        content = ((data.get("message") or {}).get("content") or "").strip()
        if not content:
            raise RuntimeError("LLM returned empty response")
        return content

    @staticmethod
    def generate_stream(base_url: str, model: str, messages: list[dict], api_key: str) -> Generator[str, None, None]:
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": 0.8, "top_k": 40},
        }
        try:
            with httpx.Client(timeout=float(os.getenv("OLLAMA_TIMEOUT", "120"))) as client:
                with client.stream(
                    "POST",
                    f"{base_url}/api/chat",
                    json=payload,
                    headers=_build_headers(api_key),
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except Exception:
                            continue
                        token = ((chunk.get("message") or {}).get("content") or "")
                        if token:
                            yield f"data: {token.replace(chr(10), '\\n')}\n\n"
                        if chunk.get("done"):
                            break
            yield "data: [DONE]\n\n"
        except httpx.TimeoutException as exc:
            yield f"data: [ERROR] LLM timeout: {exc}\n\n"
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            yield f"data: [ERROR] LLM HTTP error: {detail}\n\n"
        except httpx.RequestError as exc:
            yield f"data: [ERROR] LLM connection error: {exc}\n\n"

    @staticmethod
    def health(base_url: str, api_key: str) -> dict[str, Any]:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{base_url}/api/tags", headers=_build_headers(api_key))
            resp.raise_for_status()
            data = resp.json()
        models = [m.get("name") for m in (data.get("models") or []) if m.get("name")]
        return {"reachable": True, "model_count": len(models), "models": models}


class OpenAIDriver:
    @staticmethod
    def generate_chat(base_url: str, model: str, messages: list[dict], api_key: str) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": 0.8,
        }
        with httpx.Client(timeout=float(os.getenv("OLLAMA_TIMEOUT", "120"))) as client:
            resp = client.post(
                f"{base_url}/v1/chat/completions",
                json=payload,
                headers=_build_headers(api_key),
            )
            resp.raise_for_status()
            data = resp.json()
        choices = data.get("choices") or []
        content = (((choices[0] or {}).get("message") or {}).get("content") or "").strip() if choices else ""
        if not content:
            raise RuntimeError("LLM returned empty response")
        return content

    @staticmethod
    def generate_stream(base_url: str, model: str, messages: list[dict], api_key: str) -> Generator[str, None, None]:
        try:
            # Phase 7.5 keeps stream interface compatibility by returning single chunk.
            content = OpenAIDriver.generate_chat(base_url, model, messages, api_key)
            yield f"data: {content.replace(chr(10), '\\n')}\n\n"
            yield "data: [DONE]\n\n"
        except httpx.TimeoutException as exc:
            yield f"data: [ERROR] LLM timeout: {exc}\n\n"
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            yield f"data: [ERROR] LLM HTTP error: {detail}\n\n"
        except httpx.RequestError as exc:
            yield f"data: [ERROR] LLM connection error: {exc}\n\n"
        except Exception as exc:
            yield f"data: [ERROR] LLM error: {exc}\n\n"

    @staticmethod
    def health(base_url: str, api_key: str) -> dict[str, Any]:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{base_url}/v1/models", headers=_build_headers(api_key))
            resp.raise_for_status()
            data = resp.json()
        items = data.get("data") or []
        models = [m.get("id") for m in items if isinstance(m, dict) and m.get("id")]
        return {"reachable": True, "model_count": len(models), "models": models}


def _resolve_model(model: str | None, effective: dict[str, str]) -> str:
    return (model or "").strip() or effective["model"]


def generate_chat(messages: list[dict], model: str | None = None) -> str:
    effective = get_effective_config()
    resolved_model = _resolve_model(model, effective)
    provider = effective["provider"]
    if provider == "ollama":
        return OllamaDriver.generate_chat(effective["base_url"], resolved_model, messages, effective["api_key"])
    if provider == "openai":
        return OpenAIDriver.generate_chat(effective["base_url"], resolved_model, messages, effective["api_key"])
    raise RuntimeError(f"Unknown LLM provider: {provider}")


def generate_chat_stream(messages: list[dict], model: str | None = None) -> Generator[str, None, None]:
    effective = get_effective_config()
    resolved_model = _resolve_model(model, effective)
    provider = effective["provider"]
    if provider == "ollama":
        yield from OllamaDriver.generate_stream(effective["base_url"], resolved_model, messages, effective["api_key"])
        return
    if provider == "openai":
        yield from OpenAIDriver.generate_stream(effective["base_url"], resolved_model, messages, effective["api_key"])
        return
    raise RuntimeError(f"Unknown LLM provider: {provider}")


def get_health() -> dict[str, Any]:
    effective = get_effective_config()
    provider = effective["provider"]
    try:
        if provider == "ollama":
            details = OllamaDriver.health(effective["base_url"], effective["api_key"])
        elif provider == "openai":
            details = OpenAIDriver.health(effective["base_url"], effective["api_key"])
        else:
            raise RuntimeError(f"Unknown LLM provider: {provider}")
        return {
            "reachable": True,
            "provider": provider,
            "base_url": effective["base_url"],
            "model": effective["model"],
            "model_count": details.get("model_count", 0),
            "models": details.get("models", []),
        }
    except Exception as exc:
        return {
            "reachable": False,
            "provider": provider,
            "base_url": effective["base_url"],
            "model": effective["model"],
            "model_count": 0,
            "models": [],
            "error": str(exc),
        }
