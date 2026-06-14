"""Actor stats — archetype heuristic + stats_json parse/validate (FAZA S, S2).

Single source of truth for the 7 ability stats of NON-PLAYER actors (enemies, NPCs).
Stats are GENERATED from an archetype guessed by keywords in the actor key/label —
same keyword-heuristic pattern as `combat_service._default_zone_for_enemy`.

Design rules (game_mechanics.md CZĘŚĆ AI, Decyzja 2 / Zasady FAZY S):
- Combat path stays simplified (attack_bonus / ac_base / damage_die) — UNCHANGED.
  These stats serve opposed skill checks (S4) and skill interactions only.
- Admin still creates an enemy with 4 numbers; stats appear on their own and can be
  overridden. NULL / missing stats_json → every stat defaults to 10 (zero combat regression).
- S3 (NPC stats, lazy generation) REUSES this module — do not fork the archetype table.

All archetype numbers are STARTING values (Numbers Policy) — tune after the S20 playtest.
"""
from __future__ import annotations

import json
from typing import Any

# The 7 locked ability stats, canonical order (CLAUDE.md → Locked Game Mechanics).
STAT_KEYS: list[str] = ["STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"]

DEFAULT_STAT = 10

# Archetype → 7-stat block (STARTING values). humanoid = neutral fallback (all 10).
ARCHETYPE_STATS: dict[str, dict[str, int]] = {
    "brute":      {"STR": 16, "DEX": 10, "CON": 14, "INT": 7,  "WIS": 8,  "CHA": 8,  "LCK": 10},
    "skirmisher": {"STR": 10, "DEX": 15, "CON": 11, "INT": 10, "WIS": 12, "CHA": 9,  "LCK": 10},
    "caster":     {"STR": 8,  "DEX": 11, "CON": 10, "INT": 14, "WIS": 14, "CHA": 12, "LCK": 10},
    "beast":      {"STR": 14, "DEX": 14, "CON": 13, "INT": 3,  "WIS": 12, "CHA": 6,  "LCK": 10},
    "humanoid":   {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10},
}

# Keyword → archetype. PRIORITY ORDER matters: a combat-role keyword (archer/mage)
# must beat a generic faction keyword (bandit). Checked top-to-bottom; first hit wins,
# so `bandyta_lucznik` → skirmisher (DEX 15), not brute. PL + EN keywords.
_ARCHETYPE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("caster", (
        "mag", "magus", "mage", "wizard", "czarodziej", "czarownic", "sorcerer",
        "szaman", "shaman", "kapłan", "kaplan", "priest", "cleric", "necromancer",
        "nekromant", "warlock", "witch", "wiedźm", "wiedzm", "lich", "caster", "kabalist",
    )),
    ("skirmisher", (
        "łucznik", "lucznik", "archer", "bowman", "kusznik", "crossbow", "scout",
        "zwiadowca", "sniper", "snajper", "ranger", "strzelec", "procarz", "slinger",
    )),
    ("beast", (
        "wilk", "wolf", "niedźwiedź", "niedzwiedz", "bear", "pająk", "pajak", "spider",
        "szczur", "rat", "bestia", "beast", "zwierz", "wąż", "waz", "snake", "smok",
        "dragon", "kruk", "raven", "nietoperz", "bat", "dzik", "boar", "lew", "lion",
    )),
    ("brute", (
        "bandyta", "bandit", "zbój", "zboj", "thug", "brute", "osiłek", "osilek",
        "ogr", "ogre", "troll", "olbrzym", "giant", "barbarzyńca", "barbarzynca",
        "berserk", "wojownik", "warrior", "siłacz", "silacz", "kat", "rzezimieszek",
    )),
]


def archetype_for_actor(key: str, label: str | None = None) -> str:
    """Guess archetype from keywords in key/label. Fallback 'humanoid' (all 10)."""
    needle = f"{key or ''} {label or ''}".lower()
    for archetype, keywords in _ARCHETYPE_KEYWORDS:
        if any(k in needle for k in keywords):
            return archetype
    return "humanoid"


def stats_for_actor(key: str, label: str | None = None) -> dict[str, int]:
    """7-stat block for an actor, derived from its archetype. Always a fresh dict."""
    archetype = archetype_for_actor(key, label)
    return dict(ARCHETYPE_STATS.get(archetype, ARCHETYPE_STATS["humanoid"]))


def parse_stats_json(raw: Any) -> dict[str, int]:
    """Stored stats_json → full 7-stat dict. NULL/empty/missing keys → DEFAULT_STAT (10).

    This guarantees combat reads (`enemy.get("stats")`) get a complete block with zero
    regression for legacy enemies that never had stats.
    """
    parsed: Any = {}
    if isinstance(raw, dict):
        parsed = raw
    elif raw:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    out: dict[str, int] = {}
    for stat in STAT_KEYS:
        val = parsed.get(stat, parsed.get(stat.lower(), DEFAULT_STAT))
        try:
            out[stat] = int(val)
        except (TypeError, ValueError):
            out[stat] = DEFAULT_STAT
    return out


def validate_stats_json(values: dict[str, int] | None) -> str:
    """Admin-supplied stats dict → canonical JSON string for storage.

    None → '{}' (caller treats empty as "derive from archetype" on create, or "default 10"
    on read). Unknown stat keys are dropped; values coerced to int.
    """
    if values is None:
        return "{}"
    if not isinstance(values, dict):
        raise ValueError("invalid_stats_json")
    upper_allowed = set(STAT_KEYS)
    out: dict[str, int] = {}
    for raw_k, raw_v in values.items():
        k = str(raw_k).strip().upper()
        if k not in upper_allowed:
            raise ValueError("invalid_stats_json")
        try:
            out[k] = int(raw_v)
        except (TypeError, ValueError):
            raise ValueError("invalid_stats_json") from None
    return json.dumps(out, ensure_ascii=False)
