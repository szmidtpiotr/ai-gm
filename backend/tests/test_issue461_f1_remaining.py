"""TDD: Issue #461 F1 — remaining Effect types.

heal_on_hit  : weapon restores player HP after successful hit (life-steal)
ac_bonus     : schema registration only — engine support deferred to combat-start slice
F1b backward : old-format effect_json ({'type':'extra_damage'}) still works via _apply_weapon_effects;
               F1 helpers (_weapon_effects_of_type) ignore it safely
"""
import json
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _fixtures_schema as fx

if "httpx" not in sys.modules:
    from unittest.mock import MagicMock
    sys.modules["httpx"] = MagicMock()

from app.services import combat_service as cs
from app.services.admin_config import validate_effect_json_payload as validate_effect_json


_WEAPONS = {
    "lifesteal_sword": (
        "lifesteal_sword", "Lifesteal Sword", "1d8", "STR",
        '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"heal_on_hit","value":3}]}'
    ),
    "big_lifesteal_sword": (
        "big_lifesteal_sword", "Big Lifesteal Sword", "1d8", "STR",
        '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"heal_on_hit","value":5}]}'
    ),
    "oldformat_sword": (
        "oldformat_sword", "Old Format Sword", "1d8", "STR",
        '{"effects":[{"type":"extra_damage","dice":"1d6","damage_type":"fire"}]}'
    ),
}


