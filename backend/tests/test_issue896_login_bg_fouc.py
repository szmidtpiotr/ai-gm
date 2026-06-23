"""TDD: Issue #896 — login background FOUC fix (localStorage preload cache).

Root cause: CSS hardcodes --bg-screen-login: url(bg-login.jpg) → green monster
painted before JS runs. Fix:
  1. CSS default → none  (no hardcoded image)
  2. Inline <script> in <head> reads 'ai-gm-bg-cache' from localStorage
     and applies CSS vars synchronously before first paint
  3. loadBgSettings() saves fetched URLs to localStorage for next visit
"""
import httpx
import pytest

FRONTEND = "http://frontend:80"
BACKEND = "http://localhost:8000"


# ─── RED tests (fail before fix) ──────────────────────────────────────────────

def test_css_default_login_bg_not_hardcoded_to_image():
    """styles.css must NOT hardcode bg-login.jpg as --bg-screen-login default.

    This was the root cause of the FOUC: the browser painted the green monster
    from CSS before any JS ran. Fix: change default to 'none'.
    """
    resp = httpx.get(f"{FRONTEND}/css/styles.css", timeout=10)
    assert resp.status_code == 200, f"Could not fetch styles.css: {resp.status_code}"
    css = resp.text
    assert "bg-login.jpg" not in css, (
        "--bg-screen-login still uses bg-login.jpg (green monster) as CSS default. "
        "Change to 'none' in styles.css line ~98."
    )


def test_index_html_has_localstorage_bg_preload_script():
    """index.html <head> must contain inline script that reads 'ai-gm-bg-cache' from localStorage.

    This script runs synchronously before first paint, preventing FOUC for returning players.
    Verify: look for 'ai-gm-bg-cache' key name in the HTML source.
    """
    resp = httpx.get(f"{FRONTEND}/", timeout=10)
    assert resp.status_code == 200, f"Could not fetch index.html: {resp.status_code}"
    html = resp.text
    assert "ai-gm-bg-cache" in html, (
        "Missing localStorage bg preload script in index.html. "
        "Add inline <script> in <head> that reads 'ai-gm-bg-cache' and applies CSS vars."
    )


# ─── API contract test (verifies what localStorage depends on) ────────────────

def test_backgrounds_api_shape_supports_localstorage_cache():
    """GET /api/ui/backgrounds must return {backgrounds: {login: url_or_null, ...}}.

    The localStorage cache stores this exact shape. If the API changes shape,
    the preload script breaks.
    """
    resp = httpx.get(f"{BACKEND}/api/ui/backgrounds", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert "backgrounds" in data, "Response missing 'backgrounds' key"
    bgs = data["backgrounds"]
    assert isinstance(bgs, dict), "'backgrounds' must be a dict"
    assert "login" in bgs, "'backgrounds' dict missing 'login' key"
    login_url = bgs["login"]
    assert login_url is None or isinstance(login_url, str), (
        f"'login' must be a string URL or null, got {type(login_url)}"
    )
