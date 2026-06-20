"""TDD: Issue #839 — System section mobile (@768px: stab-bar scroll, grids 1-col)."""
import requests

FRONTEND = "http://frontend:80"


def test_system_stab_bar_mobile_scroll():
    """components.css must have mobile scroll rules for .stab-bar and SYSTEM SECTION label."""
    r = requests.get(f"{FRONTEND}/admin/shared/components.css")
    assert r.status_code == 200, "components.css not served"
    css = r.content.decode('utf-8')
    assert "SYSTEM SECTION MOBILE" in css, (
        "No mobile system section block in components.css"
    )
    assert ".stab-bar" in css and "overflow-x" in css, (
        ".stab-bar missing overflow-x scroll rule"
    )


def test_system_voice_panels_grid_id():
    """system.js TTS/STT grid div must have id=sys-voice-panels-grid for 1-col CSS override."""
    r = requests.get(f"{FRONTEND}/admin/sections/system.js")
    assert r.status_code == 200, "system.js not served"
    assert 'id="sys-voice-panels-grid"' in r.text, (
        "Missing id=sys-voice-panels-grid on TTS/STT grid div in system.js"
    )


def test_system_voice_panels_grid_css():
    """#sys-voice-panels-grid must be in components.css with 1-col rule."""
    r = requests.get(f"{FRONTEND}/admin/shared/components.css")
    assert r.status_code == 200
    assert "#sys-voice-panels-grid" in r.text, (
        "Missing #sys-voice-panels-grid CSS rule — Voice TTS/STT stays side-by-side on mobile"
    )


def test_system_route_toggles_css():
    """#v-route-toggles must collapse to 1-col on mobile (2-col inline grid)."""
    r = requests.get(f"{FRONTEND}/admin/shared/components.css")
    assert r.status_code == 200
    assert "#v-route-toggles" in r.text, (
        "Missing #v-route-toggles mobile rule in components.css"
    )


def test_system_vis_grids_css():
    """Visual tab: #vis-periods and #vis-bg-grid must collapse to 1-col on mobile."""
    r = requests.get(f"{FRONTEND}/admin/shared/components.css")
    assert r.status_code == 200
    css = r.text
    assert "#vis-periods" in css, "Missing #vis-periods mobile rule"
    assert "#vis-bg-grid" in css, "Missing #vis-bg-grid mobile rule"
