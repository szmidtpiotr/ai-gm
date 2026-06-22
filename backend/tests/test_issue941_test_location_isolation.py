"""TDD: Issue #941 — testowe lokacje 'test_loc_*' nie mogą wyciekać do generacji świata.

Root cause: POST /api/locations tworzy lokację jako canonical=1 (world-eligible),
a fixture testowy nie sprząta po sobie (return zamiast yield+DELETE), więc atrapy
'test_loc_<ts>' lądują w żywej bazie DEV i generator świata je wybiera.

Fix:
  A) helper is_test_location_key() rozpoznaje klucze fixtureów,
  B) POST wymusza canonical=0 dla takich kluczy → nie są kwalifikowalne do świata,
  C) fixture w test_phase8d_api_http.py sprząta (yield + DELETE).
"""
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.locations import is_test_location_key

client = TestClient(app)


def _admin_token() -> str:
    resp = client.post("/api/admin/dev-login", json={"username": "admin", "password": "admin"})
    if resp.status_code == 200:
        return resp.json()["token"]
    resp2 = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    if resp2.status_code == 200:
        return resp2.json()["token"]
    raise RuntimeError("Nie udało się uzyskać admin tokena")


# ─── Test główny: helper rozpoznaje klucze testowe ───────────────────────────

def test_is_test_location_key_recognizes_fixture_keys():
    """Klucz z prefiksem 'test_loc_' to atrapa fixtureowa → True."""
    # prefix 'test_'
    assert is_test_location_key("test_loc_1718900000.123") is True
    assert is_test_location_key("test_location_17821482") is True
    assert is_test_location_key("test_city_val") is True
    assert is_test_location_key("TEST_FLOW_42") is True  # case-insensitive
    # sufiks time.time() — atrapy parent_/child_ bez prefiksu 'test_'
    assert is_test_location_key("parent_immut_1782108133.1654") is True
    assert is_test_location_key("child_del_1782106957.6099145") is True
    assert is_test_location_key("parent_2_1782108148.988266") is True


def test_is_test_location_key_passes_real_keys():
    """Prawdziwe lokacje świata (polskie slugi) → False (nie ruszamy ich)."""
    assert is_test_location_key("karczma_pod_lwem") is False
    assert is_test_location_key("plac_centralny") is False
    assert is_test_location_key("las_szeptow") is False
    assert is_test_location_key(None) is False
    assert is_test_location_key("") is False


# ─── Test integracyjny: POST atrapy NIE jest world-eligible ──────────────────

def test_post_test_location_is_not_canonical():
    """POST /api/locations z kluczem test_loc_* tworzy lokację canonical=0
    (nie wpada do puli generacji świata). Sprząta po sobie."""
    token = _admin_token()
    key = f"test_loc_{time.time()}"
    resp = client.post(
        "/api/locations",
        json={"key": key, "label": "Updated Label Test", "location_type": "macro"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    try:
        body = resp.json()
        # canonical 0 (lub False) → nie kwalifikuje się do canonical=1 puli świata
        assert not body.get("canonical"), f"test_loc nie powinien być canonical: {body.get('canonical')}"
    finally:
        h = {"Authorization": f"Bearer {token}"}
        client.delete(f"/api/locations/{key}", headers=h)
        client.delete(f"/api/locations/{key}?force=true", headers=h)


def test_test_location_leaves_no_row_after_purge():
    """Acceptance #1 — atrapa po teardownie znika z bazy (force purge), brak sieroty."""
    token = _admin_token()
    h = {"Authorization": f"Bearer {token}"}
    key = f"test_loc_{time.time()}"
    assert client.post(
        "/api/locations",
        json={"key": key, "label": "Test Location", "location_type": "macro"},
        headers=h,
    ).status_code == 201
    # teardown jak w fixture: soft-delete → force purge
    client.delete(f"/api/locations/{key}", headers=h)
    client.delete(f"/api/locations/{key}?force=true", headers=h)
    # admin list (active_only=0 → także nieaktywne) NIE może zawierać klucza → fizycznie usunięty
    all_rows = client.get("/api/locations/admin/locations?active_only=0", headers=h).json()
    assert all(r.get("key") != key for r in all_rows), f"sierota {key} została w bazie"


# ─── Backward compat: zwykła lokacja nadal canonical=1 ───────────────────────

def test_post_normal_location_stays_canonical():
    """Zwykła (nietestowa) lokacja musi nadal być canonical=1 — bez regresji."""
    token = _admin_token()
    key = f"real_place_{time.time()}".replace(".", "_")
    resp = client.post(
        "/api/locations",
        json={"key": key, "label": "Karczma Pod Lwem", "location_type": "macro"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    try:
        body = resp.json()
        assert body.get("canonical"), "zwykła lokacja musi pozostać canonical=1"
    finally:
        h = {"Authorization": f"Bearer {token}"}
        client.delete(f"/api/locations/{key}", headers=h)
        client.delete(f"/api/locations/{key}?force=true", headers=h)
