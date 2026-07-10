"""Passive equipment effects — relics that work in AND out of combat (#1302).

Today only WEAPONS have a mechanical hook: the combat engine reads a weapon's
`effect_json` (#461/#462). A relic/item (e.g. "Rozbita Gwiazda") is mechanically
dead — its `effect_json` is ignored everywhere. This service is the single
chokepoint that fixes that: it aggregates the `effect_json` of a character's
EQUIPPED relic-slot items into one "effective bonus" bundle that every roll path
consumes — skill tests, saves, combat — plus the character card.

Design decisions (locked with Piotr, 2026-07-10):
  * Activation: item must be EQUIPPED in a relic slot (relic1/relic2), not merely
    carried. Two relic slots.
  * Stacking: SUM. Two +CHA relics = +2 CHA.
  * Scope: generic across all 7 stats, skills, and AC — CHA was only an example.

Effect types honored (same schema as weapons):
  * static_stat_modifier {stat, value}   → stat POINTS (STR/DEX/CON/INT/WIS/CHA/LCK)
  * static_skill_modifier {skill, value} → skill RANK points (#1302 new)
  * ac_bonus {value}                     → flat armour/AC points

Semantics match the weapon path: `static_stat_modifier.value` is stat POINTS
(added to the stat score, then the (score-10)//2 modifier is recomputed), NOT a
pre-computed modifier.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

# Two dedicated relic slots (character_inventory.slot is free-text TEXT — no migration).
RELIC_SLOTS = ("relic1", "relic2")
_STAT_KEYS = {"STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"}


def _decode_effects(raw: Any) -> list[dict]:
    """Accept a dict, a JSON string, or a bare list → list of effect dicts."""
    if not raw:
        return []
    parsed = raw
    if isinstance(raw, (str, bytes)):
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return []
    if isinstance(parsed, dict):
        eff = parsed.get("effects")
        return [e for e in eff if isinstance(e, dict)] if isinstance(eff, list) else []
    if isinstance(parsed, list):
        return [e for e in parsed if isinstance(e, dict)]
    return []


def _row_get(row: Any, key: str) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return None


def _relic_effect_lists(character_id: int, conn: sqlite3.Connection) -> list[list[dict]]:
    """One merged effect list per equipped relic-slot inventory row.

    effect_json source per row: the base item's `game_config_items.effect_json`
    (where Forge signatures land), falling back to the unified `game_items` table.
    Robust to older DBs missing the `game_item_key` column / `game_items` table.
    """
    placeholders = ",".join(["?"] * len(RELIC_SLOTS))
    # Try the rich query first (game_items join); fall back if that table/column is absent.
    queries = [
        f"""
        SELECT gi.effect_json AS item_effect,
               gt.effect_json AS game_item_effect
        FROM character_inventory ci
        LEFT JOIN game_config_items gi ON gi.key = ci.item_key
        LEFT JOIN game_items gt        ON gt.key = COALESCE(ci.game_item_key, ci.item_key)
        WHERE ci.character_id = ? AND ci.equipped = 1 AND ci.slot IN ({placeholders})
        """,
        f"""
        SELECT gi.effect_json AS item_effect,
               NULL AS game_item_effect
        FROM character_inventory ci
        LEFT JOIN game_config_items gi ON gi.key = ci.item_key
        WHERE ci.character_id = ? AND ci.equipped = 1 AND ci.slot IN ({placeholders})
        """,
    ]
    rows = None
    for q in queries:
        try:
            rows = conn.execute(q, (character_id, *RELIC_SLOTS)).fetchall()
            break
        except sqlite3.OperationalError:
            continue
    if rows is None:
        return []

    out: list[list[dict]] = []
    for r in rows:
        # Prefer the config-table effect_json; fall back to the unified game_items one.
        effects = _decode_effects(_row_get(r, "item_effect"))
        if not effects:
            effects = _decode_effects(_row_get(r, "game_item_effect"))
        if effects:
            out.append(effects)
    return out


def get_equipment_bonuses(character_id: int, conn: sqlite3.Connection) -> dict:
    """Aggregate equipped-relic effects into one bundle.

    Returns ``{"stats": {STAT: points}, "skills": {skill: rank}, "ac": int}``.
    Empty dicts / 0 when the character wears no relics. Never raises.
    """
    stats: dict[str, int] = {}
    skills: dict[str, int] = {}
    ac = 0
    try:
        cid = int(character_id)
    except (TypeError, ValueError):
        return {"stats": stats, "skills": skills, "ac": ac}

    for effects in _relic_effect_lists(cid, conn):
        for e in effects:
            etype = str(e.get("type") or "").strip()
            try:
                val = int(e.get("value") or 0)
            except (TypeError, ValueError):
                continue
            if not val:
                continue
            if etype == "static_stat_modifier":
                stat = str(e.get("stat") or "").strip().upper()
                if stat in _STAT_KEYS:
                    stats[stat] = stats.get(stat, 0) + val
            elif etype == "static_skill_modifier":
                sk = str(e.get("skill") or e.get("stat") or "").strip().lower()
                if sk:
                    skills[sk] = skills.get(sk, 0) + val
            elif etype == "ac_bonus":
                ac += val
    return {"stats": stats, "skills": skills, "ac": ac}


def get_effective_stat_bonuses(character_id: int, conn: sqlite3.Connection) -> dict[str, int]:
    """{STAT: bonus_points} from equipped relics. Empty when none worn."""
    return get_equipment_bonuses(character_id, conn)["stats"]


def get_effective_skill_bonuses(character_id: int, conn: sqlite3.Connection) -> dict[str, int]:
    """{skill_key: bonus_rank} from equipped relics."""
    return get_equipment_bonuses(character_id, conn)["skills"]


def get_effective_ac_bonus(character_id: int, conn: sqlite3.Connection) -> int:
    """Flat AC/armour points from equipped relics."""
    return get_equipment_bonuses(character_id, conn)["ac"]


def apply_stat_bonuses_to_sheet(sheet: dict, character_id: int, conn: sqlite3.Connection) -> dict[str, int]:
    """Fold relic stat POINTS into ``sheet['stats']`` in place (before a roll).

    Returns the bonuses applied so callers can surface them. No-op when the sheet
    has no stats dict or the character wears no relics.
    """
    bonuses = get_effective_stat_bonuses(character_id, conn)
    if bonuses and isinstance(sheet, dict) and isinstance(sheet.get("stats"), dict):
        for st, delta in bonuses.items():
            sheet["stats"][st] = int(sheet["stats"].get(st, 10) or 10) + int(delta)
    return bonuses
