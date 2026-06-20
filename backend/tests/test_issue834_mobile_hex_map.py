"""TDD: Issue #834 — Mobile hex map scaling + edit block (frontend guard)."""
import requests
import pytest

FRONTEND_URL = "http://frontend:80"


def test_map_js_has_mobile_readonly_guard():
    """map.js must include mobileReadonly guard to block hex edit on mobile."""
    r = requests.get(f"{FRONTEND_URL}/admin/sections/map.js", timeout=5)
    assert r.status_code == 200, "map.js not served by frontend"
    assert 'mobileReadonly' in r.text, "map.js missing mobileReadonly guard (#834)"


def test_campaigns_js_has_mobile_readonly_guard():
    """campaigns.js must include mobileReadonly guard for campaign hex overlay."""
    r = requests.get(f"{FRONTEND_URL}/admin/sections/campaigns.js", timeout=5)
    assert r.status_code == 200, "campaigns.js not served by frontend"
    assert 'mobileReadonly' in r.text, "campaigns.js missing mobileReadonly guard (#834)"


def test_components_css_has_mobile_edit_notice():
    """components.css must include .mobile-edit-notice styles for mobile map notice."""
    r = requests.get(f"{FRONTEND_URL}/admin/shared/components.css", timeout=5)
    assert r.status_code == 200, "components.css not served by frontend"
    assert 'mobile-edit-notice' in r.text, "components.css missing .mobile-edit-notice (#834)"


def test_map_js_has_mobile_notice_text():
    """map.js must insert the Polish mobile notice text."""
    r = requests.get(f"{FRONTEND_URL}/admin/sections/map.js", timeout=5)
    assert r.status_code == 200
    assert 'mobile-edit-notice' in r.text, "map.js missing mobile-edit-notice class usage (#834)"
