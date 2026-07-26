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
    # #1475 PN-2: Wojownik-Mag (gish) — HP między Wojownikiem (10) a Uczonym (6).
    # Nosi stal, więc twardszy od maga, ale dzieli uwagę z zaklęciami. Wartość startowa.
    "wojownik_mag": 8,
}

ARCHETYPE_BASE_MANA: dict[str, int] = {
    "warrior": 0,
    "scholar": 8,
    "ranger":  0,
    # #1475 PN-2: gish — baza many połowiczna (Uczony 8). Pełna formuła niżej.
    "wojownik_mag": 4,
}

#: #1475 — archetypy, które w ogóle rzucają czary (mają manę). Uczony = pełny mag,
#: Wojownik-Mag = połowiczny gish. Reszta = 0 many.
CASTER_ARCHETYPES: frozenset[str] = frozenset({"scholar", "wojownik_mag"})

#: #1475 — płaski bonus rasowy do max_many (tylko dla rzucających czary). Krew
#: oswojona Piętnowanego niesie więcej mocy. Wartość STARTOWA — Sandbox-tunable.
#: Bonus SIEDZI W FORMULE (calculate_mana), więc każda ścieżka przeliczająca manę,
#: która poda rasę, dostaje go identycznie — zero path-dependence (#1466).
RACE_MANA_BONUS: dict[str, int] = {"pietnowani": 2}


def is_caster(archetype: str | None) -> bool:
    """Czy archetyp rzuca czary (ma pulę many). Jedno źródło prawdy dla walki."""
    return str(archetype or "").strip().lower() in CASTER_ARCHETYPES


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


def calculate_mana(archetype: str, int_stat: int, level: int = 1, race: str = "human") -> int:
    """
    Mana per archetype (minimum 1 for casters, 0 for non-casters):
      Scholar (Uczony)       : 8 + INT_mod × level
      Wojownik-Mag (gish)    : 4 + (INT_mod × level) // 2   (#1475 — połowiczna pula)
      Warrior / Rogue / etc. : 0
    Plus racial flat bonus for casters (RACE_MANA_BONUS): Piętnowany +2 (#1475).

    Args:
        archetype: "warrior" | "scholar" | "rogue" | "wojownik_mag" | "ranger"
        int_stat: INT stat value (e.g. 12)
        level: character level (1 at creation)
        race: character race — adds RACE_MANA_BONUS for casters (path-independent).
    """
    arc = archetype.strip().lower()
    if arc == "scholar":
        base = ARCHETYPE_BASE_MANA["scholar"] + stat_modifier(int_stat) * level
    elif arc == "wojownik_mag":
        # #1475 — gish: baza 4 + połowa progresji INT (zaokrąglona w dół).
        base = ARCHETYPE_BASE_MANA["wojownik_mag"] + (stat_modifier(int_stat) * level) // 2
    else:
        return 0
    # Bonus rasowy tylko dla rzucających czary (base jest tu zawsze pulą maga).
    base += RACE_MANA_BONUS.get(str(race or "human").strip().lower(), 0)
    return max(1, base)


# ── #1466 — single source of truth for max_hp / max_mana ────────────────────
# Every path that (re)sets a hero's max_hp / max_mana — level-up on rest,
# resurrection, admin recalc, stat purchase (#1436) — must funnel through these
# two functions. They RECOMPUTE from the canonical formula rather than mutating
# the stored value incrementally, so the result depends only on
# (archetype, stat, level) and never on the order of prior operations. This
# kills the path-dependence in the old incremental `apply_level_up` (which
# clamped negative CON/INT modifiers with max(), so a hero levelled via rest
# could end up with a different max than the same hero recomputed by admin).

def recompute_max_hp(archetype: str, con: int, level: int) -> int:
    """Authoritative max_hp = base_hp + CON_mod × level (min 1). See #1466."""
    return calculate_hp(archetype, con, level)


def recompute_max_mana(archetype: str, int_stat: int, level: int, race: str = "human") -> int:
    """Authoritative max_mana = formula per archetype + bonus rasowy. See #1466, #1475."""
    return calculate_mana(archetype, int_stat, level, race)


def apply_level_up(
    archetype: str,
    current_max_hp: int,
    current_max_mana: int,
    con: int,
    int_stat: int,
) -> tuple[int, int]:
    """
    DEPRECATED (#1466). Incremental level-up math kept only for backward compat
    with older callers/tests. Production paths now recompute from the formula via
    ``recompute_max_hp`` / ``recompute_max_mana`` (path-independent). Do not add
    new callers.

    Rules (legacy):
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
