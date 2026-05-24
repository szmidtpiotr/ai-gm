import os
import re
import json
import time
from typing import Any, Generator

import httpx

from app.core.logging import get_logger

_runtime_config: dict[str, str] = {
    "provider": "",
    "base_url": "",
    "model": "",
    "api_key": "",
}
DEFAULT_PROVIDER = "ollama"
DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "gemma4:e4b"
logger = get_logger(__name__)


def set_runtime_config(provider: str, base_url: str, model: str, api_key: str) -> None:
    _runtime_config["provider"] = (provider or "").strip().lower()
    _runtime_config["base_url"] = (base_url or "").strip()
    _runtime_config["model"] = (model or "").strip()
    _runtime_config["api_key"] = (api_key or "").strip()


def get_runtime_config(mask_api_key: bool = False) -> dict[str, Any]:
    api_key = _runtime_config["api_key"]
    key_set = bool((api_key or "").strip())
    if mask_api_key and api_key:
        shown = f"{api_key[:6]}..." if len(api_key) > 6 else f"{api_key}..."
    else:
        shown = api_key
    return {
        "provider": _runtime_config["provider"],
        "base_url": _runtime_config["base_url"],
        "model": _runtime_config["model"],
        "api_key": shown,
        "api_key_set": key_set,
    }


def _runtime_override_is_set() -> bool:
    return any(bool((value or "").strip()) for value in _runtime_config.values())


def get_effective_config(llm_config: dict[str, str] | None = None) -> dict[str, str]:
    """
    Effective LLM config resolution.

    Precedence:
    1) explicit llm_config override (if provided)
    2) global runtime config (set by /api/settings/llm)
    3) environment variables
    """
    override = llm_config or {}

    def _pick(field: str, env_key: str) -> str:
        # If a field is explicitly present in the override, use it — except `api_key`:
        # an empty string in DB (user saved provider without pasting a key) should still
        # fall back to runtime `/api/settings/llm` or `LLM_API_KEY`, otherwise OpenAI gets 401.
        if field in override:
            val = (override.get(field) or "").strip()
            if field != "api_key" or val:
                return val
        runtime_val = _runtime_config.get(field, "")
        return (runtime_val or os.getenv(env_key, "") or "").strip()

    provider = _pick("provider", "LLM_PROVIDER") or DEFAULT_PROVIDER
    base_url = _pick("base_url", "LLM_BASE_URL") or DEFAULT_BASE_URL
    model = _pick("model", "LLM_MODEL") or DEFAULT_MODEL
    api_key = _pick("api_key", "LLM_API_KEY")
    normalized_provider = provider.strip().lower()
    return {
        "provider": normalized_provider,
        "base_url": _normalize_base_url(base_url.strip(), normalized_provider),
        "model": model.strip(),
        "api_key": api_key.strip(),
    }


