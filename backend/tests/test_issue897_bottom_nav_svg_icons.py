"""TDD: Issue #897 — bottom nav bar icons must be SVG, not emoji."""
import re
import urllib.request
import pytest

FRONTEND_URL = "http://frontend:80"
EMOJI_CHARS = ["🎲", "👤", "🎒"]

MBB_ICON_PATTERN = re.compile(
    r'<span class="mbb-btn__icon"[^>]*>(.*?)</span>', re.DOTALL
)


def _get_frontend_html():
    with urllib.request.urlopen(FRONTEND_URL, timeout=5) as resp:
        return resp.read().decode("utf-8")


def _get_icon_contents(html):
    return MBB_ICON_PATTERN.findall(html)


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_bottom_nav_icons_not_emoji():
    """mbb-btn__icon spans must not contain raw emoji characters."""
    html = _get_frontend_html()
    icons = _get_icon_contents(html)
    assert len(icons) == 3, f"Expected 3 mbb-btn__icon spans, found {len(icons)}"
    for content in icons:
        stripped = content.strip()
        for emoji in EMOJI_CHARS:
            assert emoji not in stripped, (
                f"mbb-btn__icon contains emoji '{emoji}' — replace with SVG"
            )


def test_bottom_nav_icons_have_svg():
    """mbb-btn__icon spans must contain inline SVG elements."""
    html = _get_frontend_html()
    icons = _get_icon_contents(html)
    assert len(icons) == 3, f"Expected 3 mbb-btn__icon spans, found {len(icons)}"
    for i, content in enumerate(icons):
        assert "<svg" in content, (
            f"mbb-btn__icon[{i}] has no SVG element. Content: {content.strip()!r}"
        )


def test_svg_uses_current_color():
    """SVG icons must use currentColor for automatic accent color inheritance."""
    html = _get_frontend_html()
    icons = _get_icon_contents(html)
    for i, content in enumerate(icons):
        if "<svg" in content:
            assert "currentColor" in content, (
                f"mbb-btn__icon[{i}] SVG missing currentColor — accent won't apply"
            )


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_bottom_nav_still_has_three_buttons():
    """Bottom nav must keep exactly 3 tabs regardless of icon change."""
    html = _get_frontend_html()
    game_btn = 'data-mbb="game"' in html
    char_btn = 'data-mbb="character"' in html
    inv_btn = 'data-mbb="inventory"' in html
    assert game_btn and char_btn and inv_btn, (
        "One or more mbb tabs missing — nav structure must be preserved"
    )


def test_bottom_nav_labels_unchanged():
    """Tab labels (Gra / Postać / Ekwipunek) must remain unchanged."""
    html = _get_frontend_html()
    for label in ["Gra", "Postać", "Ekwipunek"]:
        assert label in html, f"Tab label '{label}' missing from bottom nav"
