"""TDD: Issues #1167 + #1188 — Warsztat kampanii RESTORE, Bank Pomysłów RETIRE.

- campaign_workshop.py router must be registered again (tab 🔧 Warsztat was 404).
- ideas_workshop.py (Bank Pomysłów) must be retired: module gone, no /api/admin/ideas routes.
"""
import importlib

import pytest

from app.main import app


def _paths() -> set[str]:
    return {getattr(r, "path", "") for r in app.routes}


# ─── Warsztat RESTORE ────────────────────────────────────────────────────────

def test_campaign_workshop_router_registered():
    """🔧 Warsztat endpoints must be mounted again (were 404 after ca997132)."""
    paths = _paths()
    assert "/api/admin/campaigns/{campaign_id}/workshop/message" in paths
    assert "/api/admin/campaigns/{campaign_id}/workshop/apply" in paths


# ─── Bank Pomysłów RETIRE ────────────────────────────────────────────────────

def test_ideas_workshop_module_removed():
    """Bank Pomysłów backend retired — module must no longer import."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.routers.ideas_workshop")


def test_no_ideas_routes_registered():
    """No /api/admin/ideas* route may survive the retire."""
    assert not [p for p in _paths() if p.startswith("/api/admin/ideas")]
