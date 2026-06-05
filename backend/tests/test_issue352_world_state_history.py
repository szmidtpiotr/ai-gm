"""TDD: Issue #352 — B6 Admin panel: World State history viewer (backend endpoints)."""
import json
import sqlite3
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.routers.world_state_history import _require_admin

DB_PATH = "/data/ai_gm.db"
_FAKE_CAMPAIGN_ID = 999_352


def _cleanup():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "DELETE FROM world_state_snapshots WHERE campaign_id = ?",
            (_FAKE_CAMPAIGN_ID,),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client():
    """TestClient with admin auth bypassed."""
    from app.main import app
    app.dependency_overrides[_require_admin] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.pop(_require_admin, None)


def _insert_snapshot(turn_number: int, source: str = "auto", data: dict | None = None):
    payload = data or {
        "campaign_id": _FAKE_CAMPAIGN_ID,
        "turn_number": turn_number,
        "scene_enemies": [{"key": "goblin", "name": "Goblin", "hp": 10}],
        "scene_npcs": [],
        "active_quests": [],
        "player_conditions": [],
        "scene_cleared": False,
    }
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT INTO world_state_snapshots
               (campaign_id, turn_number, snapshot_json, snapshot_source)
               VALUES (?, ?, ?, ?)""",
            (_FAKE_CAMPAIGN_ID, turn_number, json.dumps(payload), source),
        )
        conn.commit()
    finally:
        conn.close()


# ─── Test 1: GET /api/admin/campaigns/{id}/world-state returns snapshot list ──

def test_world_state_endpoint_returns_snapshot_list(client):
    """GET /api/admin/campaigns/{id}/world-state must return list of snapshots."""
    _cleanup()
    _insert_snapshot(1)
    _insert_snapshot(2)

    resp = client.get(f"/api/admin/campaigns/{_FAKE_CAMPAIGN_ID}/world-state")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "snapshots" in data, f"Missing 'snapshots' key in response: {data}"
    assert isinstance(data["snapshots"], list)
    assert len(data["snapshots"]) >= 2

    _cleanup()


# ─── Test 2: Response contains required snapshot fields ──────────────────────

def test_snapshot_list_has_required_fields(client):
    """Each snapshot in list must have id, turn_number, snapshot_source, created_at, snapshot_json."""
    _cleanup()
    _insert_snapshot(5, source="combat_end")

    resp = client.get(f"/api/admin/campaigns/{_FAKE_CAMPAIGN_ID}/world-state")
    assert resp.status_code == 200
    snap = resp.json()["snapshots"][0]

    for field in ("id", "turn_number", "snapshot_source", "created_at", "snapshot_json"):
        assert field in snap, f"Missing field '{field}' in snapshot: {snap.keys()}"

    _cleanup()


# ─── Test 3: GET /api/admin/campaigns/{id}/world-state/latest ────────────────

def test_latest_endpoint_returns_most_recent_snapshot(client):
    """GET /api/admin/campaigns/{id}/world-state/latest returns single latest snapshot."""
    _cleanup()
    _insert_snapshot(1)
    _insert_snapshot(10)
    _insert_snapshot(5)

    resp = client.get(f"/api/admin/campaigns/{_FAKE_CAMPAIGN_ID}/world-state/latest")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert "snapshot" in data, f"Unexpected response shape: {data}"
    assert data["snapshot"] is not None
    assert data["snapshot"]["turn_number"] == 5  # last inserted → newest id

    _cleanup()


# ─── Test 4: Empty state (no snapshots) returns empty list, not 404 ──────────

def test_empty_snapshot_list_returns_200_not_404(client):
    """Campaign with no snapshots → 200 with empty snapshots list, not 404."""
    _cleanup()

    resp = client.get(f"/api/admin/campaigns/{_FAKE_CAMPAIGN_ID}/world-state")
    assert resp.status_code == 200
    data = resp.json()
    assert "snapshots" in data
    assert data["snapshots"] == []

    _cleanup()


# ─── Test 5: Returns max 20 snapshots ────────────────────────────────────────

def test_snapshot_list_capped_at_20(client):
    """List endpoint returns max 20 snapshots even if more exist."""
    _cleanup()
    for i in range(25):
        _insert_snapshot(i + 1)

    resp = client.get(f"/api/admin/campaigns/{_FAKE_CAMPAIGN_ID}/world-state")
    assert resp.status_code == 200
    snaps = resp.json()["snapshots"]
    assert len(snaps) <= 20, f"Expected max 20, got {len(snaps)}"

    _cleanup()


# ─── Test 6: snapshot_json is parsed dict, not raw string ────────────────────

def test_snapshot_json_is_parsed_not_string(client):
    """snapshot_json in response must be a dict, not a JSON string."""
    _cleanup()
    _insert_snapshot(3)

    resp = client.get(f"/api/admin/campaigns/{_FAKE_CAMPAIGN_ID}/world-state")
    snap = resp.json()["snapshots"][0]
    assert isinstance(snap["snapshot_json"], dict), \
        f"snapshot_json should be dict, got {type(snap['snapshot_json'])}: {snap['snapshot_json']}"

    _cleanup()
