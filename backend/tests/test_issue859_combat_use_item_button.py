"""TDD: Issue #859 — przycisk "Użyj mikstury/przedmiotu" w pasku akcji walki.

Feature jest czysto frontendowy (backend `use_inventory_item` + sync do
`active_combat` już działa — patrz `loot_service.py`). Test weryfikuje więc
KONTRAKT FRONTENDU: combat action sheet (`#combat-action-sheet`) MUSI zawierać
nowy przycisk użycia przedmiotu, a istniejące akcje walki muszą zostać.

Plik `index.html` nie jest w obrazie backendu — test szuka go po kilku
kandydujących ścieżkach (host repo, zmienna env, miejsce do którego `docker cp`
wrzuca plik w kontenerze).
"""
import os
import re

import pytest

_CANDIDATES = [
    os.environ.get("AIGM_FRONTEND_INDEX"),
    "/app/_frontend_index_test.html",  # docelowa ścieżka docker cp w kontenerze backendu
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "front", "index.html"),
    "/home/piotrszmidt/ai-gm/frontend/front/index.html",
]


def _load_index_html() -> str:
    for path in _CANDIDATES:
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
    pytest.skip(f"index.html nie znaleziony w żadnej z: {[c for c in _CANDIDATES if c]}")


def _combat_action_sheet_block(html: str) -> str:
    """Wytnij blok <div id="combat-action-sheet" ...> ... </div> (do następnego
    rodzeństwa na tym samym poziomie — wystarczy do końca listy akcji)."""
    start = html.find('id="combat-action-sheet"')
    assert start != -1, 'brak elementu #combat-action-sheet w index.html'
    # bierzemy hojny wycinek — do arkusza ataku (kolejny sibling) albo +6000 znaków
    end = html.find('id="combat-attack-sheet"', start)
    if end == -1:
        end = start + 6000
    return html[start:end]


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_combat_action_sheet_has_use_item_button():
    """Pasek akcji walki musi mieć przycisk użycia mikstury/przedmiotu (#859)."""
    html = _load_index_html()
    sheet = _combat_action_sheet_block(html)
    assert 'id="combat-item-btn"' in sheet, (
        'Brak przycisku #combat-item-btn w #combat-action-sheet — '
        'gracz nie może użyć mikstury bez wchodzenia do ekwipunku (#859).'
    )


def test_consumable_picker_overlay_exists():
    """Klik w przycisk otwiera quick-picker konsumpcyjnych z plecaka (#859)."""
    html = _load_index_html()
    assert 'id="consumable-picker-overlay"' in html, (
        'Brak overlayu #consumable-picker-overlay (quick-picker mikstur).'
    )
    assert 'id="consumable-picker-list"' in html, (
        'Brak kontenera listy #consumable-picker-list.'
    )


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_combat_sheet_keeps_existing_actions():
    """Istniejące akcje walki (Ruch/Zapasy/Zaklęcie) nie mogą zniknąć."""
    html = _load_index_html()
    sheet = _combat_action_sheet_block(html)
    for existing in ('id="combat-move-btn"', 'id="combat-wrestle-btn"', 'id="combat-spell-btn"'):
        assert existing in sheet, f'Regresja: zniknął istniejący przycisk {existing}.'


def test_use_item_button_marked_free_action():
    """#859 out-of-scope: użycie przedmiotu NIE konsumuje tury (backend nie
    przesuwa tury) → przycisk oznaczony jako reakcja/za darmo, nie '⏳ tura'."""
    html = _load_index_html()
    sheet = _combat_action_sheet_block(html)
    # wytnij sam blok przycisku item
    m = re.search(r'id="combat-item-btn".*?</button>', sheet, re.DOTALL)
    assert m, 'nie znaleziono bloku przycisku #combat-item-btn do sprawdzenia kosztu'
    btn = m.group(0)
    assert 'combat-btn__cost--reaction' in btn, (
        'Przycisk mikstury powinien być oznaczony jako akcja darmowa '
        '(combat-btn__cost--reaction), bo backend nie przesuwa tury.'
    )
