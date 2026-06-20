"""TDD: Issue #834 — Mobile hex map scaling + edit block (frontend guard).

NOTE: #846 (M5) supersedes the M0-5 read-only approach. mobileReadonly guards
were intentionally removed and replaced by full touch support (pinch-zoom/pan/tap).
Tests updated accordingly — #834 approach (block) → #846 approach (enable with touch).
"""
import requests
import pytest

FRONTEND_URL = "http://frontend:80"


def test_map_js_touch_support_replaces_mobile_guard():
    """#846 (M5) replaces mobileReadonly with touch handlers — map.js must have touchstart."""
    r = requests.get(f"{FRONTEND_URL}/admin/sections/map.js", timeout=5)
    assert r.status_code == 200, "map.js not served by frontend"
    assert 'touchstart' in r.text, "map.js missing touch support (#846 M5 supersedes #834)"
    assert 'mobileReadonly' not in r.text, \
        "mobileReadonly still present — #846 M5 should have removed it"


def test_campaigns_js_touch_support_replaces_mobile_guard():
    """#846 (M5) replaces mobileReadonly with touch handlers in campaigns.js."""
    r = requests.get(f"{FRONTEND_URL}/admin/sections/campaigns.js", timeout=5)
    assert r.status_code == 200, "campaigns.js not served by frontend"
    assert 'touchstart' in r.text, "campaigns.js missing touch support (#846 M5)"
    assert 'mobileReadonly' not in r.text, \
        "mobileReadonly still present in campaigns.js — #846 M5 should have removed it"


def test_components_css_has_mobile_edit_notice():
    """components.css still includes .mobile-edit-notice styles (used by other contexts)."""
    r = requests.get(f"{FRONTEND_URL}/admin/shared/components.css", timeout=5)
    assert r.status_code == 200, "components.css not served by frontend"
    assert 'mobile-edit-notice' in r.text, "components.css missing .mobile-edit-notice (#834)"
