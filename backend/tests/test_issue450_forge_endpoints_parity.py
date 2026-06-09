"""TDD: Issue #450 (FADM-P14) — Port Forge do modularnego /admin/.

UI-only port → backend NIETKNIĘTY. Te testy to regression lock kontraktu forge endpoints:
gwarantują że port UI nie wymagał (i nie spowodował) zmiany backendu. Forge admin endpoints
muszą zostać auth-gated, public campaign-templates publiczne.
"""
import sys
sys.path.insert(0, '/app')

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ─── Kontrakt: forge admin endpoints auth-gated ──────────────────────────────

def test_forge_templates_requires_admin():
    """GET /api/admin/forge/templates bez tokenu → 401 (nie 404 — endpoint istnieje)."""
    resp = client.get("/api/admin/forge/templates")
    assert resp.status_code == 401, f"expected 401, got {resp.status_code}"


def test_forge_hooks_requires_admin():
    """GET /api/admin/forge/hooks bez tokenu → 401."""
    resp = client.get("/api/admin/forge/hooks")
    assert resp.status_code == 401, f"expected 401, got {resp.status_code}"


def test_forge_encounters_requires_admin():
    """GET /api/admin/forge/encounters bez tokenu → 401."""
    resp = client.get("/api/admin/forge/encounters")
    assert resp.status_code == 401, f"expected 401, got {resp.status_code}"


# ─── Kontrakt: public campaign-templates dostępne dla gracza ─────────────────

def test_public_campaign_templates_open():
    """GET /api/campaign-templates → 200 (publiczne, gracz wybiera gotową kampanię)."""
    resp = client.get("/api/campaign-templates")
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "items" in body, "response must have items list"


# ─── Forge endpoints z tokenem działają (round-trip) ─────────────────────────

def test_forge_templates_with_token_ok():
    """Z ważnym tokenem admina GET /forge/templates → 200 + lista."""
    login = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    assert login.status_code == 200
    token = login.json()["token"]
    resp = client.get("/api/admin/forge/templates", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, f"forge templates with token failed: {resp.text}"
