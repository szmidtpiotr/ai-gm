"""TDD: Issue #832 — Mobile tables: card-view + scroll/sticky hybrid."""
import os

FRONTEND_DIR = '/app/tests/_frontend_832'


def _read(path):
    with open(os.path.join(FRONTEND_DIR, path)) as f:
        return f.read()


# ─── Test główny: CSS utility classes ────────────────────────────────────────

def test_components_css_has_mobile_table_scroll():
    """components.css must define .data-table--scroll mobile wrapper."""
    css = _read('shared/components.css')
    assert '.data-table--scroll' in css, "Missing .data-table--scroll in components.css"
    assert 'overflow-x: auto' in css, "Missing overflow-x: auto for scroll wrapper"


def test_components_css_has_mobile_table_cards():
    """components.css must define .data-table--cards that transforms rows to cards."""
    css = _read('shared/components.css')
    assert '.data-table--cards' in css, "Missing .data-table--cards in components.css"
    assert 'data-label' in css, "Missing ::before content: attr(data-label) in components.css"
    assert 'display: none' in css, "Missing thead hide rule for cards mode"


# ─── Test główny: JS data-label attributes ───────────────────────────────────

def test_campaigns_js_has_data_label_on_td():
    """campaigns.js dynamic rows must include data-label attributes for card-view."""
    js = _read('sections/campaigns.js')
    assert 'data-label=' in js, "campaigns.js missing data-label on <td> elements"
    assert 'data-table--cards' in js, "campaigns.js wrapper missing data-table--cards class"


def test_bugreports_js_has_data_label_on_td():
    """bugreports.js dynamic rows must include data-label attributes for card-view."""
    js = _read('sections/bugreports.js')
    assert 'data-label=' in js, "bugreports.js missing data-label on <td> elements"
    assert 'data-table--cards' in js, "bugreports.js wrapper missing data-table--cards class"


def test_players_js_has_data_label_on_td():
    """players.js dynamic rows must include data-label attributes for card-view."""
    js = _read('sections/players.js')
    assert 'data-label=' in js, "players.js missing data-label on <td> elements"
    assert 'data-table--cards' in js, "players.js wrapper missing data-table--cards class"


def test_content_js_tables_have_scroll_wrapper():
    """content.js main content tables must use data-table--scroll wrapper."""
    js = _read('sections/content.js')
    assert 'data-table--scroll' in js, "content.js missing data-table--scroll wrapper class"


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_data_table_class_still_present():
    """Existing .data-table class still used — no regression to base table styling."""
    for fname in ['sections/campaigns.js', 'sections/bugreports.js',
                  'sections/players.js', 'sections/content.js']:
        js = _read(fname)
        assert 'data-table' in js, f"{fname} lost .data-table class entirely"


def test_desktop_table_structure_unchanged():
    """Table <thead> still exists — desktop view unaffected."""
    for fname in ['sections/campaigns.js', 'sections/bugreports.js',
                  'sections/players.js', 'sections/content.js']:
        js = _read(fname)
        assert '<thead' in js or 'thead' in js, f"{fname} lost thead element"
