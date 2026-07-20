"""TDD: Issue #958 — brak endpointu i przycisku 'Wczytaj mapę (z kanonu)'."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from app.main import app

client = TestClient(app)


def _get_admin_token():
    r = client.post("/api/admin/dev-login", json={"username": "admin", "password": "admin"})
    if r.status_code == 200:
        return r.json()["token"]
    r2 = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    if r2.status_code == 200:
        return r2.json()["token"]
    raise RuntimeError("Nie udało się uzyskać admin tokena")


@pytest.fixture
def admin_token():
    return _get_admin_token()


# ── Test główny ────────────────────────────────────────────────────────────────

def test_restore_endpoint_exists_and_is_guarded(admin_token):
    """POST /map/restore istnieje; na niepustej mapie wariant BEZ ?region= → 403 (#1482).

    Legacy pełny restore kasował wszystkie krainy i wstawiał je jako 'kresy'.
    Od #1482 odtwarzamy per-krainę (?region=<klucz>); pełny wariant działa tylko
    na pustej mapie.
    """
    r = client.post(
        "/api/admin/world/map/restore",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code in (200, 403), f"Expected 200 (pusta mapa) lub 403 (guard), got {r.status_code}: {r.text}"
    if r.status_code == 403:
        assert "region" in r.json().get("detail", "").lower(), "403 musi kierować na wariant per-kraina"
    else:
        body = r.json()
        assert body.get("ok") is True, f"Expected ok=True, got: {body}"
        assert isinstance(body.get("count"), int) and body["count"] > 0, f"Expected count>0, got: {body}"


def test_restore_requires_admin_auth():
    """Brak tokenu → 401."""
    r = client.post("/api/admin/world/map/restore")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"


def test_restore_invalid_token_rejected():
    """Nieprawidłowy token → 401."""
    r = client.post(
        "/api/admin/world/map/restore",
        headers={"Authorization": "Bearer invalid_token_xyz"},
    )
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"


# ── Backward compat ─────────────────────────────────────────────────────────────

def test_snapshot_still_works(admin_token):
    """Istniejący endpoint POST /map/snapshot nadal działa po dodaniu restore."""
    r = client.post(
        "/api/admin/world/map/snapshot",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, f"snapshot broken: {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("ok") is True
    assert body.get("count", 0) > 0
