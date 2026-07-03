"""
Mechanic Resolver — V2 Phase 04 Task 11

Pure deterministic logic. No LLM, no DB writes.
Receives: action_type + params + loaded DB context dict
Returns: MechanicResult dict with outcome, rolls, deltas.

The World State Updater (in turn_pipeline.py) reads this result and writes to DB.
"""

from __future__ import annotations

import random
import structlog
from typing import Any

logger = structlog.get_logger()


# ── Dice ───────────────────────────────────────────────────────────────────

def roll_d20() -> int:
    return random.randint(1, 20)

def roll_die(sides: int) -> int:
    return random.randint(1, sides)

def parse_dice(dice_str: str) -> int:
    """Parse '2d6+2' → roll and return total. Returns 0 on parse error."""
    try:
        s = str(dice_str).strip().lower()
        bonus = 0
        if "+" in s:
            parts = s.split("+", 1)
            s = parts[0].strip()
            bonus = int(parts[1].strip())
        elif "-" in s and "d" in s:
            idx = s.rindex("-")
            bonus = -int(s[idx+1:])
            s = s[:idx]
        if "d" in s:
            count_str, sides_str = s.split("d", 1)
            count = int(count_str or 1)
            sides = int(sides_str)
            return sum(random.randint(1, sides) for _ in range(count)) + bonus
        return int(s) + bonus
    except Exception:
        return 0


def stat_modifier(stat: int) -> int:
    return (int(stat) - 10) // 2


# ── Main resolver ──────────────────────────────────────────────────────────

def resolve(
    action_type: str,
    params: dict[str, str],
    context: dict[str, Any],
) -> dict:
    """
    Route action to the appropriate resolver function.

    context keys (loaded by turn_pipeline.py from DB):
      character_sheet, location, target_enemy, target_npc, equipped_weapon,
      skill_rank, skill_stat_mod, skill_counter, item_record, combat_state

    Returns a MechanicResult dict.
    """
    resolvers = {
        "ATTACK":         _resolve_attack,
        "SKILL_ATTEMPT":  _resolve_skill,
        "STEALTH_ATTEMPT":_resolve_stealth,
        "FLEE":           _resolve_flee,
        "REST":           _resolve_rest,
        "EXAMINE":        _resolve_examine,
        "DIALOGUE":       _resolve_dialogue,
        "SEARCH":         _resolve_search,
        "ITEM_USE":       _resolve_item_use,
        "ITEM_PICKUP":    _resolve_item_pickup,
        "SHOP":           _resolve_shop,
    }
    fn = resolvers.get(action_type.upper(), _resolve_generic)
    try:
        result = fn(params, context)
        result["action_type"] = action_type.upper()
        return result
    except Exception as e:
        logger.warning("mechanic_resolver_error", action=action_type, error=str(e))
        return {
            "action_type": action_type.upper(),
            "outcome": "DESCRIPTION",
            "error": str(e),
        }


# ── Attack ─────────────────────────────────────────────────────────────────

def _resolve_attack(params: dict, ctx: dict) -> dict:
    sheet = ctx.get("character_sheet") or {}
    stats = sheet.get("stats") or {}
    skills = sheet.get("skills") or {}

    str_mod = stat_modifier(int(stats.get("STR", 10)))
    dex_mod = stat_modifier(int(stats.get("DEX", 10)))

    weapon = ctx.get("equipped_weapon") or {}
    weapon_type = str(weapon.get("weapon_type", "melee")).lower()
    linked_stat = str(weapon.get("linked_stat", "STR")).upper()
    damage_die = str(weapon.get("damage_die", "d6"))

    stat_mod = dex_mod if linked_stat == "DEX" else str_mod

    # Combat skill rank
    combat_rank = int(skills.get("melee_attack", skills.get("combat", 0)) or 0)
    proficiency = 2 if combat_rank >= 3 else 0

    roll = roll_d20()
    total_atk = roll + stat_mod + combat_rank + proficiency

    target = ctx.get("target_enemy") or {}
    ac = int(target.get("ac_base", 12))

    nat20 = roll == 20
    nat1 = roll == 1

    hit = nat20 or (not nat1 and total_atk >= ac)

    damage = 0
    crit = False
    hit_location = None

    if hit:
        dmg_roll = parse_dice(damage_die)
        damage = dmg_roll + stat_mod
        # Check crit threshold (5 over AC)
        if nat20 or (total_atk - ac >= 5):
            crit = True
            damage *= 2
            hit_location_roll = random.randint(1, 6)
            loc_map = {1: "head", 2: "torso", 3: "right_arm", 4: "left_arm",
                       5: "right_leg", 6: "left_leg"}
            hit_location = loc_map.get(hit_location_roll, "torso")

    target_hp = int(target.get("hp", target.get("hp_base", 12)))
    hp_after = max(0, target_hp - damage) if hit else target_hp

    outcome = "CRITICAL_SUCCESS" if crit else ("SUCCESS" if hit else
              ("CRITICAL_FAILURE" if nat1 else "FAILURE"))

    return {
        "outcome": outcome,
        "roll": roll,
        "modifier": stat_mod + combat_rank + proficiency,
        "total": total_atk,
        "dc": ac,
        "hit": hit,
        "damage": damage,
        "nat20": nat20,
        "nat1": nat1,
        "crit": crit,
        "hit_location": hit_location,
        "target_name": target.get("label", params.get("target", "enemy")),
        "target_hp_before": target_hp,
        "target_hp_after": hp_after,
        "target_dead": hp_after <= 0,
        "target_key": params.get("target", ""),
    }


