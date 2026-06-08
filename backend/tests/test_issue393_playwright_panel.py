"""TDD: Issue #393 — Playwright regression panel: /playwright-specs + /playwright-run endpoints."""
import hashlib
import sqlite3
import sys

sys.path.insert(0, "/app")

import pytest
from fastapi.testclient import TestClient
from app.main import app

DB_PATH = "/data/ai_gm.db"
_TEST_ADMIN_TOKEN = "tdd_test_token_393_playwright"
client = TestClient(app)


def _admin_hash() -> str:
    return hashlib.sha256(_TEST_ADMIN_TOKEN.encode()).hexdigest()


@pytest.fixture(autouse=True)
def setup_teardown():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO admin_tokens (token_hash, label) VALUES (?, 'tdd_393')",
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


def _auth():
    return {"Authorization": f"Bearer {_TEST_ADMIN_TOKEN}"}


# ─── Test główny ──────────────────────────────────────────────────────────────

def test_playwright_specs_requires_auth():
    """GET /playwright-specs bez tokenu → 401."""
    resp = client.get("/api/test_runner/playwright-specs")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


def test_playwright_specs_returns_200():
    """GET /playwright-specs z admin tokenem → 200."""
    resp = client.get("/api/test_runner/playwright-specs", headers=_auth())
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


def test_playwright_specs_has_specs_key():
    """Response zawiera klucz 'specs' (lista)."""
    resp = client.get("/api/test_runner/playwright-specs", headers=_auth())
    assert resp.status_code == 200
    data = resp.json()
    assert "specs" in data, f"Missing 'specs' key: {list(data.keys())}"
    assert isinstance(data["specs"], list), f"specs must be list, got {type(data['specs'])}"


def test_playwright_specs_returns_non_empty():
    """Lista speców nie jest pusta — test-agent widzi pliki z ux/regression/."""
    resp = client.get("/api/test_runner/playwright-specs", headers=_auth())
    data = resp.json()
    specs = data.get("specs", [])
    if data.get("error"):
        pytest.skip(f"test-agent not reachable: {data['error'][:100]}")
    assert len(specs) > 0, "Expected at least one Playwright spec file"


def test_playwright_run_requires_auth():
    """POST /playwright-run bez tokenu → 401."""
    resp = client.post("/api/test_runner/playwright-run", json={})
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_playwright_specs_wrong_token_rejected():
    """Niepoprawny token → 401."""
    resp = client.get(
        "/api/test_runner/playwright-specs",
        headers={"Authorization": "Bearer wrong_token_xyz"},
    )
    assert resp.status_code == 401, f"Expected 401 for bad token, got {resp.status_code}"


def test_agent_health_endpoint_still_works():
    """GET /agent_health nadal odpowiada 200 (istniejący endpoint nie zepsuty)."""
    resp = client.get("/api/test_runner/agent_health", headers=_auth())
    assert resp.status_code == 200, f"agent_health broken: {resp.status_code}"
    data = resp.json()
    assert "agent_url" in data, f"Missing agent_url: {data}"
