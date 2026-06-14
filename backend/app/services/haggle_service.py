"""S6 (#586) — Haggling: targowanie wpięte w ceny sklepu.

Mechanika decyduje, LLM narruje (Zasady CZĘŚĆ 10). Targowanie to test
umiejętności ``haggling`` (S5/skill pipeline): jego stopień wyniku (S1) mapuje
się na PRZEWAGĘ GRACZA — ułamek, o który poprawia się najbliższa transakcja
w sklepie. Rabat żyje w ``session_flags`` (game_sessions), jest jednorazowy
(konsumowany przez najbliższe kupno/sprzedaż) i stackuje multiplikatywnie
z pasywnym modyfikatorem CHA (F10), z klampem chroniącym ekonomię.

Wszystkie liczby to WARTOŚCI STARTOWE (Numbers Policy) — do tuningu po S20.
"""
from __future__ import annotations

from typing import Any

# session_flags keys
_FLAG_DISCOUNT = "haggle_discount"   # float: player advantage (+ = taniej/lepiej)
_FLAG_BLOCKED = "haggle_blocked"     # bool: kupiec obrażony (blokada do końca sceny)

# Stopień testu (S1) → przewaga gracza (ułamek). Design doc: sukces −10–25%,
# crit −30–50%, crit-fail +10%. Bierzemy środek widełek jako wartość startową.
_DISCOUNT_BY_OUTCOME: dict[str, float] = {
    "CRITICAL_SUCCESS": 0.40,   # −40% (środek 30–50%)
    "SUCCESS": 0.15,            # −15% (środek 10–25%)
    "FAILURE": 0.0,             # cena bez zmian
    "CRITICAL_FAILURE": -0.10,  # +10% drożej + kupiec obrażony
}

# Klampy ekonomiczne (Numbers Policy).
_BUY_MULT_FLOOR = 0.4    # cena kupna nigdy < 40% bazy
_BUY_MULT_CEIL = 2.0
_SELL_RATIO_FLOOR = 0.10
_SELL_RATIO_CEIL = 0.95


def discount_for_outcome(outcome: str) -> float:
    """Mapuj stopień testu umiejętności na przewagę gracza (ułamek)."""
    return _DISCOUNT_BY_OUTCOME.get(str(outcome or "").upper(), 0.0)


def apply_haggle_outcome(session_flags: dict, outcome: str) -> dict:
    """Zapisz wynik testu targowania do ``session_flags`` (mutacja in-place).

    Ustawia jednorazowy ``haggle_discount``; krytyczna porażka dodatkowo ustawia
    ``haggle_blocked`` (kupiec obrażony → blokada ponownego targowania w scenie).
    Zwraca słownik podsumowania dla logów/UI.
    """
    discount = discount_for_outcome(outcome)
    session_flags[_FLAG_DISCOUNT] = discount
    blocked = str(outcome or "").upper() == "CRITICAL_FAILURE"
    if blocked:
        session_flags[_FLAG_BLOCKED] = True
    return {"discount": discount, "blocked": blocked}


def peek_haggle_discount(session_flags: dict) -> float:
    """Podgląd aktywnego rabatu BEZ konsumpcji (dla UI sklepu)."""
    try:
        return float(session_flags.get(_FLAG_DISCOUNT) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def consume_haggle_discount(session_flags: dict) -> float:
    """Zwróć aktywny rabat i usuń go (jednorazowy — najbliższa transakcja)."""
    discount = peek_haggle_discount(session_flags)
    session_flags.pop(_FLAG_DISCOUNT, None)
    return discount


def is_haggle_blocked(session_flags: dict) -> bool:
    """Czy kupiec jest obrażony (blokada ponownego targowania)."""
    return bool(session_flags.get(_FLAG_BLOCKED))


def clear_haggle_block(session_flags: dict) -> None:
    """Zdejmij blokadę (np. przy zmianie lokacji/sceny)."""
    session_flags.pop(_FLAG_BLOCKED, None)


def _clamp(value: float, lo: float, hi: float) -> float:
    return round(max(lo, min(hi, value)), 4)


def effective_buy_multiplier(cha_buy_multiplier: float, discount: float) -> float:
    """Łączny mnożnik ceny kupna: pasywne CHA (F10) × targowanie, z klampem.

    discount > 0 → taniej; discount < 0 (crit-fail) → drożej.
    """
    raw = float(cha_buy_multiplier) * (1.0 - float(discount))
    return _clamp(raw, _BUY_MULT_FLOOR, _BUY_MULT_CEIL)


def effective_sell_ratio(cha_sell_ratio: float, discount: float) -> float:
    """Łączny współczynnik ceny sprzedaży: CHA × targowanie, z klampem.

    discount > 0 → drożej sprzedasz; discount < 0 → mniej dostaniesz.
    """
    raw = float(cha_sell_ratio) * (1.0 + float(discount))
    return _clamp(raw, _SELL_RATIO_FLOOR, _SELL_RATIO_CEIL)
