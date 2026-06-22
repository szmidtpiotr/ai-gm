"""G15 #813 — MP balance flags (centralized, sandbox-tunable).

All values are STARTING VALUES for playtest tuning.
Change via PATCH /api/admin/sandbox/mp-balance — effective immediately, session-scoped.
"""

# ── Wipe penalty ─────────────────────────────────────────────────────────────
# Gold loss % on party wipe, keyed by avg level bracket.
WIPE_GOLD_PCT_BY_LEVEL: dict[str, float] = {
    "1-3": 0.10,
    "4-7": 0.20,
    "8+":  0.30,
}

WIPE_GOLD_FLOOR: int = 50    # players with < this gold are exempt from penalty
WIPE_HP_PCT: float = 0.50    # revive at this fraction of max HP after wipe

# ── Difficulty scaling by active player count ─────────────────────────────────
# Multiplier applied to enemy HP and attack on MP rounds.
# Direction spec: fewer players = harder, better loot. Starting neutral (1.0).
MP_DIFFICULTY_SCALE_BY_COUNT: dict[int, float] = {
    1: 1.0,
    2: 1.0,
    3: 1.0,
    4: 1.0,
}

# ── Loot scaling by active player count ───────────────────────────────────────
# Applied on top of loot_service.MP_LOOT_WEIGHT_SCALE.
# Fewer players → higher multiplier = better individual loot. Starting neutral.
MP_LOOT_SCALE_BY_COUNT: dict[int, float] = {
    1: 1.0,
    2: 1.0,
    3: 1.0,
    4: 1.0,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_wipe_gold_pct(avg_level: int) -> float:
    """Gold loss fraction for party wipe based on average party level."""
    if avg_level <= 3:
        return WIPE_GOLD_PCT_BY_LEVEL["1-3"]
    if avg_level <= 7:
        return WIPE_GOLD_PCT_BY_LEVEL["4-7"]
    return WIPE_GOLD_PCT_BY_LEVEL["8+"]


def _clamp_count(player_count: int, table: dict[int, float]) -> float:
    """Clamp count to [1,4] and look up in table; fallback to max key."""
    count = max(1, min(player_count, 4))
    if count in table:
        return table[count]
    return table.get(max(table.keys()), 1.0)


def get_difficulty_scale(player_count: int) -> float:
    """Enemy HP/attack multiplier for MP based on active player count."""
    return _clamp_count(player_count, MP_DIFFICULTY_SCALE_BY_COUNT)


def get_loot_scale(player_count: int) -> float:
    """Loot weight multiplier for MP based on active player count."""
    return _clamp_count(player_count, MP_LOOT_SCALE_BY_COUNT)
