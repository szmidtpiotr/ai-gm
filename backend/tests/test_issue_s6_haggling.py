"""TDD: Issue #586 (S6) — Haggling: targowanie wpięte w ceny sklepu.

Sędzią mechaniki jest czysty serwis ``haggle_service`` — testujemy mapowanie
stopnia testu na rabat, jednorazową konsumpcję, klamp łączny i blokadę po
krytycznej porażce (kupiec obrażony). Liczby = wartości startowe (Numbers Policy).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.services import haggle_service as hs


# ─── Mapowanie stopnia testu (S1) → przewaga gracza ──────────────────────────

def test_discount_for_outcome_steps():
    """4 stopnie wyniku → rabat startowy z design doc."""
    assert hs.discount_for_outcome("CRITICAL_SUCCESS") == pytest.approx(0.40)
    assert hs.discount_for_outcome("SUCCESS") == pytest.approx(0.15)
    assert hs.discount_for_outcome("FAILURE") == pytest.approx(0.0)
    assert hs.discount_for_outcome("CRITICAL_FAILURE") == pytest.approx(-0.10)


def test_discount_for_outcome_unknown_is_zero():
    """Nieznany stopień nie rusza ceny (bezpieczny default)."""
    assert hs.discount_for_outcome("WHATEVER") == 0.0


# ─── Zapis wyniku do session_flags ───────────────────────────────────────────

def test_apply_success_sets_discount():
    flags: dict = {}
    hs.apply_haggle_outcome(flags, "SUCCESS")
    assert hs.peek_haggle_discount(flags) == pytest.approx(0.15)
    assert hs.is_haggle_blocked(flags) is False


def test_apply_critical_failure_sets_markup_and_block():
    """Krytyczna porażka: cena drożej + kupiec obrażony (blokada)."""
    flags: dict = {}
    hs.apply_haggle_outcome(flags, "CRITICAL_FAILURE")
    assert hs.peek_haggle_discount(flags) == pytest.approx(-0.10)
    assert hs.is_haggle_blocked(flags) is True


# ─── Konsumpcja jednorazowa ──────────────────────────────────────────────────

def test_consume_is_one_shot():
    flags: dict = {}
    hs.apply_haggle_outcome(flags, "SUCCESS")
    first = hs.consume_haggle_discount(flags)
    second = hs.consume_haggle_discount(flags)
    assert first == pytest.approx(0.15)
    assert second == pytest.approx(0.0)   # druga transakcja już bez rabatu
    assert hs.peek_haggle_discount(flags) == pytest.approx(0.0)


def test_peek_does_not_consume():
    flags: dict = {}
    hs.apply_haggle_outcome(flags, "SUCCESS")
    assert hs.peek_haggle_discount(flags) == pytest.approx(0.15)
    assert hs.peek_haggle_discount(flags) == pytest.approx(0.15)  # nadal tam


# ─── Stackowanie z CHA (F10) + klamp ─────────────────────────────────────────

def test_effective_buy_multiplier_stacks_and_clamps():
    # CHA neutralny (1.0) + sukces 15% → 0.85
    assert hs.effective_buy_multiplier(1.0, 0.15) == pytest.approx(0.85)
    # CHA już daje zniżkę 0.8 + crit 40% → 0.48
    assert hs.effective_buy_multiplier(0.8, 0.40) == pytest.approx(0.48)
    # Skrajna kombinacja nie spada poniżej klampu 0.4
    assert hs.effective_buy_multiplier(0.5, 0.40) == pytest.approx(0.4)
    # crit-fail (+10%) podnosi cenę
    assert hs.effective_buy_multiplier(1.0, -0.10) == pytest.approx(1.10)


def test_effective_sell_ratio_stacks_and_clamps():
    # bazowy ratio 0.5 + sukces 15% → 0.575
    assert hs.effective_sell_ratio(0.5, 0.15) == pytest.approx(0.575)
    # nie przekracza górnego klampu 0.95
    assert hs.effective_sell_ratio(0.9, 0.40) == pytest.approx(0.95)
    # crit-fail obniża zysk ze sprzedaży
    assert hs.effective_sell_ratio(0.5, -0.10) == pytest.approx(0.45)


# ─── Blokada po obrazie ──────────────────────────────────────────────────────

def test_clear_haggle_block():
    flags: dict = {}
    hs.apply_haggle_outcome(flags, "CRITICAL_FAILURE")
    assert hs.is_haggle_blocked(flags) is True
    hs.clear_haggle_block(flags)
    assert hs.is_haggle_blocked(flags) is False


# ─── Backward compat: brak rabatu = brak zmian ───────────────────────────────

def test_no_haggle_means_neutral():
    """Bez targowania mnożniki są neutralne (zero regresji dla zwykłego sklepu)."""
    flags: dict = {}
    assert hs.peek_haggle_discount(flags) == 0.0
    assert hs.consume_haggle_discount(flags) == 0.0
    assert hs.effective_buy_multiplier(1.0, hs.peek_haggle_discount(flags)) == pytest.approx(1.0)
    assert hs.effective_sell_ratio(0.5, hs.peek_haggle_discount(flags)) == pytest.approx(0.5)