# ── Skill attempt ─────────────────────────────────────────────────────────

def _resolve_skill(params: dict, ctx: dict) -> dict:
    sheet = ctx.get("character_sheet") or {}
    stats = sheet.get("stats") or {}
    skills = sheet.get("skills") or {}

    skill_key = params.get("skill_key", "perception")

    from app.services.skill_service import _skill_stat
    governing_stat = _skill_stat(skill_key)
    stat_val = int(stats.get(governing_stat, 10))
    stat_mod = stat_modifier(stat_val)
    skill_rank = int(skills.get(skill_key, 0))
    proficiency = 2 if skill_rank >= 3 else 0

    roll = roll_d20()
    total = roll + skill_rank + stat_mod + proficiency

    counter = ctx.get("skill_counter") or {}
    dc = int(counter.get("dc", 12))

    # Opposed check if counter provides an opponent
    opponent_total = dc
    opponent_roll = None
    if counter.get("counter_type") == "opposed":
        opponent_roll = roll_d20()
        opp_mod = int(counter.get("opponent_modifier", 0))
        opponent_total = opponent_roll + opp_mod

    nat20 = roll == 20
    nat1 = roll == 1
    success = nat20 or (not nat1 and total >= opponent_total)

    outcome = "CRITICAL_SUCCESS" if (nat20 and success) else (
              "SUCCESS" if success else (
              "CRITICAL_FAILURE" if nat1 else "FAILURE"))

    return {
        "outcome": outcome,
        "skill_key": skill_key,
        "roll": roll,
        "modifier": skill_rank + stat_mod + proficiency,
        "total": total,
        "dc": opponent_total,
        "opponent_roll": opponent_roll,
        "nat20": nat20,
        "nat1": nat1,
    }


# ── Stealth ───────────────────────────────────────────────────────────────

def _resolve_stealth(params: dict, ctx: dict) -> dict:
    params["skill_key"] = "stealth"
    return _resolve_skill(params, ctx)


# ── Flee ──────────────────────────────────────────────────────────────────

def _resolve_flee(params: dict, ctx: dict) -> dict:
    sheet = ctx.get("character_sheet") or {}
    stats = (sheet.get("stats") or {})
    char_dex = int(stats.get("DEX", 10))
    char_mod = stat_modifier(char_dex)

    combat = ctx.get("combat_state") or {}
    enemies = combat.get("combatants") or []
    alive_enemies = [e for e in enemies if e.get("type") != "player" and int(e.get("hp", 1)) > 0]

    # Use highest enemy DEX
    max_enemy_dex = max((int(e.get("dex_modifier", 0)) for e in alive_enemies), default=0)

    player_roll = roll_d20() + char_mod
    enemy_roll = roll_d20() + max_enemy_dex

    success = player_roll > enemy_roll  # tie goes to enemy

    return {
        "outcome": "SUCCESS" if success else "FAILURE",
        "roll": player_roll,
        "modifier": char_mod,
        "total": player_roll,
        "dc": enemy_roll,
        "fled": success,
        "enemy_total": enemy_roll,
    }


# ── Rest ──────────────────────────────────────────────────────────────────

def _resolve_rest(params: dict, ctx: dict) -> dict:
    sheet = ctx.get("character_sheet") or {}
    stats = (sheet.get("stats") or {})
    con_mod = stat_modifier(int(stats.get("CON", 10)))
    archetype = str(sheet.get("archetype", "warrior")).lower()

    rest_type = params.get("rest_type", "short")
    current_hp = int(sheet.get("current_hp", 0))
    max_hp = int(sheet.get("max_hp", 10))
    current_mana = int(sheet.get("current_mana", 0))
    max_mana = int(sheet.get("max_mana", 0))

    if rest_type == "long":
        new_hp = max_hp
        new_mana = max_mana
    else:
        # Short rest: 1d6 + CON mod
        heal = max(1, random.randint(1, 6) + con_mod)
        new_hp = min(max_hp, current_hp + heal)
        # Scholar recovers INT mod mana on short rest
        int_mod = stat_modifier(int(stats.get("INT", 10)))
        new_mana = min(max_mana, current_mana + int_mod) if archetype == "scholar" else current_mana

    return {
        "outcome": "SUCCESS",
        "rest_type": rest_type,
        "hp_before": current_hp,
        "hp_after": new_hp,
        "mana_before": current_mana,
        "mana_after": new_mana,
        "status": "ZAKOŃCZONY",
    }


