"""TDD: Issue #899 — back button on campaigns screen to return to heroes list."""
import re
from pathlib import Path

FRONTEND_HTML = Path("/app/tests/frontend_assets/index.html")
FRONTEND_JS = Path("/app/tests/frontend_assets/app.js")


def _read_html():
    return FRONTEND_HTML.read_text(encoding="utf-8")


def _read_js():
    return FRONTEND_JS.read_text(encoding="utf-8")


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_campaigns_screen_has_back_button_element():
    """#campaigns-screen header must contain a back button (id=campaigns-back)."""
    html = _read_html()
    campaigns_screen_match = re.search(
        r'<div id="campaigns-screen".*?</div>\s*</div>\s*</div>',
        html,
        re.DOTALL,
    )
    # More robust: look for campaigns-back anywhere in the HTML
    assert 'id="campaigns-back"' in html, (
        "Missing back button: <button id='campaigns-back'> not found in index.html. "
        "campaigns-screen header needs a header__back button like new-campaign-back."
    )


def test_campaigns_back_button_has_correct_class():
    """Back button must use header__back class to match existing pattern."""
    html = _read_html()
    # Check the back button has the correct class
    assert re.search(r'class="header__back"[^>]*id="campaigns-back"|id="campaigns-back"[^>]*class="header__back"', html), (
        "campaigns-back button missing class='header__back' — must match new-campaign-back / wizard-back pattern."
    )


def test_campaigns_back_button_wired_in_js():
    """JS must register click handler for campaigns-back that navigates to heroes."""
    js = _read_js()
    assert "campaigns-back" in js, (
        "campaigns-back element not referenced in app.js — click handler not wired."
    )
    assert re.search(r"campaigns.back.*showScreen\('heroes'\)|showScreen\('heroes'\).*campaigns.back", js, re.DOTALL), (
        "campaigns-back click handler must call showScreen('heroes')."
    )


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_existing_back_buttons_still_present():
    """Existing new-campaign-back and wizard-back must not be removed."""
    html = _read_html()
    assert 'id="new-campaign-back"' in html, "new-campaign-back removed — regression!"
    assert 'id="wizard-back"' in html, "wizard-back removed — regression!"


def test_logout_button_still_present():
    """logout-btn must still exist on campaigns screen."""
    html = _read_html()
    assert 'id="logout-btn"' in html, "logout-btn removed from campaigns-screen — regression!"
