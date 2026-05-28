"""Editable knobs for character creation (stats roll, skill budget)."""

from __future__ import annotations

import random
from typing import Final

# --- Skill budget (creation only) ---
# All archetypes now roll exactly 7 active skills from their exclusive pool.
SKILL_BUDGET: Final = {
    "warrior": {"slots": 8, "active_skills": 7},
    "scholar": {"slots": 8, "active_skills": 7},
    "rogue":   {"slots": 8, "active_skills": 7},
}

# Preferred skills — rolled with 3× weight. First 3 of these become "locked" slots in UI.
ARCHETYPE_SKILL_WEIGHTS: Final = {
    "warrior": ["melee_attack", "athletics", "endurance", "intimidation", "survival"],
    "scholar": ["arcana", "spell_attack", "lore", "investigation", "medicine"],
    "rogue":   ["stealth", "ranged_attack", "sleight_of_hand", "persuasion", "survival"],
}

# Exclusive per-archetype skill pool — only skills from this set are ever rolled for that archetype.
# Warriors don't get Arcana; Scholars don't get Melee Attack, etc.
ARCHETYPE_SKILL_EXCLUSIVE_POOL: Final = {
    "warrior": frozenset({
        "melee_attack", "athletics", "endurance", "intimidation",
        "survival", "ranged_attack", "stealth", "persuasion",
    }),
    "scholar": frozenset({
        "arcana", "spell_attack", "lore", "investigation",
        "medicine", "awareness", "alchemy", "persuasion",
    }),
    "rogue": frozenset({
        "stealth", "ranged_attack", "sleight_of_hand", "persuasion",
        "survival", "intimidation", "athletics", "awareness",
    }),
}

MAX_SKILL_LVL_AT_CREATION: Final = 2
PLAYER_SWAP_SLOTS: Final = 4
LOCKED_SKILL_COUNT: Final = 3  # first N skills shown in UI are locked (cannot swap to different skill)

# Full skill key pool used at creation (all known skills; fallback only).
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
    Weighted random skill ranks at creation.
    Skills are drawn exclusively from ARCHETYPE_SKILL_EXCLUSIVE_POOL[archetype]
    so each class only gets thematically appropriate skills.
    All keys in CREATION_SKILL_POOL appear in the returned dict; inactive skills = 0.
    """
    g = rng or random.Random()
    a = (archetype or "warrior").strip().lower()
    if a not in SKILL_BUDGET:
        a = "warrior"
    cfg = SKILL_BUDGET[a]
    preferred = set(ARCHETYPE_SKILL_WEIGHTS.get(a, ()))

    # Use archetype-exclusive pool; fall back to full pool if undefined
    exclusive = ARCHETYPE_SKILL_EXCLUSIVE_POOL.get(a, CREATION_SKILL_POOL)
    pool = sorted(exclusive)

    def wfn(key: str) -> int:
        return 3 if key in preferred else 1

    n_act = min(cfg["active_skills"], len(pool))
    picked = _weighted_sample_without_replacement(pool, wfn, n_act, g)

    ranks: dict[str, int] = {k: 0 for k in CREATION_SKILL_POOL}
    for pk in picked:
        ranks[pk] = 1

    # Distribute rank-up points (slots - active = 1 extra rank-up)
    extra = int(cfg["slots"]) - len(picked)
    for _ in range(max(0, extra)):
        eligible = [k for k in picked if ranks[k] < MAX_SKILL_LVL_AT_CREATION]
        if not eligible:
            break
        k = g.choice(eligible)
        ranks[k] += 1

    return ranks
