"""Passive equipment effects — relics that work in AND out of combat (#1302).

Today only WEAPONS have a mechanical hook: the combat engine reads a weapon's
`effect_json` (#461/#462). A relic/item (e.g. "Rozbita Gwiazda") is mechanically
dead — its `effect_json` is ignored everywhere. This service is the single
chokepoint that fixes that: it aggregates the `effect_json` of ALL of a
character's EQUIPPED items (weapon, armour, relic, amulet…) into one "effective
bonus" bundle that every roll path consumes — skill tests, saves, combat — plus
the character card.

Design decisions (locked with Piotr, 2026-07-10):
  * Activation: item must be EQUIPPED (any slot), not merely carried. Relics get
    two dedicated slots (relic1/relic2); every other equipped item counts too, so
    a fine breastplate can grant +CHA, a magic lockpick can grant a skill, etc.
  * Stacking: SUM. Two +CHA items = +2 CHA.
  * Scope: generic across all 7 stats, skills, and AC — CHA was only an example.
  * Combat applies the main-hand weapon separately (damage/heal/stat/AC), so the
    combat caller passes exclude_slots=('main_hand',) to avoid double-counting.

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


def _equipped_effect_lists(
    character_id: int, conn: sqlite3.Connection, exclude_slots: "tuple[str, ...]" = ()
) -> list[list[dict]]:
    """One merged effect list per EQUIPPED inventory row (any slot).

    #1302 (rozszerzenie, Piotr 2026-07-10): każdy założony przedmiot — broń,
    pancerz, relikt, amulet — z pasywnym effect_json wnosi bonusy. effect_json
    source per row: `game_config_items.effect_json` (itemy/pancerz + Forge
    signatures), `game_config_weapons.effect_json` (broń), fallback do unified
    `game_items`. `exclude_slots` pomija sloty liczone już gdzie indziej (walka
    aplikuje broń głównej ręki osobno → exclude 'main_hand' tam).

    Robust to older DBs missing `game_item_key` / `game_items` / `effect_json`.
    """
    exclude = {str(s).strip().lower() for s in exclude_slots}
    # Try the rich query first (game_items join); fall back if that table/column is absent.
    queries = [
        """
        SELECT ci.slot AS slot,
               gci.effect_json AS item_effect,
               gcw.effect_json AS weap_effect,
               gt.effect_json  AS game_item_effect
        FROM character_inventory ci
        LEFT JOIN game_config_items gci   ON gci.key = ci.item_key
        LEFT JOIN game_config_weapons gcw ON gcw.key = ci.weapon_key
        LEFT JOIN game_items gt           ON gt.key = COALESCE(ci.game_item_key, ci.item_key, ci.weapon_key)
        WHERE ci.character_id = ? AND ci.equipped = 1
        """,
        """
        SELECT ci.slot AS slot,
               gci.effect_json AS item_effect,
               gcw.effect_json AS weap_effect,
               NULL AS game_item_effect
        FROM character_inventory ci
        LEFT JOIN game_config_items gci   ON gci.key = ci.item_key
        LEFT JOIN game_config_weapons gcw ON gcw.key = ci.weapon_key
        WHERE ci.character_id = ? AND ci.equipped = 1
        """,
        """
        SELECT ci.slot AS slot,
               gci.effect_json AS item_effect,
               NULL AS weap_effect,
               NULL AS game_item_effect
        FROM character_inventory ci
        LEFT JOIN game_config_items gci ON gci.key = ci.item_key
        WHERE ci.character_id = ? AND ci.equipped = 1
        """,
    ]
    rows = None
    for q in queries:
        try:
            rows = conn.execute(q, (character_id,)).fetchall()
            break
        except sqlite3.OperationalError:
            continue
    if rows is None:
        return []

    out: list[list[dict]] = []
    for r in rows:
        slot = str(_row_get(r, "slot") or "").strip().lower()
        if slot in exclude:
            continue
        # Prefer item, then weapon, then the unified game_items effect_json.
        effects = _decode_effects(_row_get(r, "item_effect"))
        if not effects:
            effects = _decode_effects(_row_get(r, "weap_effect"))
        if not effects:
            effects = _decode_effects(_row_get(r, "game_item_effect"))
        if effects:
            out.append(effects)
    return out


def _apply_effect(e: dict, stats: dict[str, int], skills: dict[str, int], ac_ref: list[int]) -> None:
    """Fold one passive effect dict into the running stat/skill/ac accumulators."""
    etype = str(e.get("type") or "").strip()
    try:
        val = int(e.get("value") or 0)
    except (TypeError, ValueError):
        return
    if not val:
        return
    if etype == "static_stat_modifier":
        stat = str(e.get("stat") or "").strip().upper()
        if stat in _STAT_KEYS:
            stats[stat] = stats.get(stat, 0) + val
    elif etype == "static_skill_modifier":
        sk = str(e.get("skill") or e.get("stat") or "").strip().lower()
        if sk:
            skills[sk] = skills.get(sk, 0) + val
    elif etype == "ac_bonus":
        ac_ref[0] += val


def _worn_piece_keys(character_id: int, conn: sqlite3.Connection) -> set[str]:
    """Set of item/weapon/game_item keys the character has EQUIPPED.

    Set detection counts every equipped slot — it ignores ``exclude_slots`` used
    by the per-item effect aggregation, because a set bonus is a separate layer
    (not the piece's own effect_json), so a set weapon in main_hand still counts.
    """
    queries = [
        "SELECT item_key, weapon_key, game_item_key FROM character_inventory "
        "WHERE character_id = ? AND equipped = 1",
        "SELECT item_key, weapon_key FROM character_inventory "
        "WHERE character_id = ? AND equipped = 1",
    ]
    rows = None
    for q in queries:
        try:
            rows = conn.execute(q, (character_id,)).fetchall()
            break
        except sqlite3.OperationalError:
            continue
    out: set[str] = set()
    for r in rows or []:
        for col in ("item_key", "weapon_key", "game_item_key"):
            k = _row_get(r, col)
            if k:
                out.add(str(k).strip())
    return out


def get_active_sets(character_id: int, conn: sqlite3.Connection) -> list[dict]:
    """#1340 — equipment sets: which sets the character has partial/full pieces of.

    Returns a list (one per set with ≥1 worn piece) of::

        {key, label, description, worn: int, total: int,
         active_threshold: int | None, next_threshold: int | None,
         thresholds: [{n, active, effects}], effects: [effects of active threshold]}

    ``active_threshold`` is the highest bonus tier whose piece-count ≤ worn.
    Never raises; returns ``[]`` if the table is absent or nothing matches.
    """
    try:
        cid = int(character_id)
    except (TypeError, ValueError):
        return []
    try:
        set_rows = conn.execute(
            "SELECT key, label, description, pieces_json, bonuses_json "
            "FROM game_config_sets WHERE is_active = 1"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    if not set_rows:
        return []

    worn = _worn_piece_keys(cid, conn)
    out: list[dict] = []
    for sr in set_rows:
        try:
            pieces = json.loads(_row_get(sr, "pieces_json") or "[]")
        except (ValueError, TypeError):
            pieces = []
        piece_keys = [str(p).strip() for p in pieces if str(p).strip()]
        if not piece_keys:
            continue
        n_worn = sum(1 for p in piece_keys if p in worn)
        if n_worn <= 0:
            continue
        try:
            bonuses = json.loads(_row_get(sr, "bonuses_json") or "{}")
        except (ValueError, TypeError):
            bonuses = {}
        if not isinstance(bonuses, dict):
            bonuses = {}
        # Numeric thresholds sorted ascending; keys arrive as JSON strings.
        thresholds_raw: list[tuple[int, list]] = []
        for tk, effs in bonuses.items():
            try:
                n = int(tk)
            except (TypeError, ValueError):
                continue
            thresholds_raw.append((n, effs if isinstance(effs, list) else []))
        thresholds_raw.sort(key=lambda t: t[0])

        active_threshold = None
        active_effects: list = []
        next_threshold = None
        tinfo = []
        for n, effs in thresholds_raw:
            is_active = n_worn >= n
            if is_active:
                active_threshold = n
                active_effects = effs
            elif next_threshold is None:
                next_threshold = n
            tinfo.append({"n": n, "active": is_active, "effects": effs})
        out.append(
            {
                "key": str(_row_get(sr, "key") or ""),
                "label": str(_row_get(sr, "label") or ""),
                "description": _row_get(sr, "description") or "",
                "worn": n_worn,
                "total": len(piece_keys),
                "active_threshold": active_threshold,
                "next_threshold": next_threshold,
                "thresholds": tinfo,
                "effects": active_effects,
            }
        )
    return out


def get_equipment_bonuses(
    character_id: int, conn: sqlite3.Connection, exclude_slots: "tuple[str, ...]" = ()
) -> dict:
    """Aggregate ALL equipped-item passive effects into one bundle.

    Returns ``{"stats": {STAT: points}, "skills": {skill: rank}, "ac": int,
    "sets": [...]}``. Empty dicts / 0 when nothing worn carries effects. Never
    raises. Only passive types are read here — weapon-only
    `damage_bonus`/`heal_on_hit` are ignored. Pass ``exclude_slots`` to skip
    slots already handled elsewhere (combat passes ``('main_hand',)`` because it
    applies the main-hand weapon separately).

    #1340: equipment-set completion bonuses are folded in on top of per-item
    relic effects. Set piece-counting ignores ``exclude_slots`` (a set weapon in
    main_hand still counts toward its set), so combat sees set bonuses too.
    """
    stats: dict[str, int] = {}
    skills: dict[str, int] = {}
    ac_ref = [0]
    try:
        cid = int(character_id)
    except (TypeError, ValueError):
        return {"stats": stats, "skills": skills, "ac": 0, "sets": []}

    for effects in _equipped_effect_lists(cid, conn, exclude_slots):
        for e in effects:
            _apply_effect(e, stats, skills, ac_ref)

    # #1340 — set completion: add the active-threshold effects of each worn set.
    active_sets = get_active_sets(cid, conn)
    for s in active_sets:
        for e in s.get("effects") or []:
            if isinstance(e, dict):
                _apply_effect(e, stats, skills, ac_ref)

    return {"stats": stats, "skills": skills, "ac": ac_ref[0], "sets": active_sets}


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
