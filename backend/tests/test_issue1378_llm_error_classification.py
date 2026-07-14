"""TDD: Issue #1378 - LLM error classification, sanitized player messages, admin alert.

No silent multi-provider fallback exists (confirmed by inspection) and this
issue does not add one. It fixes what happens when the single configured
gameplay provider fails: today the raw provider error body (e.g. OpenAI's
insufficient_quota JSON) leaks straight to the player, and there is no
admin alert when the budget runs out. This test file locks in:
  - classification into budget_exhausted / rate_limited / timeout /
    provider_down / config_error
  - generate_chat raising LLMUnavailableError with a sanitized
    player_message (never the raw provider body)
  - streaming drivers yielding data: [LLM_UNAVAILABLE:<reason>] instead of
    data: [ERROR] <raw body>
  - an admin Telegram alert firing specifically on budget_exhausted
"""
import sys
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, "/app")

import httpx
import pytest


def _make_http_error(status_code: int, body: dict, headers: dict | None = None) -> httpx.HTTPStatusError:
    resp = httpx.Response(
        status_code=status_code,
        headers=headers or {"content-type": "application/json"},
        content=json.dumps(body).encode(),
    )
    return httpx.HTTPStatusError(str(status_code), request=MagicMock(), response=resp)


# --- _classify_llm_failure - reason mapping ---

def test_classify_budget_exhausted_from_quota_signature():
    from app.services.llm_service import _classify_llm_failure

    body = json.dumps({"error": {"message": "You exceeded your current quota, please check your plan and billing details.", "code": "insufficient_quota"}})
    assert _classify_llm_failure("http", 429, body) == "budget_exhausted"


def test_classify_rate_limited_without_quota_signature():
    from app.services.llm_service import _classify_llm_failure

    body = json.dumps({"error": {"message": "Rate limit reached, try again in 2s", "code": "rate_limit_exceeded"}})
    assert _classify_llm_failure("http", 429, body) == "rate_limited"


def test_classify_config_error_on_401():
    from app.services.llm_service import _classify_llm_failure

    body = json.dumps({"error": {"message": "Incorrect API key provided"}})
    assert _classify_llm_failure("http", 401, body) == "config_error"


def test_classify_provider_down_on_5xx():
    from app.services.llm_service import _classify_llm_failure

    body = json.dumps({"error": {"message": "internal server error"}})
    assert _classify_llm_failure("http", 503, body) == "provider_down"


def test_classify_timeout_kind():
    from app.services.llm_service import _classify_llm_failure

    assert _classify_llm_failure("timeout", None, "") == "timeout"


def test_classify_connection_kind():
    from app.services.llm_service import _classify_llm_failure

    assert _classify_llm_failure("connection", None, "") == "provider_down"


# --- generate_chat (non-streaming) - sanitized exception ---

def test_generate_chat_budget_exhausted_raises_sanitized_error():
    """OpenAI 429 insufficient_quota -> LLMUnavailableError, player_message has no raw body."""
    from app.services.llm_service import generate_chat, LLMUnavailableError, PLAYER_MESSAGES

    marker = "sk-secret-billing-detail-should-never-reach-player-XYZ123"
    err = _make_http_error(429, {"error": {"message": f"quota exceeded ({marker})", "code": "insufficient_quota"}})

    with patch("app.services.llm_service.httpx.Client") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value.__enter__ = lambda s: mock_client
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = err
        mock_client.post.return_value = mock_resp

        with pytest.raises(LLMUnavailableError) as excinfo:
            generate_chat(
                [{"role": "user", "content": "test"}],
                llm_config={"provider": "openai", "base_url": "https://api.openai.com",
                             "model": "gpt-4.1", "api_key": "sk-test"},
            )

    exc = excinfo.value
    assert exc.reason == "budget_exhausted"
    assert exc.player_message == PLAYER_MESSAGES["budget_exhausted"]
    assert marker not in exc.player_message


def test_generate_chat_admin_alert_fires_on_budget_exhausted():
    """Admin Telegram alert fires exactly on budget_exhausted, not on other reasons."""
    from app.services.llm_service import generate_chat, LLMUnavailableError

    err = _make_http_error(429, {"error": {"message": "quota exceeded", "code": "insufficient_quota"}})

    with patch("app.services.llm_service.httpx.Client") as MockClient, \
         patch("app.services.notification_service.send_telegram", return_value=True) as mock_send, \
         patch("app.services.notification_service._ADMIN_ALERT_CHAT_ID", "999999"):
        mock_client = MagicMock()
        MockClient.return_value.__enter__ = lambda s: mock_client
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = err
        mock_client.post.return_value = mock_resp

        with pytest.raises(LLMUnavailableError):
            generate_chat(
                [{"role": "user", "content": "test"}],
                llm_config={"provider": "openai", "base_url": "https://api.openai.com",
                             "model": "gpt-4.1", "api_key": "sk-test"},
            )

    assert mock_send.called, "Admin alert should fire on budget_exhausted"
    call_args = mock_send.call_args
    assert call_args[0][0] == "999999"