def get_default_config(mask_api_key: bool = False) -> dict[str, Any]:
    effective = get_effective_config()
    api_key = effective.get("api_key") or ""
    if mask_api_key and api_key:
        shown = f"{api_key[:6]}..." if len(api_key) > 6 else f"{api_key}..."
    else:
        shown = api_key
    return {
        "mode": "default",
        "provider": effective["provider"],
        "base_url": effective["base_url"],
        "model": effective["model"],
        "api_key": shown,
        "api_key_set": bool(api_key.strip()),
        "source": "runtime" if _runtime_override_is_set() else "env",
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
    elif provider == "azure":
        # Strip if user pasted the full deployment or completions URL
        value = re.sub(r"/openai/deployments/[^/]+/chat/completions/?$", "", value, flags=re.I)
        value = re.sub(r"/openai/deployments/[^/]+/?$", "", value, flags=re.I)
        value = re.sub(r"/openai/?$", "", value, flags=re.I)
    return value.rstrip("/")


def _duration_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _trim_error_message(raw: str) -> str:
    text = (raw or "").strip()
    if len(text) > 1200:
        return text[:1200] + "…"
    return text


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
            try:
                data = resp.json()
            except ValueError as e:
                peek = (resp.text or "")[:800]
                raise RuntimeError(
                    f"LLM returned non-JSON (status {resp.status_code}): {peek}"
                ) from e
        content = ((data.get("message") or {}).get("content") or "").strip()
        if not content:
            raise RuntimeError("LLM returned empty response")
        return content

    @staticmethod
    def generate_stream(base_url: str, model: str, messages: list[dict], api_key: str) -> Generator[str, None, None]:
        started_at = time.perf_counter()
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
                    if resp.status_code >= 400:
                        resp.read()
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
            logger.error(
                "llm_timeout",
                model=model,
                llm_provider="ollama",
                duration_ms=_duration_ms(started_at),
                error_message=str(exc),
            )
            yield f"data: [ERROR] LLM timeout: {exc}\n\n"
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            logger.error(
                "llm_error",
                model=model,
                llm_provider="ollama",
                duration_ms=_duration_ms(started_at),
                error_message=_trim_error_message(detail),
            )
            yield f"data: [ERROR] LLM HTTP error: {detail}\n\n"
        except httpx.RequestError as exc:
            logger.error(
                "llm_error",
                model=model,
                llm_provider="ollama",
                duration_ms=_duration_ms(started_at),
                error_message=str(exc),
            )
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
            try:
                data = resp.json()
            except ValueError as e:
                peek = (resp.text or "")[:800]
                raise RuntimeError(
                    f"LLM returned non-JSON (status {resp.status_code}): {peek}"
                ) from e
        choices = data.get("choices") or []
        content = (((choices[0] or {}).get("message") or {}).get("content") or "").strip() if choices else ""
        if not content:
            raise RuntimeError("LLM returned empty response")
        return content

    @staticmethod
    def generate_stream(base_url: str, model: str, messages: list[dict], api_key: str) -> Generator[str, None, None]:
        started_at = time.perf_counter()
        payload = {"model": model, "messages": messages, "stream": True, "temperature": 0.8}
        url = f"{base_url}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            with httpx.Client(timeout=float(os.getenv("OLLAMA_TIMEOUT", "120"))) as client:
                with client.stream("POST", url, json=payload, headers=headers) as resp:
                    if resp.status_code >= 400:
                        resp.read()
                        resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            raw = line[6:]
                            try:
                                chunk = json.loads(raw)
                            except Exception:
                                continue
                            token = ((chunk.get("choices") or [{}])[0]
                                     .get("delta", {}).get("content") or "")
                            if token:
                                yield f"data: {token.replace(chr(10), '\\n')}\n\n"
            yield "data: [DONE]\n\n"
        except httpx.TimeoutException as exc:
            logger.error(
                "llm_timeout",
                model=model,
                llm_provider="openai",
                duration_ms=_duration_ms(started_at),
                error_message=str(exc),
            )
            yield f"data: [ERROR] LLM timeout: {exc}\n\n"
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            logger.error(
                "llm_error",
                model=model,
                llm_provider="openai",
                duration_ms=_duration_ms(started_at),
                error_message=_trim_error_message(detail),
            )
            yield f"data: [ERROR] LLM HTTP error: {detail}\n\n"
        except httpx.RequestError as exc:
            logger.error(
                "llm_error",
                model=model,
                llm_provider="openai",
                duration_ms=_duration_ms(started_at),
                error_message=str(exc),
            )
            yield f"data: [ERROR] LLM connection error: {exc}\n\n"
        except Exception as exc:
            logger.error(
                "llm_error",
                model=model,
                llm_provider="openai",
                duration_ms=_duration_ms(started_at),
                error_message=str(exc),
            )
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


class AzureDriver:
    """Azure OpenAI Service / Azure AI Foundry driver.

    base_url: https://<resource>.openai.azure.com  (resource endpoint, no deployment path)
    model:    deployment name, e.g. "gpt-4.1"
    api_key:  Azure API key (sent as 'api-key' header, not Bearer)
    """

    _API_VERSION = "2024-02-01"

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if api_key:
            h["api-key"] = api_key
        return h

    @staticmethod
    def _url(base_url: str, model: str) -> str:
        return (
            f"{base_url}/openai/deployments/{model}/chat/completions"
            f"?api-version={AzureDriver._API_VERSION}"
        )

    @staticmethod
    def generate_chat(base_url: str, model: str, messages: list[dict], api_key: str) -> str:
        payload = {"messages": messages, "stream": False, "temperature": 0.8}
        with httpx.Client(timeout=float(os.getenv("OLLAMA_TIMEOUT", "120"))) as client:
            resp = client.post(
                AzureDriver._url(base_url, model),
                json=payload,
                headers=AzureDriver._headers(api_key),
            )
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError as e:
                peek = (resp.text or "")[:800]
                raise RuntimeError(f"Azure returned non-JSON (status {resp.status_code}): {peek}") from e
        choices = data.get("choices") or []
        content = (((choices[0] or {}).get("message") or {}).get("content") or "").strip() if choices else ""
        if not content:
            raise RuntimeError("Azure returned empty response")
        return content

    @staticmethod
    def generate_stream(base_url: str, model: str, messages: list[dict], api_key: str) -> Generator[str, None, None]:
        started_at = time.perf_counter()
        url = (
            f"{base_url}/openai/deployments/{model}/chat/completions"
            f"?api-version={AzureDriver._API_VERSION}"
        )
        payload = {"messages": messages, "stream": True, "temperature": 0.8}
        headers = AzureDriver._headers(api_key)
        try:
            with httpx.Client(timeout=float(os.getenv("OLLAMA_TIMEOUT", "120"))) as client:
                with client.stream("POST", url, json=payload, headers=headers) as resp:
                    if resp.status_code >= 400:
                        resp.read()
                        resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            raw = line[6:]
                            try:
                                chunk = json.loads(raw)
                            except Exception:
                                continue
                            token = ((chunk.get("choices") or [{}])[0]
                                     .get("delta", {}).get("content") or "")
                            if token:
                                yield f"data: {token.replace(chr(10), '\\n')}\n\n"
            yield "data: [DONE]\n\n"
        except httpx.TimeoutException as exc:
            logger.error("llm_timeout", model=model, llm_provider="azure",
                         duration_ms=_duration_ms(started_at), error_message=str(exc))
            yield f"data: [ERROR] LLM timeout: {exc}\n\n"
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            logger.error("llm_error", model=model, llm_provider="azure",
                         duration_ms=_duration_ms(started_at), error_message=_trim_error_message(detail))
            yield f"data: [ERROR] LLM HTTP error: {detail}\n\n"
        except httpx.RequestError as exc:
            logger.error("llm_error", model=model, llm_provider="azure",
                         duration_ms=_duration_ms(started_at), error_message=str(exc))
            yield f"data: [ERROR] LLM connection error: {exc}\n\n"
        except Exception as exc:
            logger.error("llm_error", model=model, llm_provider="azure",
                         duration_ms=_duration_ms(started_at), error_message=str(exc))
            yield f"data: [ERROR] LLM error: {exc}\n\n"

    @staticmethod
    def health(base_url: str, api_key: str) -> dict[str, Any]:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{base_url}/openai/models",
                headers=AzureDriver._headers(api_key),
                params={"api-version": AzureDriver._API_VERSION},
            )
            resp.raise_for_status()
            data = resp.json()
        items = data.get("data") or []
        models = [m.get("id") for m in items if isinstance(m, dict) and m.get("id")]
        return {"reachable": True, "model_count": len(models), "models": models}


