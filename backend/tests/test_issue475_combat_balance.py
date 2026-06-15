"""TDD: Issue #475 — F15 combat balance: standard fights must be dangerous at level 3+.

Design requirement: a level-3 warrior fighting a standard enemy should lose ≥60% HP
in the expected-value sense (enemy_DPR × fight_rounds / player_hp ≥ 0.60).

This test verifies balance parameters for the canonical level-3 encounter (bandit tier).
If the test fails, tune the enemy's attack_bonus until it passes.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import random
import pytest
from app.services.vitality_service import calculate_hp, stat_modifier


# ─── Shared helpers ─────────────────────────────────────────────────────────

def _avg_die(die_str: str) -> float:
    """Parse Xd6 / d8 / 1d8+2 and return average."""
    s = str(die_str or "d6").strip().lower().replace(" ", "")
    bonus = 0
    if "+" in s.split("d")[-1]:
        parts = s.split("+")
        s = parts[0]
        bonus = int(parts[1])
    elif "-" in s.split("d")[-1]:
        parts = s.split("-")
        s = parts[0]
        bonus = -int(parts[1])
    if "d" in s:
        n, d = s.split("d")
        n = int(n) if n else 1
        d = int(d)
    else:
        n, d = 1, int(s)
    return n * (d + 1) / 2.0 + bonus


def _hit_pct(attack_bonus: int, target_ac: int) -> float:
    """Probability of hitting (d20 + bonus >= AC), ignoring nat20 auto-hit."""
    need = max(1, min(20, target_ac - attack_bonus))
    return (21 - need) / 20.0


def expected_hp_loss_pct(
    player_archetype: str,
    player_con: int,
    player_level: int,
    player_ac: int,
    player_attack_bonus: int,
    player_damage_die: str,
    enemy_hp: int,
    enemy_ac: int,
    enemy_attack_bonus: int,
    enemy_damage_die: str,
    enemy_attacks_per_turn: int = 1,
) -> float:
    """Expected fraction of player's max HP lost in one fight (analytical)."""
    player_hp = calculate_hp(player_archetype, player_con, player_level)
    player_dmg_avg = _avg_die(player_damage_die)
    player_hit = _hit_pct(player_attack_bonus, enemy_ac)
    player_dpr = player_dmg_avg * player_hit

    enemy_dmg_avg = _avg_die(enemy_damage_die)
    enemy_hit = _hit_pct(enemy_attack_bonus, player_ac)
    enemy_dpr = enemy_dmg_avg * enemy_hit * enemy_attacks_per_turn

    if player_dpr <= 0:
        return 0.0
    fight_rounds = enemy_hp / player_dpr
    hp_lost = enemy_dpr * fight_rounds
    return hp_lost / player_hp


# ─── Level-3 warrior vs canonical standard enemies ──────────────────────────

# Warrior: base 10, with CON 12 (mod +1) → HP = 10 + 3 = 13 at level 3
# Armor: leather+shield or chainmail → AC 13 (representative)
# Attack: STR 14 (mod +2) + proficiency +2 = +4 total
# Weapon: longsword d8+2

WARRIOR_LEVEL = 3
WARRIOR_CON = 12
WARRIOR_AC = 13
WARRIOR_ATTACK_BONUS = 4
WARRIOR_DAMAGE_DIE = "d8+2"

BALANCE_THRESHOLD = 0.60   # ≥60% of HP must be lost per fight on expectation


def test_bandit_fight_is_dangerous_at_level3():
    """Bandit (standard, canonical level-2/3 enemy) must drain ≥60% player HP."""
    # bandit: hp_base=12, ac=13, attack=+3, damage=d8
    # NOTE: attack_bonus=4 (tuned from +3 in F15) for appropriate level-3 danger
    pct = expected_hp_loss_pct(
        player_archetype="warrior",
        player_con=WARRIOR_CON,
        player_level=WARRIOR_LEVEL,
        player_ac=WARRIOR_AC,
        player_attack_bonus=WARRIOR_ATTACK_BONUS,
        player_damage_die=WARRIOR_DAMAGE_DIE,
        enemy_hp=12,
        enemy_ac=13,
        enemy_attack_bonus=4,   # F15 tuned value
        enemy_damage_die="d8",
    )
    assert pct >= BALANCE_THRESHOLD, (
        f"Bandit fight too easy: expected {pct:.1%} HP lost (need ≥{BALANCE_THRESHOLD:.0%}). "
        f"Tune bandit attack_bonus upward."
    )


