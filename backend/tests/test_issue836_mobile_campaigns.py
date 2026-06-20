"""TDD: Issue #836 — Mobile M1: Campaigns section — card-view list + modal tabs scroll.

Frontend files are copied into /app/tests/frontend_assets/ before running:
  docker cp frontend/admin/shared/components.css  ai-gm-dev-backend-1:/app/tests/frontend_assets/components.css
  docker cp frontend/admin/sections/campaigns.js  ai-gm-dev-backend-1:/app/tests/frontend_assets/campaigns.js
"""
import os
import re

_ASSET_DIR = os.path.join(os.path.dirname(__file__), "frontend_assets")
CSS_FILE = os.path.join(_ASSET_DIR, "components.css")
CAMPAIGNS_JS = os.path.join(_ASSET_DIR, "campaigns.js")


# ─── Campaign list: card-view class present ──────────────────────────────────

def test_campaigns_table_has_cards_class():
    """campaigns.js: campaigns-table-view wrapper must have data-table--cards class."""
    with open(CAMPAIGNS_JS) as f:
        src = f.read()
    assert 'data-table--cards' in src, (
        "campaigns-table-view is missing data-table--cards class. "
        "The CSS card-view conversion won't activate on mobile without it."
    )


def test_campaigns_table_rows_have_data_labels():
    """campaigns.js: dynamically rendered <td> cells must have data-label attrs."""
    with open(CAMPAIGNS_JS) as f:
        src = f.read()
    required_labels = ["Kampania", "Bohater", "Klasa", "Poz.", "HP", "Tura", "Status"]
    for label in required_labels:
        assert f'data-label="{label}"' in src, (
            f'Missing data-label="{label}" on campaigns table <td>. '
            "Card-view CSS uses ::before content: attr(data-label) to show column headers on mobile."
        )


# ─── Campaign modal: tab bar scrollable on mobile ────────────────────────────

def test_campaigns_modal_tabs_has_class():
    """campaigns.js: modal tab bar container must have camp-modal-tabs class for mobile scroll."""
    with open(CAMPAIGNS_JS) as f:
        src = f.read()
    assert 'camp-modal-tabs' in src, (
        "Campaign modal tab bar is missing camp-modal-tabs class. "
        "Without it the @media rule cannot make the tab bar horizontally scrollable on mobile."
    )


def test_camp_modal_tabs_css_overflow_scroll():
    """components.css: .camp-modal-tabs must have overflow-x:auto inside @media max-width:768px."""
    with open(CSS_FILE) as f:
        css = f.read()
    media_blocks = re.findall(r'@media\s*\(max-width:\s*768px\).*?(?=@media|\Z)', css, re.DOTALL)
    found = any(".camp-modal-tabs" in block and "overflow-x" in block for block in media_blocks)
    assert found, (
        ".camp-modal-tabs is missing overflow-x rule in @media (max-width:768px). "
        "13 modal tabs wrap to multiple rows on 390px screen without scrollable container."
    )


def test_camp_modal_tabs_css_nowrap():
    """components.css: .camp-modal-tabs must have flex-wrap:nowrap inside @media max-width:768px."""
    with open(CSS_FILE) as f:
        css = f.read()
    media_blocks = re.findall(r'@media\s*\(max-width:\s*768px\).*?(?=@media|\Z)', css, re.DOTALL)
    found = any(".camp-modal-tabs" in block and "nowrap" in block for block in media_blocks)
    assert found, (
        ".camp-modal-tabs is missing flex-wrap:nowrap in @media (max-width:768px). "
        "Modal tabs continue to wrap instead of scrolling horizontally."
    )


# ─── Campaign modal overview: 2-col grid collapses to 1-col on mobile ────────

def test_camp_overview_grid_has_class():
    """campaigns.js: overview tab 2-column grid must have camp-overview-grid class."""
    with open(CAMPAIGNS_JS) as f:
        src = f.read()
    assert 'camp-overview-grid' in src, (
        "Campaign overview tab 2-column grid is missing camp-overview-grid class. "
        "The hardcoded grid-template-columns:1fr 1fr does not collapse on mobile."
    )


def test_camp_overview_grid_css_1col():
    """components.css: .camp-overview-grid must be 1-column inside @media max-width:768px."""
    with open(CSS_FILE) as f:
        css = f.read()
    media_blocks = re.findall(r'@media\s*\(max-width:\s*768px\).*?(?=@media|\Z)', css, re.DOTALL)
    found = any(".camp-overview-grid" in block and "grid-template-columns" in block for block in media_blocks)
    assert found, (
        ".camp-overview-grid is missing grid-template-columns override in @media (max-width:768px). "
        "The character stats + HP area overflows on 390px without single-column layout."
    )


# ─── Backward compatibility: desktop unchanged ───────────────────────────────

def test_modal_desktop_width_unchanged():
    """campaigns.js: modal width (min(1100px,96vw)) must still be present for desktop."""
    with open(CAMPAIGNS_JS) as f:
        src = f.read()
    assert '1100px' in src and '96vw' in src, (
        "Modal max-width for desktop was removed. Desktop layout will break."
    )


def test_campaigns_table_desktop_layout_preserved():
    """campaigns.js: campaigns-table must still have thead with column headers."""
    with open(CAMPAIGNS_JS) as f:
        src = f.read()
    assert '<thead>' in src and 'Kampania' in src, (
        "campaigns-table thead or column headers removed. Desktop table view broken."
    )
