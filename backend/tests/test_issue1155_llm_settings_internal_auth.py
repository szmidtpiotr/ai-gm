"""TDD: Issue #1155 — /users/{id}/llm-settings/internal nie może zwracać api_key bez auth.

Endpoint get_user_llm_settings_internal zwracał pełne ustawienia LLM (w tym prawdziwy
api_key serwera) bez żadnej autoryzacji. Ten test wymusza guard admina.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _admin_token():
    for u, p in (("admin", "admin"), ("demo", "demo")):
        r = client.post("/api/admin/dev-login", json={"username": u, "password": p})
        if r.status_code == 200:
            return r.json()["token"]
    raise RuntimeError("brak admin tokena")


# ─── Test główny — 401 bez tokena, brak wycieku api_key ──────────────────────

def test_internal_llm_settings_requires_token():
    """Bez tokena → 401, i żaden api_key nie wycieka w treści."""
    resp = client.get("/api/users/1/llm-settings/internal")
    assert resp.status_code == 401, f"endpoint przeszedł bez tokena (status {resp.status_code})"
    assert "api_key" not in resp.text


def test_internal_llm_settings_rejects_bad_token():
    """Zły token → 401."""
    resp = client.get("/api/users/1/llm-settings/internal",
                      headers={"Authorization": "Bearer nieprawidlowy"})
    assert resp.status_code == 401


# ─── Backward compat — admin z tokenem dalej dostaje dane ────────────────────

def test_internal_llm_settings_ok_with_token():
    """Z ważnym tokenem admina endpoint NIE zwraca 401."""
    tok = _admin_token()
    resp = client.get("/api/users/1/llm-settings/internal",
                      headers={"Authorization": f"Bearer {tok}"})
    assert resp.status_code != 401
