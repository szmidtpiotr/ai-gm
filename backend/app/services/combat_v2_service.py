"""
Combat V2 Service — Phase 05 Tasks 14-19

Extends the existing combat_service.py with V2 mechanics:
- TASK_14: Auto-enemy turns (full round in one backend call)
- TASK_15: Enemy behavior profiles (rule-based AI)
- TASK_16: Fear & Terror system
- TASK_17: Critical hit location table + conditions
- TASK_18: Escalating death save DC (10/13/16/19)
- TASK_19: Flee mechanic (opposed DEX roll)

All mechanics are deterministic Python. The LLM narrates after resolution.
"""

from __future__ import annotations

import json
import random
import sqlite3
import structlog
from typing import Any

logger = structlog.get_logger()

DB_PATH = "/data/ai_gm.db"

# ── Constants ──────────────────────────────────────────────────────────────

CRIT_THRESHOLD = 5  # attack_total - AC >= CRIT_THRESHOLD → critical hit

# Death save DC ladder (per 0-HP hit in same combat, pure d20 — no CON modifier)
DEATH_SAVE_DC_LADDER = [10, 13, 16, 19]

# Hit location table (d6 roll)
HIT_LOCATION_TABLE = {
    1: "head",
    2: "torso",
    3: "right_arm",
    4: "left_arm",
    5: "right_leg",
    6: "left_leg",
}

# Conditions applied by hit location (on player when enemy crits)
PLAYER_CRIT_CONDITIONS = {
    "head":      ("dazed",    1),   # skip next action
    "torso":     ("winded",   2),   # -2 STR actions for 2 rounds
    "right_arm": ("arm_wound",3),   # -1 ATK for 3 rounds
    "left_arm":  ("arm_wound",3),
    "right_leg": ("leg_wound",3),   # -2 flee roll for 3 rounds
    "left_leg":  ("leg_wound",3),
}

# Conditions applied by hit location (on enemy when player crits)
ENEMY_CRIT_CONDITIONS = {
    "head":      ("stunned",  1),   # skip next turn
    "torso":     ("bleeding", 3),   # 1 dmg/round end of round
    "right_arm": ("disarmed", 3),   # -2 DMG
    "left_arm":  ("disarmed", 3),
    "right_leg": ("hobbled",  3),   # cannot flee
    "left_leg":  ("hobbled",  3),
}


# ── Helper ─────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _stat_mod(stat: int) -> int:
    return (int(stat) - 10) // 2

def _d20() -> int:
    return random.randint(1, 20)

def _roll(sides: int) -> int:
    return random.randint(1, sides)


# ── TASK_15: Enemy Behavior Profiles ──────────────────────────────────────

def get_behavior_profile(enemy_key: str, conn: sqlite3.Connection) -> dict | None:
    """Load behavior profile for an enemy key."""
    row = conn.execute(
        "SELECT * FROM enemy_behavior_profiles WHERE enemy_key = ?", (enemy_key,)
    ).fetchone()
    if row:
        return dict(row)
    # Fallback: check behavior_profile_key column on enemy
    erow = conn.execute(
        "SELECT behavior_profile_key FROM game_config_enemies WHERE key = ?", (enemy_key,)
    ).fetchone()
    if erow and erow[0]:
        prow = conn.execute(
            "SELECT * FROM enemy_behavior_profiles WHERE enemy_key = ?", (erow[0],)
        ).fetchone()
        if prow:
            return dict(prow)
    return None


def resolve_enemy_action(
    enemy: dict,
    profile: dict | None,
    combat_state: dict,
) -> dict:
    """
    Determine what action an enemy takes this turn.
    Returns: {"action": "attack"|"flee"|"use_special"|"defend", "data": {...}}
    """
    hp = int(enemy.get("hp", 1))
    hp_max = int(enemy.get("hp_max", enemy.get("hp_base", 12)))
    hp_pct = (hp / hp_max * 100) if hp_max > 0 else 100

    if profile is None:
        return {"action": "attack", "data": {}}

    # Check flee threshold
    flee_threshold = float(profile.get("hp_threshold_flee", 0))
    if flee_threshold > 0 and hp_pct <= flee_threshold:
        return {"action": "flee", "data": {}}

    # Check special ability cooldown
    default_action = profile.get("default_action", "attack_player")
    if default_action == "use_special":
        cooldown = int(enemy.get("special_ability_cooldown_remaining", 0))
        if cooldown > 0:
            return {"action": "attack", "data": {"cooldown_fallback": True}}
        return {"action": "use_special", "data": {
            "ability_key": profile.get("special_ability_key", "")
        }}

    return {"action": default_action.replace("attack_player", "attack")
            .replace("attack_weakest", "attack"), "data": {}}