# ── Examine, Dialogue, Search, Item, Shop ─────────────────────────────────
# PT11 #1121: _resolve_movement removed with process_v2_turn (dead MOVEMENT branch).

def _resolve_examine(params: dict, ctx: dict) -> dict:
    target_key = params.get("target", "")
    npc = ctx.get("target_npc") or {}
    enemy = ctx.get("target_enemy") or {}
    item = ctx.get("item_record") or {}
    desc = npc.get("description") or enemy.get("description") or item.get("description") or ""
    return {
        "outcome": "DESCRIPTION",
        "target": target_key,
        "target_name": npc.get("label") or enemy.get("label") or item.get("label") or target_key,
        "target_description": desc,
    }


def _resolve_dialogue(params: dict, ctx: dict) -> dict:
    npc = ctx.get("target_npc") or {}
    topic = params.get("topic", "")

    # Check keyword triggers
    must_reveal = None
    is_secret = False
    import json as _json
    try:
        triggers = _json.loads(npc.get("keyword_triggers") or "[]")
        for t in triggers:
            kw = str(t.get("keyword", "")).lower()
            if kw and kw in topic.lower():
                must_reveal = t.get("must_reveal_info", "")
                is_secret = bool(t.get("is_secret", False))
                break
    except Exception:
        pass

    return {
        "outcome": "SUCCESS",
        "npc_key": params.get("npc_key", ""),
        "npc_name": npc.get("label", ""),
        "topic": topic,
        "must_reveal_info": must_reveal,
        "is_secret": is_secret,
        "secret_roll": False,
    }


def _resolve_search(params: dict, ctx: dict) -> dict:
    sheet = ctx.get("character_sheet") or {}
    stats = (sheet.get("stats") or {})
    int_mod = stat_modifier(int(stats.get("INT", 10)))
    skills = sheet.get("skills") or {}
    inv_rank = int(skills.get("investigation", 0))
    proficiency = 2 if inv_rank >= 3 else 0

    roll = roll_d20()
    total = roll + int_mod + inv_rank + proficiency
    dc = 12
    success = roll == 20 or (roll != 1 and total >= dc)

    return {
        "outcome": "SUCCESS" if success else "FAILURE",
        "focus": params.get("focus", "general"),
        "roll": roll,
        "modifier": int_mod + inv_rank + proficiency,
        "total": total,
        "dc": dc,
        "found": [],
    }


def _resolve_item_use(params: dict, ctx: dict) -> dict:
    item = ctx.get("item_record") or {}
    sheet = ctx.get("character_sheet") or {}
    stats = (sheet.get("stats") or {})
    import json as _json

    effect = {}
    try:
        effect = _json.loads(item.get("effect_json") or "{}")
    except Exception:
        pass

    hp_change = 0
    mana_change = 0
    current_hp = int(sheet.get("current_hp", 0))
    max_hp = int(sheet.get("max_hp", 10))
    current_mana = int(sheet.get("current_mana", 0))
    max_mana = int(sheet.get("max_mana", 0))

    heal_dice = effect.get("heal", "")
    if heal_dice:
        con_mod = stat_modifier(int(stats.get("CON", 10)))
        healed = parse_dice(str(heal_dice)) + con_mod
        hp_change = min(max_hp - current_hp, healed)

    restore_mana = int(effect.get("restore_mana", 0))
    if restore_mana:
        mana_change = min(max_mana - current_mana, restore_mana)

    return {
        "outcome": "SUCCESS",
        "item_key": params.get("item_key", ""),
        "item_name": item.get("label", ""),
        "effect_description": str(heal_dice or restore_mana or ""),
        "hp_change": hp_change,
        "hp_before": current_hp,
        "hp_after": current_hp + hp_change,
        "mana_change": mana_change,
    }


def _resolve_item_pickup(params: dict, ctx: dict) -> dict:
    item = ctx.get("item_record") or {}
    return {
        "outcome": "SUCCESS",
        "item_key": params.get("item_key", ""),
        "item_name": item.get("label", params.get("item_key", "")),
    }


def _resolve_shop(params: dict, ctx: dict) -> dict:
    npc = ctx.get("target_npc") or {}
    return {
        "outcome": "SUCCESS",
        "npc_key": params.get("npc_key", ""),
        "npc_name": npc.get("label", ""),
        "new_state": "SHOPPING",
    }


def _resolve_generic(params: dict, ctx: dict) -> dict:
    return {"outcome": "DESCRIPTION"}
