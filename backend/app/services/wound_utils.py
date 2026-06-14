"""Wound tier utility — C4/C5/C6 (U15).

Single source of truth for wound tiers shared by backend + frontend.
Maps hp_current/hp_max into ONE tier carrying: tier key, label, color, cue,
and the roll penalty. Works for any combatant (player, enemy, NPC).

Before U15 there were two drifting threshold sources — penalty thresholds here
(75/50/25) and visual labels in economy_service (76/51/26/11). U15 merges them
into WOUND_TIERS so a tier's label and its mechanical penalty can never diverge.

Tiers (% of max HP, strict `>` lower bound, descending):
  > 75%  healthy     →  0   (no label)
  > 50%  minor       → -1   "Ranny"
  > 25%  moderate    → -2   "Ciężko Ranny"
  > 10%  serious     → -4   "Poważnie Ranny"
  ≤ 10%  near_death  → -4   "Na Skraju Śmierci"
"""
from __future__ import annotations

# ── Single source of truth ───────────────────────────────────────────────────
# Each row: min_pct is an EXCLUSIVE lower bound — first row where pct > min_pct
# wins. Penalties reproduce the pre-U15 ladder exactly (refactor, not rebalance).
WOUND_TIERS: list[dict] = [
    {"min_pct": 75, "tier": "healthy",    "label": None,                 "color": "#4caf50", "cue": None,         "penalty": 0},
    {"min_pct": 50, "tier": "minor",      "label": "Ranny",              "color": "#ffc107", "cue": "minor_pain", "penalty": -1},
    {"min_pct": 25, "tier": "moderate",   "label": "Ciężko Ranny",       "color": "#ff9800", "cue": "impaired",   "penalty": -2},
    {"min_pct": 10, "tier": "serious",    "label": "Poważnie Ranny",     "color": "#f44336", "cue": "desperate",  "penalty": -4},
    {"min_pct": -1, "tier": "near_death", "label": "Na Skraju Śmierci",  "color": "#7f0000", "cue": "near_death", "penalty": -4},
]

# Back-compat constants (consumed by version.py and any legacy callers).
WOUND_HEALTHY_PCT: int = WOUND_TIERS[0]["min_pct"]   # 75
WOUND_MODERATE_PCT: int = WOUND_TIERS[1]["min_pct"]  # 50
WOUND_CRITICAL_PCT: int = WOUND_TIERS[2]["min_pct"]  # 25


def wound_tier(hp_current: int, hp_max: int) -> dict:
    """Return the full wound tier for an HP pair.

    Args:
        hp_current: current hit points
        hp_max:     maximum hit points (≤0 → healthy, no penalty)

    Returns:
        {tier, label, color, cue, penalty, pct}
    """
    if hp_max <= 0:
        base = WOUND_TIERS[0]
        return {**{k: base[k] for k in ("tier", "label", "color", "cue", "penalty")}, "pct": 0.0}
    pct = (hp_current / hp_max) * 100
    for row in WOUND_TIERS:
        if pct > row["min_pct"]:
            return {
                "tier": row["tier"],
                "label": row["label"],
                "color": row["color"],
                "cue": row["cue"],
                "penalty": row["penalty"],
                "pct": round(pct, 1),
            }
    last = WOUND_TIERS[-1]
    return {**{k: last[k] for k in ("tier", "label", "color", "cue", "penalty")}, "pct": round(pct, 1)}


def wound_penalty(hp_current: int, hp_max: int) -> int:
    """Return roll penalty based on HP percentage (derives from wound_tier).

    Returns 0, -1, -2, or -4.
    """
    return wound_tier(hp_current, hp_max)["penalty"]
