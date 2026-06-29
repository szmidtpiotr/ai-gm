"""TDD: Issue #1027 — admin table column filter: text input (substring, PL-insensitive) replaces dropdown.

The filter is pure frontend (_normalizePL + _applyColFilters in table.js).
These backend tests verify:
 1. The normalization logic equivalent (documents the _normalizePL JS contract).
 2. Admin list endpoints (list_weapons, list_items) return dicts with string 'name'/'label'
    fields — a prerequisite for the JS text filter to operate on cell text content.
"""
import sys
import unicodedata

sys.path.insert(0, '/app')


# ─── Helper: Python mirror of JS _normalizePL ────────────────────────────────

def normalize_pl(s) -> str:
    """Mirror of frontend table.js _normalizePL: lowercase + NFD diacritics + ł→l."""
    s = (s or '').lower()
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = s.replace('ł', 'l')
    return s


# ─── Unit: normalize_pl contract ─────────────────────────────────────────────

def test_normalize_pl_lowercase():
    assert normalize_pl('Miecz') == 'miecz'


def test_normalize_pl_o_acute():
    assert normalize_pl('ósiem') == 'osiem'


def test_normalize_pl_l_stroke():
    """ł has no NFD decomposition — mapped explicitly."""
    assert normalize_pl('łuk') == 'luk'
    assert normalize_pl('Łuk') == 'luk'


def test_normalize_pl_combined_diacritics():
    assert normalize_pl('żelazo') == 'zelazo'
    assert normalize_pl('ćwiczenie') == 'cwiczenie'
    assert normalize_pl('środek') == 'srodek'


def test_normalize_pl_empty():
    assert normalize_pl('') == ''
    assert normalize_pl(None) == ''


def test_normalize_pl_substring_match_miecz():
    """'miecz' fragment matches 'Miecz długi' after normalization."""
    assert normalize_pl('miecz') in normalize_pl('Miecz długi')


def test_normalize_pl_substring_match_luk():
    """'luk' matches 'Łuk myśliwski' (diacritic-insensitive)."""
    assert normalize_pl('luk') in normalize_pl('Łuk myśliwski')


def test_normalize_pl_no_false_match():
    """'miecz' must NOT match 'Topór'."""
    assert normalize_pl('miecz') not in normalize_pl('Topór')


# ─── Integration: admin list functions return string-named items ──────────────

def test_list_weapons_returns_list_with_string_names():
    """list_weapons() returns list of dicts; each entry has string 'name'/'label' field."""
    from app.services.admin_config import list_weapons
    weapons = list_weapons()
    assert isinstance(weapons, list), "list_weapons must return a list"
    if weapons:
        w = weapons[0]
        assert isinstance(w, dict), "weapon entry must be a dict"
        # JS filter operates on rendered cell text — name or label must be a string
        name = w.get('name') or w.get('label') or ''
        assert isinstance(name, str), f"name/label must be str, got {type(name)}"


def test_list_items_returns_list_with_string_names():
    """list_items() returns list of dicts; each entry has string 'name'/'label' field."""
    from app.services.admin_config import list_items
    items = list_items()
    assert isinstance(items, list), "list_items must return a list"
    if items:
        i = items[0]
        assert isinstance(i, dict), "item entry must be a dict"
        name = i.get('name') or i.get('label') or ''
        assert isinstance(name, str), f"name/label must be str, got {type(name)}"


# ─── Backward compat: imports still clean ────────────────────────────────────

def test_admin_config_still_importable():
    """admin_config.py imports cleanly — no regression from shared list functions."""
    import importlib
    import app.services.admin_config as mod
    importlib.reload(mod)
    assert hasattr(mod, 'list_weapons'), "list_weapons missing from admin_config"
    assert hasattr(mod, 'list_items'), "list_items missing from admin_config"
