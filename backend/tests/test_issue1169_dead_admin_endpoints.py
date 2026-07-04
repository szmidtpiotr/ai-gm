"""TDD: Issue #1169 — revive dead admin API calls (frontend hit missing routes).

- POST /api/admin/campaigns/{id}/run-command  (was 404) — wire to command engine.
- POST /api/admin/ui/bg/{screen}/from-tile     (was 404) — set bg from a tile.
- map.js canonical PATCH must target /api/locations/admin/locations/{key} (PATCH
  exists there; /api/locations/{key} only had GET/PUT/DELETE → 405).
Per-user game-modes UI was retired (no backend), so no route is expected for it.
"""
from app.main import app


def _has_route(path: str, method: str) -> bool:
    for r in app.routes:
        if getattr(r, "path", None) == path and method in (getattr(r, "methods", None) or set()):
            return True
    return False


def test_run_command_endpoint_exists():
    assert _has_route("/api/admin/campaigns/{campaign_id}/run-command", "POST")


def test_bg_from_tile_endpoint_exists():
    assert _has_route("/api/admin/ui/bg/{screen}/from-tile", "POST")


def test_locations_admin_patch_exists():
    """The canonical-flag PATCH target map.js was repointed to."""
    assert _has_route("/api/locations/admin/locations/{key}", "PATCH")
