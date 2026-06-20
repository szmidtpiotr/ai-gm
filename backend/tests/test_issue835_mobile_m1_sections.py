"""TDD: Issue #835 — Mobile M1: Overview/Invites/Push sections — responsive fixes.

Frontend files are copied into /app/tests/frontend_assets/ before running:
  docker cp frontend/admin/shared/components.css  ai-gm-dev-backend-1:/app/tests/frontend_assets/components.css
  docker cp frontend/admin/sections/overview.js   ai-gm-dev-backend-1:/app/tests/frontend_assets/overview.js
  docker cp frontend/admin/sections/push.js       ai-gm-dev-backend-1:/app/tests/frontend_assets/push.js
"""
import os
import re

_ASSET_DIR = os.path.join(os.path.dirname(__file__), "frontend_assets")
CSS_FILE = os.path.join(_ASSET_DIR, "components.css")
OVERVIEW_JS = os.path.join(_ASSET_DIR, "overview.js")
PUSH_JS = os.path.join(_ASSET_DIR, "push.js")


# ─── Section tabs mobile scroll ──────────────────────────────────────────────

def test_section_tabs_mobile_overflow_scroll():
    """components.css must have overflow-x:auto on .section-tabs inside @media max-width:768px."""
    with open(CSS_FILE) as f:
        css = f.read()

    # Find all @media (max-width: 768px) blocks and look for .section-tabs
    media_blocks = re.findall(r'@media\s*\(max-width:\s*768px\).*?(?=@media|\Z)', css, re.DOTALL)
    found = any(".section-tabs" in block and "overflow-x" in block for block in media_blocks)
    assert found, (
        ".section-tabs is missing overflow-x rule in @media (max-width:768px). "
        "7 overview tabs overflow on 390px screen."
    )


def test_section_tabs_webkit_overflow():
    """components.css must also have -webkit-overflow-scrolling:touch for .section-tabs mobile."""
    with open(CSS_FILE) as f:
        css = f.read()
    assert "-webkit-overflow-scrolling: touch" in css, (
        "Missing -webkit-overflow-scrolling:touch for iOS scrollable tabs."
    )


# ─── Overview economy table scroll wrapper ───────────────────────────────────

def test_overview_economy_table_has_scroll_wrapper():
    """overview.js: economy table must be wrapped in data-table--scroll div."""
    with open(OVERVIEW_JS) as f:
        src = f.read()

    # The economy table is the 5-column Źródło/Wpływy/Wydatki/Bilans/Liczba table
    # rendered into econHost; locate that region
    econ_idx = src.find("econHost.innerHTML")
    assert econ_idx != -1, "econHost.innerHTML assignment not found in overview.js"
    region = src[econ_idx:econ_idx + 2000]

    assert 'data-table--scroll' in region, (
        "Economy table in overview.js is missing data-table--scroll wrapper. "
        "5-column table overflows on mobile without scroll container."
    )
    scroll_in_region = region.find('data-table--scroll')
    table_in_region = region.find('<table')
    assert scroll_in_region < table_in_region, (
        "data-table--scroll wrapper must appear before the <table> tag in econHost region."
    )


def test_overview_economy_table_wrapper_is_closed():
    """overview.js: scroll wrapper div must be closed after the economy table."""
    with open(OVERVIEW_JS) as f:
        src = f.read()

    # Find the economy table region
    region_start = src.find('data-table--scroll')
    region_end = src.find("econHost.innerHTML", region_start + 1)
    if region_end == -1:
        region_end = len(src)
    region = src[region_start:region_start + 2000]

    assert "</div>" in region and "</table>" in region, (
        "data-table--scroll wrapper must close with </div> after </table> in economy table."
    )


# ─── Push table card-view ────────────────────────────────────────────────────

def test_push_table_has_cards_class():
    """push.js: subscriptions table wrapper must have data-table--cards class for mobile card view."""
    with open(PUSH_JS) as f:
        src = f.read()
    assert 'data-table--cards' in src, (
        "push.js subscriptions table is missing data-table--cards class. "
        "5-column table is unreadable on mobile without card view."
    )


def test_push_table_rows_have_data_labels():
    """push.js: dynamically rendered <td> cells must have data-label attrs for CSS ::before content."""
    with open(PUSH_JS) as f:
        src = f.read()

    required_labels = ["Gracz", "Status", "Subskrypcji", "Ostatnia rej.", "Akcja"]
    for label in required_labels:
        assert f'data-label="{label}"' in src, (
            f'Missing data-label="{label}" on push table <td>. '
            "Card-view CSS uses ::before content: attr(data-label) to show column headers on mobile."
        )


# ─── Backward compatibility: desktop layout unchanged ────────────────────────

def test_section_tabs_desktop_layout_unchanged():
    """components.css: .section-tabs base styles (flex, border-bottom) must be preserved."""
    with open(CSS_FILE) as f:
        css = f.read()

    # Find .section-tabs rule outside media query
    base_match = re.search(r'\.section-tabs\s*\{[^}]+\}', css)
    assert base_match, ".section-tabs base CSS rule missing."
    base_rule = base_match.group()
    assert "display: flex" in base_rule, "section-tabs base flex layout must remain for desktop."
    assert "border-bottom" in base_rule, "section-tabs bottom border must remain for desktop."


def test_push_table_wrapper_retains_overflow_style():
    """push.js: table-wrap must still have overflow-x:auto (desktop horizontal scroll preserved)."""
    with open(PUSH_JS) as f:
        src = f.read()
    # Both classes + overflow style should coexist
    assert 'data-table--cards' in src and 'overflow-x:auto' in src, (
        "table-wrap must keep overflow-x:auto alongside data-table--cards for desktop compatibility."
    )
