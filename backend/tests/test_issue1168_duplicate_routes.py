"""TDD: Issue #1168 — remove duplicate route registrations.

1. POST /api/campaigns/{id}/combat/start — combat.py owns it (branches to MP
   internally). The shadowed copy in multiplayer.py must be gone.
2. GET /api/admin/images/models — defined twice in admin_images.py; must be one.
"""
from app.main import app


def _routes_for(path: str, method: str):
    out = []
    for r in app.routes:
        if getattr(r, "path", None) == path and method in (getattr(r, "methods", None) or set()):
            out.append(r)
    return out


def test_combat_start_registered_once():
    """Exactly one POST route for the combat/start path (no MP duplicate)."""
    routes = _routes_for("/api/campaigns/{campaign_id}/combat/start", "POST")
    assert len(routes) == 1, f"expected 1 combat/start route, found {len(routes)}"
    # Owner must be combat.py's handler, which fans out to MP internally.
    assert routes[0].endpoint.__name__ == "post_start_combat"


def test_images_models_registered_once():
    """Exactly one GET route for /api/admin/images/models."""
    routes = _routes_for("/api/admin/images/models", "GET")
    assert len(routes) == 1, f"expected 1 images/models route, found {len(routes)}"
