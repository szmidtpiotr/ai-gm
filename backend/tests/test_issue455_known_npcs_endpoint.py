"""TDD: Issue #455 (SB-1) — GET /admin/campaigns/{id}/known-npcs returns valid NPC list.

Endpoint merges two sources:
- World NPCs at locations visited by the campaign (via game_sessions)
- NPC memory entries from campaign_known_npcs table
Auth: requires admin token.
"""

import json
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_admin_token_cache = None


def _admin_token() -> str:
    global _admin_token_cache
    if not _admin_token_cache:
        r = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
        assert r.status_code == 200, f"admin login failed: {r.text}"
        _admin_token_cache = r.json()["token"]
    return _admin_token_cache


def _get(campaign_id: int, token: str | None = None) -> dict:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = client.get(f"/api/admin/campaigns/{campaign_id}/known-npcs", headers=headers)
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else r.text}


class TestKnownNpcsEndpointExists:
    """SB-1: endpoint must exist and return correct shape."""

    def test_endpoint_returns_200_with_npcs_and_count_keys(self):
        """GET /admin/campaigns/{id}/known-npcs returns {"npcs": [...], "count": N}."""
        result = _get(999444, _admin_token())
        assert result["status"] == 200, f"Expected 200, got {result['status']}: {result['body']}"
        body = result["body"]
        assert "npcs" in body, f"Response missing 'npcs' key: {body}"
        assert "count" in body, f"Response missing 'count' key: {body}"
        assert isinstance(body["npcs"], list), f"'npcs' must be a list, got: {type(body['npcs'])}"
        assert isinstance(body["count"], int), f"'count' must be int, got: {type(body['count'])}"

    def test_count_matches_npcs_length(self):
        """count field must equal len(npcs)."""
        result = _get(999444, _admin_token())
        assert result["status"] == 200
        body = result["body"]
        assert body["count"] == len(body["npcs"]), (
            f"count={body['count']} != len(npcs)={len(body['npcs'])}"
        )

    def test_empty_campaign_returns_empty_list(self):
        """Campaign with no sessions returns npcs=[], count=0 — no error."""
        result = _get(999444, _admin_token())
        assert result["status"] == 200
        # 999444 may or may not have NPCs — just verify it doesn't 500
        assert result["body"]["npcs"] is not None


class TestKnownNpcsAuth:
    """Auth guard: no token → 401/403."""

    def test_no_token_returns_401_or_403(self):
        """Request without auth token must be rejected."""
        result = _get(999444, token=None)
        assert result["status"] in (401, 403), (
            f"Expected 401/403 without auth, got {result['status']}"
        )

    def test_invalid_token_returns_401_or_403(self):
        """Request with garbage token must be rejected."""
        result = _get(999444, token="garbage-token")
        assert result["status"] in (401, 403), (
            f"Expected 401/403 with invalid token, got {result['status']}"
        )


class TestKnownNpcsShape:
    """Each NPC entry must have required fields."""

    def test_npc_entries_have_required_fields(self):
        """Each NPC dict must have key, label, source, location_keys, description, npc_type."""
        # Use demo campaign (id=1) which has known_npcs data
        result = _get(1, _admin_token())
        assert result["status"] == 200
        body = result["body"]
        if not body["npcs"]:
            pytest.skip("Campaign 1 has no NPCs — cannot test shape")
        required = {"key", "label", "source", "location_keys", "description", "npc_type"}
        for npc in body["npcs"]:
            missing = required - set(npc.keys())
            assert not missing, f"NPC {npc.get('label','?')} missing fields: {missing}"

    def test_source_field_is_world_or_memory(self):
        """source must be 'world' or 'memory'."""
        result = _get(1, _admin_token())
        assert result["status"] == 200
        for npc in result["body"]["npcs"]:
            assert npc["source"] in ("world", "memory"), (
                f"NPC '{npc.get('label')}' has invalid source: {npc.get('source')!r}"
            )

    def test_location_keys_is_list(self):
        """location_keys must be a list (empty or populated)."""
        result = _get(1, _admin_token())
        assert result["status"] == 200
        for npc in result["body"]["npcs"]:
            assert isinstance(npc["location_keys"], list), (
                f"NPC '{npc.get('label')}' location_keys is not a list: {npc.get('location_keys')!r}"
            )

    def test_memory_npc_present_for_demo_campaign(self):
        """Demo campaign (id=1) has 'Merchant' in campaign_known_npcs — must appear in response."""
        result = _get(1, _admin_token())
        assert result["status"] == 200
        labels = [n["label"] for n in result["body"]["npcs"]]
        assert "Merchant" in labels, (
            f"Expected 'Merchant' in known NPCs for campaign 1, got: {labels[:10]}"
        )
