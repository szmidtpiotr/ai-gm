import json
import logging
import random
import re

logger = logging.getLogger(__name__)


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

VALID_TEST_NAMES = set(SKILL_TO_STAT.keys())

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


def parse_roll_command(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None

    # /roll Stealth, /roll Attack d20
    slash_match = re.match(r"^/roll(?:\s+(.+?))?(?:\s+(d\d+))?$", raw, re.I)
    if slash_match:
        raw_skill = (slash_match.group(1) or "Attack").strip()
        canonical_skill = resolve_test_name(raw_skill)
        if not canonical_skill:
            logger.warning("Unknown /roll test name: %s", raw_skill)
            return None
        dice = (slash_match.group(2) or "d20").strip().lower()
        return {"skill": canonical_skill, "dice": dice}

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


def resolve_roll(sheet_json_text: str | None, skill: str, dice: str = "d20") -> dict:
    dice_match = re.match(r"^d(\d+)$", (dice or "").strip(), re.I)
    sides = _safe_int(dice_match.group(1), 20) if dice_match else 20
    if sides <= 0:
        sides = 20

    normalized_skill = resolve_test_name(skill) or "melee_attack"
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
        "skill": normalized_skill,
        "d20": d20_roll,
        "modifier": modifier,
        "total": total,
    }


def format_roll_result_message(roll_result: dict) -> str:
    return (
        f"[Roll result: {roll_result['skill']} — rolled "
        f"{roll_result['d20']} + {roll_result['modifier']} = {roll_result['total']}]"
    )