def _resolve_model(model: str | None, effective: dict[str, str]) -> str:
    v = (model or "").strip()
    if v and v != "default":
        return v
    return effective["model"]


def _raise_llm_http_error(exc: httpx.HTTPStatusError) -> None:
    """Normalize provider HTTP failures so API layers return 502 + readable detail, not raw 500."""
    status = exc.response.status_code if exc.response is not None else None
    body = ""
    if exc.response is not None:
        try:
            body = (exc.response.text or "").strip()
        except Exception:
            body = ""
    if len(body) > 1200:
        body = body[:1200] + "…"
    raise RuntimeError(
        f"LLM HTTP {status}: {body or exc!s}"
    ) from exc


def generate_chat(messages: list[dict], model: str | None = None, llm_config: dict[str, str] | None = None) -> str:
    effective = get_effective_config(llm_config)
    resolved_model = _resolve_model(model, effective)
    provider = effective["provider"]
    started_at = time.perf_counter()
    logger.info("llm_called", model=resolved_model, llm_provider=provider, stream=False)
    if provider in ("openai", "azure") and not (effective.get("api_key") or "").strip():
        raise RuntimeError(
            f"{provider.title()} API key missing: paste it in LLM settings and Save, or set LLM_API_KEY on the server."
        )
    try:
        if provider == "ollama":
            return OllamaDriver.generate_chat(effective["base_url"], resolved_model, messages, effective["api_key"])
        if provider == "openai":
            return OpenAIDriver.generate_chat(effective["base_url"], resolved_model, messages, effective["api_key"])
        if provider == "azure":
            return AzureDriver.generate_chat(effective["base_url"], resolved_model, messages, effective["api_key"])
    except httpx.TimeoutException as exc:
        logger.error(
            "llm_timeout",
            model=resolved_model,
            llm_provider=provider,
            duration_ms=_duration_ms(started_at),
            error_message=str(exc),
        )
        raise RuntimeError(f"LLM timeout: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        logger.error(
            "llm_error",
            model=resolved_model,
            llm_provider=provider,
            duration_ms=_duration_ms(started_at),
            error_message=_trim_error_message(detail),
        )
        _raise_llm_http_error(exc)
    except httpx.RequestError as exc:
        logger.error(
            "llm_error",
            model=resolved_model,
            llm_provider=provider,
            duration_ms=_duration_ms(started_at),
            error_message=str(exc),
        )
        raise RuntimeError(f"LLM connection error: {exc}") from exc
    except RuntimeError as exc:
        logger.error(
            "llm_error",
            model=resolved_model,
            llm_provider=provider,
            duration_ms=_duration_ms(started_at),
            error_message=str(exc),
        )
        raise
    raise RuntimeError(f"Unknown LLM provider: {provider}")


