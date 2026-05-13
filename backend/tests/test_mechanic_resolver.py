"""
Tests for Mechanic Resolver — V2 Phase 04 Task 11
"""
import pytest
from app.services.mechanic_resolver import (
    resolve, stat_modifier, parse_dice, roll_d20, roll_die
)


class TestStatModifier:
    def test_10_is_zero(self): assert stat_modifier(10) == 0
    def test_12_is_plus1(self): assert stat_modifier(12) == 1
    def test_8_is_minus1(self): assert stat_modifier(8) == -1
    def test_18_is_plus4(self): assert stat_modifier(18) == 4


class TestParseDice:
    def test_flat_number(self): assert parse_dice("5") == 5
    def test_d6(self):
        for _ in range(20):
            r = parse_dice("d6")
            assert 1 <= r <= 6
    def test_2d6_plus2(self):
        for _ in range(20):
            r = parse_dice("2d6+2")
            assert 4 <= r <= 14
    def test_invalid_returns_zero(self): assert parse_dice("garbage") == 0


class TestResolveAttack:
    def _ctx(self, str_val=12, combat_rank=2, target_hp=20, ac=12):
        return {
            "character_sheet": {"stats": {"STR": str_val, "DEX": 10}, "skills": {"combat": combat_rank}},
            "target_enemy": {"label": "Goblin", "hp": target_hp, "hp_base": target_hp, "ac_base": ac},
            "equipped_weapon": {"damage_die": "d6", "linked_stat": "STR", "weapon_type": "melee"},
        }

    def test_high_roll_hits(self):
        import unittest.mock as mock
        with mock.patch("app.services.mechanic_resolver.roll_d20", return_value=18):
            result = resolve("ATTACK", {"target": "goblin_1"}, self._ctx())
        assert result["hit"] is True
        assert result["outcome"] in ("SUCCESS", "CRITICAL_SUCCESS")

    def test_low_roll_misses(self):
        import unittest.mock as mock
        with mock.patch("app.services.mechanic_resolver.roll_d20", return_value=1):
            result = resolve("ATTACK", {"target": "goblin_1"}, self._ctx(ac=20))
        assert result["hit"] is False
        assert result["outcome"] == "CRITICAL_FAILURE"

    def test_nat20_always_crits(self):
        import unittest.mock as mock
        with mock.patch("app.services.mechanic_resolver.roll_d20", return_value=20):
            result = resolve("ATTACK", {"target": "goblin_1"}, self._ctx(ac=30))
        assert result["nat20"] is True
        assert result["crit"] is True
        assert result["damage"] > 0

    def test_target_death_flag(self):
        import unittest.mock as mock
        with mock.patch("app.services.mechanic_resolver.roll_d20", return_value=20):
            with mock.patch("app.services.mechanic_resolver.parse_dice", return_value=10):
                result = resolve("ATTACK", {"target": "goblin_1"}, self._ctx(target_hp=5))
        if result["hit"]:
            assert result["target_dead"] is True


class TestResolveSkill:
    def _ctx(self, skill_rank=2, stat=12, dc=12):
        return {
            "character_sheet": {"stats": {"DEX": stat, "INT": 10, "WIS": 10}, "skills": {"stealth": skill_rank}},
            "skill_counter": {"dc": dc},
        }

    def test_success_path(self):
        import unittest.mock as mock
        with mock.patch("app.services.mechanic_resolver.roll_d20", return_value=15):
            result = resolve("SKILL_ATTEMPT", {"skill_key": "stealth"}, self._ctx())
        assert result["outcome"] in ("SUCCESS", "CRITICAL_SUCCESS")

    def test_failure_path(self):
        import unittest.mock as mock
        with mock.patch("app.services.mechanic_resolver.roll_d20", return_value=1):
            result = resolve("SKILL_ATTEMPT", {"skill_key": "stealth"}, self._ctx(dc=20))
        assert result["outcome"] == "CRITICAL_FAILURE"


class TestResolveRest:
    def test_long_rest_full_hp(self):
        ctx = {
            "character_sheet": {
                "stats": {"CON": 12}, "archetype": "warrior",
                "current_hp": 5, "max_hp": 12,
                "current_mana": 0, "max_mana": 0
            }
        }
        result = resolve("REST", {"rest_type": "long"}, ctx)
        assert result["hp_after"] == 12
        assert result["outcome"] == "SUCCESS"

    def test_short_rest_partial_heal(self):
        ctx = {
            "character_sheet": {
                "stats": {"CON": 12}, "archetype": "warrior",
                "current_hp": 3, "max_hp": 12,
                "current_mana": 0, "max_mana": 0
            }
        }
        result = resolve("REST", {"rest_type": "short"}, ctx)
        assert result["hp_after"] > result["hp_before"]
        assert result["hp_after"] <= 12


class TestResolveMovement:
    def test_movement_success(self):
        ctx = {
            "location": {"key": "loc_tavern", "label": "Karczma"},
            "destination_location": {"key": "loc_alley", "label": "Uliczka"},
        }
        result = resolve("MOVEMENT", {"destination_key": "loc_alley"}, ctx)
        assert result["outcome"] == "SUCCESS"
        assert result["to_location_key"] == "loc_alley"


class TestResolveDialogue:
    def test_keyword_trigger_fires(self):
        import json
        ctx = {
            "target_npc": {
                "label": "Boris",
                "keyword_triggers": json.dumps([
                    {"keyword": "guild", "must_reveal_info": "Gilda przy dokach.", "is_secret": False}
                ])
            }
        }
        result = resolve("DIALOGUE", {"npc_key": "boris", "topic": "guild meeting"}, ctx)
        assert result["outcome"] == "SUCCESS"
        assert result["must_reveal_info"] == "Gilda przy dokach."
        assert result["is_secret"] is False

    def test_no_keyword_match(self):
        ctx = {"target_npc": {"label": "Boris", "keyword_triggers": "[]"}}
        result = resolve("DIALOGUE", {"npc_key": "boris", "topic": "weather"}, ctx)
        assert result["must_reveal_info"] is None


class TestResolveGeneric:
    def test_unknown_action_returns_description(self):
        result = resolve("LOOK_AROUND", {}, {})
        assert result["outcome"] == "DESCRIPTION"
        assert result["action_type"] == "LOOK_AROUND"
