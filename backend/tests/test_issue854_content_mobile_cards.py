"""TDD: Issue #854 — content.js mobile card-view @390px.

Weryfikuje że content.js używa data-table--cards dla list encji (bronie, zbroje,
przedmioty, konsumable, tabele łupów, czary, afiksy) oraz że każdy wiersz tabeli
zawiera atrybuty data-label wymagane przez ::before content: attr(data-label).

Loot entries modal (wewnątrz _openLootEntriesModal) pozostaje data-table--scroll
(tabela gęsta z porównaniem kolumn).
"""
import re
import urllib.request

FRONTEND = "http://frontend:80"


def _get(path):
    with urllib.request.urlopen(f"{FRONTEND}{path}", timeout=5) as r:
        return r.read().decode()


# ─── RED: entity tables must use cards wrapper ────────────────────────────────

def test_weapons_table_uses_cards_wrapper():
    """weapons-table wrapper musi być data-table--cards na @390px."""
    js = _get("/admin/sections/content.js")
    # Extract weapons stab-panel section (between stab-weapons and stab-armor)
    match = re.search(r'stab-weapons(.*?)stab-armor', js, re.DOTALL)
    assert match, "stab-weapons section not found in content.js"
    section = match.group(1)
    assert 'data-table--cards' in section, (
        "#854: weapons-table wrapper powinien używać data-table--cards "
        "(card-view na @390px) — nie data-table--scroll"
    )


def test_consumables_table_uses_cards_wrapper():
    """consumables-table wrapper musi być data-table--cards na @390px."""
    js = _get("/admin/sections/content.js")
    match = re.search(r'stab-consumables(.*?)stab-loot', js, re.DOTALL)
    assert match, "stab-consumables section not found"
    section = match.group(1)
    assert 'data-table--cards' in section, (
        "#854: consumables-table wrapper powinien używać data-table--cards"
    )


def test_load_weapons_has_data_labels():
    """_loadWeapons musi dodawać data-label do komórek wiersza."""
    js = _get("/admin/sections/content.js")
    match = re.search(
        r'async function _loadWeapons\(\)(.*?)^async function',
        js, re.DOTALL | re.MULTILINE
    )
    assert match, "_loadWeapons not found in content.js"
    fn_body = match.group(1)
    assert 'data-label=' in fn_body, (
        "#854: _loadWeapons musi zawierać data-label= w HTML wierszy "
        "(wymagane przez CSS ::before content: attr(data-label) w card-view)"
    )


def test_load_armor_has_data_labels():
    """_loadArmor musi dodawać data-label do komórek wiersza."""
    js = _get("/admin/sections/content.js")
    match = re.search(
        r'async function _loadArmor\(\)(.*?)^async function',
        js, re.DOTALL | re.MULTILINE
    )
    assert match, "_loadArmor not found in content.js"
    fn_body = match.group(1)
    assert 'data-label=' in fn_body, (
        "#854: _loadArmor musi zawierać data-label= w HTML wierszy"
    )


# ─── GREEN od razu: loot entries modal stays scroll ──────────────────────────

def test_loot_entries_modal_stays_scroll():
    """Loot entries modal (gęsta tabela porównawcza) musi pozostać data-table--scroll."""
    js = _get("/admin/sections/content.js")
    match = re.search(
        r'_openLootEntriesModal.*?document\.body\.appendChild',
        js, re.DOTALL
    )
    assert match, "_openLootEntriesModal not found in content.js"
    modal_html = match.group(0)
    assert 'data-table--scroll' in modal_html, (
        "Loot entries modal musi zachować data-table--scroll "
        "(gęsta tabela z porównaniem kolumn)"
    )
    assert 'data-table--cards' not in modal_html, (
        "Loot entries modal NIE może używać data-table--cards"
    )