def _make_db(tmp_path: str, player_current_hp: int = 8, player_max_hp: int = 10, weapon_key: str = "lifesteal_sword") -> None:
    import os
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    sheet = json.dumps({
        "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10},
        "current_hp": player_current_hp,
        "max_hp": player_max_hp,
        "defense": {"base": 15},
        "equipped_weapon": weapon_key,
    })
    w = _WEAPONS.get(weapon_key)
    weapon_insert = (
        f"INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, effect_json) "
        f"VALUES ('{w[0]}', '{w[1]}', '{w[2]}', '{w[3]}', '{w[4]}');"
        if w else ""
    )

    conn = sqlite3.connect(tmp_path)
    fx.create_tables(conn, 'game_config_weapons', 'game_config_enemies', 'game_config_meta')
    conn.executescript(f"""
    CREATE TABLE users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
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

    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, effect_json)
    VALUES ('plain_sword', 'Plain Sword', '1d8', 'STR', NULL);
    {weapon_insert}

    INSERT INTO game_config_enemies
      (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, skills_json, loot_table_key, drop_chance)
    VALUES ('dummy', 'Dummy', 50, 10, 0, 0, '1d4', '{{}}', NULL, 0.0);

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


class TestHealOnHit(unittest.TestCase):
    """F1 heal_on_hit: weapon Effect Object heals attacker on successful hit."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp_path = self._tmp.name
        self._tmp.close()
        _make_db(self._tmp_path, player_current_hp=8, player_max_hp=10, weapon_key="lifesteal_sword")
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
    def test_heal_on_hit_restores_player_hp(self, _loot, _dmg, _d20):
        """Weapon heal_on_hit:3, player 8/10 HP → after hit player at 10 (capped), out['heal_on_hit']==3."""
        cs.initiate_combat(1, 1, ["dummy"])
        result = cs.resolve_attack(1, 20, attacker="player")

        self.assertTrue(result["hit"], "Attack should hit (roll 20 vs dodge 15)")
        self.assertEqual(result.get("heal_on_hit"), 3, "heal_on_hit should be 3")

        # Verify combatant HP updated (8 + 3 = 11 → capped at max 10)
        player = next(
            c for c in result["combat_state"]["combatants"] if c["type"] == "player"
        )
        self.assertEqual(player["hp_current"], 10, "Player HP should be capped at max_hp=10")

    @patch("app.services.combat_service.roll_d20", return_value=15)
    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    @patch("app.services.loot_service.roll_loot", return_value=[])
    def test_heal_on_hit_capped_at_max_hp(self, _loot, _dmg, _d20):
        """heal_on_hit:5, player 9/10 → capped at 10, not 14."""
        # Switch to big lifesteal sword (heal_on_hit:5), player at 9/10
        _make_db(self._tmp_path, player_current_hp=9, player_max_hp=10, weapon_key="big_lifesteal_sword")

        cs.initiate_combat(1, 1, ["dummy"])
        result = cs.resolve_attack(1, 20, attacker="player")

        self.assertTrue(result["hit"])
        self.assertEqual(result.get("heal_on_hit"), 5)
        player = next(c for c in result["combat_state"]["combatants"] if c["type"] == "player")
        self.assertEqual(player["hp_current"], 10, "9 + 5 = 14 → capped at max 10")

    # ─── Backward compatibility ──────────────────────────────────────────────

    @patch("app.services.combat_service.roll_d20", return_value=15)
    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    @patch("app.services.loot_service.roll_loot", return_value=[])
    def test_weapon_without_heal_on_hit_hp_unchanged(self, _loot, _dmg, _d20):
        """Weapon with NULL effect_json → no heal, player HP unchanged after hit."""
        _make_db(self._tmp_path, player_current_hp=8, player_max_hp=10, weapon_key="plain_sword")

        cs.initiate_combat(1, 1, ["dummy"])
        result = cs.resolve_attack(1, 20, attacker="player")

        self.assertTrue(result["hit"])
        self.assertIsNone(result.get("heal_on_hit"), "No heal_on_hit in output for plain weapon")
        player = next(c for c in result["combat_state"]["combatants"] if c["type"] == "player")
        self.assertEqual(player["hp_current"], 8, "Player HP unchanged without heal_on_hit")


class TestF1bBackwardCompat(unittest.TestCase):
    """F1b: old-format effect_json still works; F1 helpers ignore unknown types safely."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp_path = self._tmp.name
        self._tmp.close()
        _make_db(self._tmp_path, player_current_hp=20, player_max_hp=20, weapon_key="oldformat_sword")
        self._p_db = patch.object(cs, "COMBAT_DB_PATH", self._tmp_path)
        self._p_db.start()

    def tearDown(self):
        self._p_db.stop()
        import os
        if os.path.exists(self._tmp_path):
            os.unlink(self._tmp_path)

    @patch("app.services.combat_service.roll_d20", return_value=15)
    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    @patch("app.services.loot_service.roll_loot", return_value=[])
    def test_old_format_effect_json_no_crash(self, _loot, _dmg, _d20):
        """F1b: old-format effect_json (no schema_version) → F1 helpers return 0, no crash."""
        cs.initiate_combat(1, 1, ["dummy"])
        result = cs.resolve_attack(1, 20, attacker="player")

        # No crash, hit works
        self.assertTrue(result["hit"])
        # F1 helpers (damage_bonus, heal_on_hit) return nothing — old format not typed
        self.assertIsNone(result.get("damage_bonus"), "Old-format has no typed damage_bonus")
        self.assertIsNone(result.get("heal_on_hit"), "Old-format has no typed heal_on_hit")
        # Damage is base (5) only — old engine extra_damage is separate path
        self.assertGreaterEqual(result["damage"], 5, "Base damage should be present")


class TestEffectSchemaRegistration(unittest.TestCase):
    """F1a schema: heal_on_hit and ac_bonus are valid registered types."""

    def test_heal_on_hit_accepted_by_schema(self):
        """validate_effect_json accepts gear_bonus / heal_on_hit with numeric value."""
        obj = {
            "schema_version": 1,
            "effect_category": "gear_bonus",
            "effects": [{"type": "heal_on_hit", "value": 3}],
        }
        errors = validate_effect_json(obj)
        self.assertEqual(errors, [], f"heal_on_hit should be valid; errors: {errors}")

    def test_ac_bonus_accepted_by_schema(self):
        """validate_effect_json accepts gear_bonus / ac_bonus with numeric value."""
        obj = {
            "schema_version": 1,
            "effect_category": "gear_bonus",
            "effects": [{"type": "ac_bonus", "value": 2}],
        }
        errors = validate_effect_json(obj)
        self.assertEqual(errors, [], f"ac_bonus should be valid; errors: {errors}")

    def test_unknown_type_rejected(self):
        """Unknown effect type outside registered enum is rejected."""
        obj = {
            "schema_version": 1,
            "effect_category": "gear_bonus",
            "effects": [{"type": "invent_random_type", "value": 99}],
        }
        errors = validate_effect_json(obj)
        self.assertGreater(len(errors), 0, "Unknown type should produce validation errors")

    def test_heal_on_hit_requires_numeric_value(self):
        """heal_on_hit with non-numeric value is rejected."""
        obj = {
            "schema_version": 1,
            "effect_category": "gear_bonus",
            "effects": [{"type": "heal_on_hit", "value": "three"}],
        }
        errors = validate_effect_json(obj)
        self.assertGreater(len(errors), 0, "Non-numeric heal_on_hit value should be rejected")


if __name__ == "__main__":
    unittest.main()