# ── TASK_17: Critical Hits ─────────────────────────────────────────────────

def check_critical_hit(attack_total: int, target_ac: int, raw_d20: int) -> bool:
    """Returns True if this attack is a critical hit."""
    if raw_d20 == 20:
        return True
    return (attack_total - target_ac) >= CRIT_THRESHOLD


def resolve_crit_location(is_player_target: bool) -> dict:
    """
    Roll hit location and return the condition to apply.
    is_player_target: True = enemy critting player, False = player critting enemy.
    """
    d6 = _roll(6)
    location = HIT_LOCATION_TABLE[d6]
    table = PLAYER_CRIT_CONDITIONS if is_player_target else ENEMY_CRIT_CONDITIONS
    condition_type, duration = table[location]
    return {
        "location": location,
        "condition_type": condition_type,
        "duration_rounds": duration,
        "d6_roll": d6,
    }


def apply_crit_condition(
    target_id: str,
    is_player: bool,
    crit_info: dict,
    current_turn: int,
    conn: sqlite3.Connection,
    character_id: int | None = None,
) -> None:
    """Apply the critical hit condition to the appropriate target."""
    condition_type = crit_info["condition_type"]
    duration = crit_info["duration_rounds"]
    expires_at = str(current_turn + duration)

    if is_player and character_id:
        try:
            # Check if already has this condition (refresh)
            conn.execute(
                "DELETE FROM character_conditions WHERE character_id = ? AND condition_type = ?",
                (character_id, condition_type)
            )
            conn.execute(
                """INSERT INTO character_conditions
                   (character_id, condition_type, severity, rounds_remaining, expires_at, source)
                   VALUES (?, ?, 1, ?, ?, 'crit_hit')""",
                (character_id, condition_type, duration, expires_at)
            )
            conn.commit()
        except Exception as e:
            logger.warning("crit_condition_apply_failed", error=str(e))


# ── TASK_16: Fear & Terror ─────────────────────────────────────────────────

def check_fear_trigger(
    enemy_key: str,
    character_id: int,
    campaign_id: int,
    conn: sqlite3.Connection,
) -> dict | None:
    """
    Check if an enemy triggers a Fear test at combat entry.
    Returns fear check data if trigger fires, None otherwise.
    """
    erow = conn.execute(
        "SELECT fear_aura, fear_dc, label FROM game_config_enemies WHERE key = ?",
        (enemy_key,)
    ).fetchone()
    if not erow or not int(erow["fear_aura"] or 0):
        return None

    fear_dc = int(erow["fear_dc"] or 12)

    # Check if player is already immune (has frightened/panicked/break from this combat)
    existing = conn.execute(
        """SELECT condition_type FROM character_conditions
           WHERE character_id = ? AND condition_type IN ('fear_frightened','terror','break')""",
        (character_id,)
    ).fetchone()
    if existing:
        return None  # already feared — escalation handled elsewhere

    return {
        "fear_source": enemy_key,
        "fear_source_name": erow["label"],
        "fear_dc": fear_dc,
        "pending": True,
    }


