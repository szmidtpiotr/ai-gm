"""Editable knobs for character creation (stats roll, skill budget)."""

from __future__ import annotations

import random
from typing import Final

# --- Skill budget (creation only) ---
SKILL_BUDGET: Final = {
    "warrior": {"slots": 8, "active_skills": 7},
    # Łotrzyk = filar "najwięcej skilli" (CZĘŚĆ AK.2): 10 slotów / 9 aktywnych,
    # więcej niż warrior (7) i ≥ scholar (8).
    "rogue": {"slots": 10, "active_skills": 9},
    "scholar": {"slots": 10, "active_skills": 8},
}

ARCHETYPE_SKILL_WEIGHTS: Final = {
    "warrior": [
        "athletics",
        "attack",  # #1052: was melee_attack (not in catalog); attack is the catalog key
        "endurance",
        "intimidation",
        "survival",
        # #826 pkt.4 (obejmuje #744): wojownik startuje z tarczą — `shield_block` w biasie,
        # by faktycznie mógł blokować. `dodge` też mile widziany na froncie.
        "shield_block",
        "dodge",
    ],
    # Bias złodzieja/zwiadowcy (CZĘŚĆ AK.2). lockpick/acrobatics dołączone do
    # CREATION_SKILL_POOL poniżej, żeby ten bias nie był martwy.
    "rogue": [
        "stealth",
        "lockpick",
        "pickpocket",  # #1052: was sleight_of_hand (not in catalog); pickpocket is the catalog key
        "acrobatics",
        "awareness",
        "investigation",
        # #826 pkt.4: zwinny łotrzyk — `dodge` (DEX) pasuje do profilu uniku.
        "dodge",
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

# Full skill key pool used at creation — all keys must exist in game_config_skills (#1052).
CREATION_SKILL_POOL: Final = frozenset(
    {
        "athletics",
        "stealth",
        "pickpocket",   # #1052: replaces sleight_of_hand (not in catalog)
        "lockpick",
        "acrobatics",
        "endurance",
        "arcana",
        "investigation",
        "lore",
        "awareness",
        "survival",
        "medicine",
        "persuasion",
        "intimidation",
        "attack",       # #1052: replaces melee_attack/ranged_attack/spell_attack (unified combat)
        "alchemy",
        # #826 pkt.4: skille reakcji osiągalne losowo/zamianą (wcześniej poza pulą → martwe).
        # `dodge` = aktywny unik (DEX), `shield_block` = blok tarczą (STR + założona tarcza).
        "dodge",
        "shield_block",
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


def roll_creation_skills(
    archetype: str, rng: random.Random | None = None, race: str = "human"
) -> dict[str, int]:
    """
    Weighted random skill ranks at creation. All keys in _CREATION_SKILL_POOL appear;
    inactive skills are 0. Ranks are capped at MAX_SKILL_LVL_AT_CREATION.

    #1522 — pula jest odsiana bramką archetyp+rasa (`skill_access_service`), więc
    Zwiadowca nie wylosuje Arkanów, a Uczony Bloku Tarczą. Rasa dokłada własny
    bias (elf w kniei, krasnolud w kamieniu), ale niczego nie odbiera.
    """
    from app.services.skill_access_service import (
        RACE_SKILL_WEIGHTS,
        filter_allowed_skills,
    )

    g = rng or random.Random()
    a = (archetype or "warrior").strip().lower()
    if a not in SKILL_BUDGET:
        a = "warrior"
    r = str(race or "human").strip().lower()
    cfg = SKILL_BUDGET[a]
    preferred = set(ARCHETYPE_SKILL_WEIGHTS.get(a, ()))
    race_preferred = set(RACE_SKILL_WEIGHTS.get(r, ()))
    pool = filter_allowed_skills(sorted(CREATION_SKILL_POOL), a, r)

    def wfn(key: str) -> int:
        w = 3 if key in preferred else 1
        return w * 2 if key in race_preferred else w

    n_act = min(cfg["active_skills"], len(pool))
    picked = _weighted_sample_without_replacement(pool, wfn, n_act, g)

    # Klucze spoza puli tej pary archetyp+rasa zostają w arkuszu z rangą 0 —
    # nie znikają, żeby stary kod czytający pełny zestaw kluczy nie padał.
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
