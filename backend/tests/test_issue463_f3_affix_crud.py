"""TDD: Issue #463 — F3 Admin Affix Builder: POST/PATCH/DELETE /api/admin/affixes.

F3 adds CRUD endpoints for game_config_affixes so admin panel can create/edit/delete
affixes without direct DB access. Effect Object schema (F1) is used for effect_json.
"""
import sys
sys.path.insert(0, '/app')

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

_CLEANUP_KEY = "tdd463_test_affix"


def _token():
    r = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["token"]


def _headers():
    return {"Authorization": f"Bearer {_token()}"}


def _cleanup():
    client.delete(f"/api/admin/affixes/{_CLEANUP_KEY}", headers=_headers())


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_post_affix_creates_record():
    """POST /api/admin/affixes → 200, record appears in GET list."""
    _cleanup()
    h = _headers()
    payload = {
        "key": _CLEANUP_KEY,
        "name": "TDD Test Affix",
        "tier": 1,
        "allowed_item_types": "weapon",
        "effect_json": '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":1}]}',
        "is_active": True,
    }
    r = client.post("/api/admin/affixes", json=payload, headers=h)
    assert r.status_code == 200, f"POST /admin/affixes failed: {r.status_code} — {r.text}"
    body = r.json()
    assert "item" in body, f"response must have 'item': {body}"
    assert body["item"]["key"] == _CLEANUP_KEY

    # Verify in list
    lst = client.get("/api/admin/affixes", headers=h)
    assert lst.status_code == 200
    keys = [a["key"] for a in lst.json().get("items", [])]
    assert _CLEANUP_KEY in keys, f"new affix not in list: {keys}"

    _cleanup()


def test_post_affix_duplicate_key_returns_409():
    """POST with duplicate key → 409 Conflict."""
    _cleanup()
    h = _headers()
    payload = {"key": _CLEANUP_KEY, "name": "Dup", "tier": 1, "allowed_item_types": "weapon"}
    client.post("/api/admin/affixes", json=payload, headers=h)
    r2 = client.post("/api/admin/affixes", json=payload, headers=h)
    assert r2.status_code == 409, f"expected 409 on duplicate, got {r2.status_code}: {r2.text}"
    _cleanup()


def test_patch_affix_updates_name():
    """PATCH /api/admin/affixes/{key} → 200, name updated."""
    _cleanup()
    h = _headers()
    client.post("/api/admin/affixes", json={
        "key": _CLEANUP_KEY, "name": "Original", "tier": 1, "allowed_item_types": "weapon"
    }, headers=h)

    r = client.patch(f"/api/admin/affixes/{_CLEANUP_KEY}", json={"name": "Updated"}, headers=h)
    assert r.status_code == 200, f"PATCH failed: {r.status_code} — {r.text}"
    body = r.json()
    assert body["item"]["name"] == "Updated", f"name not updated: {body}"

    _cleanup()


def test_delete_affix_removes_record():
    """DELETE /api/admin/affixes/{key} → 200, record gone from list."""
    h = _headers()
    client.post("/api/admin/affixes", json={
        "key": _CLEANUP_KEY, "name": "ToDelete", "tier": 1, "allowed_item_types": "weapon"
    }, headers=h)

    r = client.delete(f"/api/admin/affixes/{_CLEANUP_KEY}", headers=h)
    assert r.status_code == 200, f"DELETE failed: {r.status_code} — {r.text}"

    lst = client.get("/api/admin/affixes", headers=h)
    keys = [a["key"] for a in lst.json().get("items", [])]
    assert _CLEANUP_KEY not in keys, "record still in list after delete"


def test_delete_affix_not_found_returns_404():
    """DELETE non-existent key → 404."""
    r = client.delete("/api/admin/affixes/does_not_exist_xyz", headers=_headers())
    assert r.status_code == 404, f"expected 404, got {r.status_code}"


def test_post_affix_invalid_effect_json_rejected():
    """POST with invalid effect_json type → 422."""
    _cleanup()
    h = _headers()
    payload = {
        "key": _CLEANUP_KEY,
        "name": "Bad Effect",
        "tier": 1,
        "allowed_item_types": "weapon",
        "effect_json": '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"UNKNOWN_TYPE","value":5}]}',
    }
    r = client.post("/api/admin/affixes", json=payload, headers=h)
    assert r.status_code == 422, f"expected 422 for invalid effect type, got {r.status_code}: {r.text}"
    _cleanup()


def test_post_affix_requires_auth():
    """POST without token → 401."""
    r = client.post("/api/admin/affixes", json={"key": "x", "name": "x", "tier": 1, "allowed_item_types": "weapon"})
    assert r.status_code == 401, f"expected 401, got {r.status_code}"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_get_affixes_still_returns_200():
    """Existing GET /api/admin/affixes → 200 with items list (regression)."""
    r = client.get("/api/admin/affixes", headers=_headers())
    assert r.status_code == 200, f"GET /admin/affixes regressed: {r.status_code}"
    assert "items" in r.json(), "response must have items list"
