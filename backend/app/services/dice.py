import json
import logging
import random
import re

logger = logging.getLogger(__name__)


SKILL_STAT_MAP = {
    "athletics": "STR",
    "melee_attack": "STR",
    "stealth": "DEX",
    "ranged_attack": "DEX",
    "arcana": "INT",
    "lore": "INT",
    "investigation": "INT",
    "spell_attack": "INT",
    "awareness": "WIS",
    "survival": "WIS",
    "medicine": "WIS",
    "persuasion": "CHA",
    "intimidation": "CHA",
}

SAVE_STAT_MAP = {
    "fortitude_save": "CON",
    "reflex_save": "DEX",
    "willpower_save": "WIS",
    "arcane_save": "INT",
}

# Keep spell_attack in INT mapping, as locked in phases.
SKILL_STAT_MAP["spell_attack"] = "INT"

VALID_TEST_NAMES = set(SKILL_STAT_MAP.keys()) | set(SAVE_STAT_MAP.keys())

TEST_NAME_ALIASES = {
    "Str Save": "fortitude_save",
    "Con Save": "fortitude_save",
    "Dex Save": "reflex_save",
    "Wis Save": "willpower_save",
    "Int Save": "arcane_save",
    "Cha Save": "willpower_save",
    "Athletics": "athletics",
    "Stealth": "stealth",
    "Awareness": "awareness",
    "Perception": "awareness",
    "Survival": "survival",
    "Lore": "lore",
    "Investigation": "investigation",
    "Arcana": "arcana",
    "Medicine": "medicine",
    "Persuasion": "persuasion",
    "Intimidation": "intimidation",
    "Attack": "melee_attack",
    "Melee Attack": "melee_attack",
    "Ranged Attack": "ranged_attack",
    "Spell Attack": "spell_attack",
    "Initiative": "reflex_save",
}

# Mapping used by POST /api/gm/dice endpoint (Phase 7 tests).
GM_DICE_ALIAS_MAP = {
    "attack": "melee_attack",
    "dex_save": "reflex_save",
    "int_save": "arcane_save",
    "wis_save": "willpower_save",
}

GM_DICE_DIRECT_STAT_ALIASES = {
    "str_save": "STR",
    "con_save": "CON",
}


