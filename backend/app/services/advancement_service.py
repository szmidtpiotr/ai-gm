"""
Advancement Service — per-level purchase limiter (#1467, Faza AUDIT G5).

Caps how many progression purchases a hero may make within a single character
level:

  * stat-up  (spend_stat_point_up)          → max 1 per level
  * NEW skill / NEW spell (first acquisition) → max 2 per level

Rank-ups of an ALREADY-known skill or spell are NOT counted (Wariant A, #1467,
confirmed with Piotr) — they remain gated only by their XP cost. "Nauka nowej"
means the first rank a hero gains in a given skill/spell (skill rank 0→1, or a
fresh row in character_spells).

The counter lives in ``sheet_json["advancement_spent"]``::

    {"level": <int>, "stat_ups": <int>, "skill_ups": <int>}

It resets LAZILY: whenever the stored ``level`` differs from the character's
current level, the counter is treated as a fresh {level, 0, 0}. A level-up
therefore frees a new allotment automatically — no path (rest, admin grant,
combat XP) has to remember to clear it.

Numbers Policy (starting values, Sandbox/config-tunable later):
    STAT_UPS_PER_LEVEL   = 1
    NEW_SKILLS_PER_LEVEL = 2
"""
from __future__ import annotations

from typing import Any

# ── Starting values (Numbers Policy — tunable) ──────────────────────────────
STAT_UPS_PER_LEVEL = 1
NEW_SKILLS_PER_LEVEL = 2


def _counter_for_level(sheet: dict[str, Any]) -> dict[str, int]:
    """Return the live counter for the sheet's CURRENT level (lazy reset)."""
    level = int(sheet.get("level") or 1)
    adv = sheet.get("advancement_spent") or {}
    if int(adv.get("level") or 0) != level:
        # Stale (or absent) → fresh allotment for this level.
        return {"level": level, "stat_ups": 0, "skill_ups": 0}
    return {
        "level": level,
        "stat_ups": int(adv.get("stat_ups") or 0),
        "skill_ups": int(adv.get("skill_ups") or 0),
    }


# ── Stat-ups ────────────────────────────────────────────────────────────────

def check_stat_up(sheet: dict[str, Any]) -> dict[str, int]:
    """Raise ``ValueError('stat_up_limit_per_level')`` if the cap is reached.

    Returns the (level-current) counter to hand to :func:`commit_stat_up`.
    """
    adv = _counter_for_level(sheet)
    if adv["stat_ups"] >= STAT_UPS_PER_LEVEL:
        raise ValueError("stat_up_limit_per_level")
    return adv


def commit_stat_up(sheet: dict[str, Any], adv: dict[str, int]) -> None:
    """Persist a consumed stat-up onto ``sheet['advancement_spent']``."""
    adv["stat_ups"] = int(adv.get("stat_ups") or 0) + 1
    sheet["advancement_spent"] = adv


# ── New skills / spells ──────────────────────────────────────────────────────

def check_new_skill(sheet: dict[str, Any]) -> dict[str, int]:
    """Raise ``ValueError('new_skill_limit_per_level')`` if the cap is reached.

    Applies only to LEARNING a new skill/spell — rank-ups do not call this.
    """
    adv = _counter_for_level(sheet)
    if adv["skill_ups"] >= NEW_SKILLS_PER_LEVEL:
        raise ValueError("new_skill_limit_per_level")
    return adv


def commit_new_skill(sheet: dict[str, Any], adv: dict[str, int]) -> None:
    """Persist a consumed new-skill slot onto ``sheet['advancement_spent']``."""
    adv["skill_ups"] = int(adv.get("skill_ups") or 0) + 1
    sheet["advancement_spent"] = adv
