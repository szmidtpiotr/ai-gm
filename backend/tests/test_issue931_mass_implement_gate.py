"""TDD: Issue #931 — gate testowy: --build przed pytest + baseline-diff dla refaktorów.

Testy:
1. Kontrolny: reduce_stacking_conditions zwraca wynik (wykrywa brakujący 'return out, changed')
2. Template: prompt-template.md zawiera '--build' (wymaganie #931)
3. Template: zakres-template.md zawiera 'baseline-diff' (wymaganie refaktorów)
"""
import os
import sys
import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(TESTS_DIR, "..")
sys.path.insert(0, APP_DIR)

FIXTURES_DIR = os.path.join(TESTS_DIR, "fixtures_931")


# ─── Test kontrolny (control test) ──────────────────────────────────────────

def test_reduce_stacking_conditions_returns_result():
    """Control test: combat function must return a valid tuple (not None).

    Jeśli usunąć 'return out, changed' z reduce_stacking_conditions → ten test failuje.
    Gate mass-implement MUSI złapać taki fail (po dodaniu --build do pętli testowej).
    """
    from app.services.combat_service import reduce_stacking_conditions

    # pusta lista → żadna kondycja nie usunięta
    result = reduce_stacking_conditions([], remove_all=False)
    assert result is not None, (
        "reduce_stacking_conditions zwróciło None — brakuje 'return out, changed' "
        "(sztuczna regresja wykryta przez gate #931)"
    )
    out, changed = result
    assert isinstance(out, list), f"Pierwsza wartość powinna być listą, dostano {type(out)}"
    assert changed is False, "Pusta lista → changed powinno być False"

    # remove_all=True → też musi zwrócić tuple
    result2 = reduce_stacking_conditions([], remove_all=True)
    assert result2 is not None
    out2, changed2 = result2
    assert isinstance(out2, list)
    assert changed2 is False


# ─── Testy szablonów (RED przed fixem, GREEN po fixie) ──────────────────────

def _read_fixture(filename: str) -> str:
    path = os.path.join(FIXTURES_DIR, filename)
    if not os.path.exists(path):
        pytest.skip(f"Fixture '{filename}' nie dostępne w kontenerze — docker cp nie wykonany")
    with open(path) as f:
        return f.read()


def test_prompt_template_has_build_instruction():
    """prompt-template.md musi zawierać '--build' (wymaganie #931 — przebuduj przed pytest)."""
    content = _read_fixture("prompt-template.md")
    assert "--build" in content, (
        "prompt-template.md nie zawiera '--build' — child nie przebuduje obrazu przed pytest (#931)"
    )


def test_zakres_template_has_baseline_diff():
    """zakres-template.md musi zawierać 'baseline-diff' dla refaktorów (wymaganie #931)."""
    content = _read_fixture("zakres-template.md")
    assert "baseline-diff" in content, (
        "zakres-template.md nie zawiera 'baseline-diff' — "
        "refaktory nie mają wymogu porównania PASS/FAIL (#931)"
    )


# ─── Backward compat ────────────────────────────────────────────────────────

def test_mass_status_markers_format():
    """Backward compat: format markerów MASS_STATUS niezmieniony po fixie."""
    content = _read_fixture("prompt-template.md")
    for marker in ["MASS_STATUS: DONE", "MASS_STATUS: DONE-ALREADY", "MASS_STATUS: GATE", "MASS_STATUS: ERROR"]:
        assert marker in content, f"Brakuje markera '{marker}' w szablonie po fixie"
