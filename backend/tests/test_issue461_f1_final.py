"""TDD: Issue #461 F1 final — apply_condition on hit, ac_bonus engine, static_stat_modifier engine.

apply_condition (gear_bonus): weapon applies condition to enemy on successful hit
ac_bonus engine: weapon ac_bonus Effect added to player defense at combat-start
static_stat_modifier engine: weapon stat bonus applied to player stats at combat-start
"""
import json
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if "httpx" not in sys.modules:
    from unittest.mock import MagicMock
    sys.modules["httpx"] = MagicMock()

from app.services import combat_service as cs
from app.services.admin_config import validate_effect_json_payload as validate_effect_json


_WEAPON_EFFECTS = {
    "burning_sword": '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"apply_condition","condition_key":"burning","duration_rounds":2}]}',
    "shieldblade": '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"ac_bonus","value":2}]}',
    "strength_sword": '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"static_stat_modifier","stat":"STR","value":2}]}',
    "combo_sword": '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"ac_bonus","value":1},{"type":"static_stat_modifier","stat":"DEX","value":2}]}',
}


def _make_db(
    tmp_path: str,
    weapon_key: str = "burning_sword",
    player_str: int = 14,
    player_base_ac: int = 10,
) -> None:
    import os
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)

    effect_json = _WEAPON_EFFECTS.get(weapon_key, "NULL")
    effect_sql = f"'{effect_json}'" if effect_json != "NULL" else "NULL"
    label = weapon_key.replace("_", " ").title()
    extra_weapon_sql = (
        f"INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, effect_json) "
        f"VALUES ('{weapon_key}', '{label}', '1d8', 'STR', {effect_sql});"
        if weapon_key != "plain_sword" else ""
    )

    sheet = json.dumps({
        "stats": {"STR": player_str, "DEX": 12, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10},
        "current_hp": 20,
        "max_hp": 20,
        "defense": {"base": player_base_ac},
        "equipped_weapon": weapon_key,
    })

    conn = sqlite3.connect(tmp_path)
    conn.executescript(f"""
    CREATE TABLE users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
      display_name TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1, 'u', 'x', 'U');

    CREATE TABLE campaigns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL, system_id TEXT NOT NULL, model_id TEXT NOT NULL,
      owner_user_id INTEGER NOT NULL,
      language TEXT NOT NULL DEFAULT 'pl', mode TEXT NOT NULL DEFAULT 'solo',
      status TEXT NOT NULL DEFAULT 'active',
      death_reason TEXT, ended_at TEXT, epitaph TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (owner_user_id) REFERENCES users(id)
    );
    INSERT INTO campaigns (id, title, system_id, model_id, owner_user_id) VALUES (1, 'T', 'fantasy', 'm', 1);

    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
      name TEXT NOT NULL, system_id TEXT NOT NULL, sheet_json TEXT NOT NULL,
      location TEXT, is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
      FOREIGN KEY (user_id) REFERENCES users(id)
    );
    INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json)
    VALUES (1, 1, 1, 'Hero', 'fantasy', '{sheet}');

    CREATE TABLE game_config_weapons (
      key TEXT PRIMARY KEY, label TEXT NOT NULL,
      damage_die TEXT NOT NULL, linked_stat TEXT NOT NULL,
      allowed_classes TEXT NOT NULL DEFAULT 'warrior',
      is_active INTEGER NOT NULL DEFAULT 1,
      weapon_type TEXT NOT NULL DEFAULT 'melee',
      two_handed INTEGER NOT NULL DEFAULT 0,
      finesse INTEGER NOT NULL DEFAULT 0,
      range_m INTEGER, locked_at TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      effect_json TEXT
    );
    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, effect_json)
    VALUES ('plain_sword', 'Plain Sword', '1d8', 'STR', NULL);
    {extra_weapon_sql}

    CREATE TABLE game_config_enemies (
      key TEXT PRIMARY KEY, label TEXT NOT NULL,
      hp_base INTEGER NOT NULL, ac_base INTEGER NOT NULL,
      attack_bonus INTEGER NOT NULL, dex_modifier INTEGER NOT NULL DEFAULT 0,
      damage_die TEXT NOT NULL, tier TEXT DEFAULT 'standard',
      xp_award INTEGER NOT NULL DEFAULT 0, description TEXT,
      is_active INTEGER NOT NULL DEFAULT 1, skills_json TEXT,
      locked_at TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      loot_table_key TEXT, drop_chance REAL NOT NULL DEFAULT 1.0
    );
    INSERT INTO game_config_enemies
      (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, skills_json, loot_table_key, drop_chance)
    VALUES ('dummy', 'Dummy', 50, 10, 0, 0, '1d4', '{{}}', NULL, 0.0);

    CREATE TABLE IF NOT EXISTS game_config_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

    CREATE TABLE IF NOT EXISTS active_combat (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL UNIQUE, character_id INTEGER NOT NULL,
      round INTEGER NOT NULL DEFAULT 1, turn_order TEXT NOT NULL,
      current_turn TEXT NOT NULL, combatants TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active', ended_reason TEXT,
      location_tag TEXT DEFAULT NULL, loot_pool TEXT DEFAULT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
      FOREIGN KEY (character_id) REFERENCES characters(id)
    );

    CREATE TABLE IF NOT EXISTS combat_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      combat_id INTEGER NOT NULL, campaign_id INTEGER NOT NULL,
      turn_number REAL NOT NULL, actor TEXT NOT NULL,
      event_type TEXT NOT NULL, roll_value INTEGER, damage INTEGER,
      hp_after INTEGER, target_id TEXT, target_name TEXT, hit INTEGER,
      narrative TEXT,
      created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    );
    CREATE INDEX IF NOT EXISTS idx_combat_turns_campaign ON combat_turns(campaign_id, turn_number);
    CREATE INDEX IF NOT EXISTS idx_combat_turns_combat ON combat_turns(combat_id, turn_number);

    CREATE TABLE IF NOT EXISTS campaign_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL, character_id INTEGER NOT NULL,
      user_text TEXT NOT NULL, route TEXT NOT NULL, assistant_text TEXT,
      turn_number INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
      FOREIGN KEY (character_id) REFERENCES characters(id)
    );
    CREATE TABLE IF NOT EXISTS game_sessions (
      id TEXT PRIMARY KEY, campaign_id INTEGER NOT NULL,
      session_flags TEXT DEFAULT '{{}}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.close()


class TestApplyConditionOnHit(unittest.TestCase):
    """F1 apply_condition: weapon applies condition to enemy on hit."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp_path = self._tmp.name
        self._tmp.close()
        _make_db(self._tmp_path, weapon_key="burning_sword")
        self._p_db = patch.object(cs, "COMBAT_DB_PATH", self._tmp_path)
        self._p_db.start()

    def tearDown(self):
        self._p_db.stop()
        import os
        if os.path.exists(self._tmp_path):
            os.unlink(self._tmp_path)

    # ─── Test główny ─────────────────────────────────────────────────────────

    @patch("app.services.combat_service.roll_d20", return_value=15)
    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    @patch("app.services.loot_service.roll_loot", return_value=[])
    def test_apply_condition_on_weapon_hit(self, _loot, _dmg, _d20):
        """Weapon apply_condition:burning → enemy gets burning condition after hit."""
        cs.initiate_combat(1, 1, ["dummy"])
        result = cs.resolve_attack(1, 20, attacker="player")

        self.assertTrue(result["hit"])
        applied = result.get("weapon_conditions_applied") or []
        self.assertIn("burning", applied, f"burning should be applied; got {applied}")

        # Verify in combat_state combatants
        enemy = next(
            c for c in result["combat_state"]["combatants"] if c.get("type") == "enemy"
        )
        cond_keys = [c.get("key") for c in (enemy.get("conditions") or [])]
        self.assertIn("burning", cond_keys, f"burning missing from enemy conditions: {cond_keys}")

    @patch("app.services.combat_service.roll_d20", return_value=15)
    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    @patch("app.services.loot_service.roll_loot", return_value=[])
    def test_apply_condition_no_duplicate(self, _loot, _dmg, _d20):
        """Weapon apply_condition: enemy already has burning → not duplicated."""
        cs.initiate_combat(1, 1, ["dummy"])

        # Pre-add burning to enemy combatant
        conn = sqlite3.connect(self._tmp_path)
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        combatants = json.loads(row[0])
        for c in combatants:
            if c.get("type") == "enemy":
                c.setdefault("conditions", []).append({
                    "key": "burning", "label": "Burning",
                    "duration_rounds": 3, "runtime": {},
                })
        conn.execute("UPDATE active_combat SET combatants=? WHERE campaign_id=1",
                     (json.dumps(combatants),))
        conn.commit()
        conn.close()

        result = cs.resolve_attack(1, 20, attacker="player")
        self.assertTrue(result["hit"])

        enemy = next(
            c for c in result["combat_state"]["combatants"] if c.get("type") == "enemy"
        )
        burning_count = sum(1 for c in (enemy.get("conditions") or []) if c.get("key") == "burning")
        self.assertEqual(burning_count, 1, "burning should appear exactly once (no duplicate)")

    # ─── Backward compatibility ──────────────────────────────────────────────

    @patch("app.services.combat_service.roll_d20", return_value=15)
    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    @patch("app.services.loot_service.roll_loot", return_value=[])
    def test_no_apply_condition_weapon_unchanged(self, _loot, _dmg, _d20):
        """Plain weapon with NULL effect_json → no conditions applied, no crash."""
        _make_db(self._tmp_path, weapon_key="plain_sword")
        cs.initiate_combat(1, 1, ["dummy"])
        result = cs.resolve_attack(1, 20, attacker="player")

        self.assertTrue(result["hit"])
        applied = result.get("weapon_conditions_applied") or []
        self.assertNotIn("burning", applied)


class TestAcBonusAtCombatStart(unittest.TestCase):
    """F1 ac_bonus engine: weapon ac_bonus Effect Object added to player defense at combat-start."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp_path = self._tmp.name
        self._tmp.close()
        self._p_db = patch.object(cs, "COMBAT_DB_PATH", self._tmp_path)
        self._p_db.start()

    def tearDown(self):
        self._p_db.stop()
        import os
        if os.path.exists(self._tmp_path):
            os.unlink(self._tmp_path)

    # ─── Test główny ─────────────────────────────────────────────────────────

    @patch("app.services.combat_service.roll_d20", return_value=5)
    def test_ac_bonus_added_at_combat_start(self, _d20):
        """Weapon ac_bonus:2, base AC 10 → combatant defense = 12 after initiate_combat."""
        _make_db(self._tmp_path, weapon_key="shieldblade", player_base_ac=10)
        cs.initiate_combat(1, 1, ["dummy"])

        conn = sqlite3.connect(self._tmp_path)
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        conn.close()
        combatants = json.loads(row[0])
        player = next(c for c in combatants if c["type"] == "player")
        self.assertEqual(player["defense"], 12, "AC 10 + ac_bonus 2 should equal 12")

    @patch("app.services.combat_service.roll_d20", return_value=5)
    def test_no_ac_bonus_defense_unchanged(self, _d20):
        """Plain weapon → player defense equals base AC, no change."""
        _make_db(self._tmp_path, weapon_key="plain_sword", player_base_ac=10)
        cs.initiate_combat(1, 1, ["dummy"])

        conn = sqlite3.connect(self._tmp_path)
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        conn.close()
        combatants = json.loads(row[0])
        player = next(c for c in combatants if c["type"] == "player")
        self.assertEqual(player["defense"], 10, "Without ac_bonus weapon, defense = base 10")


class TestStatModifierAtCombatStart(unittest.TestCase):
    """F1 static_stat_modifier engine: weapon stat bonus applied to combatant stats at combat-start."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp_path = self._tmp.name
        self._tmp.close()
        self._p_db = patch.object(cs, "COMBAT_DB_PATH", self._tmp_path)
        self._p_db.start()

    def tearDown(self):
        self._p_db.stop()
        import os
        if os.path.exists(self._tmp_path):
            os.unlink(self._tmp_path)

    @patch("app.services.combat_service.roll_d20", return_value=5)
    def test_stat_modifier_applied_at_combat_start(self, _d20):
        """Weapon static_stat_modifier STR+2, base STR 14 → combatant stats.STR = 16."""
        _make_db(self._tmp_path, weapon_key="strength_sword", player_str=14)
        cs.initiate_combat(1, 1, ["dummy"])

        conn = sqlite3.connect(self._tmp_path)
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        conn.close()
        combatants = json.loads(row[0])
        player = next(c for c in combatants if c["type"] == "player")
        str_in_combat = player["stats"]["STR"]
        self.assertEqual(str_in_combat, 16, f"STR 14 + modifier 2 should be 16; got {str_in_combat}")

    @patch("app.services.combat_service.roll_d20", return_value=5)
    def test_multiple_stat_modifiers_stacked(self, _d20):
        """Weapon combo_sword: ac_bonus:1 + static_stat_modifier DEX+2 → both applied."""
        _make_db(self._tmp_path, weapon_key="combo_sword", player_base_ac=10)
        cs.initiate_combat(1, 1, ["dummy"])

        conn = sqlite3.connect(self._tmp_path)
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        conn.close()
        combatants = json.loads(row[0])
        player = next(c for c in combatants if c["type"] == "player")
        self.assertEqual(player["defense"], 11, "AC 10 + ac_bonus 1 = 11")
        self.assertEqual(player["stats"]["DEX"], 14, "DEX 12 + modifier 2 = 14")

    @patch("app.services.combat_service.roll_d20", return_value=5)
    def test_no_stat_modifier_stats_unchanged(self, _d20):
        """Plain weapon → player stats unchanged (STR stays base)."""
        _make_db(self._tmp_path, weapon_key="plain_sword", player_str=14)
        cs.initiate_combat(1, 1, ["dummy"])

        conn = sqlite3.connect(self._tmp_path)
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        conn.close()
        combatants = json.loads(row[0])
        player = next(c for c in combatants if c["type"] == "player")
        self.assertEqual(player["stats"]["STR"], 14, "Without modifier, STR stays at base 14")


class TestApplyConditionSchema(unittest.TestCase):
    """Schema: apply_condition valid in gear_bonus category for weapons."""

    def test_apply_condition_gear_bonus_valid(self):
        """gear_bonus + apply_condition with condition_key is valid."""
        obj = {
            "schema_version": 1,
            "effect_category": "gear_bonus",
            "effects": [{"type": "apply_condition", "condition_key": "burning", "duration_rounds": 2}],
        }
        errors = validate_effect_json(obj)
        self.assertEqual(errors, [], f"apply_condition gear_bonus should be valid; errors: {errors}")

    def test_apply_condition_gear_bonus_missing_key_rejected(self):
        """gear_bonus + apply_condition without condition_key is rejected."""
        obj = {
            "schema_version": 1,
            "effect_category": "gear_bonus",
            "effects": [{"type": "apply_condition"}],
        }
        errors = validate_effect_json(obj)
        self.assertGreater(len(errors), 0, "Missing condition_key should produce error")


if __name__ == "__main__":
    unittest.main()
