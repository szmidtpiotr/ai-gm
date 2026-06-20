"""TDD: Issue #855 — world.js mobile responsive tables (@390px).

Frontend-only fix: adds data-table--cards / data-table--scroll wrapper classes
to tables in world.js so they render correctly at 390px viewport.
"""
import pytest
import re

WORLD_JS_PATH = "/app/tests/_world_855_fixture.js"


def _read_world_js():
    with open(WORLD_JS_PATH) as f:
        return f.read()


# ─── RED tests — verify mobile classes are present ────────────────────────────

def test_npc_table_has_cards_class():
    """NPC table wrapper must use data-table--cards for mobile card layout."""
    content = _read_world_js()
    # The NPC table-wrap div must have the --cards modifier
    assert 'data-table--cards' in content, \
        "world.js must contain data-table--cards class for NPC/list tables"


def test_enemies_table_has_mobile_class():
    """Enemies table must have a mobile-responsive wrapper class."""
    content = _read_world_js()
    has_cards = 'data-table--cards' in content
    has_scroll = 'data-table--scroll' in content
    assert has_cards or has_scroll, \
        "world.js must have at least one mobile table modifier (--cards or --scroll)"


def test_loot_table_has_scroll_class():
    """Loot tables (numeric comparison) must use data-table--scroll wrapper."""
    content = _read_world_js()
    assert 'data-table--scroll' in content, \
        "world.js must contain data-table--scroll class for multi-column comparison tables"


def test_pending_table_has_mobile_class():
    """Pending bestiary table must use a mobile-responsive wrapper."""
    content = _read_world_js()
    # The pending container innerHTML sets up the table
    # After fix: must have --cards modifier
    cards_count = content.count('data-table--cards')
    assert cards_count >= 2, \
        f"world.js should have at least 2 data-table--cards usages (NPC + pending), got {cards_count}"


def test_npc_rows_have_data_labels():
    """NPC table rows must have data-label attributes for card-view on mobile."""
    content = _read_world_js()
    # In _loadNPCs function, td cells must have data-label
    assert 'data-label=' in content, \
        "world.js must add data-label attributes to td cells for card-view labels"


# ─── Backward compat — existing structure untouched ──────────────────────────

def test_npc_table_id_still_present():
    """npcs-table id must remain for JS selectors to work."""
    content = _read_world_js()
    assert 'id="npcs-table"' in content, "npcs-table id must not be removed"


def test_world_enemies_table_id_still_present():
    """world-enemies-table id must remain for JS selectors to work."""
    content = _read_world_js()
    assert 'id="world-enemies-table"' in content, "world-enemies-table id must not be removed"