def resolve_fear_save(
    character_id: int,
    d20_roll: int,
    fear_dc: int,
    current_round: int,
    conn: sqlite3.Connection,
) -> dict:
    """
    Resolve a Fear/Terror WIS saving throw.
    d20_roll: the player's pure d20 (no modifiers — pure fate per design decisions).
    """
    # Check current fear state for escalation
    existing_fear = conn.execute(
        """SELECT condition_type FROM character_conditions
           WHERE character_id = ?
           AND condition_type IN ('fear_shaken','fear_frightened','terror')
           ORDER BY CASE condition_type
             WHEN 'terror' THEN 3
             WHEN 'fear_frightened' THEN 2
             ELSE 1 END DESC LIMIT 1""",
        (character_id,)
    ).fetchone()
    current_fear = existing_fear[0] if existing_fear else None

    success = d20_roll >= fear_dc
    nat1 = d20_roll == 1
    nat20 = d20_roll == 20

    if nat20 or success:
        return {
            "outcome": "SUCCESS",
            "roll": d20_roll,
            "dc": fear_dc,
            "condition_applied": None,
            "nat20": nat20,
        }

    # Failed — determine new condition
    if nat1 or current_fear == "fear_frightened":
        new_condition = "terror"
        duration = 3
    elif current_fear == "fear_shaken":
        new_condition = "fear_frightened"
        duration = 2
    else:
        new_condition = "fear_shaken"
        duration = 3

    expires_at = str(current_round + duration)
    try:
        conn.execute(
            "DELETE FROM character_conditions WHERE character_id = ? AND condition_type LIKE 'fear_%'",
            (character_id,)
        )
        conn.execute(
            """INSERT INTO character_conditions
               (character_id, condition_type, severity, rounds_remaining, expires_at, source)
               VALUES (?, ?, 1, ?, ?, 'fear_aura')""",
            (character_id, new_condition, duration, expires_at)
        )
        conn.commit()
    except Exception as e:
        logger.warning("fear_condition_apply_failed", error=str(e))

    return {
        "outcome": "FAILURE",
        "roll": d20_roll,
        "dc": fear_dc,
        "condition_applied": new_condition,
        "nat1": nat1,
    }


# ── TASK_18: Escalating Death Save DC ─────────────────────────────────────

def get_death_save_dc(death_save_count: int) -> int:
    """Return DC for the Nth time player reaches 0 HP in current combat."""
    idx = min(death_save_count - 1, len(DEATH_SAVE_DC_LADDER) - 1)
    return DEATH_SAVE_DC_LADDER[max(0, idx)]


def resolve_death_save_v2(
    character_id: int,
    d20_roll: int,
    death_save_count: int,
    current_failure_count: int,
    conn: sqlite3.Connection,
) -> dict:
    """
    Resolve death save using escalating DC ladder. Pure d20 — no modifiers.

    death_save_count: how many times player has hit 0 HP this combat (1-indexed)
    current_failure_count: failures accumulated so far this combat
    Returns result dict + updates character HP if survived.
    """
    dc = get_death_save_dc(death_save_count)
    nat20 = d20_roll == 20
    nat1 = d20_roll == 1
    success = nat20 or (not nat1 and d20_roll >= dc)

    failures_added = 0
    if not success:
        failures_added = 2 if nat1 else 1

    new_failures = current_failure_count + failures_added
    dead = new_failures >= 3

    if success and not dead:
        # Restore to 1 HP
        try:
            row = conn.execute(
                "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
            ).fetchone()
            if row:
                sheet = json.loads(row[0] or "{}")
                sheet["current_hp"] = 1
                conn.execute(
                    "UPDATE characters SET sheet_json = ? WHERE id = ?",
                    (json.dumps(sheet), character_id)
                )
                conn.commit()
        except Exception as e:
            logger.warning("death_save_hp_restore_failed", error=str(e))

    return {
        "outcome": "SURVIVED" if success else ("DEAD" if dead else "FAILED"),
        "roll": d20_roll,
        "dc": dc,
        "death_save_count": death_save_count,
        "nat20": nat20,
        "nat1": nat1,
        "success": success,
        "failures_added": failures_added,
        "total_failures": new_failures,
        "dead": dead,
        "hp_restored": 1 if success else 0,
    }


# ── TASK_19: Flee Mechanic ─────────────────────────────────────────────────

