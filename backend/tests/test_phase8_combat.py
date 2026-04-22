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
    VALUES ('bandit', 'Bandit', 12, 13, 3, 1, '1d8', NULL, 0.0);

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

    @patch("app.services.combat_service.roll_d20", return_value=2)
    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    @patch("app.services.game_engine.resolve_enemy_loot", return_value=[])
    def test_resolve_attack_hit_reduces_hp(self, _loot, _dmg, _d20):
        cs.initiate_combat(1, 1, ["bandit"])
        r = cs.resolve_attack(1, 20, attacker="player")
        self.assertTrue(r["hit"])
        self.assertFalse(r["dodged"])
        self.assertEqual(r["damage"], 5)
        self.assertLess(r["target_hp_remaining"], 12)
        self.assertEqual(r.get("enemy_key"), "bandit")

    @patch("app.services.combat_service.roll_d20", return_value=10)
    @patch("app.services.combat_service.roll_damage_dice", return_value=0)
    def test_resolve_attack_miss(self, _dmg, _d20):
        cs.initiate_combat(1, 1, ["bandit"])
        r = cs.resolve_attack(1, 5, attacker="player")
        self.assertFalse(r["hit"])
        self.assertTrue(r["dodged"])
        self.assertEqual(r["damage"], 0)
        self.assertEqual(r["target_hp_remaining"], 12)

    @patch("app.services.combat_service.roll_d20", return_value=1)
    @patch("app.services.combat_service.roll_damage_dice", return_value=50)
    @patch("app.services.game_engine.resolve_enemy_loot", return_value=[{"source_type": "item", "source_key": "gold", "qty": 1}])
    def test_enemy_death_victory_and_loot(self, _loot, _dmg, _d20):
        cs.initiate_combat(1, 1, ["bandit"])
        r = cs.resolve_attack(1, 20, attacker="player")
        self.assertTrue(r.get("enemy_dead"))
        self.assertEqual(len(r.get("loot") or []), 1)
        st = r["combat_state"]
        self.assertEqual(st["status"], "ended")
        self.assertEqual(st["ended_reason"], "victory")

    @patch("app.services.combat_service.roll_d20", return_value=20)
    @patch("app.services.combat_service.roll_damage_dice", return_value=6)
    def test_player_nat20_auto_hit_bypasses_dodge(self, _dmg, _d20):
        cs.initiate_combat(1, 1, ["bandit"])
        r = cs.resolve_attack(1, 4, attacker="player", raw_d20=20)
        self.assertTrue(r["hit"])
        self.assertFalse(r["dodged"])
        self.assertEqual(r["damage"], 6)
        self.assertEqual(r["dodge_roll"]["verdict"], "hit")

    @patch("app.services.combat_service.roll_damage_dice", return_value=6)
    def test_player_nat1_auto_miss_bypasses_dodge(self, _dmg):
        cs.initiate_combat(1, 1, ["bandit"])
        r = cs.resolve_attack(1, 25, attacker="player", raw_d20=1)
        self.assertFalse(r["hit"])
        self.assertTrue(r["dodged"])
        self.assertTrue(r["player_nat1"])
        self.assertEqual(r["damage"], 0)
        self.assertNotIn("dodge_roll", r)

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

    @patch("app.services.combat_service.roll_d20", return_value=2)
    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    @patch("app.services.game_engine.resolve_enemy_loot", return_value=[])
    def test_resolve_attack_normalizes_generic_enemy_key_for_roll_card(
        self, _loot, _dmg, _d20
    ):
        """Legacy JSON z enemy_key=enemy / name=Wróg → odpowiedź i stan z prawdziwym kluczem z config."""
        cs.initiate_combat(1, 1, ["bandit"])
        conn = sqlite3.connect(str(self._tmp))
        row = conn.execute(
            "SELECT combatants FROM active_combat WHERE campaign_id=1"
        ).fetchone()
        com = json.loads(row["combatants"] or "[]")
        for c in com:
            if isinstance(c, dict) and c.get("type") == "enemy":
                c["enemy_key"] = "enemy"
                c["name"] = "Wróg"
        conn.execute(
            "UPDATE active_combat SET combatants=? WHERE campaign_id=?",
            (json.dumps(com), 1),
        )
        conn.commit()
        conn.close()
        r = cs.resolve_attack(1, 20, attacker="player")
        self.assertEqual(r.get("enemy_key"), "bandit")
        self.assertEqual(r.get("target_name"), "Bandit")
        st = r.get("combat_state") or {}
        enemies = [c for c in (st.get("combatants") or []) if c.get("type") == "enemy"]
        self.assertTrue(enemies)
        self.assertEqual(str(enemies[0].get("enemy_key")), "bandit")

    def test_compute_dodge_tie_favors_defender(self):
        dodged, hit, total = cs.compute_player_attack_dodge_outcome(10, 9, 1, None)
        self.assertTrue(dodged)
        self.assertFalse(hit)
        self.assertEqual(total, 10)

    def test_compute_dodge_attack_strictly_higher_hits(self):
        dodged, hit, total = cs.compute_player_attack_dodge_outcome(11, 9, 1, None)
        self.assertFalse(dodged)
        self.assertTrue(hit)
        self.assertEqual(total, 10)

    def test_compute_dodge_nat20_bypasses_high_dodge(self):
        dodged, hit, _t = cs.compute_player_attack_dodge_outcome(5, 20, 5, 20)
        self.assertFalse(dodged)
        self.assertTrue(hit)

    def test_compute_dodge_nat1_auto_miss(self):
        dodged, hit, _t = cs.compute_player_attack_dodge_outcome(30, 1, 0, 1)
        self.assertTrue(dodged)
        self.assertFalse(hit)

    @patch("app.services.combat_service.roll_d20")
    def test_find_enemy_for_gm_roll_prefers_target_id_with_duplicate_keys(self, mock_r20):
        from app.api import turns as turns_mod

        mock_r20.side_effect = [18, 10, 12]
        st = cs.initiate_combat(1, 1, ["bandit", "bandit"])
        enemy_ids = [c["id"] for c in st["combatants"] if c.get("type") == "enemy"]
        self.assertEqual(len(enemy_ids), 2)
        tid = str(enemy_ids[1])
        enemy = turns_mod._find_enemy_for_gm_roll(
            1,
            {"enemy_key": "bandit", "target_id": tid, "target_name": ""},
        )
        self.assertIsNotNone(enemy)
        self.assertEqual(str(enemy.get("id")), tid)

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


