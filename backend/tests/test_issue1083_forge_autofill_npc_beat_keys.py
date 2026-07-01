"""TDD: Issue #1083 — forge generate-plan auto-fills required_npc_keys + required_beats.

After generate-plan saves gm_plan_json, backend should extract and save:
  - required_npc_keys = [npc["key"] for npc in plan.key_npcs]
  - required_beats    = [beat["beat_key"] for beat in all acts if not optional]

Only when those fields are currently empty (don't overwrite manual admin edits).
Response includes auto_filled_npc_keys + auto_filled_beat_keys.
"""
import sys
import os
import json
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from fastapi.testclient import TestClient


# ─── Minimal valid CampaignPlan returned by mocked LLM ───────────────────────

PLAN_WITH_NPCS_AND_BEATS = {
    "title": "Test plan #1083",
    "premise": "Bohater ratuje kuźnię przed sabotażem.",
    "acts": [
        {
            "number": 1,
            "title": "Akt 1",
            "summary": "Start przygody",
            "key_beats": [
                {"beat_key": "spotkaj_brunna", "summary": "Spotkaj Brunna", "objective_type": "talk_to_npc", "objective_value": "brunn", "optional": False},
                {"beat_key": "zbadaj_szkody", "summary": "Zbadaj kuźnię", "objective_type": "visit_location", "objective_value": "kuznia", "optional": False},
                {"beat_key": "opcjonalny_side", "summary": "Porozmawiaj z gośćmi", "optional": True},
            ],
        },
        {
            "number": 2,
            "title": "Akt 2",
            "summary": "Konfrontacja",
            "key_beats": [
                {"beat_key": "pokonaj_wyrostki", "summary": "Pokonaj sprawców", "objective_type": "kill_enemy", "objective_value": "wyrostek", "optional": False},
            ],
        },
    ],
    "endings": [
        {"id": "end_victory", "title": "Kuźnia ocalała", "type": "primary", "description": "Bohater wygrywa.", "requirements": ["spotkaj_brunna", "pokonaj_wyrostki"]},
    ],
    "key_npcs": [
        {"key": "brunn_zelaznorek", "name": "Brunn Żelaznoreki", "role": "Zleceniodawca", "importance": "critical", "deviation_consequence": "steer", "alive": True},
        {"key": "toma_czeladnik", "name": "Toma", "role": "Świadek", "importance": "supporting", "deviation_consequence": "ignore", "alive": True},
    ],
    "key_locations": [
        {"key": "kuznia", "name": "Kuźnia", "role": "Centrum wydarzeń", "visited": False},
    ],
    "engine_private": {
        "secret_predisposition_hint": "Sabotaż zlecony przez konkurenta.",
        "hidden_twist": "Wyrostek to wnuk karczmarz.",
        "contingency": "Jeśli bohater nie działa, kuźnia ginie.",
    },
}

EXPECTED_NPC_KEYS = ["brunn_zelaznorek", "toma_czeladnik"]
EXPECTED_BEAT_KEYS = ["spotkaj_brunna", "zbadaj_szkody", "pokonaj_wyrostki"]  # NOT opcjonalny_side


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _login(client: TestClient) -> str:
    r = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["token"]


def _get_or_create_empty_template(client: TestClient, token: str) -> int:
    """Get a template with empty required_npc_keys/required_beats, or create one."""
    hdrs = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/admin/forge/templates", headers=hdrs)
    assert r.status_code == 200
    for tpl in r.json().get("items", []):
        if not tpl.get("required_npc_keys") and not tpl.get("required_beats"):
            return tpl["id"]
    r2 = client.post("/api/admin/forge/templates", headers=hdrs, json={
        "title": "Test autofill #1083",
        "genre": "fantasy",
        "tone": "dark",
        "act_count": 2,
    })
    assert r2.status_code in (200, 201), f"create failed: {r2.text}"
    return r2.json()["id"]


# ─── RED: verifies the feature does NOT exist yet ─────────────────────────────

