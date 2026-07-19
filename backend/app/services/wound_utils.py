"""Wound tier utility — C4/C5/C6 (U15) · rebalanced G1 (#1459, wariant A łagodny).

Single source of truth for wound tiers shared by backend + frontend.
Maps hp_current/hp_max into ONE tier carrying: tier key, label, color, cue,
the roll penalty and the DEX penalty. Works for any combatant (player, enemy, NPC).

**G1 rebalance (#1459, 2026-07-19 — decyzja Piotra: wariant A łagodny).**
Poprzednia drabina (wariant B "ostry": 75/50/25/10 → 0/-1/-2/-4) karała już od
<75% HP i groziła "spiralą śmierci" przy permadeath (ranny → bijesz słabiej →
dostajesz więcej → giniesz bez okna na odwrót). Wariant A przesuwa pierwszą realną
karę na ≤25% HP, dając graczowi okno na ucieczkę lub leczenie. Zgodne z
`game_mechanics.md` CZĘŚĆ AB. Wartości startowe — do dostrojenia po playteście.

Ladder A — trzy źródła MUSZĄ być identyczne (jedno źródło prawdy):
  • ten plik (WOUND_TIERS)
  • Księga Zasad  frontend/rules/index.html  (§ Stopnie ran)
  • game_mechanics.md CZĘŚĆ AB (tabela docelowych progów ran)

Tiers (% of max HP, strict `>` lower bound, descending):
  > 50%  healthy     →  0            (no label)
  > 25%  minor       →  0            "Ranny"            (tylko klimat/narracja)
  > 10%  serious     → -1            "Poważnie Ranny"
  ≤ 10%  near_death  → -2, -1 DEX    "Na Skraju Śmierci"
"""
from __future__ import annotations

# ── Single source of truth ───────────────────────────────────────────────────
# Each row: min_pct is an EXCLUSIVE lower bound — first row where pct > min_pct
# wins. `penalty` = malus do rzutów (atak + testy umiejętności); `dex_penalty` =
# dodatkowy malus DEX na skraju śmierci (dane w źródle; wiring silnika DEX = follow-up).
WOUND_TIERS: list[dict] = [
    {"min_pct": 50, "tier": "healthy",    "label": None,                 "color": "#4caf50", "cue": None,         "penalty": 0,  "dex_penalty": 0},
    {"min_pct": 25, "tier": "minor",      "label": "Ranny",              "color": "#ffc107", "cue": "minor_pain", "penalty": 0,  "dex_penalty": 0},
    {"min_pct": 10, "tier": "serious",    "label": "Poważnie Ranny",     "color": "#f44336", "cue": "desperate",  "penalty": -1, "dex_penalty": 0},
    {"min_pct": -1, "tier": "near_death", "label": "Na Skraju Śmierci",  "color": "#7f0000", "cue": "near_death", "penalty": -2, "dex_penalty": -1},
]

# Back-compat constants (consumed by version.py and any legacy callers).
WOUND_HEALTHY_PCT: int = WOUND_TIERS[0]["min_pct"]   # 50 — pierwszy próg klimatyczny
WOUND_MODERATE_PCT: int = WOUND_TIERS[1]["min_pct"]  # 25 — pierwsza realna kara (-1)
WOUND_CRITICAL_PCT: int = WOUND_TIERS[2]["min_pct"]  # 10 — na skraju śmierci (-2)

_TIER_KEYS = ("tier", "label", "color", "cue", "penalty", "dex_penalty")


def wound_tier(hp_current: int, hp_max: int) -> dict:
    """Return the full wound tier for an HP pair.

    Args:
        hp_current: current hit points
        hp_max:     maximum hit points (≤0 → healthy, no penalty)

    Returns:
        {tier, label, color, cue, penalty, dex_penalty, pct}
    """
    if hp_max <= 0:
        base = WOUND_TIERS[0]
        return {**{k: base[k] for k in _TIER_KEYS}, "pct": 0.0}
    pct = (hp_current / hp_max) * 100
    for row in WOUND_TIERS:
        if pct > row["min_pct"]:
            return {**{k: row[k] for k in _TIER_KEYS}, "pct": round(pct, 1)}
    last = WOUND_TIERS[-1]
    return {**{k: last[k] for k in _TIER_KEYS}, "pct": round(pct, 1)}


def wound_penalty(hp_current: int, hp_max: int) -> int:
    """Return roll penalty based on HP percentage (derives from wound_tier).

    Wariant A (łagodny): 0 (>25% HP), -1 (11–25%), -2 (≤10%).
    """
    return wound_tier(hp_current, hp_max)["penalty"]


def wound_dex_penalty(hp_current: int, hp_max: int) -> int:
    """Return the extra DEX penalty for the wound tier (0 or -1 at near-death)."""
    return wound_tier(hp_current, hp_max)["dex_penalty"]
