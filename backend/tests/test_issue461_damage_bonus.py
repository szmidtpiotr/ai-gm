"""TDD: Issue #461 — F1 damage_bonus effect type.

F1a: Add damage_bonus to ALLOWED_EFFECT_JSON_TYPES
F1c: Combat engine reads and applies damage_bonus from weapon effect_json
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


def _schema_sql() -> str:
    """Schema for damage_bonus test (based on test_phase8_combat.py + effect_json)."""
    return """
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
      title TEXT NOT NULL,
      system_id TEXT NOT NULL,
      model_id TEXT NOT NULL,
      owner_user_id INTEGER NOT NULL,
      language TEXT NOT NULL DEFAULT 'pl',
      mode TEXT NOT NULL DEFAULT 'solo',
      status TEXT NOT NULL DEFAULT 'active',
      death_reason TEXT,
      ended_at TEXT,
      epitaph TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (owner_user_id) REFERENCES users(id)
    );
    INSERT INTO campaigns (id, title, system_id, model_id, owner_user_id)
    VALUES (1, 'T', 'fantasy', 'm', 1);

    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      system_id TEXT NOT NULL,
      sheet_json TEXT NOT NULL,
      location TEXT,
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
      FOREIGN KEY (user_id) REFERENCES users(id)
    );
    INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json)
    VALUES (
      1, 1, 1, 'Hero', 'fantasy',
      '{"stats":{"STR":14,"DEX":12,"CON":12,"INT":10,"WIS":10,"CHA":10},"current_hp":20,"max_hp":20,"defense":{"base":15},"equipped_weapon":"bonus_sword"}'
    );

    CREATE TABLE game_config_weapons (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      damage_die TEXT NOT NULL,
      linked_stat TEXT NOT NULL,
      allowed_classes TEXT NOT NULL DEFAULT 'warrior',
      is_active INTEGER NOT NULL DEFAULT 1,
      weapon_type TEXT NOT NULL DEFAULT 'melee',
      two_handed INTEGER NOT NULL DEFAULT 0,
      finesse INTEGER NOT NULL DEFAULT 0,
      range_m INTEGER,
      locked_at TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      effect_json TEXT
    );
    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, effect_json)
    VALUES ('plain_sword', 'Plain Sword', '1d8', 'STR', NULL);
    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, effect_json)
    VALUES (
      'bonus_sword',
      'Bonus Sword',
      '1d8',
      'STR',
      '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":5}]}'
    );

    CREATE TABLE game_config_enemies (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      hp_base INTEGER NOT NULL,
      ac_base INTEGER NOT NULL,
      attack_bonus INTEGER NOT NULL,
      dex_modifier INTEGER NOT NULL DEFAULT 0,
      damage_die TEXT NOT NULL,
      tier TEXT DEFAULT 'standard',
      xp_award INTEGER NOT NULL DEFAULT 0,
      description TEXT,
      is_active INTEGER NOT NULL DEFAULT 1,
      skills_json TEXT,
      locked_at TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      loot_table_key TEXT,
      drop_chance REAL NOT NULL DEFAULT 1.0
    );
    INSERT INTO game_config_enemies
      (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, skills_json, loot_table_key, drop_chance)
    VALUES ('dummy', 'Dummy', 50, 10, 0, 0, '1d4', '{}', NULL, 0.0);

    CREATE TABLE IF NOT EXISTS game_config_meta (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS active_combat (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL UNIQUE,
      character_id INTEGER NOT NULL,
      round INTEGER NOT NULL DEFAULT 1,
      turn_order TEXT NOT NULL,
      current_turn TEXT NOT NULL,
      combatants TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active',
      ended_reason TEXT,
      location_tag TEXT DEFAULT NULL,
      loot_pool TEXT DEFAULT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
      FOREIGN KEY (character_id) REFERENCES characters(id)
    );

    CREATE TABLE IF NOT EXISTS combat_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      combat_id INTEGER NOT NULL,
      campaign_id INTEGER NOT NULL,
      turn_number REAL NOT NULL,
      actor TEXT NOT NULL,
      event_type TEXT NOT NULL,
      roll_value INTEGER,
      damage INTEGER,
      hp_after INTEGER,
      target_id TEXT,
      target_name TEXT,
      hit INTEGER,
      narrative TEXT,
      created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    );
    CREATE INDEX IF NOT EXISTS idx_combat_turns_campaign
      ON combat_turns(campaign_id, turn_number);
    CREATE INDEX IF NOT EXISTS idx_combat_turns_combat
      ON combat_turns(combat_id, turn_number);

    CREATE TABLE IF NOT EXISTS campaign_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      character_id INTEGER NOT NULL,
      user_text TEXT NOT NULL,
      route TEXT NOT NULL,
      assistant_text TEXT,
      turn_number INTEGER NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
      FOREIGN KEY (character_id) REFERENCES characters(id)
    );
    CREATE TABLE IF NOT EXISTS game_sessions (
      id TEXT PRIMARY KEY,
      campaign_id INTEGER NOT NULL,
      session_flags TEXT DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """


class TestDamageBonusEffect(unittest.TestCase):
    """F1 damage_bonus: weapon effect_json adds flat bonus to damage."""

    def setUp(self):
        """Create temp DB with bonus_sword weapon."""
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp_path = self._tmp.name
        self._tmp.close()

        conn = sqlite3.connect(self._tmp_path)
        conn.executescript(_schema_sql())
        conn.close()

        # Patch combat_service to use test DB
        self._p_db = patch.object(cs, "COMBAT_DB_PATH", self._tmp_path)
        self._p_db.start()

    def tearDown(self):
        """Clean up temp DB."""
        self._p_db.stop()
        import os
        if os.path.exists(self._tmp_path):
            os.unlink(self._tmp_path)

    # ─── Test główny ─────────────────────────────────────────────────────────

    @patch("app.services.combat_service.roll_d20", return_value=15)
    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    @patch("app.services.loot_service.roll_loot", return_value=[])
    def test_damage_bonus_adds_to_total_damage(self, _loot, _dmg, _d20):
        """Weapon with damage_bonus:5 → damage = base(5) + bonus(5) = 10."""
        # Character equipped with bonus_sword (effect_json has damage_bonus:5)
        cs.initiate_combat(1, 1, ["dummy"])

        result = cs.resolve_attack(1, 20, attacker="player")

        self.assertTrue(result["hit"], "Attack should hit (roll 15 vs AC 10)")
        # Base damage from mock: 5
        # Expected: 5 + 5 (damage_bonus) = 10
        self.assertEqual(
            result["damage"],
            10,
            "Damage should be base(5) + damage_bonus(5) = 10"
        )

    # ─── Backward compatibility ──────────────────────────────────────────────

    @patch("app.services.combat_service.roll_d20", return_value=15)
    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    @patch("app.services.loot_service.roll_loot", return_value=[])
    def test_weapon_without_effect_json_still_works(self, _loot, _dmg, _d20):
        """Weapon with NULL effect_json → base damage only (no crash)."""
        # Update character to use plain_sword (no effect_json)
        conn = sqlite3.connect(self._tmp_path)
        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = 1",
            (json.dumps({
                "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10},
                "current_hp": 20,
                "max_hp": 20,
                "defense": {"base": 15},
                "equipped_weapon": "plain_sword"
            }),)
        )
        conn.commit()
        conn.close()

        cs.initiate_combat(1, 1, ["dummy"])
        result = cs.resolve_attack(1, 20, attacker="player")

        self.assertTrue(result["hit"])
        self.assertEqual(result["damage"], 5, "Plain weapon → base damage only (5)")


if __name__ == "__main__":
    unittest.main()