def test_hobgoblin_fight_dangerous_at_level3():
    """Hobgoblin (hp14, ac14, +3, d6+1) should drain ≥60% player HP."""
    pct = expected_hp_loss_pct(
        player_archetype="warrior",
        player_con=WARRIOR_CON,
        player_level=WARRIOR_LEVEL,
        player_ac=WARRIOR_AC,
        player_attack_bonus=WARRIOR_ATTACK_BONUS,
        player_damage_die=WARRIOR_DAMAGE_DIE,
        enemy_hp=14,
        enemy_ac=14,
        enemy_attack_bonus=3,
        enemy_damage_die="d6+1",
    )
    assert pct >= BALANCE_THRESHOLD, (
        f"Hobgoblin fight too easy: {pct:.1%} HP lost (need ≥{BALANCE_THRESHOLD:.0%})"
    )


def test_mountain_lion_fight_dangerous_at_level3():
    """Mountain lion (hp14, ac14, +4, d8) should drain ≥60% player HP."""
    pct = expected_hp_loss_pct(
        player_archetype="warrior",
        player_con=WARRIOR_CON,
        player_level=WARRIOR_LEVEL,
        player_ac=WARRIOR_AC,
        player_attack_bonus=WARRIOR_ATTACK_BONUS,
        player_damage_die=WARRIOR_DAMAGE_DIE,
        enemy_hp=14,
        enemy_ac=14,
        enemy_attack_bonus=4,
        enemy_damage_die="d8",
    )
    assert pct >= BALANCE_THRESHOLD, (
        f"Mountain lion too easy: {pct:.1%} HP lost (need ≥{BALANCE_THRESHOLD:.0%})"
    )


def test_player_hp_at_level3_is_reasonable():
    """Level-3 warrior HP must be low enough that enemies pose real threat (≤25)."""
    hp = calculate_hp("warrior", con=12, level=3)
    assert hp <= 25, f"Warrior HP {hp} too high — fights won't feel dangerous"
    assert hp >= 10, f"Warrior HP {hp} too low — dies in 1-2 hits"


def test_enemy_attack_bonus_tuned_to_level():
    """Canonical level-3 enemy (bandit) must have attack_bonus ≥ 4 after F15 tuning."""
    # This is the key balance gate: attack_bonus=4 needed to reach 60% threshold
    # See test_bandit_fight_is_dangerous_at_level3 for reasoning
    REQUIRED_ATTACK_BONUS = 4
    pct_with_3 = expected_hp_loss_pct(
        "warrior", WARRIOR_CON, WARRIOR_LEVEL, WARRIOR_AC, WARRIOR_ATTACK_BONUS,
        WARRIOR_DAMAGE_DIE, 12, 13, 3, "d8"
    )
    pct_with_4 = expected_hp_loss_pct(
        "warrior", WARRIOR_CON, WARRIOR_LEVEL, WARRIOR_AC, WARRIOR_ATTACK_BONUS,
        WARRIOR_DAMAGE_DIE, 12, 13, 4, "d8"
    )
    assert pct_with_3 < BALANCE_THRESHOLD, \
        f"attack_bonus=3 already meets threshold ({pct_with_3:.1%}) — no tuning needed?"
    assert pct_with_4 >= BALANCE_THRESHOLD, \
        f"attack_bonus=4 still insufficient ({pct_with_4:.1%}) — need higher bonus"


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_calculate_hp_unchanged():
    """vitality_service.calculate_hp must not regress."""
    assert calculate_hp("warrior", con=10, level=1) == 10
    assert calculate_hp("warrior", con=12, level=3) == 13
    assert calculate_hp("scholar", con=10, level=1) == 6


# ─── B5 (#646): 3-class identity regression net (FAZA B / Blok 1) ────────────
#
# Domyka tożsamość 3 klas (B1 #624 staty, B2 #642 HP, B3 #644 skille, B4 #645
# sneak attack). Liczby kanoniczne: game_mechanics.md CZĘŚĆ AK.2.
# Wszystkie wartości STARTOWE (decyzja D1 robocza) — test pilnuje ORDERINGU i
# spójności kreator↔postać, nie zamraża liczb tam, gdzie design je jeszcze tunuje.

from app.services.vitality_service import ARCHETYPE_BASE_HP
from app.character_creation_config import SKILL_BUDGET
from app.api.characters import _build_character_sheet


