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

# Set once per process the first time we lazy-hydrate from the stored active
# preset (see _ensure_runtime_hydrated). Prevents repeated DB reads when there
# is genuinely no active preset.
_hydrate_attempted = False


class LLMConfigError(RuntimeError):
    """No LLM provider/model could be resolved from the active preset or env.

    Raised at actual call sites (generate_chat / generate_chat_stream) instead
    of silently falling back to the hardcoded Ollama default — so a missing or
    broken preset fails loudly rather than quietly hitting a local model.
    """


def _ensure_runtime_hydrated() -> None:
    """Lazy-load the active stored preset into this process's runtime config.

    The FastAPI lifespan hydrates on startup, but fresh processes (pytest,
    one-off scripts, workers) import this module with an empty ``_runtime_config``.
    Without this they would skip the admin's active preset and resolve to the
    hardcoded Ollama/``gemma4:e4b`` default. Runs at most once per process, and
    only while the runtime is still empty.
    """
    global _hydrate_attempted
    if _hydrate_attempted or _runtime_override_is_set():
        return
    _hydrate_attempted = True
    try:
        # Lazy import — llm_admin_service imports this module at top level.
        from app.services.llm_admin_service import hydrate_runtime_from_stored_preset

        hydrate_runtime_from_stored_preset()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("runtime_hydrate_failed", error=str(exc))


def _provider_canonical_base_url(provider: str) -> str:
    """Deterministic base URL for a provider when its preset leaves it blank.

    Not a 'random' fallback — each provider has exactly one canonical endpoint.
    Returns '' for providers (e.g. azure) where the base URL must be explicit.
    """
    if provider == "ollama":
        return DEFAULT_BASE_URL
    if provider == "openai":
        return "https://api.openai.com"
    return ""


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


def get_effective_config(
    llm_config: dict[str, str] | None = None, strict: bool = False
) -> dict[str, str]:
    """Resolve the effective LLM config as a COHERENT endpoint identity.

    provider + base_url + model always come from ONE source — never mixed —
    in priority order:
      1) explicit per-user override (``llm_config`` that names a provider)
      2) active preset / global runtime config (lazy-hydrated from the DB)
      3) environment variables (``LLM_PROVIDER`` etc.)

    The hardcoded Ollama endpoint/model is applied ONLY when the resolved
    provider is itself Ollama, so an OpenAI/Azure preset can never inherit
    ``gemma4:e4b`` or ``localhost:11434``.

    ``api_key`` is a credential, not part of the endpoint identity, so it may
    fall back across sources (user picks a provider but reuses the server key).

    strict=True (used at real call sites): raise :class:`LLMConfigError` when no
    provider/model is configured anywhere, instead of silently using Ollama.
    strict=False (display paths): return a best-effort, possibly-empty config.
    """
    override = llm_config or {}

    # Make sure a fresh process honors the admin's active preset.
    _ensure_runtime_hydrated()

    def _has_provider(src: dict[str, str]) -> bool:
        return bool((src.get("provider") or "").strip())

    env_src: dict[str, str] = {
        "provider": os.getenv("LLM_PROVIDER", ""),
        "base_url": os.getenv("LLM_BASE_URL", ""),
        "model": os.getenv("LLM_MODEL", ""),
        "api_key": os.getenv("LLM_API_KEY", ""),
    }

    # Pick the endpoint identity from the highest-priority source that names a provider.
    if _has_provider(override):
        identity: dict[str, str] | None = override
    elif _runtime_override_is_set():
        identity = _runtime_config
    elif _has_provider(env_src):
        identity = env_src
    else:
        identity = None

    if identity is None:
        if strict:
            raise LLMConfigError(
                "No active LLM preset configured. Activate one in "
                "Admin → Accounts, or set LLM_PROVIDER/LLM_MODEL on the server."
            )
        return {"provider": "", "base_url": "", "model": "", "api_key": ""}

    provider = (identity.get("provider") or "").strip().lower()
    base_url = (identity.get("base_url") or "").strip()
    model = (identity.get("model") or "").strip()

    # Deterministic per-provider base URL when the chosen source leaves it blank.
    if not base_url:
        base_url = _provider_canonical_base_url(provider)

    # api_key may fall back across sources (credential, not endpoint identity).
    api_key = (override.get("api_key") or "").strip()
    if not api_key:
        api_key = (identity.get("api_key") or "").strip()
    if not api_key:
        api_key = (_runtime_config.get("api_key") or "").strip()
    if not api_key:
        api_key = (os.getenv("LLM_API_KEY", "") or "").strip()

    if strict and not model:
        raise LLMConfigError(
            f"Active LLM preset for provider '{provider or 'unknown'}' has no "
            "model set. Fix the preset in Admin → Accounts."
        )

    return {
        "provider": provider,
        "base_url": _normalize_base_url(base_url, provider),
        "model": model,
        "api_key": api_key,
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
                    if not resp.is_success:
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
        max_retries = 3
        attempt = 0
        while True:
            try:
                with httpx.Client(timeout=float(os.getenv("OLLAMA_TIMEOUT", "120"))) as client:
                    with client.stream("POST", url, json=payload, headers=headers) as resp:
                        if not resp.is_success:
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
                return
            except httpx.HTTPStatusError as exc:
                if exc.response is not None and exc.response.status_code == 429 and attempt < max_retries - 1:
                    retry_after = float((exc.response.headers or {}).get("retry-after", "5"))
                    retry_after = min(retry_after + 1.0, 60.0)
                    logger.warning(
                        "llm_429_retry",
                        model=model,
                        llm_provider="openai",
                        attempt=attempt + 1,
                        retry_after_s=retry_after,
                    )
                    time.sleep(retry_after)
                    attempt += 1
                    continue
                detail = exc.response.text if exc.response is not None else str(exc)
                logger.error(
                    "llm_error",
                    model=model,
                    llm_provider="openai",
                    duration_ms=_duration_ms(started_at),
                    error_message=_trim_error_message(detail),
                )
                yield f"data: [ERROR] LLM HTTP error: {detail}\n\n"
                return
            except httpx.TimeoutException as exc:
                logger.error(
                    "llm_timeout",
                    model=model,
                    llm_provider="openai",
                    duration_ms=_duration_ms(started_at),
                    error_message=str(exc),
                )
                yield f"data: [ERROR] LLM timeout: {exc}\n\n"
                return
            except httpx.RequestError as exc:
                logger.error(
                    "llm_error",
                    model=model,
                    llm_provider="openai",
                    duration_ms=_duration_ms(started_at),
                    error_message=str(exc),
                )
                yield f"data: [ERROR] LLM connection error: {exc}\n\n"
                return
            except Exception as exc:
                logger.error(
                    "llm_error",
                    model=model,
                    llm_provider="openai",
                    duration_ms=_duration_ms(started_at),
                    error_message=str(exc),
                )
                yield f"data: [ERROR] LLM error: {exc}\n\n"
                return

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
                    if not resp.is_success:
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
    effective = get_effective_config(llm_config, strict=True)
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
    effective = get_effective_config(llm_config, strict=True)
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
