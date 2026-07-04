"""TDD: Issue #1170 — public GET /api/spells catalog for Scholar level-up modal.

Frontend game.js hit /api/spells (404 swallowed → empty spell list). Add a
public catalog endpoint backed by spell_service.get_spell_catalog().
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_spell_catalog_endpoint_exists():
    """Route must be registered (was missing entirely)."""
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/spells" in paths


def test_spell_catalog_returns_spells_with_ui_fields():
    """GET /api/spells → {spells:[...]} where each row has key/label/description."""
    resp = client.get("/api/spells")
    assert resp.status_code == 200
    body = resp.json()
    assert "spells" in body and isinstance(body["spells"], list)
    assert body["spells"], "catalog should not be empty (game_config_spells seeded)"
    first = body["spells"][0]
    for field in ("key", "label", "description"):
        assert field in first, f"catalog row missing '{field}'"


def test_service_get_spell_catalog_only_active():
    """Service helper returns only active spells."""
    from app.services.spell_service import get_spell_catalog
    rows = get_spell_catalog()
    assert isinstance(rows, list)
    assert all(int(r.get("is_active", 1)) == 1 for r in rows)
