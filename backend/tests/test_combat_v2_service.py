"""
Tests for Combat V2 Service — Phase 05 Tasks 14-19
"""
from _fixtures_schema import table_sql
import json
import sqlite3
import pytest
from unittest.mock import patch

from app.services.combat_v2_service import (
    check_critical_hit, resolve_crit_location, get_death_save_dc,
    resolve_death_save_v2, resolve_flee, resolve_enemy_action,
    check_fear_trigger, resolve_fear_save,
    CRIT_THRESHOLD, DEATH_SAVE_DC_LADDER, HIT_LOCATION_TABLE,
    PLAYER_CRIT_CONDITIONS, ENEMY_CRIT_CONDITIONS,
)
from app.services.solo_death_service import (
    apply_death_save_outcome, get_v2_death_save_dc
)


# ── DB Fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, sheet_json TEXT DEFAULT '{}'
        );
        """ + table_sql("game_config_enemies") + """
        CREATE TABLE enemy_behavior_profiles (
            enemy_key TEXT PRIMARY KEY,
            default_action TEXT DEFAULT 'attack_player',
            hp_threshold_flee REAL DEFAULT 0,
            special_ability_key TEXT,
            special_ability_cooldown_turns INTEGER DEFAULT 3,
            dialogue_on_aggro TEXT DEFAULT '',
            dialogue_on_death TEXT DEFAULT '',
            fear_aura INTEGER DEFAULT 0,
            fear_dc INTEGER DEFAULT 12
        );
        CREATE TABLE character_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, condition_type TEXT,
            severity INTEGER DEFAULT 1,
            rounds_remaining INTEGER,
            expires_at TEXT, source TEXT DEFAULT ''
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, item_key TEXT,
            weapon_key TEXT, equipped INTEGER DEFAULT 0
        );
        """ + table_sql("game_config_items") + """
        CREATE TABLE active_combat (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER, status TEXT DEFAULT 'active',
            combatants TEXT DEFAULT '[]', turn_order TEXT DEFAULT '[]',
            round INTEGER DEFAULT 1
        );

        INSERT INTO characters VALUES (1, '{"stats":{"DEX":12,"STR":14,"CON":10},"current_hp":12,"max_hp":12}');
        INSERT INTO game_config_enemies (key, label, dex_modifier, attack_bonus, damage_die, damage_bonus, fear_aura, fear_dc) VALUES ('goblin', 'Goblin', 1, 2, '1d6', 0, 0, 12);
        INSERT INTO game_config_enemies (key, label, dex_modifier, attack_bonus, damage_die, damage_bonus, fear_aura, fear_dc) VALUES ('vampire', 'Vampire', 2, 4, '1d8', 2, 1, 16);
        INSERT INTO enemy_behavior_profiles VALUES ('goblin','attack_player',25,NULL,3,'','',0,0);
        INSERT INTO enemy_behavior_profiles VALUES ('vampire','attack_player',0,'drain_life',3,'','',1,16);
    """)
    conn.commit()
    yield conn
    conn.close()


# ── TASK_17: Critical Hits ────────────────────────────────────────────────

class TestCriticalHits:
    def test_nat20_always_crits(self):
        assert check_critical_hit(10, 20, 20) is True  # would miss but nat20

    def test_threshold_met(self):
        assert check_critical_hit(17, 12, 15) is True   # 17 - 12 = 5 >= threshold
        assert check_critical_hit(16, 12, 14) is False  # 16 - 12 = 4 < threshold

    def test_exact_threshold(self):
        assert check_critical_hit(17, 12, 15) is True   # exactly CRIT_THRESHOLD

    def test_crit_location_valid(self):
        for _ in range(50):
            result = resolve_crit_location(is_player_target=True)
            assert result["location"] in HIT_LOCATION_TABLE.values()
            assert result["condition_type"] in ("dazed", "winded", "arm_wound", "leg_wound")
            assert result["d6_roll"] in range(1, 7)

    def test_player_target_conditions(self):
        locations = set()
        for _ in range(100):
            r = resolve_crit_location(is_player_target=True)
            locations.add(r["location"])
            assert r["condition_type"] in ("dazed", "winded", "arm_wound", "leg_wound")
        # Should see multiple locations over 100 rolls
        assert len(locations) > 1

    def test_enemy_target_conditions(self):
        for _ in range(50):
            r = resolve_crit_location(is_player_target=False)
            assert r["condition_type"] in ("stunned", "bleeding", "disarmed", "hobbled")


# ── TASK_18: Death Save DC Ladder ────────────────────────────────────────

class TestDeathSaveDC:
    def test_ladder_values(self):
        assert get_death_save_dc(1) == 10
        assert get_death_save_dc(2) == 13
        assert get_death_save_dc(3) == 16
        assert get_death_save_dc(4) == 19

    def test_ladder_caps_at_19(self):
        assert get_death_save_dc(5) == 19
        assert get_death_save_dc(99) == 19

    def test_v2_dc_consistency(self):
        assert get_death_save_dc(1) == get_v2_death_save_dc(1)
        assert get_death_save_dc(4) == get_v2_death_save_dc(4)


class TestDeathSaveV2:
    def test_success_survives(self, db):
        result = resolve_death_save_v2(
            character_id=1, d20_roll=15,
            death_save_count=1, current_failure_count=0, conn=db
        )
        assert result["outcome"] == "SURVIVED"
        assert result["roll"] == 15
        assert result["dc"] == 10
        assert result["hp_restored"] == 1

    def test_failure_accumulates(self, db):
        result = resolve_death_save_v2(
            character_id=1, d20_roll=5,
            death_save_count=1, current_failure_count=0, conn=db
        )
        assert result["outcome"] == "FAILED"
        assert result["failures_added"] == 1
        assert result["total_failures"] == 1

    def test_nat1_adds_two_failures(self, db):
        result = resolve_death_save_v2(
            character_id=1, d20_roll=1,
            death_save_count=1, current_failure_count=0, conn=db
        )
        assert result["nat1"] is True
        assert result["failures_added"] == 2

    def test_three_failures_kills(self, db):
        result = resolve_death_save_v2(
            character_id=1, d20_roll=5,
            death_save_count=1, current_failure_count=2, conn=db
        )
        assert result["dead"] is True
        assert result["outcome"] == "DEAD"

    def test_escalating_dc(self, db):
        # 2nd 0-HP: DC 13, so roll 11 fails
        result = resolve_death_save_v2(
            character_id=1, d20_roll=11,
            death_save_count=2, current_failure_count=0, conn=db
        )
        assert result["dc"] == 13
        assert result["outcome"] == "FAILED"

    def test_nat20_always_survives(self, db):
        result = resolve_death_save_v2(
            character_id=1, d20_roll=20,
            death_save_count=4, current_failure_count=2, conn=db
        )
        assert result["nat20"] is True
        assert result["outcome"] == "SURVIVED"


# ── Updated solo_death_service ─────────────────────────────────────────────

class TestApplyDeathSaveOutcomeV2:
    def test_v2_uses_escalating_dc(self):
        sheet = {"death_save_count": 2, "death_save_failures": 0}
        roll = {"test": "death_save", "total": 11, "is_nat20": False, "is_nat1": False}
        updated, died = apply_death_save_outcome(sheet, roll)
        # DC for count=2 is 13, roll 11 < 13 → fail
        assert updated["death_save_failures"] == 1
        assert died is False

    def test_v2_success_at_escalated_dc(self):
        sheet = {"death_save_count": 3, "death_save_failures": 1}
        roll = {"test": "death_save", "total": 16, "is_nat20": False, "is_nat1": False}
        updated, died = apply_death_save_outcome(sheet, roll)
        # DC for count=3 is 16, roll 16 >= 16 → success
        assert died is False


# ── TASK_16: Fear & Terror ────────────────────────────────────────────────

class TestFearSystem:
    def test_non_fear_enemy_no_trigger(self, db):
        result = check_fear_trigger("goblin", 1, 1, db)
        assert result is None

    def test_fear_enemy_triggers(self, db):
        result = check_fear_trigger("vampire", 1, 1, db)
        assert result is not None
        assert result["fear_dc"] == 16
        assert result["pending"] is True

    def test_fear_success(self, db):
        result = resolve_fear_save(1, 18, 16, 1, db)
        assert result["outcome"] == "SUCCESS"
        assert result["condition_applied"] is None

    def test_fear_failure_applies_condition(self, db):
        result = resolve_fear_save(1, 5, 16, 1, db)
        assert result["outcome"] == "FAILURE"
        assert result["condition_applied"] == "fear_shaken"
        # Check DB
        row = db.execute(
            "SELECT condition_type FROM character_conditions WHERE character_id = 1"
        ).fetchone()
        assert row and row[0] == "fear_shaken"

    def test_nat1_escalates_to_terror(self, db):
        result = resolve_fear_save(1, 1, 12, 1, db)
        assert result["nat1"] is True
        assert result["condition_applied"] == "terror"


# ── TASK_15: Enemy Behavior Profiles ─────────────────────────────────────

class TestEnemyBehavior:
    def _enemy(self, hp=12, hp_max=12, key="goblin"):
        return {"id": f"{key}_1", "key": key, "template_key": key,
                "hp": hp, "hp_max": hp_max, "name": "Goblin"}

    def test_default_attack_action(self, db):
        profile = {"default_action": "attack_player", "hp_threshold_flee": 0}
        action = resolve_enemy_action(self._enemy(), profile, {})
        assert action["action"] == "attack"

    def test_flee_threshold_triggers(self, db):
        # hp=3, hp_max=12 → 25%, threshold=25 → flee
        profile = {"default_action": "attack_player", "hp_threshold_flee": 25}
        action = resolve_enemy_action(self._enemy(hp=3, hp_max=12), profile, {})
        assert action["action"] == "flee"

    def test_flee_not_triggered_above_threshold(self, db):
        # hp=6, hp_max=12 → 50%, threshold=25 → no flee
        profile = {"default_action": "attack_player", "hp_threshold_flee": 25}
        action = resolve_enemy_action(self._enemy(hp=6, hp_max=12), profile, {})
        assert action["action"] == "attack"

    def test_no_profile_defaults_to_attack(self, db):
        action = resolve_enemy_action(self._enemy(), None, {})
        assert action["action"] == "attack"

    def test_special_ability_on_cooldown_falls_back(self, db):
        enemy = {**self._enemy(), "special_ability_cooldown_remaining": 2}
        profile = {"default_action": "use_special", "hp_threshold_flee": 0,
                   "special_ability_key": "throw_rock"}
        action = resolve_enemy_action(enemy, profile, {})
        assert action["action"] == "attack"
        assert action["data"].get("cooldown_fallback") is True


# ── TASK_19: Flee Mechanic ────────────────────────────────────────────────

class TestFleeMechanic:
    def test_player_high_dex_flees(self, db):
        db.execute("INSERT INTO active_combat (campaign_id, combatants) VALUES (1, ?)",
                   (json.dumps([{"id": "goblin_1", "key": "goblin", "template_key": "goblin",
                                 "hp": 8, "type": "enemy"}]),))
        db.commit()
        with patch("app.services.combat_v2_service._d20", side_effect=[20, 5]):
            result = resolve_flee(1, 1, db)
        assert result["fled"] is True
        assert result["outcome"] == "SUCCESS"

    def test_player_low_roll_fails(self, db):
        db.execute("INSERT INTO active_combat (campaign_id, combatants) VALUES (1, ?)",
                   (json.dumps([{"id": "goblin_1", "key": "goblin", "template_key": "goblin",
                                 "hp": 8, "type": "enemy"}]),))
        db.commit()
        with patch("app.services.combat_v2_service._d20", side_effect=[3, 15]):
            result = resolve_flee(1, 1, db)
        assert result["fled"] is False
        assert result["outcome"] == "FAILURE"

    def test_tie_goes_to_enemy(self, db):
        db.execute("INSERT INTO active_combat (campaign_id, combatants) VALUES (2, ?)",
                   (json.dumps([{"id": "goblin_1", "template_key": "goblin",
                                 "hp": 8, "type": "enemy"}]),))
        db.commit()
        # Player DEX 12 mod+1, goblin DEX mod+1 → same modifier
        with patch("app.services.combat_v2_service._d20", side_effect=[10, 10]):
            result = resolve_flee(2, 1, db)
        assert result["fled"] is False  # tie → enemy wins
