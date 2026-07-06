"""
Vitality Service — V2 Phase 02 Task 05

HP and Mana formulas. Single source of truth for both backend
(character creation, level-up) and as documentation for the frontend
(wizard live preview).

Formulas:
  HP   = base_hp[archetype] + CON_modifier × level   (min 1)
  Mana = 8 + INT_modifier × level                     (Scholar only, min 1)
  Mana = 0                                             (Warrior)

Base HP constants (canonical class balance, game_mechanics.md CZĘŚĆ AK.2):
  Warrior: 10   (tank — najwięcej HP)
  Rogue:    8   (zwiadowca — mniej niż warrior, więcej niż mag)
  Scholar:  6   (glass cannon — najmniej HP)
"""

from __future__ import annotations

# ── Base values ────────────────────────────────────────────────────────────

ARCHETYPE_BASE_HP: dict[str, int] = {
    "warrior": 10,
    "rogue":   8,    # B2 (#642): zwiadowca — mniej HP niż warrior, więcej niż mag
    "scholar": 6,
    "ranger":  8,    # future archetype — forward-compatible
}

ARCHETYPE_BASE_MANA: dict[str, int] = {
    "warrior": 0,
    "scholar": 8,
    "ranger":  0,
}


# ── Core formulas ──────────────────────────────────────────────────────────

def stat_modifier(stat_value: int) -> int:
    """Standard RPG modifier: (stat - 10) // 2. Integer division toward -inf.

    Delegates to the single source of truth in ``app.core.mechanics`` (#1181).
    """
    from app.core.mechanics import stat_modifier as _core
    return _core(stat_value)


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
