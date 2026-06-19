"""TDD: Issue #826 — spójny model obrony (jeden rzut obronny + pancerz=redukcja + margines→dmg).

Testy jednostkowe czystych helperów silnika walki (bez DB) + osiągalność skilli reakcji.
Pokrywają kryteria akceptacji #826 punkt po punkcie.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.combat_service import (  # noqa: E402
    ARMOR_REDUCTION_OFFSET,
    MARGIN_DAMAGE_BONUS,
    MARGIN_DAMAGE_STEP,
    apply_defense_model,
    compute_enemy_attack_hit,
    _armor_value,
    _margin_damage_bonus,
)
from app.character_creation_config import (  # noqa: E402
    CREATION_SKILL_POOL,
    roll_creation_skills,
)
import random  # noqa: E402


# ─── #826 pkt.3: Margines sukcesu → obrażenia ─────────────────────────────────

def test_margin_below_step_gives_no_bonus():
    """Trafienie o mniej niż próg (5) → brak bonusu marginesowego."""
    assert _margin_damage_bonus(attack_total=14, defense_stat=10) == 0  # margines 4 < 5


def test_margin_one_step_gives_one_bonus():
    """Trafienie 5–9 pkt ponad obronę → +1 dmg (jeden próg)."""
    assert _margin_damage_bonus(attack_total=15, defense_stat=10) == 1 * MARGIN_DAMAGE_BONUS
    assert _margin_damage_bonus(attack_total=19, defense_stat=10) == 1 * MARGIN_DAMAGE_BONUS


def test_margin_two_steps_gives_two_bonus():
    """Trafienie 10–14 pkt ponad obronę → +2 dmg (dwa progi)."""
    assert _margin_damage_bonus(attack_total=20, defense_stat=10) == 2 * MARGIN_DAMAGE_BONUS


def test_margin_negative_no_bonus():
    """Atak poniżej obrony (teoretyczny) → brak bonusu, nie ujemny."""
    assert _margin_damage_bonus(attack_total=8, defense_stat=12) == 0


# ─── #826 pkt.2: Pancerz = redukcja obrażeń ───────────────────────────────────

def test_armor_value_is_offset_above_baseline():
    """Pancerz = ac_base − OFFSET, nigdy ujemny."""
    assert _armor_value(16) == max(0, 16 - ARMOR_REDUCTION_OFFSET)
    assert _armor_value(8) == 0  # poniżej nieopancerzonego progu → 0


def test_armor_reduces_damage():
    """ac_base redukuje obrażenia po trafieniu (nie blokuje trafienia)."""
    # bazowe 10 dmg, atak ledwo trafia (margines 0), pancerz ac_base=16 → redukcja 6
    res = apply_defense_model(base_damage=10, attack_total=12, defense_stat=16, ignore_armor=False)
    assert res["armor_reduction"] == _armor_value(16)
    assert res["final"] == 10 - _armor_value(16)


def test_armor_min_one_damage_on_hit():
    """Gruby pancerz nie zeruje trafienia — min 1 dmg (zabezpieczenie z Numbers Policy)."""
    res = apply_defense_model(base_damage=2, attack_total=12, defense_stat=99, ignore_armor=False)
    assert res["final"] == 1


def test_nat20_ignores_armor():
    """Nat 20 (ignore_armor) pomija pancerz całkowicie."""
    res = apply_defense_model(base_damage=10, attack_total=12, defense_stat=99, ignore_armor=True)
    assert res["armor_reduction"] == 0
    assert res["final"] >= 10


def test_zero_damage_stays_zero():
    """Brak obrażeń wejściowych (np. udany unik) → 0 (nie min 1)."""
    res = apply_defense_model(base_damage=0, attack_total=20, defense_stat=10, ignore_armor=False)
    assert res["final"] == 0


def test_margin_and_armor_combined():
    """Margines dodaje PRZED redukcją pancerza; oba widoczne w wyniku."""
    # atak 22 vs obrona 10 → margines 12 → 2 progi → +2; baza 8 → 10; pancerz=0 (ac 10) → 10
    res = apply_defense_model(base_damage=8, attack_total=22, defense_stat=10, ignore_armor=False)
    assert res["margin_bonus"] == 2 * MARGIN_DAMAGE_BONUS
    assert res["final"] == 8 + 2 * MARGIN_DAMAGE_BONUS  # ac_base 10 → armor 0


# ─── #826 pkt.1: Jeden rzut obronny — koniec double jeopardy ───────────────────

def test_enemy_hit_nat1_auto_miss():
    """Nat 1 wroga = auto-pudło niezależnie od uniku gracza."""
    assert compute_enemy_attack_hit(attack_roll=30, raw_d20=1, player_evasion_total=5) is False


def test_enemy_hit_nat20_auto_hit():
    """Nat 20 wroga = auto-trafienie niezależnie od uniku gracza."""
    assert compute_enemy_attack_hit(attack_roll=2, raw_d20=20, player_evasion_total=99) is True


def test_enemy_hit_opposed_defender_wins_ties():
    """Pojedynczy test: trafienie gdy attack > evasion; remis = obrońca wygrywa (miss)."""
    assert compute_enemy_attack_hit(attack_roll=15, raw_d20=10, player_evasion_total=14) is True
    assert compute_enemy_attack_hit(attack_roll=14, raw_d20=10, player_evasion_total=14) is False  # remis
    assert compute_enemy_attack_hit(attack_roll=13, raw_d20=10, player_evasion_total=14) is False


def test_no_double_jeopardy_single_evasion_decides():
    """Regresja double jeopardy: trafienie zależy WYŁĄCZNIE od jednego testu uniku,
    nie od przebicia AC PLUS uniku. Niski atak (poniżej dawnego AC) i tak idzie przez unik."""
    # Atak 9 — kiedyś nie przebiłby AC 12 (auto-miss bez szansy na unik dla gracza).
    # Teraz: jeśli evasion gracza < 9 → trafia (gracz miał realny pojedynczy test, nie podwójny).
    assert compute_enemy_attack_hit(attack_roll=9, raw_d20=9, player_evasion_total=8) is True
    assert compute_enemy_attack_hit(attack_roll=9, raw_d20=9, player_evasion_total=10) is False


# ─── #826 pkt.4: Skille reakcji osiągalne ─────────────────────────────────────

def test_dodge_and_shield_block_in_creation_pool():
    """`dodge` i `shield_block` są w puli losowania tworzenia postaci (były martwe)."""
    assert "dodge" in CREATION_SKILL_POOL
    assert "shield_block" in CREATION_SKILL_POOL


def test_warrior_can_roll_shield_block():
    """Wojownik (biasowany shield_block) realnie losuje blok w wielu seedach (#744)."""
    got_shield = False
    for seed in range(200):
        ranks = roll_creation_skills("warrior", random.Random(seed))
        if int(ranks.get("shield_block", 0) or 0) >= 1:
            got_shield = True
            break
    assert got_shield, "wojownik nigdy nie wylosował shield_block w 200 seedach"


def test_rogue_can_roll_dodge():
    """Łotrzyk (biasowany dodge) realnie losuje unik w wielu seedach."""
    got_dodge = False
    for seed in range(200):
        ranks = roll_creation_skills("rogue", random.Random(seed))
        if int(ranks.get("dodge", 0) or 0) >= 1:
            got_dodge = True
            break
    assert got_dodge, "łotrzyk nigdy nie wylosował dodge w 200 seedach"


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_existing_skills_still_in_pool():
    """Stare skille nie zniknęły z puli (zero regresji tworzenia postaci)."""
    for k in ("athletics", "stealth", "melee_attack", "arcana", "alchemy"):
        assert k in CREATION_SKILL_POOL


def test_roll_creation_skills_shape_unchanged():
    """roll_creation_skills nadal zwraca rank dla KAŻDEGO klucza puli (kontrakt niezmieniony)."""
    ranks = roll_creation_skills("warrior", random.Random(1))
    assert set(ranks.keys()) == set(CREATION_SKILL_POOL)
    assert all(isinstance(v, int) for v in ranks.values())
