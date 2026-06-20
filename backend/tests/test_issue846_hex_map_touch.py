"""TDD: Issue #846 — Hex mapa pełna obsługa dotykowa (M5).

Weryfikuje że M5 touch-support jest wdrożony:
- map.js ma handlery touchstart/touchmove/touchend z pinch-zoom i pan
- campaigns.js ma handlery dotykowe dla SVG hex-map
- OLD M0-5 blokady (mobileReadonly, static mobile-edit-notice) zostały usunięte
"""
import requests
import pytest

FRONTEND_URL = "http://frontend:80"


# ─── Test główny — nowe touch handlery ───────────────────────────────────────

def test_map_js_has_touch_start_handler():
    """map.js musi mieć touchstart handler dla pinch-zoom/pan na wb-svg (#846 M5)."""
    r = requests.get(f"{FRONTEND_URL}/admin/sections/map.js", timeout=5)
    assert r.status_code == 200
    assert 'touchstart' in r.text, "map.js brak touchstart — M5 touch support nie wdrożony"


def test_map_js_has_pinch_zoom_logic():
    """map.js musi mieć logikę pinch-zoom (obliczanie dystansu między palcami)."""
    r = requests.get(f"{FRONTEND_URL}/admin/sections/map.js", timeout=5)
    assert r.status_code == 200
    assert 'touches.length === 2' in r.text, "map.js brak pinch detection (2 touches)"
    assert 'Math.hypot' in r.text, "map.js brak Math.hypot — obliczanie dystansu pinch"


def test_map_js_touch_tap_calls_hex_click():
    """map.js touchend musi wywoływać _wbOnHexClick dla tap (bez ruchu)."""
    r = requests.get(f"{FRONTEND_URL}/admin/sections/map.js", timeout=5)
    assert r.status_code == 200
    assert '_wbOnHexClick' in r.text, "map.js brak wywołania _wbOnHexClick"
    assert 'touchend' in r.text, "map.js brak touchend handler"


def test_campaigns_js_has_touch_support():
    """campaigns.js musi mieć touch handlery dla hex mapy kampanii (#846 M5)."""
    r = requests.get(f"{FRONTEND_URL}/admin/sections/campaigns.js", timeout=5)
    assert r.status_code == 200
    assert 'touchstart' in r.text, "campaigns.js brak touchstart — M5 nie wdrożony"
    assert 'touchend' in r.text, "campaigns.js brak touchend"
    assert 'pinch' in r.text, "campaigns.js brak pinch-zoom logic"


def test_campaigns_js_tap_opens_hex_edit():
    """campaigns.js touchend tap musi wywoływać _showHexEditModal."""
    r = requests.get(f"{FRONTEND_URL}/admin/sections/campaigns.js", timeout=5)
    assert r.status_code == 200
    assert '_showHexEditModal' in r.text, "campaigns.js brak _showHexEditModal"


# ─── Backward compatibility — stare blokady M0-5 usunięte ───────────────────

def test_map_js_no_longer_has_mobile_readonly_guard():
    """M5 zastępuje M0-5: mobileReadonly blokada usunięta z map.js."""
    r = requests.get(f"{FRONTEND_URL}/admin/sections/map.js", timeout=5)
    assert r.status_code == 200
    assert 'mobileReadonly' not in r.text, \
        "map.js wciąż ma mobileReadonly — M5 powinien zastąpić blokadę M0-5"


def test_campaigns_js_no_static_mobile_edit_notice():
    """M5 zastępuje M0-5: statyczny komunikat 'edytuj na desktop' usunięty z campaigns.js."""
    r = requests.get(f"{FRONTEND_URL}/admin/sections/campaigns.js", timeout=5)
    assert r.status_code == 200
    assert 'Edycja hexów niedostępna na mobile' not in r.text, \
        "campaigns.js wciąż ma statyczny komunikat blokady M0-5"
