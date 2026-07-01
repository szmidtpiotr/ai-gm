"""TDD: Issue #1079 — przywrócenie usuwania lokacji w panelu admin (regresja noDelete:true)."""
import requests
import pytest

FRONTEND_URL = "http://frontend:80"


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_map_js_nodelete_flag_removed():
    """map.js nie powinien blokować usuwania lokacji — flaga noDelete musi zniknąć z _ROW_REGISTRY."""
    r = requests.get(f"{FRONTEND_URL}/admin/sections/map.js", timeout=5)
    assert r.status_code == 200, "map.js nie jest serwowany przez frontend"
    assert 'noDelete:true' not in r.text, (
        "Flaga noDelete:true nadal obecna w map.js — usuwanie lokacji jest zablokowane (#1079). "
        "Usuń noDelete:true z _ROW_REGISTRY['locations-table']."
    )


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_map_js_locations_table_config_intact():
    """Konfiguracja locations-table w _ROW_REGISTRY musi być nienaruszona po usunięciu noDelete."""
    r = requests.get(f"{FRONTEND_URL}/admin/sections/map.js", timeout=5)
    assert r.status_code == 200, "map.js nie jest serwowany przez frontend"
    content = r.text
    assert "'locations-table'" in content or '"locations-table"' in content, \
        "Brak klucza locations-table w _ROW_REGISTRY"
    assert "/api/admin/locations" in content, \
        "Brak endpointu /api/admin/locations w konfiguracji"
    assert "_loadLocations" in content, \
        "Brak reload callback _loadLocations"
