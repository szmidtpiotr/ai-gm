"""Phase 8A — combat service and API wiring (SQLite temp DB)."""
import json
import os
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if "httpx" not in sys.modules:
    from unittest.mock import MagicMock

    sys.modules["httpx"] = MagicMock()

from app.services import admin_config
from app.services import combat_service as cs


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
      '{"stats":{"STR":14,"DEX":12,"CON":12,"INT":10,"WIS":10,"CHA":10},"current_hp":20,"max_hp":20,"defense":{"base":15},"equipped_weapon":"sword"}'
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
    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, allowed_classes)
    VALUES ('sword', 'Sword', '1d8', 'STR', 'warrior');

    CREATE TABLE game_config_enemies (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      hp_base INTEGER NOT NULL,
      ac_base INTEGER NOT NULL,
      attack_bonus INTEGER NOT NULL,
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
      (key, label, hp_base, ac_base, attack_bonus, damage_die, loot_table_key, drop_chance)
    VALUES ('bandit', 'Bandit', 12, 13, 3, '1d8', NULL, 0.0);

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
    """


class TestPhase8Combat(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_phase8_combat_test.db"
        if self._tmp.exists():
            self._tmp.unlink()
        conn = sqlite3.connect(str(self._tmp))
        conn.executescript(_schema_sql())
        conn.close()
        self._p_db = patch.object(cs, "COMBAT_DB_PATH", str(self._tmp))
        self._p_admin = patch.object(admin_config, "DB_PATH", str(self._tmp))
        self._p_db.start()
        self._p_admin.start()

    def tearDown(self):
        self._p_admin.stop()
        self._p_db.stop()
        if self._tmp.exists():
            self._tmp.unlink()

    @patch("app.services.combat_service.roll_d20")
    def test_initiate_combat_order_and_initiative(self, mock_r20):
        mock_r20.side_effect = [18, 10, 12]
        st = cs.initiate_combat(1, 1, ["bandit", "bandit"])
        self.assertEqual(st["status"], "active")
        order = st["turn_order"]
        self.assertEqual(order[0], "player")
        self.assertIn("bandit_01", order)
        self.assertIn("bandit_02", order)
        ids = [c["id"] for c in st["combatants"]]
        self.assertEqual(len(ids), 3)

    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    @patch("app.services.game_engine.resolve_enemy_loot", return_value=[])
    def test_resolve_attack_hit_reduces_hp(self, _loot, _dmg):
        cs.initiate_combat(1, 1, ["bandit"])
        r = cs.resolve_attack(1, 20, attacker="player")
        self.assertTrue(r["hit"])
        self.assertEqual(r["damage"], 5)
        self.assertLess(r["target_hp_remaining"], 12)

    @patch("app.services.combat_service.roll_damage_dice", return_value=0)
    def test_resolve_attack_miss(self, _dmg):
        cs.initiate_combat(1, 1, ["bandit"])
        r = cs.resolve_attack(1, 5, attacker="player")
        self.assertFalse(r["hit"])
        self.assertEqual(r["target_hp_remaining"], 12)

    @patch("app.services.combat_service.roll_damage_dice", return_value=50)
    @patch("app.services.game_engine.resolve_enemy_loot", return_value=[{"source_type": "item", "source_key": "gold", "qty": 1}])
    def test_enemy_death_victory_and_loot(self, _loot, _dmg):
        cs.initiate_combat(1, 1, ["bandit"])
        r = cs.resolve_attack(1, 20, attacker="player")
        self.assertTrue(r.get("enemy_dead"))
        self.assertEqual(len(r.get("loot") or []), 1)
        st = r["combat_state"]
        self.assertEqual(st["status"], "ended")
        self.assertEqual(st["ended_reason"], "victory")

    @patch("app.services.combat_service.roll_d20", return_value=20)
    @patch("app.services.combat_service.roll_damage_dice", return_value=25)
    def test_player_hit_updates_sheet_json(self, _dmg, _r20):
        cs.initiate_combat(1, 1, ["bandit"])
        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT current_turn FROM active_combat WHERE campaign_id=1").fetchone()
        enemy_id = row["current_turn"]
        if enemy_id == "player":
            cs.advance_turn(1)
        r = cs.resolve_attack(1, 0, attacker="enemy")
        self.assertTrue(r["hit"])
        sh = conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()
        conn.close()
        sheet = json.loads(sh["sheet_json"])
        self.assertEqual(sheet.get("current_hp"), 0)
        self.assertTrue(r.get("player_incapacitated"))
        self.assertEqual(r["combat_state"]["status"], "ended")
        self.assertEqual(r["combat_state"]["ended_reason"], "player_dead")

    @patch("app.services.combat_service.roll_d20")
    def test_advance_turn_round_increment(self, mock_r20):
        mock_r20.side_effect = [20, 1]
        cs.initiate_combat(1, 1, ["bandit"])
        st = cs.get_active_combat(1)
        self.assertEqual(st["round"], 1)
        t1 = cs.advance_turn(1)
        st2 = cs.get_active_combat(1)
        self.assertNotEqual(st["current_turn"], st2["current_turn"])
        t2 = cs.advance_turn(1)
        st3 = cs.get_active_combat(1)
        self.assertGreaterEqual(st3["round"], 2)
        self.assertIsNotNone(t2)

    def test_flee(self):
        cs.initiate_combat(1, 1, ["bandit"])
        cs.end_combat(1, "fled")
        st = cs.load_combat_snapshot(1)
        self.assertEqual(st["status"], "ended")
        self.assertEqual(st["ended_reason"], "fled")

    def test_get_combat_context_for_prompt(self):
        cs.initiate_combat(1, 1, ["bandit"])
        txt = cs.get_combat_context_for_prompt(1)
        self.assertIsNotNone(txt)
        self.assertIn("ACTIVE COMBAT", txt)
        self.assertIn("Aldric", txt)

    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    def test_combat_turns_logged_start_and_player_attack(self, _dmg):
        cs.initiate_combat(1, 1, ["bandit"])
        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
        n = conn.execute("SELECT COUNT(*) AS c FROM combat_turns").fetchone()["c"]
        self.assertGreaterEqual(n, 1)
        types = [r["event_type"] for r in conn.execute("SELECT event_type FROM combat_turns").fetchall()]
        self.assertIn("start", types)
        cs.resolve_attack(1, 20, attacker="player")
        rows = conn.execute("SELECT actor, event_type FROM combat_turns ORDER BY id").fetchall()
        conn.close()
        actors_events = [(r["actor"], r["event_type"]) for r in rows]
        self.assertIn(("player", "attack"), actors_events)

    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    def test_list_combat_turns_for_campaign(self, _dmg):
        cs.initiate_combat(1, 1, ["bandit"])
        cs.resolve_attack(1, 20, attacker="player")
        rows = cs.list_combat_turns_for_campaign(1, limit=20)
        self.assertGreaterEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