def resolve_flee(
    character_id: int,
    campaign_id: int,
    conn: sqlite3.Connection,
) -> dict:
    """
    Opposed DEX roll: player vs highest enemy DEX modifier.
    Success: escape. Failure: player loses turn.
    """
    char_row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    sheet = json.loads((char_row or {})["sheet_json"] or "{}") if char_row else {}
    stats = sheet.get("stats") or {}
    char_dex_mod = _stat_mod(int(stats.get("DEX", 10)))

    # Get combat state for enemy DEX modifiers
    combat_row = conn.execute(
        "SELECT combatants FROM active_combat WHERE campaign_id = ? AND status = 'active'",
        (campaign_id,)
    ).fetchone()

    max_enemy_dex = 0
    if combat_row:
        combatants = json.loads(combat_row[0] or "[]")
        for c in combatants:
            if c.get("type") != "player" and int(c.get("hp", 1)) > 0:
                enemy_key = str(c.get("template_key") or c.get("key", ""))
                # Try to get dex_modifier from DB
                if enemy_key:
                    erow = conn.execute(
                        "SELECT dex_modifier FROM game_config_enemies WHERE key = ?",
                        (enemy_key.split("_")[0] if "_" in enemy_key else enemy_key,)
                    ).fetchone()
                    if erow:
                        max_enemy_dex = max(max_enemy_dex, int(erow[0] or 0))

    player_roll = _d20() + char_dex_mod
    enemy_roll = _d20() + max_enemy_dex

    success = player_roll > enemy_roll  # tie goes to enemy

    return {
        "outcome": "SUCCESS" if success else "FAILURE",
        "player_roll": player_roll,
        "player_dex_mod": char_dex_mod,
        "enemy_roll": enemy_roll,
        "enemy_dex_mod": max_enemy_dex,
        "fled": success,
    }


# ── TASK_14: Full round resolution ─────────────────────────────────────────

def resolve_full_round_after_player(
    campaign_id: int,
    character_id: int,
    player_action_result: dict,
    conn: sqlite3.Connection,
) -> list[dict]:
    """
    After player's action resolves, auto-resolve all enemy turns in initiative order.
    Returns list of enemy action results for narrator context.
    """
    combat_row = conn.execute(
        "SELECT combatants, turn_order, round FROM active_combat WHERE campaign_id = ? AND status = 'active'",
        (campaign_id,)
    ).fetchone()
    if not combat_row:
        return []

    combatants = json.loads(combat_row["combatants"] or "[]")
    turn_order = json.loads(combat_row["turn_order"] or "[]")
    current_round = int(combat_row["round"] or 1)

    # Find player position in order, then resolve all enemies after player this round
    player_idx = next((i for i, tid in enumerate(turn_order) if tid == "player"), -1)

    enemy_results = []
    for i, combatant_id in enumerate(turn_order):
        if combatant_id == "player":
            continue  # player already acted

        # Find combatant
        combatant = next((c for c in combatants if c.get("id") == combatant_id), None)
        if not combatant or int(combatant.get("hp", 0)) <= 0:
            continue  # dead or missing

        profile = get_behavior_profile(
            str(combatant.get("template_key", combatant.get("key", ""))).split("_")[0],
            conn
        )
        action = resolve_enemy_action(combatant, profile, {"combatants": combatants})

        if action["action"] in ("attack", "attack_player", "attack_weakest"):
            result = _resolve_enemy_attack(combatant, character_id, current_round, conn)
            result["enemy_id"] = combatant_id
            result["enemy_name"] = combatant.get("name", combatant_id)
            enemy_results.append(result)
        elif action["action"] == "flee":
            enemy_results.append({
                "enemy_id": combatant_id,
                "enemy_name": combatant.get("name", combatant_id),
                "action": "flee",
                "outcome": "ENEMY_FLED",
            })
            # Mark enemy as fled (hp = 0 effectively)
            combatant["hp"] = 0

    # Persist condition ticks at end of round
    _tick_conditions_end_of_round(character_id, combatants, conn)

    # Update combatants in DB
    conn.execute(
        "UPDATE active_combat SET combatants = ? WHERE campaign_id = ?",
        (json.dumps(combatants), campaign_id)
    )
    conn.commit()

    return enemy_results