class TestAtakCommandTurn(unittest.TestCase):
    """Dispatcher POST /turns — /atak i /walka zwracają JSON command bez LLM."""

    def setUp(self):
        import app.api.turns as turns_mod

        self._turns_mod = turns_mod
        self._tmp = Path(__file__).resolve().parent / "_phase8_atak_turn_test.db"
        if self._tmp.exists():
            self._tmp.unlink()
        conn = sqlite3.connect(str(self._tmp))
        conn.executescript(_schema_sql())
        conn.close()
        self._p_db = patch.object(cs, "COMBAT_DB_PATH", str(self._tmp))
        self._p_turns_db = patch.object(turns_mod, "DB_PATH", str(self._tmp))
        self._p_db.start()
        self._p_turns_db.start()

    def tearDown(self):
        self._p_turns_db.stop()
        self._p_db.stop()
        if self._tmp.exists():
            self._tmp.unlink()

    def _conn(self):
        c = sqlite3.connect(str(self._tmp))
        c.row_factory = sqlite3.Row
        return c

    def test_post_turns_atak_no_active_combat(self):
        from app.api.turns import TurnCreate, create_turn

        with patch.object(self._turns_mod, "get_db", self._conn):
            out = create_turn(1, TurnCreate(character_id=1, text="/atak"), None)
        self.assertEqual(out["route"], "command")
        res = out["result"]
        self.assertEqual(res["command"], "atak")
        self.assertFalse(res["combat_active"])
        self.assertIsNone(res["combat_state"])
        self.assertEqual(res["message"], "Nie trwa żadna walka.")

    @patch("app.services.combat_service.roll_d20")
    def test_post_turns_atak_active_combat_has_enemy_hp(self, mock_r20):
        from app.api.turns import TurnCreate, create_turn

        mock_r20.side_effect = [18, 10]
        cs.initiate_combat(1, 1, ["bandit"])
        with patch.object(self._turns_mod, "get_db", self._conn):
            out = create_turn(1, TurnCreate(character_id=1, text="/atak"), None)
        self.assertEqual(out["route"], "command")
        res = out["result"]
        self.assertTrue(res["combat_active"])
        st = res["combat_state"]
        self.assertIsNotNone(st)
        enemies = [c for c in st.get("combatants") or [] if c.get("type") == "enemy"]
        self.assertTrue(enemies)
        self.assertIn("hp_current", enemies[0])

    def test_post_turns_walka_alias_matches_atak(self):
        from app.api.turns import TurnCreate, create_turn

        with patch.object(self._turns_mod, "get_db", self._conn):
            out_walka = create_turn(1, TurnCreate(character_id=1, text="/walka"), None)
            out_atak = create_turn(1, TurnCreate(character_id=1, text="/atak"), None)
        self.assertEqual(out_walka["result"]["command"], "atak")
        self.assertEqual(out_atak["result"]["command"], "atak")
        self.assertEqual(out_walka["result"]["combat_active"], out_atak["result"]["combat_active"])


if __name__ == "__main__":
    unittest.main()
