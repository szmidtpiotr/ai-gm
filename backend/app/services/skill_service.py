"""
Skill test service — Task 12.

Handles:
  1. [SKILL_TEST:skill_key:DC:14] and [SKILL_TEST:skill_key:OPPOSED:perception] tag interception
  2. [TRAP:skill_key:dc:damage_dice:condition] tag interception
  3. resolve_pending_skill_test() — called when player sends their d20 roll
"""

import json
import re
import random
import sqlite3
import uuid
from typing import Optional

from app.services.vitality_service import stat_modifier
from app.services.dice import roll_d20

DB_PATH = "/data/ai_gm.db"

# Fallback skill → governing stat (used when DB lookup unavailable)
_SKILL_STAT_FALLBACK: dict[str, str] = {
    "stealth": "DEX", "lockpick": "DEX", "acrobatics": "DEX",
    "perception": "WIS", "insight": "WIS", "survival": "WIS",
    "persuasion": "CHA", "deception": "CHA", "intimidation": "CHA",
    "athletics": "STR", "arcana": "INT", "medicine": "INT", "lore": "INT",
}

# Fallback labels
_SKILL_LABEL_FALLBACK: dict[str, str] = {
    "stealth": "Skradanie", "lockpick": "Otwieranie zamków", "acrobatics": "Akrobatyka",
    "perception": "Percepcja", "insight": "Wnikliwość", "survival": "Przetrwanie",
    "persuasion": "Perswazja", "deception": "Oszustwo", "intimidation": "Zastraszenie",
    "athletics": "Atletyka", "arcana": "Arkana", "medicine": "Medycyna", "lore": "Wiedza",
}

