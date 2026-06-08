"""TDD: Issue #387 D12 — Hub→Game navigation uses SPA showScreen, no page reload."""
import sys
import urllib.request

sys.path.insert(0, "/app")

FRONTEND_URL = "http://frontend:80"


def _fetch_js(path: str) -> str:
    with urllib.request.urlopen(f"{FRONTEND_URL}{path}", timeout=5) as resp:
        return resp.read().decode("utf-8", errors="replace")


# ─── Test główny ──────────────────────────────────────────────────────────────

def test_navigation_uses_show_screen_not_reload():
    """app.js używa showScreen() do nawigacji, nie location.reload/href."""
    js = _fetch_js("/front/js/app.js")
    assert "showScreen" in js, "showScreen function must exist"
    # No full-page reload calls for navigation
    assert "location.reload()" not in js, "app.js must not use location.reload() for navigation"
    assert "location.href = " not in js or js.count("location.href = ") == 0, \
        "app.js must not assign location.href for navigation"


def test_show_screen_function_exists():
    """Funkcja showScreen jest zdefiniowana w app.js."""
    js = _fetch_js("/front/js/app.js")
    assert "function showScreen(" in js or "showScreen = function" in js or \
           "showScreen(" in js and "function" in js, \
           "showScreen must be defined"


def test_game_screen_exists_in_html():
    """Ekran gry (#game-screen lub #campaign-screen) istnieje w HTML."""
    with urllib.request.urlopen(f"{FRONTEND_URL}/", timeout=5) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    assert "game-screen" in html or "campaign-screen" in html or "game" in html, \
        "game/campaign screen must exist in player UI HTML"


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_heroes_screen_exists():
    """Ekran bohaterów (#heroes-screen) nadal istnieje."""
    with urllib.request.urlopen(f"{FRONTEND_URL}/", timeout=5) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    assert "heroes-screen" in html or "heroes" in html, "heroes screen must exist"


def test_login_screen_exists():
    """Ekran logowania nadal istnieje."""
    with urllib.request.urlopen(f"{FRONTEND_URL}/", timeout=5) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    assert "login-screen" in html, "login screen must exist"