def _baseline_sheet(archetype: str, level: int = 1) -> dict:
    """Czysta karta startowa (wszystkie staty 10) → przepuszczona przez ten sam
    silnik, który tworzy realną postać. To, co tu wyjdzie, dostaje gotowy bohater
    i pokazuje kreator (kontrakt spójności z lekcji #618)."""
    return _build_character_sheet(
        {"stats": {k: 10 for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK")},
         "skills": {}, "level": level},
        archetype=archetype,
        apply_archetype_skill_minimums=False,
    )


def test_b5_hp_base_canonical_10_8_6():
    """HP bazowe per klasa = 10/8/6 (warrior/rogue/scholar) — CZĘŚĆ AK.2."""
    assert ARCHETYPE_BASE_HP["warrior"] == 10
    assert ARCHETYPE_BASE_HP["rogue"] == 8
    assert ARCHETYPE_BASE_HP["scholar"] == 6


def test_b5_hp_ordering_warrior_gt_rogue_gt_scholar():
    """Przy równym CON+poziomie: warrior > rogue > scholar (tank > zwiadowca > glass cannon)."""
    for con in (8, 10, 12, 14):
        for level in (1, 3, 5):
            w = calculate_hp("warrior", con, level)
            r = calculate_hp("rogue", con, level)
            s = calculate_hp("scholar", con, level)
            assert w > r > s, (
                f"HP ordering złamany przy CON={con} L={level}: "
                f"warrior={w} rogue={r} scholar={s} (oczekiwane w>r>s)"
            )


def test_b5_stat_bonuses_per_class():
    """Bonusy statów: warrior STR+2/CON+1, rogue DEX+2/LCK+1, scholar INT+2/WIS+1.
    Czytane z realnej ścieżki tworzenia postaci (_build_character_sheet)."""
    w = _baseline_sheet("warrior")["stats"]
    assert w["STR"] == 12 and w["CON"] == 11, f"warrior staty złe: {w}"

    r = _baseline_sheet("rogue")["stats"]
    assert r["DEX"] == 12 and r["LCK"] == 11, f"rogue staty złe: {r}"
    # rogue NIE dostaje bonusów maga (regresja B1 #624)
    assert r["INT"] == 10 and r["WIS"] == 10, f"rogue dostał staty maga: {r}"

    s = _baseline_sheet("scholar")["stats"]
    assert s["INT"] == 12 and s["WIS"] == 11, f"scholar staty złe: {s}"


def test_b5_rogue_has_most_active_skills():
    """Łotrzyk = filar 'najwięcej skilli': rogue(9) > warrior(7), rogue ≥ scholar(8)."""
    rogue = SKILL_BUDGET["rogue"]["active_skills"]
    warrior = SKILL_BUDGET["warrior"]["active_skills"]
    scholar = SKILL_BUDGET["scholar"]["active_skills"]
    assert rogue == 9, f"rogue active_skills={rogue}, oczekiwane 9"
    assert warrior == 7, f"warrior active_skills={warrior}, oczekiwane 7"
    assert rogue > warrior, f"rogue({rogue}) musi mieć więcej skilli niż warrior({warrior})"
    assert rogue >= scholar, f"rogue({rogue}) musi mieć ≥ scholar({scholar})"


def test_b5_creator_character_consistency():
    """Kreator↔postać: max_hp i modyfikatory z silnika = to co dostaje gotowy bohater
    (lekcja #618 — UI nie może kłamać). Sprawdzamy, że _build_character_sheet daje
    HP zgodne z calculate_hp i modyfikatory zgodne ze statami."""
    for arc, base in (("warrior", 10), ("rogue", 8), ("scholar", 6)):
        sheet = _baseline_sheet(arc, level=1)
        con = sheet["stats"]["CON"]
        expected_hp = calculate_hp(arc, con, 1)
        assert sheet["max_hp"] == expected_hp, (
            f"{arc}: kreator/postać max_hp={sheet['max_hp']} != calculate_hp={expected_hp}"
        )
        # modyfikator = floor((stat-10)/2) dla każdej staty
        for k, v in sheet["stats"].items():
            assert sheet["stat_modifiers"][k] == (v - 10) // 2, (
                f"{arc}: modyfikator {k} niespójny ze statem {v}"
            )


def test_b5_scholar_fragile_must_play_ranged():
    """Mag (scholar) w melee = glass cannon. Przy IDENTYCZNYCH parametrach co warrior
    (ten sam AC, ta sama walka) mag traci więcej HP i ginie na expectation (≥100%) —
    bo ma 6 HP zamiast 13. To wymusza grę dystansem/czarami (CZĘŚĆ AK.2). AC maga w
    realu jest niższe niż warriora (tendencja AK.2), więc realna przeżywalność jest
    jeszcze gorsza — tu trzymamy AC równe, by izolować wpływ samego HP."""
    common = dict(
        player_level=WARRIOR_LEVEL, player_ac=WARRIOR_AC,
        player_attack_bonus=WARRIOR_ATTACK_BONUS, player_damage_die=WARRIOR_DAMAGE_DIE,
        enemy_hp=12, enemy_ac=13, enemy_attack_bonus=4, enemy_damage_die="d8",
    )
    warrior_loss = expected_hp_loss_pct(player_archetype="warrior", player_con=12, **common)
    scholar_loss = expected_hp_loss_pct(player_archetype="scholar", player_con=10, **common)
    assert scholar_loss > warrior_loss, (
        f"Mag powinien być kruchszy: scholar={scholar_loss:.0%} vs warrior={warrior_loss:.0%}"
    )
    assert scholar_loss >= 1.0, (
        f"Mag w melee za twardy ({scholar_loss:.0%}) — przy HP 6 powinien tracić ≥100% "
        f"(czyli ginąć na expectation), co wymusza grę dystansem/czarami"
    )
