import json
import random
import re


SKILL_TO_STAT = {
    "athletics": "STR",
    "melee_attack": "STR",
    "stealth": "DEX",
    "reflex_save": "DEX",
    "ranged_attack": "DEX",
    "fortitude_save": "CON",
    "arcana": "INT",
    "lore": "INT",
    "investigation": "INT",
    "arcane_save": "INT",
    "spell_attack": "INT",
    "awareness": "WIS",
    "survival": "WIS",
    "medicine": "WIS",
    "willpower_save": "WIS",
    "persuasion": "CHA",
    "intimidation": "CHA",
}

ALIASES = {
    "str_save": "fortitude_save",
    "dex_save": "reflex_save",
    "int_save": "arcane_save",
    "wis_save": "willpower_save",
    "cha_save": "persuasion",
    "con_save": "fortitude_save",
    "attack": "melee_attack",
}


def parse_roll_command(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None

    # /roll Stealth, /roll Attack d20
    slash_match = re.match(r"^/roll(?:\s+(.+?))?(?:\s+(d\d+))?$", raw, re.I)
    if slash_match:
        skill = (slash_match.group(1) or "Attack").strip()
        dice = (slash_match.group(2) or "d20").strip().lower()
        return {"skill": skill, "dice": dice}

    # Roll Attack d20 (button-like payload)
    roll_line_match = re.match(r"^roll\s+(.+?)\s+(d\d+)$", raw, re.I)
    if roll_line_match:
        return {
            "skill": (roll_line_match.group(1) or "").strip(),
            "dice": (roll_line_match.group(2) or "d20").strip().lower(),
        }

    return None


def _normalize_skill(skill: str) -> str:
    normalized = (skill or "").strip().lower().replace("-", "_").replace(" ", "_")
    return ALIASES.get(normalized, normalized)


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def resolve_roll(sheet_json_text: str | None, skill: str, dice: str = "d20") -> dict:
    dice_match = re.match(r"^d(\d+)$", (dice or "").strip(), re.I)
    sides = _safe_int(dice_match.group(1), 20) if dice_match else 20
    if sides <= 0:
        sides = 20

    normalized_skill = _normalize_skill(skill)
    d20_roll = random.randint(1, sides)

    try:
        sheet = json.loads(sheet_json_text) if sheet_json_text else {}
    except Exception:
        sheet = {}

    stats = sheet.get("stats") if isinstance(sheet.get("stats"), dict) else {}
    skills = sheet.get("skills") if isinstance(sheet.get("skills"), dict) else {}

    stat_name = SKILL_TO_STAT.get(normalized_skill)
    stat_value = _safe_int(stats.get(stat_name, 10), 10) if stat_name else 10
    stat_modifier = (stat_value - 10) // 2 if stat_name else 0
    skill_rank = _safe_int(skills.get(normalized_skill, 0), 0)
    proficiency_bonus = 2 if skill_rank >= 3 else 0
    modifier = stat_modifier + skill_rank + proficiency_bonus
    total = d20_roll + modifier

    return {
        "skill": (skill or "Attack").strip() or "Attack",
        "d20": d20_roll,
        "modifier": modifier,
        "total": total,
    }


def format_roll_result_message(roll_result: dict) -> str:
    return (
        f"[Roll result: {roll_result['skill']} — rolled "
        f"{roll_result['d20']} + {roll_result['modifier']} = {roll_result['total']}]"
    )
