"""Issue #1475 — domknięcie: bonus +2 many rasy + tempo rozwoju czarów gisha.

Follow-upy z rekordu #1547:
  * Piętnowany +2 max_many (RACE_MANA_BONUS) — SIEDZI W FORMULE calculate_mana,
    więc każda ścieżka przeliczająca (rest/xp/resurrection/admin/creation) daje
    ten sam wynik — path-independent (#1466),
  * Wojownik-Mag (gish) rozwija czary WOLNIEJ: płaci 2× XP (odwzorowanie designowego
    „1 pkt arkanów / 2 poziomy"; arcane_points są martwe, waluta = XP),
  * gish JEST casterem w ekonomii XP (endpoint spend-spell nie odrzuca go).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.characters import (
    GISH_SPELL_XP_MULTIPLIER,
    SPELL_LEARN_COST,
    SPELL_UPGRADE_COSTS,
)
from app.services.vitality_service import (
    RACE_MANA_BONUS,
    calculate_mana,
    is_caster,
    recompute_max_mana,
)


# ─── Bonus +2 many rasy (path-independent) ───────────────────────────────────

def test_pietnowani_mana_bonus_constant():
    assert RACE_MANA_BONUS["pietnowani"] == 2


def test_scholar_pietnowani_gets_plus_two_mana():
    # Uczony INT 14 (mod +2) L1: człowiek 8+2=10; Piętnowany 10+2=12.
    assert calculate_mana("scholar", 14, 1, "human") == 10
    assert calculate_mana("scholar", 14, 1, "pietnowani") == 12


def test_gish_pietnowani_gets_plus_two_mana():
    # Gish INT 14 (mod +2) L1: baza 4 + (2×1)//2 = 5; Piętnowany 5+2=7.
    assert calculate_mana("wojownik_mag", 14, 1, "human") == 5
    assert calculate_mana("wojownik_mag", 14, 1, "pietnowani") == 7


def test_mana_bonus_only_for_casters():
    # Wojownik nie dostaje many niezależnie od rasy.
    assert calculate_mana("warrior", 14, 1, "pietnowani") == 0


def test_other_races_no_mana_bonus():
    assert calculate_mana("scholar", 14, 1, "elf") == 10
    assert calculate_mana("scholar", 14, 1, "dwarf") == 10


def test_recompute_is_path_independent_with_race():
    """Ten sam wynik z formuły niezależnie od ścieżki — recompute == calculate."""
    for lvl in (1, 3, 5, 8):
        assert recompute_max_mana("scholar", 14, lvl, "pietnowani") == calculate_mana("scholar", 14, lvl, "pietnowani")
        assert recompute_max_mana("wojownik_mag", 14, lvl, "pietnowani") == calculate_mana("wojownik_mag", 14, lvl, "pietnowani")


def test_default_race_is_human_no_bonus():
    # Wywołanie bez rasy = człowiek = brak bonusu (bezpieczny domyślny).
    assert calculate_mana("scholar", 14, 1) == 10


# ─── Tempo rozwoju czarów gisha (2× XP) ──────────────────────────────────────

def test_gish_xp_multiplier_is_two():
    assert GISH_SPELL_XP_MULTIPLIER == 2


def test_gish_learn_costs_double():
    scholar_cost = SPELL_LEARN_COST
    gish_cost = SPELL_LEARN_COST * GISH_SPELL_XP_MULTIPLIER
    assert gish_cost == 150 and scholar_cost == 75


def test_gish_upgrade_r2_costs_double():
    # Gish może rozwijać tylko do R2 (cap PN-2); R2 = 50 XP × 2 = 100.
    assert SPELL_UPGRADE_COSTS[2] * GISH_SPELL_XP_MULTIPLIER == 100


def test_gish_is_caster_for_xp_economy():
    # Endpoint spend-spell bramkuje przez is_caster — gish nie może być odrzucony.
    assert is_caster("wojownik_mag") is True