def parse_roll_command(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None

    # /roll Stealth, /roll Attack d20, /roll Attack 14
    slash_match = re.match(r"^/roll(?:\s+(.+?))?(?:\s+(d\d+|\d+))?$", raw, re.I)
    if slash_match:
        raw_skill = (slash_match.group(1) or "Attack").strip()
        canonical_skill = resolve_test_name(raw_skill)
        if not canonical_skill:
            logger.warning("Unknown /roll test name: %s", raw_skill)
            return None
        roll_arg = (slash_match.group(2) or "d20").strip().lower()
        raw_roll = _safe_int(roll_arg, 0) if roll_arg.isdigit() else None
        return {"skill": canonical_skill, "dice": roll_arg, "raw_roll": raw_roll}

    # Roll Attack d20 (button-like payload)
    roll_line_match = re.match(r"^roll\s+(.+?)\s+(d\d+)$", raw, re.I)
    if roll_line_match:
        raw_skill = (roll_line_match.group(1) or "").strip()
        canonical_skill = resolve_test_name(raw_skill)
        if not canonical_skill:
            logger.warning("Unknown roll cue test name: %s", raw_skill)
            return None
        return {
            "skill": canonical_skill,
            "dice": (roll_line_match.group(2) or "d20").strip().lower(),
            "raw_roll": None,
        }

    return None


def resolve_test_name(raw: str) -> str | None:
    source = (raw or "").strip()
    if not source:
        return None

    title_key = " ".join(source.split()).title()
    alias_match = TEST_NAME_ALIASES.get(title_key)
    if alias_match:
        return alias_match

    normalized = source.lower().replace("-", "_").replace(" ", "_")
    if normalized in VALID_TEST_NAMES:
        return normalized

    return None


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def parse_character_sheet(sheet_json_text: str | None) -> dict:
    try:
        sheet = json.loads(sheet_json_text) if sheet_json_text else {}
    except Exception:
        sheet = {}
    return sheet if isinstance(sheet, dict) else {}


def roll_d20(advantage: bool = False, disadvantage: bool = False) -> int:
    if advantage and not disadvantage:
        return max(random.randint(1, 20), random.randint(1, 20))
    if disadvantage and not advantage:
        return min(random.randint(1, 20), random.randint(1, 20))
    return random.randint(1, 20)


def resolve_roll(
    character_sheet: dict,
    test_name: str,
    raw_roll: int | None = None,
    advantage: bool = False,
    disadvantage: bool = False,
) -> dict:
    normalized_test = resolve_test_name(test_name) or "melee_attack"
    sheet = character_sheet if isinstance(character_sheet, dict) else {}
    stats = sheet.get("stats") if isinstance(sheet.get("stats"), dict) else {}
    skills = sheet.get("skills") if isinstance(sheet.get("skills"), dict) else {}

    effective_raw_roll = raw_roll
    if effective_raw_roll is None or advantage or disadvantage:
        effective_raw_roll = roll_d20(advantage=advantage, disadvantage=disadvantage)
    effective_raw_roll = _safe_int(effective_raw_roll, 1)
    if effective_raw_roll < 1:
        effective_raw_roll = 1
    if effective_raw_roll > 20:
        effective_raw_roll = 20

    if normalized_test in SAVE_STAT_MAP:
        stat_key = SAVE_STAT_MAP[normalized_test]
        stat_value = _safe_int(stats.get(stat_key, 10), 10)
        stat_mod = (stat_value - 10) // 2
        total = effective_raw_roll + stat_mod
        return {
            "test": normalized_test,
            "raw": effective_raw_roll,
            "stat_mod": stat_mod,
            "skill_rank": 0,
            "proficiency": 0,
            "total": total,
            "is_nat20": effective_raw_roll == 20,
            "is_nat1": effective_raw_roll == 1,
        }

    stat_key = SKILL_STAT_MAP.get(normalized_test)
    stat_value = _safe_int(stats.get(stat_key, 10), 10) if stat_key else 10
    stat_mod = (stat_value - 10) // 2 if stat_key else 0
    skill_rank = _safe_int(skills.get(normalized_test, 0), 0)
    proficiency = 2 if skill_rank >= 3 else 0
    total = effective_raw_roll + stat_mod + skill_rank + proficiency

    return {
        "test": normalized_test,
        "raw": effective_raw_roll,
        "stat_mod": stat_mod,
        "skill_rank": skill_rank,
        "proficiency": proficiency,
        "total": total,
        "is_nat20": effective_raw_roll == 20,
        "is_nat1": effective_raw_roll == 1,
    }


def format_roll_result_message(roll_result: dict) -> str:
    return (
        f"[Roll result: {roll_result['test']} — rolled "
        f"{roll_result['raw']} + "
        f"{roll_result['stat_mod'] + roll_result['skill_rank'] + roll_result['proficiency']} "
        f"= {roll_result['total']}]"
    )


def resolve_gm_dice_roll_key(roll_key: str) -> dict | None:
    normalized = (roll_key or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return None

    if normalized in GM_DICE_DIRECT_STAT_ALIASES:
        return {
            "skill": None,
            "stat": GM_DICE_DIRECT_STAT_ALIASES[normalized],
            "resolved_key": normalized,
            "is_save": True,
        }

    canonical = GM_DICE_ALIAS_MAP.get(normalized, normalized)
    if canonical in SAVE_STAT_MAP:
        return {
            "skill": canonical,
            "stat": SAVE_STAT_MAP[canonical],
            "resolved_key": canonical,
            "is_save": True,
        }
    if canonical in SKILL_STAT_MAP:
        return {
            "skill": canonical,
            "stat": SKILL_STAT_MAP[canonical],
            "resolved_key": canonical,
            "is_save": False,
        }

    return None


def build_gm_dice_breakdown(character_sheet: dict, roll_key: str, roll: int) -> dict | None:
    resolved = resolve_gm_dice_roll_key(roll_key)
    if not resolved:
        return None

    sheet = character_sheet if isinstance(character_sheet, dict) else {}
    stats = sheet.get("stats") if isinstance(sheet.get("stats"), dict) else {}
    skills = sheet.get("skills") if isinstance(sheet.get("skills"), dict) else {}

    stat_key = resolved["stat"]
    stat_value = _safe_int(stats.get(stat_key, 10), 10)
    stat_modifier = (stat_value - 10) // 2

    skill = resolved["skill"]
    skill_rank = 0 if (resolved["is_save"] or not skill) else _safe_int(skills.get(skill, 0), 0)
    proficiency_bonus = 0 if resolved["is_save"] else (2 if skill_rank >= 3 else 0)
    final_total = _safe_int(roll, 0) + stat_modifier + skill_rank + proficiency_bonus

    return {
        "roll": _safe_int(roll, 0),
        "stat": stat_key,
        "stat_modifier": stat_modifier,
        "skill": skill or resolved["resolved_key"],
        "skill_rank": skill_rank,
        "proficiency_bonus": proficiency_bonus,
        "final_total": final_total,
    }
