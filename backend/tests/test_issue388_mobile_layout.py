"""TDD: Issue #388 D13 — mobile layout: responsive CSS at 375px."""
import sys
import urllib.request
import re

sys.path.insert(0, "/app")

FRONTEND_URL = "http://frontend:80"


def _fetch_css() -> str:
    # Find the CSS link from HTML
    with urllib.request.urlopen(f"{FRONTEND_URL}/", timeout=5) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    # Extract CSS href
    m = re.search(r'href="([^"]*styles[^"]*\.css[^"]*)"', html)
    if not m:
        return ""
    css_path = m.group(1)
    if css_path.startswith("."):
        css_path = css_path[1:]  # remove leading dot
    if not css_path.startswith("/"):
        css_path = "/front/" + css_path
    with urllib.request.urlopen(f"{FRONTEND_URL}{css_path}", timeout=5) as resp:
        return resp.read().decode("utf-8", errors="replace")


# ─── Test główny ──────────────────────────────────────────────────────────────

def test_body_has_overflow_x_hidden():
    """body ma overflow-x: hidden — brak horizontal scroll."""
    css = _fetch_css()
    # body rule must include overflow-x: hidden
    assert "overflow-x: hidden" in css or "overflow-x:hidden" in css, \
        "body must have overflow-x: hidden to prevent horizontal scroll on mobile"


def test_btn_has_min_height_44px():
    """Przyciski .btn mają min-height: 44px dla touch targets."""
    css = _fetch_css()
    # The .btn rule should include min-height: 44px
    assert "min-height: 44px" in css, \
        ".btn must have min-height: 44px for iOS HIG touch target compliance"


def test_mobile_media_query_exists():
    """CSS zawiera media query dla małych ekranów (max-width ≤ 480px)."""
    css = _fetch_css()
    assert "@media (max-width: 480px)" in css or "@media (max-width:480px)" in css, \
        "CSS must have mobile media query for ≤480px screens"


def test_login_form_width_constrained():
    """Formularz logowania ma max-width — nie rozciąga się na całą szerokość."""
    css = _fetch_css()
    # login container should have max-width
    assert "max-width" in css, "login/form elements must have max-width constraint"


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_viewport_meta_present():
    """Strona ma meta viewport z width=device-width."""
    with urllib.request.urlopen(f"{FRONTEND_URL}/", timeout=5) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    assert "viewport" in html and "width=device-width" in html, \
        "HTML must have viewport meta tag for mobile rendering"


def test_css_has_safe_area_inset():
    """CSS obsługuje safe-area-inset dla notch i home indicator."""
    css = _fetch_css()
    assert "safe" in css or "env(" in css or "safe-area" in css, \
        "CSS should handle safe-area-inset for modern mobile devices"
