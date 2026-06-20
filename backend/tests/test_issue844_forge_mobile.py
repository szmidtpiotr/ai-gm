"""TDD: Issue #844 — Kuźnia (forge.js) na mobile @390px.

Czysto frontendowy fix. Testy sprawdzają że pliki źródłowe zawierają
wymagane klasy CSS do obsługi mobilnej.
"""
import os

FORGE_JS = '/tmp/forge_test/forge.js'
CSS_FILE = '/tmp/forge_test/components.css'

# ─── RED: testy muszą failować przed dodaniem klas ──────────────────────────

def test_forge_js_has_mobile_grid_2col_class():
    """forge.js musi używać klasy forge-grid-2col dla 2-kolumnowych siatek."""
    with open(FORGE_JS, encoding='utf-8') as f:
        content = f.read()
    assert 'forge-grid-2col' in content, (
        "forge.js nie zawiera klasy 'forge-grid-2col' — "
        "wymagana dla responsywnych siatek 2-kolumnowych na mobile"
    )


def test_forge_js_has_mobile_grid_3col_class():
    """forge.js musi używać klasy forge-grid-3col dla 3-kolumnowych siatek."""
    with open(FORGE_JS, encoding='utf-8') as f:
        content = f.read()
    assert 'forge-grid-3col' in content, (
        "forge.js nie zawiera klasy 'forge-grid-3col' — "
        "wymagana dla siatki postaci/lokacji/wrogów (3 kolumny na desktop)"
    )


def test_forge_js_has_tpl_header_class():
    """forge.js musi używać klasy forge-tpl-header dla zawijania przycisków edytora szablonu."""
    with open(FORGE_JS, encoding='utf-8') as f:
        content = f.read()
    assert 'forge-tpl-header' in content, (
        "forge.js nie zawiera klasy 'forge-tpl-header' — "
        "wymagana do zawijania przycisków nagłówka edytora szablonów na mobile"
    )


def test_forge_js_has_encounter_modal_body_class():
    """forge.js musi używać klasy forge-encounter-modal-body dla modalnego spotkania."""
    with open(FORGE_JS, encoding='utf-8') as f:
        content = f.read()
    assert 'forge-encounter-modal-body' in content, (
        "forge.js nie zawiera klasy 'forge-encounter-modal-body' — "
        "wymagana dla 2-kolumnowego layoutu modalu spotkania (→ 1-kol na mobile)"
    )


def test_components_css_has_forge_mobile_rules():
    """components.css musi zawierać reguły mobilne dla forge."""
    with open(CSS_FILE, encoding='utf-8') as f:
        content = f.read()
    assert 'forge-grid-2col' in content, (
        "components.css nie zawiera '.forge-grid-2col' — "
        "wymagana reguła @media dla responsywnych siatek forge"
    )
    assert 'forge-float-chat' in content, (
        "components.css nie zawiera '.forge-float-chat' w bloku mobile — "
        "wymagana reguła bottom-sheet na @max-width:768px"
    )


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_forge_js_still_has_forge_float_chat_class():
    """Pływający chat nadal musi istnieć w forge.js (nie usunięty)."""
    with open(FORGE_JS, encoding='utf-8') as f:
        content = f.read()
    assert 'forge-float-chat' in content, (
        "forge.js nie zawiera 'forge-float-chat' — element chat nie może zostać usunięty"
    )


def test_forge_js_still_has_scenario_panel():
    """Panel scenariusza musi nadal istnieć (nie usunięty podczas mobilizacji)."""
    with open(FORGE_JS, encoding='utf-8') as f:
        content = f.read()
    assert 'forge-scenario-col' in content, (
        "forge.js nie zawiera 'forge-scenario-col' — panel scenariusza nie może zostać usunięty"
    )
