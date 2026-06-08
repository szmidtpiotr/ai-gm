"""TDD: Issue #449 (FADM-P13) — Port ekranu logowania admina do modularnego shella /admin/.

Backend contract tests dla frontendu: endpoint dev-login musi zwracać username (do wyświetlenia
w sidebar) + pełny round-trip login→verify→logout.
"""
import sys
sys.path.insert(0, '/app')

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_admin_login_returns_username():
    """POST /admin/dev-login zwraca pole 'username' — potrzebne do wyświetlenia w modularnym shellu."""
    resp = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    assert resp.status_code == 200, f"login failed: {resp.text}"
    body = resp.json()
    assert body.get("ok") is True
    assert "token" in body, "response missing token"
    # FAILS z obecnym kodem: response tylko {ok, token}, brakuje 'username'
    assert "username" in body, "response must include username for modular shell sidebar display"
    assert body["username"] == "demo", f"wrong username in response: {body.get('username')}"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_admin_login_invalid_creds_returns_401():
    """Błędne hasło → 401 (kontrakt frontendu dla obsługi błędu logowania)."""
    resp = client.post("/api/admin/dev-login", json={"username": "demo", "password": "wrong_pass_xyz"})
    assert resp.status_code == 401, f"expected 401, got {resp.status_code}: {resp.text}"


def test_admin_verify_without_token_returns_401():
    """GET /admin/verify bez tokenu → 401 — wyzwala 'admin-unauthorized' w shellu."""
    resp = client.get("/api/admin/verify")
    assert resp.status_code == 401, f"expected 401, got {resp.status_code}"


def test_admin_login_roundtrip_verify():
    """Login → token → verify 200 (pełny round-trip który frontend wykonuje po zalogowaniu)."""
    login_resp = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    verify_resp = client.get("/api/admin/verify", headers={"Authorization": f"Bearer {token}"})
    assert verify_resp.status_code == 200, f"verify after login failed: {verify_resp.text}"