def test_generate_chat_timeout_does_not_alert_admin():
    """Timeout is classified but must NOT page the admin (only budget_exhausted does)."""
    from app.services.llm_service import generate_chat, LLMUnavailableError

    with patch("app.services.llm_service.httpx.Client") as MockClient, \
         patch("app.services.notification_service.send_telegram", return_value=True) as mock_send, \
         patch("app.services.notification_service._ADMIN_ALERT_CHAT_ID", "999999"):
        mock_client = MagicMock()
        MockClient.return_value.__enter__ = lambda s: mock_client
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(LLMUnavailableError) as excinfo:
            generate_chat(
                [{"role": "user", "content": "test"}],
                llm_config={"provider": "openai", "base_url": "https://api.openai.com",
                             "model": "gpt-4.1", "api_key": "sk-test"},
            )

    assert excinfo.value.reason == "timeout"
    assert not mock_send.called


# --- Streaming drivers - sanitized SSE sentinel ---

def test_openai_stream_budget_exhausted_yields_sanitized_sentinel():
    from app.services.llm_service import OpenAIDriver

    marker = "raw-billing-body-must-not-leak-ABC999"
    err_body = json.dumps({"error": {"message": f"quota exceeded ({marker})", "code": "insufficient_quota"}}).encode()
    resp_429 = httpx.Response(status_code=429, headers={"content-type": "application/json"}, content=err_body)

    class OneShot:
        def __enter__(self): return self
        def __exit__(self, *a): pass

        def stream(self, method, url, **kwargs):
            mock = MagicMock()
            mock.is_success = False

            def raise_for_status():
                raise httpx.HTTPStatusError("429", request=MagicMock(), response=resp_429)
            mock.raise_for_status = raise_for_status
            mock.headers = {}
            mock.__enter__ = lambda s: s
            mock.__exit__ = MagicMock(return_value=False)
            return mock

    with patch("app.services.llm_service.httpx.Client", return_value=OneShot()), \
         patch("app.services.notification_service.send_telegram", return_value=True), \
         patch("app.services.notification_service._ADMIN_ALERT_CHAT_ID", "999999"):
        results = list(OpenAIDriver.generate_stream(
            base_url="https://api.openai.com",
            model="gpt-4.1",
            messages=[{"role": "user", "content": "test"}],
            api_key="sk-test",
        ))

    joined = "".join(results)
    assert "data: [LLM_UNAVAILABLE:budget_exhausted]" in joined
    assert marker not in joined
    assert "[ERROR]" not in joined


def test_ollama_stream_connection_error_yields_provider_down_sentinel():
    from app.services.llm_service import OllamaDriver

    class Boom:
        def __enter__(self): return self
        def __exit__(self, *a): pass

        def stream(self, method, url, **kwargs):
            raise httpx.ConnectError("connection refused", request=MagicMock())

    with patch("app.services.llm_service.httpx.Client", return_value=Boom()):
        results = list(OllamaDriver.generate_stream(
            base_url="http://localhost:11434",
            model="gemma4:e4b",
            messages=[{"role": "user", "content": "test"}],
            api_key="",
        ))

    joined = "".join(results)
    assert "data: [LLM_UNAVAILABLE:provider_down]" in joined
    assert "connection refused" not in joined


# --- Backward compat ---

def test_generate_chat_unknown_provider_still_plain_runtime_error():
    """Non-LLM-call errors (bad config, not a provider failure) stay plain RuntimeError."""
    from app.services.llm_service import generate_chat, LLMUnavailableError

    with pytest.raises(RuntimeError) as excinfo:
        generate_chat(
            [{"role": "user", "content": "test"}],
            llm_config={"provider": "carrier-pigeon", "base_url": "http://example.com",
                         "model": "x", "api_key": "k"},
        )
    assert not isinstance(excinfo.value, LLMUnavailableError)


def test_generate_chat_non_429_non_quota_still_raises_llm_unavailable_error():
    """404 (model not found) is still an LLM failure -> LLMUnavailableError (IS-A RuntimeError)."""
    from app.services.llm_service import generate_chat, LLMUnavailableError

    err = _make_http_error(404, {"error": {"message": "model not found"}})

    with patch("app.services.llm_service.httpx.Client") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value.__enter__ = lambda s: mock_client
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = err
        mock_client.post.return_value = mock_resp

        with pytest.raises(RuntimeError) as excinfo:
            generate_chat(
                [{"role": "user", "content": "test"}],
                llm_config={"provider": "openai", "base_url": "https://api.openai.com",
                             "model": "gpt-4.1", "api_key": "sk-test"},
            )
    assert isinstance(excinfo.value, LLMUnavailableError)
