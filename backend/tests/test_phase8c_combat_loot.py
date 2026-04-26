"""Phase 8C-4 — combat to loot_service integration."""

import json
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import combat_service as cs
from app.services import loot_service as ls


def _schema_sql() -> str:
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
      1, 1, 1, 'Aldric', 'fantasy',
      '{"stats":{"STR":14,"DEX":12,"CON":12,"INT":10,"WIS":10,"CHA":10},"current_hp":20,"max_hp":20,"defense":{"base":15},"equipped_weapon":"sword_iron"}'
    );

    CREATE TABLE game_config_weapons (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      damage_die TEXT NOT NULL,
      linked_stat TEXT NOT NULL,
      allowed_classes TEXT NOT NULL DEFAULT 'warrior',
      is_active INTEGER NOT NULL DEFAULT 1,
      locked_at TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, allowed_classes, is_active)
    VALUES ('sword_iron', 'Iron Sword', '1d8', 'STR', 'warrior', 1);

    CREATE TABLE game_config_items (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      item_type TEXT NOT NULL DEFAULT 'misc',
      description TEXT NOT NULL DEFAULT '',
      value_gp INTEGER NOT NULL DEFAULT 0,
      weight REAL NOT NULL DEFAULT 0.0,
      weight_kg REAL NOT NULL DEFAULT 0.0,
      effect_json TEXT,
      is_active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE game_config_consumables (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      description TEXT NOT NULL DEFAULT '',
      effect_type TEXT NOT NULL DEFAULT 'misc',
      effect_dice TEXT,
      effect_bonus INTEGER NOT NULL DEFAULT 0,
      effect_target TEXT NOT NULL DEFAULT 'self',
      weight_kg REAL NOT NULL DEFAULT 0.0,
      charges INTEGER NOT NULL DEFAULT 1,
      base_price INTEGER NOT NULL DEFAULT 0,
      note TEXT,
      is_active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS game_config_enemies (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      hp_base INTEGER NOT NULL,
      ac_base INTEGER NOT NULL,
      attack_bonus INTEGER NOT NULL,
      dex_modifier INTEGER NOT NULL DEFAULT 0,
      damage_die TEXT NOT NULL,
      description TEXT,
      is_active INTEGER NOT NULL DEFAULT 1,
      locked_at TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      loot_table_key TEXT,
      drop_chance REAL NOT NULL DEFAULT 1.0
    );
    INSERT INTO game_config_enemies
      (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, loot_table_key, drop_chance)
    VALUES ('bandit', 'Bandit', 12, 13, 3, 1, '1d8', 'bandit_loot', 1.0);

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
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
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

    CREATE TABLE IF NOT EXISTS character_inventory (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      character_id INTEGER NOT NULL,
      item_key TEXT,
      weapon_key TEXT,
      consumable_key TEXT,
      quantity INTEGER NOT NULL DEFAULT 1,
      equipped INTEGER NOT NULL DEFAULT 0,
      slot TEXT,
      acquired_at TEXT NOT NULL DEFAULT (datetime('now')),
      source TEXT,
      meta_json TEXT,
      CONSTRAINT inv_xor CHECK (
        (CASE WHEN item_key IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN weapon_key IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN consumable_key IS NOT NULL THEN 1 ELSE 0 END) = 1
      )
    );
    """


class TestCombatLootIntegration(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_phase8c_combat_loot_test.db"
        if self._tmp.exists():
            self._tmp.unlink()
        conn = sqlite3.connect(str(self._tmp))
        conn.executescript(_schema_sql())
        conn.close()

        self._p_combat = patch.object(cs, "COMBAT_DB_PATH", str(self._tmp))
        self._p_loot = patch.object(ls, "LOOT_DB_PATH", str(self._tmp))
        self._p_combat.start()
        self._p_loot.start()

    def tearDown(self):
        self._p_loot.stop()
        self._p_combat.stop()
        if self._tmp.exists():
            self._tmp.unlink()

    @patch("app.services.loot_service.roll_loot", return_value=[{"weapon_key": "sword_iron", "quantity": 1}])
    @patch("app.services.combat_service.roll_damage_dice", return_value=50)
    @patch("app.services.combat_service.roll_d20", return_value=1)
    def test_enemy_death_grants_loot_to_inventory(self, _d20, _dmg, _roll):
        cs.initiate_combat(1, 1, ["bandit"])
        out = cs.resolve_attack(1, 20, attacker="player")
        self.assertTrue(out.get("enemy_dead"))
        self.assertEqual(len(out.get("loot") or []), 1)
        self.assertEqual(str((out.get("loot") or [])[0].get("key")), "sword_iron")

        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT weapon_key, quantity, source FROM character_inventory WHERE character_id = ?",
            (1,),
        ).fetchall()
        conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(str(rows[0]["weapon_key"]), "sword_iron")
        self.assertEqual(int(rows[0]["quantity"]), 1)
        self.assertEqual(str(rows[0]["source"]), "loot")

    @patch("app.services.loot_service.roll_loot", return_value=[])
    @patch("app.services.combat_service.roll_damage_dice", return_value=50)
    @patch("app.services.combat_service.roll_d20", return_value=1)
    def test_enemy_death_no_loot_table_returns_empty_list(self, _d20, _dmg, _roll):
        cs.initiate_combat(1, 1, ["bandit"])
        out = cs.resolve_attack(1, 20, attacker="player")
        self.assertTrue(out.get("enemy_dead"))
        self.assertEqual(out.get("loot"), [])
        st = out.get("combat_state") or {}
        self.assertEqual(st.get("loot_pool") or [], [])
