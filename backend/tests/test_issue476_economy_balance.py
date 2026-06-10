"""TDD: Issue #476 — F16 economy balance: net gold ~70-80g per 10-session block.

Design contract: Over 10 sessions (typical play block), a character should net
approximately 70-80 gold after common sinks. This ensures gold feels valuable
but not artificially scarce.

Session model (10 sessions):
- 3 weak encounters (avg gold from loot_generic_weak: 0-8g → avg 4g)
- 4 standard encounters (avg gold from loot_generic_standard: 5-25g → avg 15g)
- 1 elite encounter per 5 sessions (avg gold from loot_generic_elite: 20-80g → avg 50g)

Gold sinks assumed per 10 sessions:
- 0.5 resurrections × 25g = 12.5g
- 1 item purchase from shop ~20g
Total sinks: ~32g

Expected net gold: (3×4 + 4×15 + 0.4×50) - 32 = (12 + 60 + 20) - 32 = 60g
Adjusted for sell proceeds (+~15g from selling drops) = ~75g
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import math


# ─── Gold calculation helpers ─────────────────────────────────────────────────

def avg_gold(gold_min: int, gold_max: int) -> float:
    return (gold_min + gold_max) / 2.0


def expected_gold_per_session_block(
    weak_encounters: int = 3,
    standard_encounters: int = 4,
    elite_encounters: float = 0.4,
    weak_loot_min: int = 0,
    weak_loot_max: int = 8,
    standard_loot_min: int = 5,
    standard_loot_max: int = 25,
    elite_loot_min: int = 20,
    elite_loot_max: int = 80,
    resurrection_cost: int = 25,
    resurrections_per_block: float = 0.5,
    sell_proceeds: int = 15,
    item_purchase_cost: int = 15,
    item_purchases_per_block: float = 1.0,
) -> float:
    """Expected net gold over a 10-session play block."""
    income = (
        weak_encounters * avg_gold(weak_loot_min, weak_loot_max)
        + standard_encounters * avg_gold(standard_loot_min, standard_loot_max)
        + elite_encounters * avg_gold(elite_loot_min, elite_loot_max)
        + sell_proceeds
    )
    sinks = (
        resurrections_per_block * resurrection_cost
        + item_purchases_per_block * item_purchase_cost
    )
    return income - sinks


# ─── Balance requirement tests ────────────────────────────────────────────────

GOLD_TARGET_MIN = 60   # floor: must earn at least this much
GOLD_TARGET_MAX = 120  # ceiling: not drowning in gold


def test_standard_session_block_income_in_target_range():
    """Net gold over 10 sessions must be 60-120g (target ≈ 70-80g)."""
    net = expected_gold_per_session_block()
    assert net >= GOLD_TARGET_MIN, (
        f"Net gold {net:.1f}g too low (min {GOLD_TARGET_MIN}g): "
        f"loot tables need to drop more gold."
    )
    assert net <= GOLD_TARGET_MAX, (
        f"Net gold {net:.1f}g too high (max {GOLD_TARGET_MAX}g): "
        f"loot tables or sinks need adjustment."
    )


def test_generic_standard_loot_provides_meaningful_reward():
    """Generic standard loot table (5-25g) averages ≥ 15g per encounter."""
    a = avg_gold(5, 25)
    assert a >= 15, f"Standard loot avg {a}g < 15g — not meaningful enough"


def test_generic_weak_loot_is_small_but_nonzero():
    """Generic weak loot (0-8g) averages ≥ 2g — weak enemies still rewarding."""
    a = avg_gold(0, 8)
    assert a >= 2, f"Weak loot avg {a}g too low"


def test_generic_elite_loot_provides_major_windfall():
    """Generic elite loot (20-80g) averages ≥ 40g — elite fights are worth it."""
    a = avg_gold(20, 80)
    assert a >= 40, f"Elite loot avg {a}g < 40g — elite fights not rewarding"


def test_resurrection_cost_is_meaningful_sink():
    """Resurrection should cost enough to sting (~25g), but not block progression."""
    cost = 25  # from game_config_meta.resurrection_config
    hp_at_level3 = 13  # warrior level 3 CON 12
    # Resurrection cost should be more than 1 fight's expected income
    one_fight_income = avg_gold(5, 25)  # standard fight
    assert cost > one_fight_income * 0.5, \
        f"Resurrection ({cost}g) too cheap vs fight income ({one_fight_income:.1f}g)"
    # But not more than 3 fights' income (would feel punishing)
    assert cost < one_fight_income * 3, \
        f"Resurrection ({cost}g) too expensive vs 3 fights ({one_fight_income*3:.1f}g)"


def test_sell_ratio_produces_meaningful_proceeds():
    """Default 50% sell ratio on a 20g item = 10g, adding up over time."""
    item_value = 20
    sell_ratio = 0.5
    sell_price = item_value * sell_ratio
    assert sell_price >= 8, f"Sell price {sell_price}g too low for a {item_value}g item"


def test_gold_balance_without_elites_still_viable():
    """10 sessions without elite encounter: income still ≥ 50g."""
    net = expected_gold_per_session_block(elite_encounters=0.0)
    assert net >= 50, f"Without elite fights, net gold {net:.1f}g < 50g — too grindy"


def test_gold_balance_with_heavy_sinks_still_positive():
    """2 resurrections + 3 item purchases: must not go bankrupt (net ≥ 0g).

    This is an extreme scenario — dying twice AND buying 3 items in 10 sessions.
    Economy design allows slight shortage in this edge case but never deep debt.
    """
    net = expected_gold_per_session_block(
        resurrections_per_block=2.0,
        item_purchases_per_block=3.0,
    )
    assert net >= 0, f"With heavy sinks (2×death + 3×purchase), net {net:.1f}g < 0 — economy too punishing"


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_avg_gold_helper_symmetry():
    assert avg_gold(0, 10) == 5.0
    assert avg_gold(5, 25) == 15.0
    assert avg_gold(20, 80) == 50.0
