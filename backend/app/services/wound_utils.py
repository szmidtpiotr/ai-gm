"""Wound penalty utility — C4.

Converts hp_current/hp_max into a roll modifier.
Works for any combatant (player, enemy, NPC).

Thresholds (% of max HP):
  > 75%  →  0   (healthy)
  > 50%  → -1   (lightly wounded)
  > 25%  → -2   (moderately wounded)
  ≤ 25%  → -4   (critically wounded)
"""
from __future__ import annotations


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
    if pct > 75:
        return 0
    if pct > 50:
        return -1
    if pct > 25:
        return -2
    return -4
