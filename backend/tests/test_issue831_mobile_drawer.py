"""TDD: Issue #831 — Mobile drawer navigation (hamburger + 18 sections in overlay)."""
import requests


def _get_admin_html():
    resp = requests.get("http://frontend:80/admin/", timeout=5)
    resp.raise_for_status()
    return resp.text


def test_admin_html_has_mobile_drawer():
    """Admin /admin/ HTML must contain mobile drawer elements (hamburger, drawer, overlay)."""
    html = _get_admin_html()
    assert 'id="hamburger-btn"' in html, "Brak hamburger-btn — szuflada mobilna nie otworzy się"
    assert 'id="mobile-drawer"' in html, "Brak mobile-drawer — szuflada nie istnieje"
    assert 'id="drawer-overlay"' in html, "Brak drawer-overlay — nie można zamknąć szuflady"
    assert 'id="mobile-drawer-nav"' in html, "Brak mobile-drawer-nav — sekcje nie pojawią się"


def test_admin_sidebar_still_exists():
    """Desktop sidebar (admin-nav) must still exist — backward compat for >= 1024px."""
    html = _get_admin_html()
    assert 'id="admin-nav"' in html, "Sidebar admin-nav usunięty — regresja na desktopie"
    assert 'class="sidebar"' in html, "Element .sidebar usunięty — regresja na desktopie"