class TestIssue1083Red:
    """These tests FAIL before the fix: generate-plan does not fill required_npc_keys/beats."""

    def test_generate_plan_autofills_required_npc_keys(self):
        """RED→GREEN: after generate-plan, required_npc_keys in DB = extracted NPC keys."""
        from app.services.llm_service import set_runtime_config
        from app.main import app

        client = TestClient(app)
        token = _login(client)
        template_id = _get_or_create_empty_template(client, token)

        set_runtime_config("openai", "https://api.openai.com/v1", "gpt-5.4", "test-key")

        with patch("app.services.llm_service.OpenAIDriver.generate_chat", return_value=json.dumps(PLAN_WITH_NPCS_AND_BEATS)):
            r = client.post(
                f"/api/admin/forge/templates/{template_id}/generate-plan",
                headers={"Authorization": f"Bearer {token}"},
                json={"suggested_act_count": 2},
            )

        assert r.status_code == 200, f"generate-plan failed: {r.text}"

        # Verify DB was updated
        r2 = client.get(f"/api/admin/forge/templates/{template_id}", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200, f"get template failed: {r2.text}"
        tpl = r2.json()
        npc_keys = tpl.get("required_npc_keys") or []
        assert set(npc_keys) == set(EXPECTED_NPC_KEYS), (
            f"Expected required_npc_keys={EXPECTED_NPC_KEYS}, got {npc_keys}\n"
            "Bug #1083: generate-plan does not auto-fill required_npc_keys."
        )

    def test_generate_plan_autofills_required_beats(self):
        """RED→GREEN: after generate-plan, required_beats = non-optional beat_keys from all acts."""
        from app.services.llm_service import set_runtime_config
        from app.main import app

        client = TestClient(app)
        token = _login(client)
        template_id = _get_or_create_empty_template(client, token)

        set_runtime_config("openai", "https://api.openai.com/v1", "gpt-5.4", "test-key")

        with patch("app.services.llm_service.OpenAIDriver.generate_chat", return_value=json.dumps(PLAN_WITH_NPCS_AND_BEATS)):
            r = client.post(
                f"/api/admin/forge/templates/{template_id}/generate-plan",
                headers={"Authorization": f"Bearer {token}"},
                json={"suggested_act_count": 2},
            )

        assert r.status_code == 200, f"generate-plan failed: {r.text}"

        r2 = client.get(f"/api/admin/forge/templates/{template_id}", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200
        tpl = r2.json()
        beat_keys = tpl.get("required_beats") or []
        assert set(beat_keys) == set(EXPECTED_BEAT_KEYS), (
            f"Expected required_beats={EXPECTED_BEAT_KEYS}, got {beat_keys}\n"
            "Bug #1083: optional beats must be excluded; generate-plan does not auto-fill."
        )

    def test_optional_beats_excluded_from_required_beats(self):
        """Non-optional beats only: 'opcjonalny_side' (optional=True) must NOT be in required_beats."""
        from app.services.llm_service import set_runtime_config
        from app.main import app

        client = TestClient(app)
        token = _login(client)
        template_id = _get_or_create_empty_template(client, token)

        set_runtime_config("openai", "https://api.openai.com/v1", "gpt-5.4", "test-key")

        with patch("app.services.llm_service.OpenAIDriver.generate_chat", return_value=json.dumps(PLAN_WITH_NPCS_AND_BEATS)):
            r = client.post(
                f"/api/admin/forge/templates/{template_id}/generate-plan",
                headers={"Authorization": f"Bearer {token}"},
                json={"suggested_act_count": 2},
            )

        assert r.status_code == 200
        r2 = client.get(f"/api/admin/forge/templates/{template_id}", headers={"Authorization": f"Bearer {token}"})
        beat_keys = (r2.json().get("required_beats") or [])
        assert "opcjonalny_side" not in beat_keys, (
            f"Optional beat 'opcjonalny_side' must not be in required_beats, got: {beat_keys}"
        )


# ─── GREEN: backward compat / edge cases ──────────────────────────────────────

class TestIssue1083Compat:
    """These pass both before and after the fix."""

    def test_autofill_does_not_overwrite_manually_set_npc_keys(self):
        """If required_npc_keys already set manually, generate-plan must NOT overwrite them."""
        from app.services.llm_service import set_runtime_config
        from app.main import app

        client = TestClient(app)
        token = _login(client)
        hdrs = {"Authorization": f"Bearer {token}"}

        # Create template and manually set required_npc_keys
        r = client.post("/api/admin/forge/templates", headers=hdrs, json={
            "title": "Manual override #1083",
            "genre": "fantasy",
            "tone": "dark",
            "act_count": 2,
        })
        assert r.status_code in (200, 201), f"create failed: {r.text}"
        template_id = r.json()["id"]

        # Manually set required_npc_keys
        client.patch(
            f"/api/admin/forge/templates/{template_id}",
            headers=hdrs,
            json={"required_npc_keys": ["manual_npc_only"]},
        )

        set_runtime_config("openai", "https://api.openai.com/v1", "gpt-5.4", "test-key")

        with patch("app.services.llm_service.OpenAIDriver.generate_chat", return_value=json.dumps(PLAN_WITH_NPCS_AND_BEATS)):
            client.post(
                f"/api/admin/forge/templates/{template_id}/generate-plan",
                headers=hdrs,
                json={"suggested_act_count": 2},
            )

        r2 = client.get(f"/api/admin/forge/templates/{template_id}", headers=hdrs)
        npc_keys = r2.json().get("required_npc_keys") or []
        assert npc_keys == ["manual_npc_only"], (
            f"Manual required_npc_keys overwritten by auto-fill! Got: {npc_keys}"
        )
