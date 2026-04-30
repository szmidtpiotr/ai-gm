"""Phase 9A-5 — Admin Test Runner API (router) tests."""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.routers import test_runner as tr  # noqa: E402


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(tr.router, prefix="/api")
    return TestClient(app)


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer testtoken"}


class TestPhase9aAdminUI(unittest.TestCase):
    def setUp(self) -> None:
        with tr._runs_lock:
            tr._runs.clear()

    def test_requires_admin_token(self) -> None:
        client = _make_client()
        r = client.post("/api/test_runner/start", json={"yaml": '{"name": "x"}'})
        self.assertEqual(r.status_code, 401)

    @patch.object(tr, "verify_admin_token", return_value=True)
    def test_generate_scenario_stub_returns_ready_and_yaml(self, _m) -> None:
        with patch.dict(os.environ, {"AI_TEST_STUB_SCENARIO": "1"}):
            client = _make_client()
            r = client.post(
                "/api/test_runner/generate_scenario",
                json={"message": "Pierwsza wiadomość", "history": []},
                headers=_auth_headers(),
            )
            self.assertEqual(r.status_code, 200, r.text)
            b = r.json()
            self.assertIn("reply", b)
            self.assertFalse(b.get("ready"), b)

            r2 = client.post(
                "/api/test_runner/generate_scenario",
                json={
                    "message": "Uzupełniam: max_steps 5",
                    "history": [
                        {"role": "user", "content": "Pierwsza wiadomość"},
                        {"role": "assistant", "content": "Doprecyzuj proszę."},
                    ],
                },
                headers=_auth_headers(),
            )
            self.assertEqual(r2.status_code, 200, r2.text)
            b2 = r2.json()
            self.assertTrue(b2.get("ready"), b2)
            self.assertIsNotNone(b2.get("yaml"))

    @patch.object(tr, "verify_admin_token", return_value=True)
    @patch.object(tr, "generate_chat", return_value='{"reply": "ok", "yaml": null, "ready": false}')
    def test_generate_scenario_with_llm_override_bypasses_stub_llm(self, _gc, _m) -> None:
        with patch.dict(
            os.environ,
            {"AI_TEST_STUB_LLM": "1", "AI_TEST_STUB_SCENARIO": "0"},
            clear=False,
        ):
            client = _make_client()
            r = client.post(
                "/api/test_runner/generate_scenario",
                json={
                    "message": "Hej",
                    "history": [],
                    "llm": {
                        "provider": "ollama",
                        "base_url": "http://127.0.0.1:11434",
                        "model": "m1",
                    },
                },
                headers=_auth_headers(),
            )
            self.assertEqual(r.status_code, 200, r.text)
            _gc.assert_called_once()
            args, kwargs = _gc.call_args
            self.assertIn("llm_config", kwargs)
            self.assertEqual(kwargs.get("llm_config", {}).get("model"), "m1")

    @patch.object(tr, "verify_admin_token", return_value=True)
    def test_ai_test_config_returns_player_id_from_file(self, _m) -> None:
        payload = {
            "player_id": 41,
            "character_id": 2,
            "campaign_id": 3,
            "player_username": "x",
        }
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            json.dump(payload, f)
            p = f.name
        try:
            with patch.dict(os.environ, {"AI_TEST_CONFIG_PATH": p}, clear=False):
                client = _make_client()
                r = client.get("/api/test_runner/ai_test_config", headers=_auth_headers())
            self.assertEqual(r.status_code, 200, r.text)
            body = r.json()
            self.assertEqual(body.get("player_id"), 41)
            self.assertEqual(body.get("config_path"), p)
        finally:
            os.unlink(p)

    @patch.object(tr, "verify_admin_token", return_value=True)
    @patch.object(tr, "get_health", return_value={"reachable": True, "models": ["a", "b"], "base_url": "x"})
    def test_llm_models_post_returns_list(self, _h, _m) -> None:
        client = _make_client()
        r = client.post(
            "/api/test_runner/llm_models",
            json={"provider": "ollama", "base_url": "http://127.0.0.1:11434"},
            headers=_auth_headers(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json().get("models"), ["a", "b"])

    @patch.object(tr, "verify_admin_token", return_value=True)
    @patch.object(tr.httpx, "Client")
    def test_agent_health_ok(self, client_cls, _m) -> None:
        inst = MagicMock()
        client_cls.return_value.__enter__.return_value = inst
        client_cls.return_value.__exit__.return_value = None
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"scenarios": ["a.json", "b.json"]}
        inst.get.return_value = resp
        client = _make_client()
        r = client.get("/api/test_runner/agent_health", headers=_auth_headers())
        self.assertEqual(r.status_code, 200, r.text)
        b = r.json()
        self.assertTrue(b.get("reachable"))
        self.assertEqual(b.get("scenario_count"), 2)

    @patch.object(tr, "verify_admin_token", return_value=True)
    def test_start_run_returns_run_id_and_status_ends(self, _m) -> None:
        mock_client_cls = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client_instance
        mock_client_cls.return_value.__exit__.return_value = None

        stream_resp = MagicMock()
        stream_resp.status_code = 200
        stream_resp.iter_lines.return_value = iter(
            ['data: {"done": true, "success": true, "steps": 0}']
        )
        stream_cm = MagicMock()
        stream_cm.__enter__.return_value = stream_resp
        stream_cm.__exit__.return_value = None
        mock_client_instance.stream.return_value = stream_cm

        with patch.object(tr.httpx, "Client", mock_client_cls):
            client = _make_client()
            r = client.post(
                "/api/test_runner/start",
                json={"yaml": '{"name": "t", "max_steps": 1}'},
                headers=_auth_headers(),
            )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("run_id", body)
        run_id = body["run_id"]

        for _ in range(30):
            time.sleep(0.05)
            s = client.get(
                f"/api/test_runner/status/{run_id}",
                headers=_auth_headers(),
            )
            if s.status_code == 200 and s.json().get("status") in ("DONE", "ERROR"):
                self.assertIn(s.json()["status"], ("DONE", "ERROR"))
                return
        self.fail("Status did not leave RUNNING in time")

    @patch.object(tr, "verify_admin_token", return_value=True)
    def test_scenarios_list_includes_saved_file(self, _m) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"AI_TEST_SCENARIOS_DIR": tmp}):
                client = _make_client()
                r0 = client.post(
                    "/api/test_runner/save_scenario",
                    json={"filename": "z_phase9a_ui.json", "content": '{\n  "name": "a"\n}'},
                    headers=_auth_headers(),
                )
                self.assertEqual(r0.status_code, 200, r0.text)
                r = client.get("/api/test_runner/scenarios", headers=_auth_headers())
                self.assertEqual(r.status_code, 200, r.text)
                self.assertIn("z_phase9a_ui.json", r.json().get("scenarios", []))


if __name__ == "__main__":
    unittest.main()
