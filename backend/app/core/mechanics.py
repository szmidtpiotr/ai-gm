"""Shared game-math helpers — single source of truth for locked formulas (#1181).

Centralizes the two RPG primitives that were reimplemented inline across many
modules, so the formulas live in exactly one place and cannot drift:

- ``stat_modifier``   : (stat - 10) // 2   — standard ability modifier
- ``proficiency_bonus``: +2 when rank >= 3 — locked skill/combat proficiency rule

Formulas are LOCKED per ``game_mechanics.md`` / ``backend/prompts/system_prompt.txt``.
Change only with explicit approval.
"""
from __future__ import annotations


def stat_modifier(stat: int) -> int:
    """Standard RPG ability modifier: ``(stat - 10) // 2`` (floor toward -inf)."""
    return (int(stat) - 10) // 2


def proficiency_bonus(rank: int) -> int:
    """Locked mechanic: ``+2`` when ``skill_rank >= 3``, else ``0``."""
    return 2 if int(rank) >= 3 else 0
