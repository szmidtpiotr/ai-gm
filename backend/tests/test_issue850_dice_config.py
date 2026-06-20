"""TDD: Issue #850 — Admin dice style configurator: GET/POST /api/admin/dice-config + public /api/game/dice-config."""
import sys
sys.path.insert(0, '/app')

import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

_ADMIN_TOKEN = None

def _get_admin_token():
    global _ADMIN_TOKEN
    if _ADMIN_TOKEN:
        return _ADMIN_TOKEN
    r = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    assert r.status_code == 200, f"admin login failed: {r.text}"
    _ADMIN_TOKEN = r.json()["token"]
    return _ADMIN_TOKEN


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_admin_get_dice_config_returns_defaults():
    """GET /api/admin/dice-config zwraca domyślny config z wymaganymi polami."""
    token = _get_admin_token()
    r = client.get("/api/admin/dice-config", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "config" in body, f"missing 'config' key: {body}"
    cfg = body["config"]
    # Required top-level keys
    assert "customColorset" in cfg, f"missing customColorset: {cfg}"
    assert "gravity_multiplier" in cfg, f"missing gravity_multiplier: {cfg}"
    assert "strength" in cfg
    assert "baseScale" in cfg
    assert "light_intensity" in cfg
    # customColorset sub-keys
    cc = cfg["customColorset"]
    assert "foreground" in cc
    assert "background" in cc
    assert "outline" in cc
    assert "texture" in cc
    assert "material" in cc


def test_admin_post_dice_config_saves_and_reads_back():
    """POST /api/admin/dice-config zapisuje config i GET go odczytuje."""
    token = _get_admin_token()
    new_cfg = {
        "customColorset": {
            "foreground": "#ff0000",
            "background": ["#000000"],
            "outline": "#ffffff",
            "texture": "fire",
            "material": "metal",
        },
        "gravity_multiplier": 300,
        "strength": 2.0,
        "baseScale": 80,
        "light_intensity": 1.5,
    }
    r = client.post(
        "/api/admin/dice-config",
        json={"config": new_cfg},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"POST failed: {r.status_code}: {r.text}"
    assert r.json().get("ok") is True

    # Read back
    r2 = client.get("/api/admin/dice-config", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    saved = r2.json()["config"]
    assert saved["customColorset"]["foreground"] == "#ff0000"
    assert saved["customColorset"]["texture"] == "fire"
    assert saved["gravity_multiplier"] == 300


def test_public_dice_config_returns_without_auth():
    """GET /api/game/dice-config dostępne bez auth — player frontend używa bez tokenu."""
    r = client.get("/api/game/dice-config")
    assert r.status_code == 200, f"public endpoint returned {r.status_code}: {r.text}"
    body = r.json()
    assert "config" in body, f"missing 'config': {body}"
    cfg = body["config"]
    assert "customColorset" in cfg
    assert "gravity_multiplier" in cfg


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_admin_dice_config_requires_auth():
    """Bez tokenu admin endpoint zwraca 401/403."""
    r = client.get("/api/admin/dice-config")
    assert r.status_code in (401, 403), f"expected auth error, got {r.status_code}"


def test_admin_post_dice_config_requires_auth():
    """POST bez tokenu → 401/403."""
    r = client.post("/api/admin/dice-config", json={"config": {}})
    assert r.status_code in (401, 403), f"expected auth error, got {r.status_code}"
