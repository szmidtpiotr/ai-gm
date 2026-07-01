"""TDD: Issue #1060 — POST /api/admin/forge/validate-plan endpoint."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _beat(summary, *, objective_type=None, objective_value=None, optional=False, beat_key=None):
    b = {"summary": summary, "optional": optional}
    if objective_type:
        b["objective_type"] = objective_type
    if objective_value:
        b["objective_value"] = objective_value
    if beat_key:
        b["beat_key"] = beat_key
    return b


def _act(number, beats):
    return {"number": number, "title": f"Akt {number}", "key_beats": beats}


# ─── Unit tests for validate_gm_plan function ────────────────────────────────

class TestValidateGmPlanUnit:
    """Tests for the validate_gm_plan helper function."""

    def test_orphan_beat_returns_error(self):
        """Beat without objective_type and not optional → error."""
        from app.services.campaign_plan_runtime import validate_gm_plan
        plan = {
            "acts": [
                _act(1, [_beat("Zabij smoka")])  # no objective_type, not optional
            ]
        }
        result = validate_gm_plan(plan)
        assert result["errors"], "expected ≥1 error for orphan beat"
        assert any(i["type"] == "error" and "orphan" in i["code"] for i in result["issues"]), \
            "expected error with code containing 'orphan'"

    def test_optional_beat_no_objective_is_not_error(self):
        """Optional beat without objective_type is intentionally skippable — not an error."""
        from app.services.campaign_plan_runtime import validate_gm_plan
        plan = {
            "acts": [
                _act(1, [
                    _beat("Opcjonalny side quest", optional=True),
                    _beat("Wymagany z celem", objective_type="kill_enemy", objective_value="goblin"),
                ])
            ]
        }
        result = validate_gm_plan(plan)
        assert not result["errors"], f"unexpected errors: {result['errors']}"

    def test_beat_with_objective_type_no_value_returns_warning(self):
        """Beat with objective_type but no objective_value → warning (wildcard — may be intentional)."""
        from app.services.campaign_plan_runtime import validate_gm_plan
        plan = {
            "acts": [
                _act(1, [_beat("Zabij kogoś", objective_type="kill_enemy")])  # no objective_value
            ]
        }
        result = validate_gm_plan(plan)
        assert any(i["type"] == "warning" and "objective_value" in i["code"] for i in result["issues"]), \
            "expected warning for missing objective_value"
        # NOT an error — wildcard is allowed
        assert not result["errors"], f"unexpected errors: {result['errors']}"

    def test_act_without_beats_returns_error(self):
        """Act with empty key_beats → error."""
        from app.services.campaign_plan_runtime import validate_gm_plan
        plan = {"acts": [_act(1, [])]}
        result = validate_gm_plan(plan)
        assert result["errors"], "expected error for act without beats"
        assert any(i["type"] == "error" and "empty_act" in i["code"] for i in result["issues"]), \
            "expected error with code 'empty_act'"

    def test_valid_plan_no_issues(self):
        """Plan with proper beats returns no errors and no warnings."""
        from app.services.campaign_plan_runtime import validate_gm_plan
        plan = {
            "acts": [
                _act(1, [
                    _beat("Zabij goblina", objective_type="kill_enemy", objective_value="goblin"),
                    _beat("Side quest", optional=True),
                ]),
                _act(2, [
                    _beat("Odwiedź wieś", objective_type="visit_location", objective_value="wioska_kremlin"),
                ]),
            ]
        }
        result = validate_gm_plan(plan)
        assert not result["errors"], f"unexpected errors: {result['errors']}"
        assert not result["warnings"], f"unexpected warnings: {result['warnings']}"
        assert result["ok"]

    def test_issue_context_includes_act_and_beat(self):
        """Each issue includes act_number and beat_key for UI pinpointing."""
        from app.services.campaign_plan_runtime import validate_gm_plan
        plan = {
            "acts": [
                _act(1, [_beat("Orphan", beat_key="orphan_beat_1")])
            ]
        }
        result = validate_gm_plan(plan)
        issue = next((i for i in result["issues"] if i["type"] == "error"), None)
        assert issue is not None
        assert issue.get("act_number") == 1
        assert "orphan_beat_1" in str(issue.get("beat_key", ""))

    def test_empty_plan_returns_no_issues(self):
        """Null/empty plan (no acts) — no issues (plan may not have acts yet)."""
        from app.services.campaign_plan_runtime import validate_gm_plan
        assert validate_gm_plan(None)["ok"]
        assert validate_gm_plan({})["ok"]
        assert validate_gm_plan({"acts": []})["ok"]

    def test_multiple_errors_all_reported(self):
        """Multiple orphan beats across acts — all reported, not just first."""
        from app.services.campaign_plan_runtime import validate_gm_plan
        plan = {
            "acts": [
                _act(1, [_beat("Orphan A")]),
                _act(2, [_beat("Orphan B")]),
            ]
        }
        result = validate_gm_plan(plan)
        error_beats = [i["beat_key"] for i in result["issues"] if i["type"] == "error"]
        assert len(error_beats) >= 2, f"expected ≥2 errors, got {error_beats}"


# ─── API endpoint tests ───────────────────────────────────────────────────────

class TestValidatePlanEndpoint:
    """Tests for POST /api/admin/forge/validate-plan endpoint."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    @pytest.fixture
    def admin_token(self, client):
        r = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
        assert r.status_code == 200, f"dev-login failed: {r.text}"
        return r.json()["token"]

    def test_endpoint_exists(self, client):
        """POST /api/admin/forge/validate-plan exists — returns 401, not 404."""
        r = client.post("/api/admin/forge/validate-plan", json={"gm_plan_json": {}})
        assert r.status_code != 404, "endpoint does not exist"

    def test_endpoint_returns_issues_for_orphan_beat(self, client, admin_token):
        """Endpoint returns structured issues for a plan with orphan beat."""
        plan = {"acts": [_act(1, [_beat("Orphan")])]}
        r = client.post(
            "/api/admin/forge/validate-plan",
            json={"gm_plan_json": plan},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert "issues" in body
        assert any(i["type"] == "error" for i in body["issues"])

    def test_endpoint_returns_ok_for_valid_plan(self, client, admin_token):
        """Endpoint returns ok=true, empty issues for a valid plan."""
        plan = {
            "acts": [
                _act(1, [_beat("Goal", objective_type="kill_enemy", objective_value="boss")])
            ]
        }
        r = client.post(
            "/api/admin/forge/validate-plan",
            json={"gm_plan_json": plan},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert body["issues"] == []
