"""Phase 9A-3 — feature flags endpoint tests for Playwright PoC."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.routers import debug as debug_api


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(debug_api.router, prefix="/api")
    return TestClient(app)


class TestPhase9APlaywrightPoc(unittest.TestCase):
    def test_feature_flags_endpoint_ai_test_mode_true(self):
        with patch.dict(os.environ, {"AI_TEST_MODE": "1"}):
            client = _make_client()
            r = client.get("/api/debug/settings/feature_flags")
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json(), {"ai_test_mode": True})

    def test_feature_flags_endpoint_ai_test_mode_false(self):
        with patch.dict(os.environ, {"AI_TEST_MODE": "0"}):
            client = _make_client()
            r = client.get("/api/debug/settings/feature_flags")
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json(), {"ai_test_mode": False})

    def test_llm_stub_stream_for_playwright(self):
        from app.services import llm_service

        with patch.dict(
            os.environ,
            {"AI_TEST_MODE": "1", "AI_TEST_STUB_LLM": "1", "AI_TEST_STUB_LLM_TEXT": "stub-GM"},
        ):
            chunks = list(
                llm_service.generate_chat_stream([{"role": "user", "content": "x"}], "gemma", {})
            )
        joined = "".join(chunks)
        self.assertIn("stub-GM", joined)
        self.assertIn("[DONE]", joined)
