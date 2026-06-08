"""TDD: Issue #415 — Map endpoints: hex-terrain-config, generate, clear, locations-map."""
import hashlib
import sqlite3
import sys

sys.path.insert(0, "/app")

import pytest
from fastapi.testclient import TestClient
from app.main import app

DB_PATH = "/data/ai_gm.db"
_TEST_ADMIN_TOKEN = "tdd_test_token_415_map"
client = TestClient(app)


def _admin_hash() -> str:
    return hashlib.sha256(_TEST_ADMIN_TOKEN.encode()).hexdigest()


def _has_spawn_terrain() -> bool:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM hex_type_config WHERE is_active = 1 AND spawn_weight > 0"
        ).fetchone()
        return row and row["n"] > 0
    except Exception:
        return False
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def setup_teardown():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO admin_tokens (token_hash, label) VALUES (?, 'tdd_415')",
            (_admin_hash(),),
        )
        conn.commit()
    finally:
        conn.close()
    yield
    conn2 = sqlite3.connect(DB_PATH)
    try:
        conn2.execute("DELETE FROM admin_tokens WHERE token_hash = ?", (_admin_hash(),))
        conn2.commit()
    finally:
        conn2.close()


def _headers():
    return {"Authorization": f"Bearer {_TEST_ADMIN_TOKEN}"}


# ─── Auth guards ──────────────────────────────────────────────────────────────

def test_terrain_config_requires_auth():
    """GET /hex-terrain-config bez tokenu → 401."""
    resp = client.get("/api/admin/world/hex-terrain-config")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


def test_locations_map_requires_auth():
    """GET /locations-map bez tokenu → 401."""
    resp = client.get("/api/admin/world/locations-map")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


def test_generate_requires_auth():
    """POST /generate bez tokenu → 401."""
    resp = client.post("/api/admin/world/generate", json={"seed": 1, "radius": 2})
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


def test_clear_requires_auth():
    """DELETE /clear bez tokenu → 401."""
    resp = client.delete("/api/admin/world/clear")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


# ─── Test główny ──────────────────────────────────────────────────────────────

def test_terrain_config_returns_list():
    """GET /hex-terrain-config → 200 + lista obiektów."""
    resp = client.get("/api/admin/world/hex-terrain-config", headers=_headers())
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert isinstance(data, list), f"Expected list, got: {type(data)}"


def test_locations_map_returns_data():
    """GET /locations-map → 200 z kluczami 'locations' i 'pending_count'."""
    resp = client.get("/api/admin/world/locations-map", headers=_headers())
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "locations" in data, f"Missing 'locations' key: {list(data.keys())}"
    assert "pending_count" in data, f"Missing 'pending_count': {list(data.keys())}"
    assert isinstance(data["locations"], list)
    assert isinstance(data["pending_count"], int)


def test_world_generate_returns_valid_response():
    """POST /generate → 200 z hexes_created, counts, seed."""
    if not _has_spawn_terrain():
        pytest.skip("No terrain types with spawn_weight > 0 — cannot test world generation")
    resp = client.post(
        "/api/admin/world/generate",
        json={"seed": 999415, "radius": 2},
        headers=_headers(),
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "hexes_created" in data, f"Missing hexes_created: {data}"
    assert "counts" in data, f"Missing counts: {data}"
    assert "seed" in data, f"Missing seed: {data}"
    assert isinstance(data["hexes_created"], int)
    assert data["seed"] == 999415


def test_world_generate_radius_limit():
    """POST /generate z radius > 50 → 400."""
    resp = client.post(
        "/api/admin/world/generate",
        json={"seed": 1, "radius": 51},
        headers=_headers(),
    )
    assert resp.status_code == 400, f"Expected 400 for radius > 50, got {resp.status_code}"


def test_world_clear_returns_deleted_count():
    """DELETE /clear → 200 z 'hexes_deleted'."""
    if _has_spawn_terrain():
        # Generate a tiny world first so there's something to clear
        client.post(
            "/api/admin/world/generate",
            json={"seed": 12345415, "radius": 1},
            headers=_headers(),
        )
    resp = client.delete("/api/admin/world/clear", headers=_headers())
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "hexes_deleted" in data, f"Missing hexes_deleted: {data}"
    assert isinstance(data["hexes_deleted"], int)


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_world_map_endpoint_still_works():
    """GET /api/admin/world/map → 200 (istniejący endpoint nie zepsuty przez #415)."""
    resp = client.get("/api/admin/world/map", headers=_headers())
    assert resp.status_code == 200, f"GET /map broken: {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "hexes" in data, f"Missing 'hexes' in map response"


def test_hex_types_endpoint_still_works():
    """GET /api/admin/world/hex-types → 200 (istniejący endpoint)."""
    resp = client.get("/api/admin/world/hex-types", headers=_headers())
    assert resp.status_code == 200, f"GET /hex-types broken: {resp.status_code}"
    data = resp.json()
    assert "hex_types" in data, f"Missing hex_types key"
