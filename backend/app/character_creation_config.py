"""Editable knobs for character creation (stats roll, skill budget)."""

from __future__ import annotations

import random
from typing import Final

# --- Skill budget (creation only) ---
SKILL_BUDGET: Final = {
    "warrior": {"slots": 8, "active_skills": 7},
    "scholar": {"slots": 10, "active_skills": 8},
}

ARCHETYPE_SKILL_WEIGHTS: Final = {
    "warrior": [
        "athletics",
        "melee_attack",
        "endurance",
        "intimidation",
        "survival",
    ],
    "scholar": [
        "arcana",
        "lore",
        "investigation",
        "medicine",
        "awareness",
    ],
}

MAX_SKILL_LVL_AT_CREATION: Final = 2
PLAYER_SWAP_SLOTS: Final = 4

# Full skill key pool used at creation (matches prior backend + extras).
CREATION_SKILL_POOL: Final = frozenset(
    {
        "athletics",
        "stealth",
        "sleight_of_hand",
        "endurance",
        "arcana",
        "investigation",
        "lore",
        "awareness",
        "survival",
        "medicine",
        "persuasion",
        "intimidation",
        "melee_attack",
        "ranged_attack",
        "spell_attack",
        "alchemy",
    }
)


def roll_4d6_drop_lowest(rng: random.Random | None = None) -> int:
    """Roll 4d6, drop lowest die, sum the rest. Result in 3–18."""
    g = rng or random
    dice = [g.randint(1, 6) for _ in range(4)]
    dice.sort()
    return sum(dice[1:])


def _weighted_sample_without_replacement(
    items: list[str],
    weight_fn,
    k: int,
    rng: random.Random,
) -> list[str]:
    pool = list(items)
    out: list[str] = []
    for _ in range(min(k, len(pool))):
        weights = [weight_fn(x) for x in pool]
        choice = rng.choices(pool, weights=weights, k=1)[0]
        idx = pool.index(choice)
        out.append(choice)
        pool.pop(idx)
    return out


def roll_creation_skills(archetype: str, rng: random.Random | None = None) -> dict[str, int]:
    """
    Weighted random skill ranks at creation. All keys in _CREATION_SKILL_POOL appear;
    inactive skills are 0. Ranks are capped at MAX_SKILL_LVL_AT_CREATION.
    """
    g = rng or random.Random()
    a = (archetype or "warrior").strip().lower()
    if a not in SKILL_BUDGET:
        a = "warrior"
    cfg = SKILL_BUDGET[a]
    preferred = set(ARCHETYPE_SKILL_WEIGHTS.get(a, ()))
    pool = sorted(CREATION_SKILL_POOL)

    def wfn(key: str) -> int:
        return 3 if key in preferred else 1

    n_act = min(cfg["active_skills"], len(pool))
    picked = _weighted_sample_without_replacement(pool, wfn, n_act, g)

    ranks: dict[str, int] = {k: 0 for k in CREATION_SKILL_POOL}
    for pk in picked:
        ranks[pk] = 1

    extra = int(cfg["slots"]) - len(picked)
    for _ in range(max(0, extra)):
        eligible = [k for k in picked if ranks[k] < MAX_SKILL_LVL_AT_CREATION]
        if not eligible:
            break
        k = g.choice(eligible)
        ranks[k] += 1

    return ranks
