"""Issue #1475 PN-3 — cechy rasowe Piętnowanych i magia krwi oswojonej.

Zakres:
  * miscast krwi oswojonej: łagodniejszy, flaga blood_miscast, próg Nat 1 (nie 2),
  * odporność na obrażenia nekrotyczne/Rdzenia (−2, min 1) — lustro dwarf toughness,
  * pula czarów startowych Piętnowanego (race_lock='pietnowani', tier 1–2).

Narzut sklepowy +10% (piętno społeczne) = ścieżka DB → smoke/PN-4.
Bonus +2 max_mana ODŁOŻONY (path-independence #1466 — patrz issue).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import spell_service
from app.services.combat_service import (
    PIETNOWANI_RESIST_REDUCTION,
    PIETNOWANI_RESIST_TYPES,
    apply_defense_model,
)


# ─── Miscast krwi oswojonej ──────────────────────────────────────────────────

def test_pietnowani_miscast_is_gentle_and_flagged():
    sheet = {"level": 3, "current_hp": 20}
    res = spell_service.resolve_miscast(sheet, {}, sqlite3.connect(":memory:"), race="pietnowani")
    assert res["blood_miscast"] is True
    assert res["rdzen_miscast"] is False and res["tuning_miscast"] is False
    # L≤4: brak obrażeń własnych, brak ogłuszenia — kontrola zamiast eksplozji.
    assert res["self_damage"] == 0
    assert res["stun"] is False


def test_pietnowani_miscast_threshold_is_nat_one():
    # Człowiek/elf/Piętnowany: tylko Nat 1. Krasnolud: Nat 1–2.
    assert spell_service.is_miscast(1, "pietnowani") is True
    assert spell_service.is_miscast(2, "pietnowani") is False
    assert spell_service.is_miscast(2, "dwarf") is True


def test_pietnowani_high_level_miscast_softer_than_human():
    ph = {"level": 9, "current_hp": 40}
    hp0 = ph["current_hp"]
    res = spell_service.resolve_miscast(dict(ph), {}, sqlite3.connect(":memory:"), race="pietnowani")
    # L8+ gish/uczony: 1d6 obrażeń (max 6) — brak drugorzędnego efektu jak u człowieka (1d8+secondary).
    assert res["self_damage"] <= 6
    assert "secondary" not in res


# ─── Odporność nekrotyczna / Rdzenia ─────────────────────────────────────────

def test_pietnowani_resists_necrotic_and_rdzen():
    assert PIETNOWANI_RESIST_TYPES == {"necrotic", "rdzen"}
    assert PIETNOWANI_RESIST_REDUCTION == 2


def test_defense_model_reduces_necrotic_for_pietnowani():
    # base 8, atak=obrona (brak marginesu), ignore_armor by wyłączyć pancerz z równania.
    out = apply_defense_model(
        8, attack_total=10, defense_stat=10, ignore_armor=True,
        race="pietnowani", damage_type="necrotic",
    )
    assert out["final"] == 6  # 8 − 2
    assert out["toughness_reduction"] == 2


def test_defense_model_physical_unreduced_for_pietnowani():
    out = apply_defense_model(
        8, attack_total=10, defense_stat=10, ignore_armor=True,
        race="pietnowani", damage_type="physical",
    )
    assert out["final"] == 8
    assert out["toughness_reduction"] == 0


def test_defense_model_dwarf_still_works():
    """Zero regresji na krasnoludzie (poison/dark/rdzen −2)."""
    out = apply_defense_model(
        8, attack_total=10, defense_stat=10, ignore_armor=True,
        race="dwarf", damage_type="poison",
    )
    assert out["final"] == 6


def test_necrotic_reduction_floors_at_one():
    out = apply_defense_model(
        2, attack_total=10, defense_stat=10, ignore_armor=True,
        race="pietnowani", damage_type="necrotic",
    )
    assert out["final"] == 1  # max(1, 2 − 2)


# ─── Pula czarów startowych ──────────────────────────────────────────────────

def test_pietnowani_starting_spells_registered():
    assert spell_service.PIETNOWANI_STARTING_SPELLS == (
        "ash_bolt", "salt_ward", "blood_mend", "cinder_snare"
    )
    assert spell_service._RACE_STARTING_SPELLS["pietnowani"] == spell_service.PIETNOWANI_STARTING_SPELLS
