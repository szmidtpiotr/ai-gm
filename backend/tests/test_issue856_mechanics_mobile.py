"""TDD: Issue #856 — mechanics.js mobile responsive tables (@390px).

Frontend-only fix: adds data-table--cards wrapper classes to all 6 tables
in mechanics.js (stats/skills/dc/conditions/archetypes/xp) so they render
correctly at 390px viewport. Modals get max-width instead of fixed width.
"""
import urllib.request

FRONTEND = "http://frontend:80"


def _get(path):
    with urllib.request.urlopen(f"{FRONTEND}{path}", timeout=5) as r:
        return r.read().decode()


# ─── RED tests — verify mobile classes are present ───────────────────────────

def test_mechanics_has_cards_class():
    """mechanics.js must contain data-table--cards for mobile card layout."""
    js = _get("/admin/sections/mechanics.js")
    assert 'data-table--cards' in js, \
        "mechanics.js must contain data-table--cards class for mobile tables"


def test_all_six_tables_use_cards():
    """All 6 table wrappers must use data-table--cards (one per table)."""
    js = _get("/admin/sections/mechanics.js")
    cards_count = js.count('data-table--cards')
    assert cards_count >= 6, \
        f"mechanics.js must have at least 6 data-table--cards usages (one per table), got {cards_count}"


def test_stats_rows_have_data_labels():
    """Stats table rows must have data-label attributes for card-view labels."""
    js = _get("/admin/sections/mechanics.js")
    assert 'data-label=' in js, \
        "mechanics.js must add data-label attributes to td cells for card-view"


def test_skills_rows_have_data_labels():
    """Skills table tds must carry data-label for stat and rank columns."""
    js = _get("/admin/sections/mechanics.js")
    assert 'data-label="Statystyka"' in js, \
        "mechanics.js skills rows must have data-label=\"Statystyka\""
    assert 'data-label="Maks. rang"' in js, \
        "mechanics.js skills rows must have data-label=\"Maks. rang\""


def test_dc_rows_have_data_labels():
    """DC table tds must carry data-label."""
    js = _get("/admin/sections/mechanics.js")
    assert 'data-label="Wartość"' in js, \
        "mechanics.js dc rows must have data-label=\"Wartość\""


def test_conditions_rows_have_data_labels():
    """Conditions table tds must carry data-label."""
    js = _get("/admin/sections/mechanics.js")
    assert 'data-label="Efekt JSON"' in js, \
        "mechanics.js conditions rows must have data-label=\"Efekt JSON\""
    assert 'data-label="Kumulowalny"' in js, \
        "mechanics.js conditions rows must have data-label=\"Kumulowalny\""


def test_archetypes_rows_have_data_labels():
    """Archetypes table tds must carry data-label."""
    js = _get("/admin/sections/mechanics.js")
    assert 'data-label="HP bazowe"' in js, \
        "mechanics.js archetypes rows must have data-label=\"HP bazowe\""


def test_xp_awards_rows_have_data_labels():
    """XP awards table tds must carry data-label."""
    js = _get("/admin/sections/mechanics.js")
    assert 'data-label="Kategoria"' in js, \
        "mechanics.js xp rows must have data-label=\"Kategoria\""
    assert 'data-label="XP"' in js, \
        "mechanics.js xp rows must have data-label=\"XP\""


def test_modals_use_max_width_not_fixed_width():
    """Modals must use max-width (not fixed width:440px) so they fit on mobile."""
    js = _get("/admin/sections/mechanics.js")
    assert 'style="width:440px"' not in js, \
        "mechanics.js modals must not use fixed style=\"width:440px\" — use max-width instead"
    assert 'max-width:440px' in js, \
        "mechanics.js modals must use max-width:440px for responsive layout"


# ─── Backward compat — existing table IDs untouched ─────────────────────────

def test_stats_table_id_still_present():
    """stats-table id must remain for JS selectors."""
    js = _get("/admin/sections/mechanics.js")
    assert 'id="stats-table"' in js, "stats-table id must not be removed"


def test_skills_table_id_still_present():
    """skills-table id must remain for JS selectors."""
    js = _get("/admin/sections/mechanics.js")
    assert 'id="skills-table"' in js, "skills-table id must not be removed"


def test_conditions_table_id_still_present():
    """conditions-table id must remain for JS selectors."""
    js = _get("/admin/sections/mechanics.js")
    assert 'id="conditions-table"' in js, "conditions-table id must not be removed"