def generate_chat_stream(
    messages: list[dict], model: str | None = None, llm_config: dict[str, str] | None = None
) -> Generator[str, None, None]:
    effective = get_effective_config(llm_config)
    resolved_model = _resolve_model(model, effective)
    if os.getenv("AI_TEST_MODE") == "1" and os.getenv("AI_TEST_STUB_LLM") == "1":
        stub = (os.getenv("AI_TEST_STUB_LLM_TEXT") or "").strip() or (
            "Krótki opis otoczenia (odpowiedź testowa, bez wywołania LLM)."
        )
        logger.info("llm_stub_stream", model=resolved_model, reason="AI_TEST_STUB_LLM")
        yield f"data: {stub.replace('\n', '\\n')}\n\n"
        yield "data: [DONE]\n\n"
        return
    provider = effective["provider"]
    logger.info("llm_called", model=resolved_model, llm_provider=provider, stream=True)
    if provider in ("openai", "azure") and not (effective.get("api_key") or "").strip():
        raise RuntimeError(
            f"{provider.title()} API key missing: paste it in LLM settings and Save, or set LLM_API_KEY on the server."
        )
    if provider == "ollama":
        yield from OllamaDriver.generate_stream(effective["base_url"], resolved_model, messages, effective["api_key"])
        return
    if provider == "openai":
        yield from OpenAIDriver.generate_stream(effective["base_url"], resolved_model, messages, effective["api_key"])
        return
    if provider == "azure":
        yield from AzureDriver.generate_stream(effective["base_url"], resolved_model, messages, effective["api_key"])
        return
    raise RuntimeError(f"Unknown LLM provider: {provider}")


def get_health(llm_config: dict[str, str] | None = None) -> dict[str, Any]:
    effective = get_effective_config(llm_config)
    provider = effective["provider"]
    try:
        if provider == "ollama":
            details = OllamaDriver.health(effective["base_url"], effective["api_key"])
        elif provider == "openai":
            details = OpenAIDriver.health(effective["base_url"], effective["api_key"])
        elif provider == "azure":
            details = AzureDriver.health(effective["base_url"], effective["api_key"])
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
