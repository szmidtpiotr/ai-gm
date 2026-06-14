"""TDD: Issue #581 (S1) — Margines sukcesu: 4 stopnie wyniku testu umiejętności.

Decyzja 1 (Piotr 2026-06-12): test umiejętności ma 4 stopnie zależne od marginesu
(o ile player_total pobił opponent_total). Nat 20 / nat 1 mają ABSOLUTNE pierwszeństwo.
Dotyczy WYŁĄCZNIE resolve_skill_test — rzuty ataku w walce bez zmian.

| Wynik              | Warunek                       |
|--------------------|-------------------------------|
| CRITICAL_SUCCESS   | nat 20  lub  margines >= +5   |
| SUCCESS            | margines 0…+4                 |
| FAILURE            | margines -1…-4                |
| CRITICAL_FAILURE   | nat 1   lub  margines <= -5   |
"""
import sqlite3
import pytest

from app.services.skill_service import resolve_skill_test, build_skill_result_context


def _conn():
    # in-memory conn — dc-counter + no-trap path never touches the DB
    return sqlite3.connect(":memory:")


def _pending(dc: int, mod: int = 0, skill_key: str = "athletics"):
    return {
        "skill_key": skill_key,
        "skill_label": skill_key.title(),
        "counter": {"counter_type": "dc", "counter_key": None, "dc": dc},
        "modifier_breakdown": {"total": mod},
    }


def _resolve(d20: int, dc: int, mod: int = 0):
    return resolve_skill_test(d20, _pending(dc, mod), _conn(), 1, 1)


# ─── Test główny — tabela 4 stopni wg marginesu ──────────────────────────────

@pytest.mark.parametrize("d20,dc,mod,expected_outcome,expected_margin", [
    # margin >= +5 → CRITICAL_SUCCESS (bez nat 20)
    (10, 5, 0, "CRITICAL_SUCCESS", 5),
    (15, 8, 2, "CRITICAL_SUCCESS", 9),
    # margin 0…+4 → SUCCESS
    (10, 6, 0, "SUCCESS", 4),
    (10, 10, 0, "SUCCESS", 0),
    # margin -1…-4 → FAILURE
    (10, 11, 0, "FAILURE", -1),
    (10, 14, 0, "FAILURE", -4),
    # margin <= -5 → CRITICAL_FAILURE (bez nat 1)
    (10, 15, 0, "CRITICAL_FAILURE", -5),
    (5, 18, 0, "CRITICAL_FAILURE", -13),
])
def test_margin_maps_to_four_outcomes(d20, dc, mod, expected_outcome, expected_margin):
    r = _resolve(d20, dc, mod)
    assert r["outcome"] == expected_outcome
    assert r["margin"] == expected_margin


def test_exact_plus5_boundary_is_critical_success():
    """Brzeg dokładnie +5 → CRITICAL_SUCCESS."""
    assert _resolve(12, 7, 0)["outcome"] == "CRITICAL_SUCCESS"   # margin +5


def test_exact_minus5_boundary_is_critical_failure():
    """Brzeg dokładnie -5 → CRITICAL_FAILURE."""
    assert _resolve(7, 12, 0)["outcome"] == "CRITICAL_FAILURE"   # margin -5


# ─── Nat 20 / nat 1 — absolutne pierwszeństwo nad marginesem ─────────────────

def test_nat20_with_negative_margin_still_critical_success():
    """Nat 20 z marginesem -3 → CRITICAL_SUCCESS (auto-sukces niezależnie od marginesu)."""
    r = _resolve(20, 100, 0)  # player_total 20 vs dc 100 → margin -80
    assert r["nat20"] is True
    assert r["outcome"] == "CRITICAL_SUCCESS"
    assert r["success"] is True


def test_nat1_with_positive_margin_still_critical_failure():
    """Nat 1 z dodatnim marginesem → CRITICAL_FAILURE (auto-porażka)."""
    r = _resolve(1, 5, 10)  # player_total 11 vs dc 5 → margin +6, ale nat 1
    assert r["nat1"] is True
    assert r["outcome"] == "CRITICAL_FAILURE"
    assert r["success"] is False


# ─── Margines w kontekście narratora ─────────────────────────────────────────

def test_context_includes_margin():
    """build_skill_result_context dokłada margines liczbowo do kontekstu narratora."""
    r = _resolve(10, 5, 0)  # margin +5
    ctx = build_skill_result_context(r)
    assert "+5" in ctx or "5" in ctx
    assert "margines" in ctx.lower() or "margin" in ctx.lower()


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_enum_values_unchanged():
    """Zestaw wartości outcome bez zmian — kompatybilność konsumentów."""
    outcomes = {
        _resolve(20, 100, 0)["outcome"],
        _resolve(10, 5, 0)["outcome"],
        _resolve(10, 10, 0)["outcome"],
        _resolve(10, 12, 0)["outcome"],
        _resolve(1, 5, 10)["outcome"],
    }
    assert outcomes <= {"CRITICAL_SUCCESS", "SUCCESS", "FAILURE", "CRITICAL_FAILURE"}


def test_result_keys_preserved():
    """Stare klucze wyniku nadal obecne (success, nat20, nat1, player_total, opponent_total)."""
    r = _resolve(10, 12, 0)
    for k in ("success", "nat20", "nat1", "player_total", "opponent_total", "outcome", "skill_key"):
        assert k in r
