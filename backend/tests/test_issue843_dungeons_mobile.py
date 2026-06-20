"""TDD: Issue #843 — dungeons.js card-view na mobile @390px."""
import re
import pytest

DUNGEONS_JS = "/app/frontend/admin/sections/dungeons.js"


def _read_js():
    with open(DUNGEONS_JS, encoding="utf-8") as f:
        return f.read()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_dungeons_table_wrap_has_cards_class():
    """table-wrap przy dungeons-table musi mieć klasę data-table--cards."""
    src = _read_js()
    # dtab-dungeons zawiera table-wrap z klasą data-table--cards
    dtab = re.search(r'dtab-dungeons(.*?)dtab-riddles', src, re.DOTALL)
    assert dtab, "Nie znaleziono bloku dtab-dungeons"
    assert 'data-table--cards' in dtab.group(1), \
        "Brak klasy data-table--cards w table-wrap dla Lochy"


def test_riddles_table_wrap_has_cards_class():
    """table-wrap przy riddles-table musi mieć klasę data-table--cards."""
    src = _read_js()
    dtab = re.search(r'dtab-riddles(.*?)dtab-tiles', src, re.DOTALL)
    assert dtab, "Nie znaleziono bloku dtab-riddles"
    assert 'data-table--cards' in dtab.group(1), \
        "Brak klasy data-table--cards w table-wrap dla Zagadki"


def test_tilecats_table_wrap_has_cards_class():
    """table-wrap przy tilecats-table musi mieć klasę data-table--cards."""
    src = _read_js()
    dtab = re.search(r'dtab-tilecats(.*?)$', src, re.DOTALL)
    assert dtab, "Nie znaleziono bloku dtab-tilecats"
    assert 'data-table--cards' in dtab.group(1), \
        "Brak klasy data-table--cards w table-wrap dla Kategorie"


def test_load_dungeons_has_data_labels():
    """_loadDungeons() musi generować <td data-label=...> dla każdej kolumny danych."""
    src = _read_js()
    load_block = re.search(r'async function _loadDungeons\(\)(.*?)(?=\n  async function|\n  function)', src, re.DOTALL)
    assert load_block, "Nie znaleziono _loadDungeons()"
    block = load_block.group(1)
    assert 'data-label' in block, \
        "_loadDungeons() nie zawiera data-label na <td> — brak etykiet w card-view"


def test_load_riddles_has_data_labels():
    """_loadRiddles() musi generować <td data-label=...> dla każdej kolumny danych."""
    src = _read_js()
    load_block = re.search(r'async function _loadRiddles\(\)(.*?)(?=\n  function|\n  async function)', src, re.DOTALL)
    assert load_block, "Nie znaleziono _loadRiddles()"
    block = load_block.group(1)
    assert 'data-label' in block, \
        "_loadRiddles() nie zawiera data-label na <td> — brak etykiet w card-view"


def test_load_tile_categories_has_data_labels():
    """_loadTileCategories() musi generować <td data-label=...>."""
    src = _read_js()
    load_block = re.search(r'async function _loadTileCategories\(\)(.*?)(?=\n  function|\n  async function)', src, re.DOTALL)
    assert load_block, "Nie znaleziono _loadTileCategories()"
    block = load_block.group(1)
    assert 'data-label' in block, \
        "_loadTileCategories() nie zawiera data-label na <td> — brak etykiet w card-view"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_tiles_grid_not_table():
    """Tab Kafelki musi pozostać grid (nie table) — nie ruszamy go."""
    src = _read_js()
    dtab_tiles = re.search(r'dtab-tiles(.*?)dtab-tilecats', src, re.DOTALL)
    assert dtab_tiles, "Nie znaleziono bloku dtab-tiles"
    block = dtab_tiles.group(1)
    assert 'tiles-grid' in block, "dtab-tiles musi mieć tiles-grid (CSS grid, nie table)"
    # grid nie powinien mieć klasy data-table
    assert 'data-table' not in re.sub(r'data-table--cards|data-table--scroll', '', block), \
        "dtab-tiles nie powinno mieć klasy data-table (jest gridem)"


def test_dungeons_table_still_exists():
    """Tabela #dungeons-table musi nadal istnieć (nie usunięto jej)."""
    src = _read_js()
    assert 'id="dungeons-table"' in src or "id='dungeons-table'" in src, \
        "Tabela dungeons-table zniknęła z kodu"
