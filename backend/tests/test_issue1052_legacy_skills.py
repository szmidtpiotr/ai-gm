"""TDD: Issue #1052 — legacy skill keys cause unknown_skill error in Awansuj screen."""
import json
import random
import sys

sys.path.insert(0, "/app")

from app.character_creation_config import CREATION_SKILL_POOL, roll_creation_skills
from app.services.dice import DICE_TEST_TO_CONFIG_SKILL_KEY
from app.services.weapon_rules import resolve_attack_roll_for_weapon
from app.services import xp_service

LEGACY_KEYS = frozenset({"melee_attack", "ranged_attack", "spell_attack", "sleight_of_hand"})

_CATALOG_KEYS = {
    "attack", "arcana", "pickpocket", "endurance", "athletics",
    "stealth", "lockpick", "acrobatics", "awareness", "investigation",
    "lore", "survival", "medicine", "persuasion", "intimidation",
    "alchemy", "dodge", "shield_block",
}


# ─── CREATION POOL ───────────────────────────────────────────────────────────


def test_creation_pool_has_no_legacy_keys():
    """CREATION_SKILL_POOL must not contain keys absent from game_config_skills catalog."""
    overlap = LEGACY_KEYS & CREATION_SKILL_POOL
    assert not overlap, f"Legacy keys still in CREATION_SKILL_POOL: {overlap}"


def test_rolled_skills_have_no_legacy_keys_warrior():
    rng = random.Random(42)
    skills = roll_creation_skills("warrior", rng)
    legacy = {k: v for k, v in skills.items() if k in LEGACY_KEYS and v > 0}
    assert not legacy, f"warrior rolled legacy keys: {legacy}"


def test_rolled_skills_have_no_legacy_keys_rogue():
    rng = random.Random(42)
    skills = roll_creation_skills("rogue", rng)
    legacy = {k: v for k, v in skills.items() if k in LEGACY_KEYS and v > 0}
    assert not legacy, f"rogue rolled legacy keys: {legacy}"


def test_rolled_skills_have_no_legacy_keys_scholar():
    rng = random.Random(42)
    skills = roll_creation_skills("scholar", rng)
    legacy = {k: v for k, v in skills.items() if k in LEGACY_KEYS and v > 0}
    assert not legacy, f"scholar rolled legacy keys: {legacy}"


# ─── DICE_TEST_TO_CONFIG_SKILL_KEY ───────────────────────────────────────────


def test_dice_mapping_covers_ranged_attack():
    assert "ranged_attack" in DICE_TEST_TO_CONFIG_SKILL_KEY


def test_dice_mapping_covers_spell_attack():
    assert "spell_attack" in DICE_TEST_TO_CONFIG_SKILL_KEY


def test_dice_mapping_covers_sleight_of_hand():
    assert "sleight_of_hand" in DICE_TEST_TO_CONFIG_SKILL_KEY


# ─── WEAPON RULES — canonical key fallback ───────────────────────────────────


def test_melee_attack_uses_attack_rank_when_legacy_missing():
    """Sheet with 'attack' rank but no 'melee_attack' key → skill_rank == attack rank."""
    sheet = {"stats": {"STR": 14, "DEX": 10}, "skills": {"attack": 2}}
    weapon = {"weapon_type": "melee", "key": "sword", "label": "Miecz"}
    result = resolve_attack_roll_for_weapon(sheet, raw_roll=10, weapon_row=weapon)
    assert result["skill_rank"] == 2, f"Expected 2, got {result['skill_rank']}"


def test_ranged_attack_uses_attack_rank_when_legacy_missing():
    sheet = {"stats": {"DEX": 14, "STR": 10}, "skills": {"attack": 1}}
    weapon = {"weapon_type": "ranged", "key": "bow", "label": "Łuk"}
    result = resolve_attack_roll_for_weapon(sheet, raw_roll=10, weapon_row=weapon)
    assert result["skill_rank"] == 1, f"Expected 1, got {result['skill_rank']}"


def test_spell_attack_uses_arcana_rank_when_legacy_missing():
    sheet = {"stats": {"INT": 16, "STR": 10, "DEX": 10}, "skills": {"arcana": 2}}
    weapon = {"weapon_type": "spell", "key": "magic_bolt", "label": "Kantryp"}
    result = resolve_attack_roll_for_weapon(sheet, raw_roll=10, weapon_row=weapon)
    assert result["skill_rank"] == 2, f"Expected 2, got {result['skill_rank']}"


# ─── Backward compat: legacy key still wins when present ─────────────────────


def test_melee_attack_legacy_key_takes_precedence():
    """Pre-migration sheet: melee_attack rank wins over attack rank."""
    sheet = {"stats": {"STR": 14, "DEX": 10}, "skills": {"melee_attack": 3, "attack": 1}}
    weapon = {"weapon_type": "melee", "key": "sword", "label": "Miecz"}
    result = resolve_attack_roll_for_weapon(sheet, raw_roll=10, weapon_row=weapon)
    assert result["skill_rank"] == 3, f"Expected 3 (legacy wins), got {result['skill_rank']}"


# ─── XP spend strict catalog check ───────────────────────────────────────────


# _skill_known_in_catalog validates against the LIVE game_config_skills table
# (same source as /mechanics/skills the UI reads). Legacy dice-test names were
# removed from that table by #1052, so they stay rejected without any mocking.


def test_xp_catalog_rejects_melee_attack():
    """_skill_known_in_catalog must reject melee_attack — removed from table (#1052)."""
    assert not xp_service._skill_known_in_catalog("melee_attack")


def test_xp_catalog_rejects_ranged_attack():
    assert not xp_service._skill_known_in_catalog("ranged_attack")


def test_xp_catalog_rejects_spell_attack():
    assert not xp_service._skill_known_in_catalog("spell_attack")


def test_xp_catalog_accepts_attack():
    """attack IS in the game_config_skills table → allowed for XP spending."""
    assert xp_service._skill_known_in_catalog("attack")


def test_xp_catalog_accepts_pickpocket():
    assert xp_service._skill_known_in_catalog("pickpocket")
