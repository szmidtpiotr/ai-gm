"""TDD: Issue #389 — LLM 429 rate-limit retry logic."""
import sys
import os
import time
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, "/app")

import httpx
import pytest


def _make_429_response(retry_after: float = 5.0) -> httpx.Response:
    body = json.dumps({
        "error": {
            "message": f"Rate limit reached. Please try again in {retry_after}s.",
            "type": "tokens",
            "code": "rate_limit_exceeded",
        }
    }).encode()
    resp = httpx.Response(
        status_code=429,
        headers={"retry-after": str(retry_after), "content-type": "application/json"},
        content=body,
    )
    return resp


def _make_200_stream_response(tokens: list[str]) -> MagicMock:
    lines = []
    for t in tokens:
        chunk = {"choices": [{"delta": {"content": t}}]}
        lines.append(f"data: {json.dumps(chunk)}")
    lines.append("data: [DONE]")

    mock = MagicMock()
    mock.is_success = True
    mock.status_code = 200
    mock.iter_lines.return_value = iter(lines)
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


# ─── Test główny: retry na 429 w generate_stream ────────────────────────────

def test_openai_stream_retries_on_429():
    """429 → wait → retry → stream succeeds. No error yielded to user."""
    from app.services.llm_service import OpenAIDriver

    call_count = 0

    class FakeClient:
        def __enter__(self): return self
        def __exit__(self, *a): pass

        def stream(self, method, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                resp_429 = _make_429_response(retry_after=0.01)
                mock = MagicMock()
                mock.is_success = False
                mock.status_code = 429
                mock.read = MagicMock()
                mock.headers = {"retry-after": "0.01"}

                def raise_for_status():
                    raise httpx.HTTPStatusError(
                        "429", request=MagicMock(), response=resp_429
                    )
                mock.raise_for_status = raise_for_status
                mock.__enter__ = lambda s: s
                mock.__exit__ = MagicMock(return_value=False)
                return mock
            else:
                return _make_200_stream_response(["Hello", " world"])

    with patch("app.services.llm_service.httpx.Client", return_value=FakeClient()):
        results = list(OpenAIDriver.generate_stream(
            base_url="https://api.openai.com",
            model="gpt-4.1",
            messages=[{"role": "user", "content": "test"}],
            api_key="sk-test",
        ))

    error_chunks = [r for r in results if "[ERROR]" in r]
    assert error_chunks == [], f"No error expected after retry, got: {error_chunks}"
    assert call_count == 2, f"Expected 2 attempts (1 retry), got {call_count}"
    assert any("Hello" in r for r in results), f"Expected content in results: {results}"


def test_openai_stream_gives_up_after_max_retries():
    """429 on all attempts → error yielded after max retries exceeded."""
    from app.services.llm_service import OpenAIDriver

    class AlwaysFailing:
        def __enter__(self): return self
        def __exit__(self, *a): pass

        def stream(self, method, url, **kwargs):
            resp_429 = _make_429_response(retry_after=0.01)
            mock = MagicMock()
            mock.is_success = False

            def raise_for_status():
                raise httpx.HTTPStatusError(
                    "429", request=MagicMock(), response=resp_429
                )
            mock.raise_for_status = raise_for_status
            mock.headers = {"retry-after": "0.01"}
            mock.__enter__ = lambda s: s
            mock.__exit__ = MagicMock(return_value=False)
            return mock

    with patch("app.services.llm_service.httpx.Client", return_value=AlwaysFailing()):
        results = list(OpenAIDriver.generate_stream(
            base_url="https://api.openai.com",
            model="gpt-4.1",
            messages=[{"role": "user", "content": "test"}],
            api_key="sk-test",
        ))

    # Contract updated by #1378: sanitized sentinel instead of raw [ERROR] body.
    error_chunks = [r for r in results if "[LLM_UNAVAILABLE:" in r]
    assert len(error_chunks) == 1, f"Expected exactly one error after max retries, got: {results}"
    assert not any("[ERROR]" in r for r in results), "raw [ERROR] sentinel should no longer be used (#1378)"


def test_openai_stream_non_429_error_no_retry():
    """Non-429 HTTP error → immediate error, no retry."""
    from app.services.llm_service import OpenAIDriver

    call_count = 0

    class OneShot:
        def __enter__(self): return self
        def __exit__(self, *a): pass

        def stream(self, method, url, **kwargs):
            nonlocal call_count
            call_count += 1
            body = json.dumps({"error": {"message": "Unauthorized"}}).encode()
            resp_401 = httpx.Response(
                status_code=401,
                headers={"content-type": "application/json"},
                content=body,
            )
            mock = MagicMock()
            mock.is_success = False

            def raise_for_status():
                raise httpx.HTTPStatusError(
                    "401", request=MagicMock(), response=resp_401
                )
            mock.raise_for_status = raise_for_status
            mock.__enter__ = lambda s: s
            mock.__exit__ = MagicMock(return_value=False)
            return mock

    with patch("app.services.llm_service.httpx.Client", return_value=OneShot()):
        results = list(OpenAIDriver.generate_stream(
            base_url="https://api.openai.com",
            model="gpt-4.1",
            messages=[{"role": "user", "content": "test"}],
            api_key="sk-test",
        ))

    assert call_count == 1, f"Should not retry 401, got {call_count} attempts"
    # Contract updated by #1378: sanitized sentinel instead of raw [ERROR] body.
    error_chunks = [r for r in results if "[LLM_UNAVAILABLE:" in r]
    assert len(error_chunks) == 1


# ─── Backward compat: non-429 errors still propagate ────────────────────────

def test_generate_chat_non_429_still_raises():
    """Non-429 errors in generate_chat still raise RuntimeError (backward compat)."""
    from app.services.llm_service import generate_chat

    body = json.dumps({"error": {"message": "model not found"}}).encode()
    resp_404 = httpx.Response(
        status_code=404,
        headers={"content-type": "application/json"},
        content=body,
    )

    def raise_404(*args, **kwargs):
        raise httpx.HTTPStatusError("404", request=MagicMock(), response=resp_404)

    with patch("app.services.llm_service.httpx.Client") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value.__enter__ = lambda s: mock_client
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=resp_404
        )
        mock_client.post.return_value = mock_resp

        with pytest.raises(RuntimeError):
            generate_chat(
                [{"role": "user", "content": "test"}],
                llm_config={"provider": "openai", "base_url": "https://api.openai.com",
                             "model": "gpt-4.1", "api_key": "sk-test"},
            )
