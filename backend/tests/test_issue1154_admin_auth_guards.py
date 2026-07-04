"""TDD: Issue #1154 — routery adminowe bez autoryzacji muszą zwracać 401 bez tokena.

Kilka routerów pod /api/admin/* (i mutujący hex_chain_travel) nie deklarowało
Depends(require_admin_token) — każdy anonimowy request przechodził (HTTP 200).
Ten test wymusza 401 na każdym z nich, zachowując otwarte publiczne endpointy.
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


# ─── Test główny — każdy dotknięty endpoint 401 bez tokena ───────────────────

# (metoda, ścieżka, opcjonalne body)
GUARDED = [
    ("get", "/api/admin/world/pending/counts", None),          # world_review
    ("get", "/api/admin/images/config", None),                 # admin_images
    ("get", "/api/admin/sandbox/heroes", None),                # sandbox
    ("get", "/api/admin/rest-sandbox/heroes", None),           # rest_sandbox
    ("get", "/api/admin/game-mechanics/content", None),        # game_mechanics
    ("get", "/api/admin/ui-texts", None),                      # admin_ui_texts admin_router
    ("get", "/api/admin/visual", None),                        # admin_visual admin_router
    ("post", "/api/admin/world/campaigns/1/hex-travel",
     {"character_id": 1, "destination_q": 0, "destination_r": 0}),  # hex_chain_travel
]


@pytest.mark.parametrize("method,path,body", GUARDED)
def test_guarded_endpoint_requires_token(method, path, body):
    """Bez nagłówka Authorization → 401 (a nie 200)."""
    resp = getattr(client, method)(path, json=body) if body else getattr(client, method)(path)
    assert resp.status_code == 401, f"{path} przeszło bez tokena (status {resp.status_code})"


@pytest.mark.parametrize("method,path,body", GUARDED)
def test_guarded_endpoint_rejects_bad_token(method, path, body):
    """Zły token → 401."""
    h = {"Authorization": "Bearer nieprawidlowy"}
    resp = (getattr(client, method)(path, json=body, headers=h) if body
            else getattr(client, method)(path, headers=h))
    assert resp.status_code == 401, f"{path} przyjęło zły token (status {resp.status_code})"


# ─── Backward compat — z tokenem przechodzi (nie 401), publiczne otwarte ─────

def test_admin_endpoint_ok_with_token():
    """Z ważnym tokenem endpoint admina NIE zwraca 401."""
    tok = _admin_token()
    r = client.get("/api/admin/world/pending/counts",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code != 401


def test_public_ui_texts_still_open():
    """Publiczny GET /api/ui/texts musi zostać dostępny bez tokena."""
    r = client.get("/api/ui/texts")
    assert r.status_code != 401


def test_public_visual_still_open():
    """Publiczny GET /api/visual/public musi zostać dostępny bez tokena."""
    r = client.get("/api/visual/public")
    assert r.status_code != 401
