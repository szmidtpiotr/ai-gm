"""TDD: Issue #1081 — forge generate-plan crashes 'no model set' when model is stripped from llm_config.

Root cause: adventure_forge.py strips `model` from llm_cfg before passing to generate_chat.
generate_chat calls get_effective_config(stripped_config, strict=True) → sees provider but no model → raises.
The model= param passed separately is never reached.

Fix (Option A): don't strip model — pass llm_cfg directly to generate_chat(llm_config=llm_cfg).
"""
import sys
import os
import json
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from fastapi.testclient import TestClient


# ─── Valid CampaignPlan for mocking LLM response ─────────────────────────────

VALID_PLAN = {
    "title": "Przygoda testowa #1081",
    "premise": "Bohater musi pokonać nadciągające zło.",
    "acts": [
        {
            "number": 1,
            "title": "Prolog",
            "summary": "Bohater wyrusza w drogę",
            "key_beats": [
                {
                    "beat_key": "spotkaj_sojusznika",
                    "summary": "Spotkaj sojusznika",
                    "objective_type": "talk_to_npc",
                    "objective_value": "mira",
                    "optional": False,
                }
            ],
        },
        {
            "number": 2,
            "title": "Finał",
            "summary": "Ostateczna konfrontacja",
            "key_beats": [
                {
                    "beat_key": "pokonaj_bossa",
                    "summary": "Pokonaj głównego antagonistę",
                    "objective_type": "kill_enemy",
                    "objective_value": "goblin_warlord",
                    "optional": False,
                }
            ],
        },
    ],
    "endings": [
        {
            "id": "end_victory",
            "title": "Zwycięstwo",
            "type": "primary",
            "description": "Bohater pokonuje zło i ratuje wioskę.",
            "requirements": [],
        }
    ],
    "key_npcs": [
        {
            "key": "mira",
            "name": "Mira",
            "role": "Sojusznik — prowadzi bohatera",
            "importance": "critical",
            "deviation_consequence": "steer",
            "alive": True,
        }
    ],
    "key_locations": [
        {
            "key": "wioska_start",
            "name": "Wioska startowa",
            "role": "Punkt wyjścia przygody",
            "visited": False,
        }
    ],
    "engine_private": {
        "secret_predisposition_hint": "Bohater ma skryty cel zemsty.",
        "hidden_twist": "Mira jest córką antagonisty.",
        "contingency": "Jeśli bohater ginie, zło opanowuje krainę.",
    },
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _login(client: TestClient) -> str:
    r = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["token"]


def _get_or_create_template(client: TestClient, token: str) -> int:
    hdrs = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/admin/forge/templates", headers=hdrs)
    assert r.status_code == 200, f"list templates failed: {r.text}"
    templates = r.json().get("items", [])
    if templates:
        return templates[0]["id"]
    r2 = client.post("/api/admin/forge/templates", headers=hdrs, json={
        "title": "Test #1081",
        "genre": "fantasy",
        "tone": "heroic",
        "act_count": 2,
    })
    assert r2.status_code in (200, 201), f"create template failed: {r2.text}"
    return r2.json()["id"]


# ─── Unit: reproduces root cause ─────────────────────────────────────────────

class TestIssue1081RootCause:
    """Unit tests that pin the exact bug: stripped llm_config + strict=True → raises."""

    def test_get_effective_config_strict_raises_when_model_stripped(self):
        """Bug: config with provider but no model causes strict=True to raise LLMConfigError.

        This is exactly what adventure_forge does at line 1311: strips model from llm_cfg,
        then passes stripped config to generate_chat → get_effective_config(stripped, strict=True) raises.
        """
        from app.services.llm_service import get_effective_config, LLMConfigError

        stripped = {
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": "test-key",
            # no "model" key
        }
        with pytest.raises(LLMConfigError, match="has no model set"):
            get_effective_config(stripped, strict=True)

    def test_get_effective_config_strict_passes_when_model_present(self):
        """Fix: full config (with model) passes strict=True without raising."""
        from app.services.llm_service import get_effective_config

        full_cfg = {
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-5.4",
            "api_key": "test-key",
        }
        result = get_effective_config(full_cfg, strict=True)
        assert result["model"] == "gpt-5.4"
        assert result["provider"] == "openai"


# ─── Integration: endpoint RED→GREEN ─────────────────────────────────────────

class TestIssue1081Endpoint:
    """Endpoint-level tests. Patch at OpenAIDriver (HTTP layer) — not generate_chat itself —
    so the real strict-resolve logic runs and the bug/fix can be observed."""

    def test_forge_generate_plan_succeeds_when_preset_has_model(self):
        """RED→GREEN: endpoint returns 200 when preset has model and generate_chat gets full config.

        BEFORE fix: generate_chat receives stripped config → strict raises → 500 'no model set'.
        AFTER fix: generate_chat receives full config → strict passes → calls driver → 200.
        """
        from app.services.llm_service import set_runtime_config
        from app.main import app

        client = TestClient(app)
        token = _login(client)
        template_id = _get_or_create_template(client, token)

        set_runtime_config("openai", "https://api.openai.com/v1", "gpt-5.4", "test-key")

        # Patch at the HTTP driver level — real generate_chat runs, bug surfaces or not
        with patch(
            "app.services.llm_service.OpenAIDriver.generate_chat",
            return_value=json.dumps(VALID_PLAN),
        ):
            r = client.post(
                f"/api/admin/forge/templates/{template_id}/generate-plan",
                headers={"Authorization": f"Bearer {token}"},
                json={"suggested_act_count": 2},
            )

        assert r.status_code == 200, (
            f"Expected 200, got {r.status_code}: {r.text}\n"
            "Bug #1081: if 'no model set' in detail, model was stripped from llm_config."
        )
        body = r.json()
        assert body.get("ok") is True
        assert "gm_plan_json" in body

    def test_forge_polish_guard_fires_when_preset_has_no_model(self):
        """Backward compat: when active preset has no model, forge returns 400 with Polish message.

        adventure_forge.py:1304 guard must still catch real missing-model cases.
        This must pass both before AND after the fix.
        """
        from app.services.llm_service import set_runtime_config
        from app.main import app

        client = TestClient(app)
        token = _login(client)
        template_id = _get_or_create_template(client, token)

        # Runtime config with provider but NO model
        set_runtime_config("openai", "https://api.openai.com/v1", "", "test-key")

        r = client.post(
            f"/api/admin/forge/templates/{template_id}/generate-plan",
            headers={"Authorization": f"Bearer {token}"},
            json={"suggested_act_count": 2},
        )

        assert r.status_code == 400, (
            f"Expected 400 (Polish guard), got {r.status_code}: {r.text}"
        )
        detail = r.json().get("detail", "")
        assert "Brak modelu" in detail, (
            f"Expected Polish 'Brak modelu' message, got: {detail}"
        )