def _resolve_enemy_attack(
    enemy: dict,
    character_id: int,
    current_round: int,
    conn: sqlite3.Connection,
) -> dict:
    """Resolve a single enemy attack against the player."""
    char_row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    sheet = json.loads((char_row or {}).get("sheet_json") or "{}") if char_row else {}

    # Player AC
    equipped_armor = conn.execute(
        """SELECT gi.ac_bonus FROM character_inventory ci
           JOIN game_config_items gi ON gi.key = ci.item_key
           WHERE ci.character_id = ? AND ci.equipped = 1 AND gi.item_type = 'armor'
           LIMIT 1""",
        (character_id,)
    ).fetchone()
    base_ac = 10
    stats = sheet.get("stats") or {}
    dex_mod = _stat_mod(int(stats.get("DEX", 10)))
    armor_bonus = int((equipped_armor or [0])[0] or 0)
    player_ac = base_ac + dex_mod + armor_bonus

    atk_bonus = int(enemy.get("attack_bonus", 2))
    damage_die = str(enemy.get("damage_die", "d6"))
    dmg_bonus = int(enemy.get("damage_bonus", 0))

    raw = _d20()
    total = raw + atk_bonus
    nat20 = raw == 20
    nat1 = raw == 1
    hit = nat20 or (not nat1 and total >= player_ac)

    damage = 0
    crit = False
    crit_info = None

    if hit:
        from app.services.mechanic_resolver import parse_dice
        base_dmg = parse_dice(damage_die)
        damage = max(0, base_dmg + dmg_bonus)

        if check_critical_hit(total, player_ac, raw):
            crit = True
            damage *= 2
            crit_info = resolve_crit_location(is_player_target=True)
            apply_crit_condition(
                enemy.get("id", ""), True, crit_info, current_round, conn, character_id
            )

    # Apply damage to player
    current_hp = int(sheet.get("current_hp", 0))
    max_hp = int(sheet.get("max_hp", 10))
    new_hp = max(0, current_hp - damage) if hit else current_hp

    if hit and new_hp != current_hp:
        sheet["current_hp"] = new_hp
        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet), character_id)
        )
        conn.commit()

    return {
        "action": "attack",
        "outcome": "CRITICAL_HIT" if crit else ("HIT" if hit else "MISS"),
        "roll": raw,
        "atk_bonus": atk_bonus,
        "total": total,
        "player_ac": player_ac,
        "hit": hit,
        "damage": damage,
        "nat20": nat20,
        "nat1": nat1,
        "crit": crit,
        "crit_info": crit_info,
        "player_hp_before": current_hp,
        "player_hp_after": new_hp,
        "player_at_zero": new_hp <= 0,
    }


def _tick_conditions_end_of_round(
    character_id: int,
    combatants: list[dict],
    conn: sqlite3.Connection,
) -> None:
    """Apply end-of-round condition damage (Bleeding, Poisoned) and decrement durations."""
    try:
        # Player conditions: bleeding, poisoned
        rows = conn.execute(
            """SELECT id, condition_type, rounds_remaining, expires_at
               FROM character_conditions
               WHERE character_id = ? AND condition_type IN ('bleeding','poisoned')""",
            (character_id,)
        ).fetchall()

        char_row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        if char_row:
            sheet = json.loads(char_row[0] or "{}")
            hp = int(sheet.get("current_hp", 0))
            changed = False

            for row in rows:
                dmg = 2 if row["condition_type"] == "poisoned" else 1
                hp = max(0, hp - dmg)
                changed = True

                # Decrement rounds
                rounds = row["rounds_remaining"]
                if rounds is not None:
                    new_rounds = int(rounds) - 1
                    if new_rounds <= 0:
                        conn.execute("DELETE FROM character_conditions WHERE id = ?", (row["id"],))
                    else:
                        conn.execute(
                            "UPDATE character_conditions SET rounds_remaining = ? WHERE id = ?",
                            (new_rounds, row["id"])
                        )

            if changed:
                sheet["current_hp"] = hp
                conn.execute(
                    "UPDATE characters SET sheet_json = ? WHERE id = ?",
                    (json.dumps(sheet), character_id)
                )

        # Enemy bleeding conditions (stored in combatant dicts)
        for c in combatants:
            if c.get("bleeding_rounds", 0) > 0:
                c["hp"] = max(0, int(c.get("hp", 0)) - 1)
                c["bleeding_rounds"] = int(c["bleeding_rounds"]) - 1

        conn.commit()
    except Exception as e:
        logger.warning("condition_tick_failed", error=str(e))