def _query_skill_from_db(skill_key: str) -> tuple[str, str] | None:
    """Query game_config_skills for a single skill. Returns (linked_stat, label) or None."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT linked_stat, label FROM game_config_skills WHERE key = ? AND is_active = 1 LIMIT 1",
            (skill_key,),
        ).fetchone()
        conn.close()
        if row:
            return str(row["linked_stat"] or "INT").upper(), str(row["label"] or skill_key.title())
    except Exception:
        pass
    return None


def _skill_stat(skill_key: str) -> str:
    """Return governing stat for a skill. Always reads from DB, falls back to hardcoded map."""
    result = _query_skill_from_db(skill_key)
    if result:
        return result[0]
    return _SKILL_STAT_FALLBACK.get(skill_key, "INT")


def _skill_label(skill_key: str) -> str:
    """Return display label for a skill. Always reads from DB, falls back to hardcoded map."""
    result = _query_skill_from_db(skill_key)
    if result:
        return result[1]
    return _SKILL_LABEL_FALLBACK.get(skill_key, skill_key.title())


# Keep SKILL_LABELS for backward compat (tag intercept code)
SKILL_LABELS = _SKILL_LABEL_FALLBACK


# ── Modifier calculation ──────────────────────────────────────────────────────

def calc_skill_modifier_info(sheet: dict, skill_key: str) -> dict:
    """Return full modifier breakdown for the Roll Popup."""
    stats = sheet.get("stats") or {}
    skills = sheet.get("skills") or {}
    governing_stat = _skill_stat(skill_key)
    stat_val = int(stats.get(governing_stat, 10))
    stat_mod = stat_modifier(stat_val)
    skill_rank = int(skills.get(skill_key, 0))
    proficiency = 2 if skill_rank >= 3 else 0
    total = skill_rank + stat_mod + proficiency
    return {
        "governing_stat": governing_stat,
        "skill_rank": skill_rank,
        "stat_mod": stat_mod,
        "proficiency": proficiency,
        "total": total,
    }


# ── Counter lookup ────────────────────────────────────────────────────────────

def _get_counter(conn: sqlite3.Connection, skill_key: str) -> dict:
    try:
        row = conn.execute(
            "SELECT counter_type, counter_key, default_dc FROM skill_counters WHERE player_skill_key = ? LIMIT 1",
            (skill_key,),
        ).fetchone()
        if row:
            return {"counter_type": row[0], "counter_key": row[1], "dc": row[2] or 12}
    except sqlite3.OperationalError:
        pass
    return {"counter_type": "dc", "counter_key": None, "dc": 12}


def _resolve_opponent(conn: sqlite3.Connection, counter: dict, campaign_id: int) -> tuple[int, int | None]:
    """Roll the opponent side of an opposed check. Returns (opponent_total, opponent_roll)."""
    if counter.get("counter_type") != "opposed":
        return int(counter.get("dc", 12)), None

    counter_key = counter.get("counter_key") or "WIS"
    opp_roll = random.randint(1, 20)

    # counter_key can be a stat name (e.g. "WIS") or a skill name (e.g. "perception")
    # For opposed: we need the NPC/enemy modifier — use a fixed moderate modifier as fallback
    opp_mod = 2  # default moderate opponent modifier
    return opp_roll + opp_mod, opp_roll


# ── [SKILL_TEST:...] tag interception ────────────────────────────────────────

SKILL_TEST_RE = re.compile(
    r"\[SKILL_TEST:([a-z_]+):(DC|OPPOSED):([^\]]+)\]",
    re.IGNORECASE,
)

TRAP_RE = re.compile(
    r"\[TRAP:([a-z_]+):(\d+):([^:]+):([^\]]*)\]",
    re.IGNORECASE,
)


def intercept_skill_test_tag(
    prose: str,
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
) -> tuple[str, dict | None]:
    """
    Strip first [SKILL_TEST:...] tag from prose and return pending context.
    Returns (cleaned_prose, pending_dict | None).
    """
    m = SKILL_TEST_RE.search(prose)
    if not m:
        return prose, None

    skill_key = m.group(1).lower()
    res_type = m.group(2).upper()
    value = m.group(3).strip()

    # Build counter
    if res_type == "DC":
        counter = {"counter_type": "dc", "counter_key": None, "dc": int(value) if value.isdigit() else 12}
    else:
        counter = {"counter_type": "opposed", "counter_key": value.lower(), "dc": 12}

    # Load character sheet for modifier
    sheet = {}
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1", (character_id,)
        ).fetchone()
        if row:
            sheet = json.loads(row[0] or "{}")
    except Exception:
        pass

    mod_info = calc_skill_modifier_info(sheet, skill_key)
    skill_test_id = f"st-{uuid.uuid4().hex[:8]}"

    pending = {
        "skill_test_id": skill_test_id,
        "skill_key": skill_key,
        "skill_label": _skill_label(skill_key),
        "counter": counter,
        "modifier_breakdown": mod_info,
    }

    cleaned = prose[:m.start()].rstrip() + prose[m.end():]
    cleaned = cleaned.strip()
    return cleaned, pending


def intercept_trap_tag(
    prose: str,
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    sheet: dict,
) -> tuple[str, dict | None]:
    """
    Strip first [TRAP:...] tag; return pending trap context.
    Traps also go through the Roll Popup but carry damage/condition on fail.
    """
    m = TRAP_RE.search(prose)
    if not m:
        return prose, None

    skill_key = m.group(1).lower()
    dc = int(m.group(2))
    damage_dice = m.group(3).strip()
    condition_key = m.group(4).strip() or None

    mod_info = calc_skill_modifier_info(sheet, skill_key)
    skill_test_id = f"tr-{uuid.uuid4().hex[:8]}"

    pending = {
        "skill_test_id": skill_test_id,
        "skill_key": skill_key,
        "skill_label": _skill_label(skill_key),
        "counter": {"counter_type": "dc", "dc": dc},
        "modifier_breakdown": mod_info,
        "trap": {
            "damage_dice": damage_dice,
            "condition_key": condition_key,
        },
    }

    cleaned = prose[:m.start()].rstrip() + prose[m.end():]
    cleaned = cleaned.strip()
    return cleaned, pending


# ── Skill test resolution ─────────────────────────────────────────────────────

def resolve_skill_test(
    d20_roll: int,
    pending: dict,
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
) -> dict:
    """
    Resolve a pending skill test given the player's d20 roll.
    Returns resolution result dict for narrator context injection.
    """
    skill_key = pending.get("skill_key", "perception")
    mod_info = pending.get("modifier_breakdown", {})
    counter = pending.get("counter", {"counter_type": "dc", "dc": 12})

    player_total = d20_roll + int(mod_info.get("total", 0))

    nat20 = d20_roll == 20
    nat1 = d20_roll == 1

    # Opponent side
    opponent_total, opponent_roll = _resolve_opponent(conn, counter, campaign_id)

    success = nat20 or (not nat1 and player_total >= opponent_total)

    if nat20:
        outcome = "CRITICAL_SUCCESS"
    elif nat1:
        outcome = "CRITICAL_FAILURE"
    elif success:
        outcome = "SUCCESS"
    else:
        outcome = "FAILURE"

    result = {
        "skill_key": skill_key,
        "skill_label": pending.get("skill_label", skill_key),
        "d20_roll": d20_roll,
        "modifier": int(mod_info.get("total", 0)),
        "player_total": player_total,
        "opponent_total": opponent_total,
        "opponent_roll": opponent_roll,
        "outcome": outcome,
        "nat20": nat20,
        "nat1": nat1,
        "success": success,
    }

    # Handle trap damage/condition on failure
    trap = pending.get("trap")
    if trap and not success:
        damage_dice = trap.get("damage_dice", "1d4")
        dmg = _roll_dice(damage_dice)
        result["trap_damage"] = dmg
        result["trap_damage_dice"] = damage_dice
        result["trap_condition_key"] = trap.get("condition_key")
        # Apply HP damage
        _apply_trap_damage(character_id, dmg, conn)

    return result


def _roll_dice(expr: str) -> int:
    m = re.match(r"^(\d*)d(\d+)([+-]\d+)?$", expr.lower().strip())
    if not m:
        return 1
    n = int(m.group(1) or 1)
    sides = int(m.group(2))
    bonus = int(m.group(3) or 0)
    return max(0, sum(random.randint(1, sides) for _ in range(max(1, n))) + bonus)


def _apply_trap_damage(character_id: int, damage: int, conn: sqlite3.Connection) -> None:
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        if not row:
            return
        sheet = json.loads(row[0] or "{}")
        cur_hp = int(sheet.get("current_hp", 0))
        new_hp = max(0, cur_hp - damage)
        sheet["current_hp"] = new_hp
        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), character_id),
        )
        conn.commit()
    except Exception:
        pass


# ── Narrator context for resolution ──────────────────────────────────────────

def build_skill_result_context(result: dict) -> str:
    """Build context string to inject into the second narrator call."""
    outcome_label = {
        "CRITICAL_SUCCESS": "Krytyczny sukces!",
        "SUCCESS": "Sukces",
        "FAILURE": "Niepowodzenie",
        "CRITICAL_FAILURE": "Krytyczne niepowodzenie!",
    }.get(result["outcome"], result["outcome"])

    lines = [
        f"[WYNIK TESTU UMIEJĘTNOŚCI]",
        f"Umiejętność: {result['skill_label']}",
        f"Rzut gracza: {result['d20_roll']} + {result['modifier']} = {result['player_total']}",
        f"Próg: {result['opponent_total']}" + (f" (przeciwnik rzucił {result['opponent_roll']})" if result.get('opponent_roll') else ""),
        f"Wynik: {outcome_label}",
    ]
    if result.get("nat20"):
        lines.append("Naturalny 20 — wyjątkowy sukces.")
    if result.get("nat1"):
        lines.append("Naturalny 1 — komplikacja w narracji.")
    if result.get("trap_damage"):
        lines.append(f"Pułapka zadała {result['trap_damage']} obrażeń.")
    return "\n".join(lines)
