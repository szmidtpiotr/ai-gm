"""Wound penalty utility — C4/C6.

Converts hp_current/hp_max into a roll modifier.
Works for any combatant (player, enemy, NPC).

Thresholds (% of max HP) — single source of truth for frontend + backend:
  > WOUND_HEALTHY_PCT   →  0   (healthy)
  > WOUND_MODERATE_PCT  → -1   (lightly wounded)
  > WOUND_CRITICAL_PCT  → -2   (moderately wounded)
  ≤ WOUND_CRITICAL_PCT  → -4   (critically wounded)
"""
from __future__ import annotations

WOUND_HEALTHY_PCT: int = 75
WOUND_MODERATE_PCT: int = 50
WOUND_CRITICAL_PCT: int = 25


def wound_penalty(hp_current: int, hp_max: int) -> int:
    """Return roll penalty based on HP percentage.

    Args:
        hp_current: current hit points
        hp_max:     maximum hit points (0 → returns 0, no penalty)

    Returns:
        0, -1, -2, or -4
    """
    if hp_max <= 0:
        return 0
    pct = (hp_current / hp_max) * 100
    if pct > WOUND_HEALTHY_PCT:
        return 0
    if pct > WOUND_MODERATE_PCT:
        return -1
    if pct > WOUND_CRITICAL_PCT:
        return -2
    return -4
