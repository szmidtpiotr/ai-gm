"""TDD: Issue #642 — B2: Rogue HP base = 8 (warrior 10 > rogue 8 > mag 6).

Design (game_mechanics.md CZĘŚĆ AK.2): łotrzyk to zwiadowca/złodziej — ma MNIEJ
HP niż wojownik, WIĘCEJ niż mag. Kanon: warrior 10 / rogue 8 / scholar 6.
Wcześniej rogue dziedziczył domyślne 10 (== warrior), łamiąc filar tożsamości klasy.

Wzór HP niezmienny (Locked Mechanics): HP = base_hp + CON_mod × level (min 1).
Zmienia się TYLKO stała bazowa rogue: 10 → 8.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.vitality_service import calculate_hp, ARCHETYPE_BASE_HP


# ─── Test główny — rogue base HP = 8 ─────────────────────────────────────────

def test_rogue_base_hp_is_8():
    """Łotrzyk z CON 10 (mod 0) na L1 ma dokładnie 8 HP (baza, bez modyfikatora)."""
    assert ARCHETYPE_BASE_HP["rogue"] == 8
    assert calculate_hp("rogue", con=10, level=1) == 8


def test_rogue_hp_with_con_modifier():
    """Wzór niezmienny: rogue CON 12 (mod +1) L1 → 8 + 1 = 9 HP."""
    assert calculate_hp("rogue", con=12, level=1) == 9


# ─── Ordering tożsamości klas — warrior > rogue > scholar ────────────────────

def test_hp_class_ordering_warrior_rogue_scholar():
    """Przy tym samym CON: wojownik > łotrzyk > mag (filar tożsamości AK.2)."""
    con = 14  # mod +2 — ta sama wartość dla wszystkich, izoluje bazę
    warrior = calculate_hp("warrior", con=con, level=1)
    rogue = calculate_hp("rogue", con=con, level=1)
    scholar = calculate_hp("scholar", con=con, level=1)
    assert warrior > rogue > scholar, (warrior, rogue, scholar)


# ─── Backward compatibility — pozostałe klasy bez zmian ──────────────────────

def test_warrior_base_hp_unchanged():
    """Wojownik zostaje 10 (nie ruszamy balansu walk #475)."""
    assert ARCHETYPE_BASE_HP["warrior"] == 10
    assert calculate_hp("warrior", con=10, level=1) == 10


def test_scholar_base_hp_unchanged():
    """Mag zostaje 6 (poprawnie kruchy)."""
    assert ARCHETYPE_BASE_HP["scholar"] == 6
    assert calculate_hp("scholar", con=10, level=1) == 6
