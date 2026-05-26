"""
Vitality Service — V2 Phase 02 Task 05

HP and Mana formulas. Single source of truth for both backend
(character creation, level-up) and as documentation for the frontend
(wizard live preview).

Formulas:
  HP   = base_hp[archetype] + CON_modifier × level   (min 1)
  Mana = 8 + INT_modifier × level                     (Scholar only, min 1)
  Mana = 0                                             (Warrior)

Base HP constants match game_config_archetypes.hp_base:
  Warrior: 10
  Scholar: 6
"""

from __future__ import annotations

# ── Base values ────────────────────────────────────────────────────────────

ARCHETYPE_BASE_HP: dict[str, int] = {
    "warrior": 10,
    "scholar": 6,
    "ranger":  8,   # future archetype — forward-compatible
}

ARCHETYPE_BASE_MANA: dict[str, int] = {
    "warrior": 0,
    "scholar": 8,
    "ranger":  0,
}


# ── Core formulas ──────────────────────────────────────────────────────────

def stat_modifier(stat_value: int) -> int:
    """Standard RPG modifier: (stat - 10) // 2. Integer division toward -inf."""
    return (int(stat_value) - 10) // 2


# ── Wound penalties (issue #26, Option A — mild) ───────────────────────────
#
# Low-HP characters take mechanical penalties in addition to the cosmetic
# wound labels emitted from context_injector. Thresholds use the same HP%
# breakpoints as the labels in context_injector._WOUND_LABELS so the visual
# severity stamp matches the mechanical effect.
#
#   HP% range     Label                      ATK   DEX
#   ──────────────────────────────────────────────────
#   > 25%          (mild / none)             0     0
#   11 – 25%       Poważnie ranny/a          -1    0
#   1 – 10%        Ciężko ranny / Na skraju  -2   -1
#
# Returned dict is intentionally additive — callers add the values onto
# their existing modifier totals without needing to know which tier fired.


def wound_penalty(sheet: dict) -> dict[str, int]:
    """Compute attack/DEX wound penalties from current HP fraction.

    Returns ``{"atk": int <= 0, "dex": int <= 0, "tier": str}`` where tier
    is ``""`` / ``"severe"`` / ``"critical"`` for downstream display.
    """
    try:
        cur = int(sheet.get("current_hp") or 0)
        mx = int(sheet.get("max_hp") or 0)
    except (TypeError, ValueError):
        return {"atk": 0, "dex": 0, "tier": ""}
    if mx <= 0 or cur <= 0:
        return {"atk": 0, "dex": 0, "tier": ""}
    pct = (cur / mx) * 100.0
    if pct <= 10:
        return {"atk": -2, "dex": -1, "tier": "critical"}
    if pct <= 25:
        return {"atk": -1, "dex": 0, "tier": "severe"}
    return {"atk": 0, "dex": 0, "tier": ""}


def calculate_hp(archetype: str, con: int, level: int = 1) -> int:
    """
    HP = base_hp + CON_modifier × level.  Minimum 1.

    Args:
        archetype: "warrior" | "scholar" | "ranger"
        con: CON stat value (e.g. 12)
        level: character level (1 at creation)
    """
    arc = archetype.lower()
    base = ARCHETYPE_BASE_HP.get(arc, 10)
    return max(1, base + stat_modifier(con) * level)


def calculate_mana(archetype: str, int_stat: int, level: int = 1) -> int:
    """
    Mana = 8 + INT_modifier × level  (Scholar only, minimum 1).
    Warriors and Rangers always return 0.

    Args:
        archetype: "warrior" | "scholar" | "ranger"
        int_stat: INT stat value (e.g. 12)
        level: character level (1 at creation)
    """
    arc = archetype.lower()
    if arc != "scholar":
        return 0
    base = ARCHETYPE_BASE_MANA["scholar"]
    return max(1, base + stat_modifier(int_stat) * level)


def apply_level_up(
    archetype: str,
    current_max_hp: int,
    current_max_mana: int,
    con: int,
    int_stat: int,
) -> tuple[int, int]:
    """
    Calculate new max_hp and max_mana after gaining one level.

    Rules:
    - max_hp += CON_modifier (never decreases below current max)
    - max_mana += INT_modifier (Scholar only, never decreases below current max)

    Returns:
        (new_max_hp, new_max_mana)
    """
    con_mod = stat_modifier(con)
    new_hp = max(current_max_hp, current_max_hp + con_mod)

    if archetype.lower() == "scholar":
        int_mod = stat_modifier(int_stat)
        new_mana = max(current_max_mana, current_max_mana + int_mod)
    else:
        new_mana = current_max_mana  # warriors keep 0

    return new_hp, new_mana
