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


def _last_structlog_event_kw(mock_info, event_name: str) -> dict | None:
    """Last kwargs passed to structlog ``logger.info(event_name, **kw)``."""
    for call in reversed(mock_info.call_args_list):
        args, kwargs = call
        if args and args[0] == event_name:
            return dict(kwargs)
    return None


def _step81_loot_by_enemy_key(ek: str) -> list[dict]:
    """Side-effect for roll_loot in two-enemy victory test."""
    return [{"item_key": f"loot_{ek}", "quantity": 1}]


def _grant_passthrough(_character_id: int, loot_items: list[dict], source: str = "loot") -> list[dict]:
    """Test helper: mimic grant output from incoming roll payload."""
    out = []
    for it in loot_items or []:
        key = it.get("item_key") or it.get("weapon_key") or it.get("consumable_key")
        qty = int(it.get("quantity") or 1)
        out.append({"key": key, "label": str(key), "item_type": "item", "quantity": qty, "source": source})
    return out


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
        player = next(c for c in st["combatants"] if c.get("type") == "player")
        self.assertIn("stats", player)
        self.assertEqual(player["stats"].get("STR"), 14)
        self.assertIn("speed", player["stats"])
        enemy = next(c for c in st["combatants"] if c.get("id") == "bandit_01")
        self.assertIn("dex_modifier", enemy)

    def test_initiate_combat_skips_unknown_enemy_keys(self):
        st = cs.initiate_combat(1, 1, ["not_a_real_enemy_zz", "bandit"])
        self.assertEqual(st["status"], "active")
        enemies = [c for c in st["combatants"] if c.get("type") == "enemy"]
        self.assertEqual(len(enemies), 1)
        self.assertEqual(enemies[0].get("enemy_key"), "bandit")

    def test_initiate_combat_raises_when_all_enemy_keys_unknown(self):
        with self.assertRaises(ValueError):
            cs.initiate_combat(1, 1, ["fake_one", "fake_two"])

    @patch("app.services.combat_service.roll_d20", return_value=2)
    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    @patch("app.services.loot_service.roll_loot", return_value=[])
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

    @patch("app.services.combat_service.roll_d20", return_value=2)
    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    def test_resolve_player_attack_alias_matches_resolve_attack(self, _dmg, _d20):
        cs.initiate_combat(1, 1, ["bandit"])
        a = cs.resolve_attack(1, 5, attacker="player")
        b = cs.resolve_player_attack(1, 5)
        self.assertEqual(a.get("hit"), b.get("hit"))
        self.assertEqual(a.get("dodged"), b.get("dodged"))
        self.assertEqual(a.get("damage"), b.get("damage"))

    @patch("app.services.combat_service.resolve_attack")
    def test_resolve_enemy_attack_alias_calls_resolve_attack(self, mock_ra):
        mock_ra.return_value = {"hit": True}
        out = cs.resolve_enemy_attack(42, roll_result=99, raw_d20=8)
        mock_ra.assert_called_once_with(42, 0, attacker="enemy", raw_d20=None)
        self.assertEqual(out, {"hit": True})

    @patch("app.services.combat_service.roll_d20", return_value=1)
    @patch("app.services.combat_service.roll_damage_dice", return_value=50)
    @patch("app.services.loot_service.grant_loot_to_character", side_effect=_grant_passthrough)
    @patch("app.services.loot_service.roll_loot", return_value=[{"item_key": "gold", "quantity": 1}])
    def test_enemy_death_victory_and_loot(self, _loot, _grant, _dmg, _d20):
        cs.initiate_combat(1, 1, ["bandit"])
        r = cs.resolve_attack(1, 20, attacker="player")
        self.assertTrue(r.get("enemy_dead"))
        self.assertEqual(len(r.get("loot") or []), 1)
        st = r["combat_state"]
        self.assertEqual(st["status"], "ended")
        self.assertEqual(st["ended_reason"], "victory")
        self.assertEqual(len(st.get("loot_pool") or []), 1)
        self.assertEqual(st["loot_pool"][0].get("key"), "gold")
        enemies = [c for c in (st.get("combatants") or []) if c.get("type") == "enemy"]
        self.assertEqual(len(enemies), 1)
        self.assertTrue(enemies[0].get("dead"))

    @patch("app.services.combat_service.roll_d20", return_value=1)
    @patch("app.services.combat_service.roll_damage_dice", return_value=50)
    @patch("app.services.loot_service.roll_loot", return_value=[])
    def test_enemy_death_victory_empty_loot_pool_when_no_drops(self, _loot, _dmg, _d20):
        cs.initiate_combat(1, 1, ["bandit"])
        r = cs.resolve_attack(1, 20, attacker="player")
        self.assertTrue(r.get("enemy_dead"))
        st = r["combat_state"]
        self.assertEqual(st.get("loot_pool") or [], [])

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

    @patch("app.services.combat_service.logger.info")
    @patch("app.services.combat_service.roll_d20", return_value=2)
    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    def test_step82_dice_roll_player_attack_logs_dc_outcome_and_source(self, _dmg, _d20, mock_info):
        cs.initiate_combat(1, 1, ["bandit"])
        mock_info.reset_mock()
        cs.resolve_attack(1, 20, attacker="player", raw_d20=14)
        kw = _last_structlog_event_kw(mock_info, "dice_roll")
        self.assertIsNotNone(kw)
        self.assertEqual(kw.get("source"), "combat_attack")
        self.assertEqual(kw.get("dc"), 13)
        self.assertEqual(kw.get("outcome"), "hit")
        self.assertEqual(kw.get("roll_type"), "1d20")
        self.assertEqual(kw.get("result"), 20)
        self.assertEqual(kw.get("campaign_id"), 1)

    @patch("app.services.combat_service.logger.info")
    @patch("app.services.combat_service.roll_d20", return_value=2)
    @patch("app.services.combat_service.roll_damage_dice", return_value=1)
    def test_step82_dice_roll_player_nat20_is_critical_hit(self, _dmg, _d20, mock_info):
        cs.initiate_combat(1, 1, ["bandit"])
        mock_info.reset_mock()
        cs.resolve_attack(1, 4, attacker="player", raw_d20=20)
        kw = _last_structlog_event_kw(mock_info, "dice_roll")
        self.assertEqual(kw.get("outcome"), "critical_hit")
        self.assertEqual(kw.get("dc"), 13)

    @patch("app.services.combat_service.logger.info")
    @patch("app.services.combat_service.roll_d20", return_value=2)
    @patch("app.services.combat_service.roll_damage_dice", return_value=0)
    def test_step82_dice_roll_player_nat1_is_critical_miss(self, _dmg, _d20, mock_info):
        cs.initiate_combat(1, 1, ["bandit"])
        mock_info.reset_mock()
        cs.resolve_attack(1, 25, attacker="player", raw_d20=1)
        kw = _last_structlog_event_kw(mock_info, "dice_roll")
        self.assertEqual(kw.get("outcome"), "critical_miss")
        self.assertEqual(kw.get("dc"), 13)

    @patch("app.services.combat_service.logger.info")
    @patch("app.services.combat_service.roll_d20")
    @patch("app.services.combat_service.roll_damage_dice", return_value=0)
    def test_step82_dice_roll_enemy_attack_logs_dc_outcome_and_source(self, _dmg, mock_r20, mock_info):
        mock_r20.side_effect = [2, 19]
        cs.initiate_combat(1, 1, ["bandit"])
        mock_info.reset_mock()
        mock_r20.return_value = 10
        mock_r20.side_effect = None
        r = cs.resolve_attack(1, 0, attacker="enemy")
        self.assertFalse(r["hit"])
        kw = _last_structlog_event_kw(mock_info, "dice_roll")
        self.assertIsNotNone(kw)
        self.assertEqual(kw.get("source"), "combat_enemy")
        self.assertEqual(kw.get("dc"), 15)
        self.assertEqual(kw.get("outcome"), "miss")
        self.assertEqual(kw.get("result"), 13)

    @patch(
        "app.services.solo_death_service.get_user_llm_settings_full",
        return_value={"provider": "ollama", "base_url": "http://127.0.0.1", "model": "m", "api_key": ""},
    )
    @patch("app.services.solo_death_service.generate_epitaph_llm", return_value="Test epitaph combat.")
    @patch("app.services.combat_service.roll_d20", return_value=20)
    @patch("app.services.combat_service.roll_damage_dice", return_value=25)
    def test_player_hit_updates_sheet_json(self, _dmg, _r20, _epi, _llm):
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
        sheet = json.loads(sh["sheet_json"])
        self.assertEqual(sheet.get("current_hp"), 0)
        self.assertTrue(r.get("player_incapacitated"))
        self.assertEqual(r["combat_state"]["status"], "ended")
        self.assertEqual(r["combat_state"]["ended_reason"], "player_dead")
        self.assertEqual(r.get("defeated_by"), "Bandit")
        camp = conn.execute(
            "SELECT status, death_reason, epitaph FROM campaigns WHERE id=1"
        ).fetchone()
        self.assertEqual(str(camp["status"]), "ended")
        self.assertIn("Bandit", str(camp["death_reason"] or ""))
        self.assertIn("walce", str(camp["death_reason"] or "").lower())
        self.assertEqual(str(camp["epitaph"] or "").strip(), "Test epitaph combat.")
        conn.close()

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
        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
        camp = conn.execute("SELECT status FROM campaigns WHERE id=1").fetchone()
        conn.close()
        self.assertEqual(str(camp["status"]), "active")

    def test_step_32_turn_helpers(self):
        self.assertFalse(cs.is_combat_active(None, 1))
        self.assertIsNone(cs.get_current_actor(None, 1))
        self.assertIsNone(cs.advance_turn(None, 1))
        cs.initiate_combat(1, 1, ["bandit"])
        self.assertTrue(cs.is_combat_active(None, 1))
        cur = cs.get_current_actor(None, 1)
        self.assertIsNotNone(cur)
        nxt = cs.advance_turn(None, 1)
        self.assertIsNotNone(nxt)
        self.assertNotEqual(cur, nxt)

    def test_get_combat_context_for_prompt(self):
        cs.initiate_combat(1, 1, ["bandit"])
        txt = cs.get_combat_context_for_prompt(1)
        self.assertIsNotNone(txt)
        self.assertIn("ACTIVE COMBAT", txt)
        self.assertIn("Aldric", txt)

    def test_get_enemy_catalog_for_prompt(self):
        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
        try:
            txt = cs.get_enemy_catalog_for_prompt(conn)
        finally:
            conn.close()
        self.assertIn("bandit", txt)
        self.assertIn("Dostępni wrogowie", txt)
        self.assertLessEqual(len(txt), 1500)

    @patch("app.services.game_engine.build_runtime_config_block", return_value="")
    @patch("app.services.game_engine.loadrecentturns", return_value=[])
    def test_build_narrative_messages_includes_enemy_catalog_when_no_combat(self, _, __):
        from app.services.game_engine import build_narrative_messages

        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
        try:
            camp = conn.execute("SELECT * FROM campaigns WHERE id=1").fetchone()
            char = conn.execute("SELECT * FROM characters WHERE id=1").fetchone()
            msgs = build_narrative_messages(conn, camp, char, "Idziemy dalej", None, None)
        finally:
            conn.close()
        body = msgs[0]["content"]
        self.assertIn("Dostępni wrogowie", body)
        self.assertIn("bandit", body)

    @patch("app.services.game_engine.build_runtime_config_block", return_value="")
    @patch("app.services.game_engine.loadrecentturns", return_value=[])
    def test_build_narrative_messages_omits_enemy_catalog_when_combat_active(self, _, __):
        from app.services.game_engine import build_narrative_messages

        cs.initiate_combat(1, 1, ["bandit"])
        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
        try:
            camp = conn.execute("SELECT * FROM campaigns WHERE id=1").fetchone()
            char = conn.execute("SELECT * FROM characters WHERE id=1").fetchone()
            msgs = build_narrative_messages(conn, camp, char, "Atakuję", None, None)
        finally:
            conn.close()
        body = msgs[0]["content"]
        self.assertIn("ACTIVE COMBAT", body)
        self.assertNotIn("Dostępni wrogowie", body)

    @patch("app.services.combat_service.roll_d20", return_value=2)
    @patch("app.services.combat_service.roll_damage_dice", return_value=5)
    @patch("app.services.loot_service.roll_loot", return_value=[])
    def test_resolve_attack_normalizes_generic_enemy_key_for_roll_card(
        self, _loot, _dmg, _d20
    ):
        """Legacy JSON z enemy_key=enemy / name=Wróg → odpowiedź i stan z prawdziwym kluczem z config."""
        cs.initiate_combat(1, 1, ["bandit"])
        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
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
        self.assertGreaterEqual(n, 3)
        types = [r["event_type"] for r in conn.execute("SELECT event_type FROM combat_turns").fetchall()]
        self.assertIn("start", types)
        self.assertGreaterEqual(types.count("initiative"), 2)
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

    # --- docs/combat_system_2/step_8.1_e2e_testing.txt — automated slice (pytest) ---

    @patch("app.services.loot_service.grant_loot_to_character", side_effect=_grant_passthrough)
    @patch("app.services.loot_service.roll_loot", return_value=[{"item_key": "gem", "quantity": 2}])
    @patch("app.services.combat_service.roll_d20", return_value=1)
    @patch("app.services.combat_service.roll_damage_dice", return_value=50)
    def test_step81_victory_sql_active_combat_matches_doc(self, _dmg, _d20, _loot, _grant):
        """STEP 4 (doc): SELECT status, ended_reason, loot_pool after victory."""
        cs.initiate_combat(1, 1, ["bandit"])
        cs.resolve_attack(1, 20, attacker="player")
        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status, ended_reason, loot_pool FROM active_combat WHERE campaign_id = 1"
        ).fetchone()
        conn.close()
        self.assertEqual(str(row["status"]), "ended")
        self.assertEqual(str(row["ended_reason"]), "victory")
        pool = json.loads(row["loot_pool"] or "[]")
        self.assertEqual(len(pool), 1)
        self.assertEqual(pool[0].get("key"), "gem")
        self.assertEqual(int(pool[0].get("quantity") or 0), 2)

    @patch("app.services.loot_service.roll_loot", return_value=[])
    @patch("app.services.combat_service.roll_d20", return_value=1)
    @patch("app.services.combat_service.roll_damage_dice", return_value=12)
    def test_step81_enemy_hp_exactly_zero_counts_as_dead_victory(self, _dmg, _d20, _loot):
        """SC-4B: obrażenia równe HP → hp_current 0, enemy_dead, zwycięstwo (jeden wróg)."""
        cs.initiate_combat(1, 1, ["bandit"])
        r = cs.resolve_attack(1, 20, attacker="player")
        self.assertEqual(r.get("target_hp_remaining"), 0)
        self.assertTrue(r.get("enemy_dead"))
        self.assertEqual(r["combat_state"]["status"], "ended")
        self.assertEqual(r["combat_state"]["ended_reason"], "victory")
        enemies = [c for c in (r["combat_state"].get("combatants") or []) if c.get("type") == "enemy"]
        self.assertTrue(enemies[0].get("dead"))

    @patch("app.services.loot_service.grant_loot_to_character", side_effect=_grant_passthrough)
    @patch("app.services.loot_service.roll_loot", side_effect=_step81_loot_by_enemy_key)
    @patch("app.services.combat_service.roll_damage_dice", return_value=50)
    @patch("app.services.combat_service.roll_d20")
    def test_step81_two_enemies_victory_loot_pool_accumulates(self, mock_r20, _dmg, _loot, _grant):
        """Dwóch wrogów w JSON → dwa ciosy, victory, loot_pool z dwóch roll_loot."""
        mock_r20.side_effect = [18, 10, 12, 1, 1]
        cs.initiate_combat(1, 1, ["bandit", "bandit"])
        r1 = cs.resolve_attack(1, 20, attacker="player")
        self.assertEqual(r1["combat_state"]["status"], "active")
        r2 = cs.resolve_attack(1, 20, attacker="player")
        self.assertEqual(r2["combat_state"]["status"], "ended")
        self.assertEqual(r2["combat_state"]["ended_reason"], "victory")
        pool = r2["combat_state"].get("loot_pool") or []
        self.assertEqual(len(pool), 2)
        # Oba wrogowie mają ten sam enemy_key „bandit” — roll_loot wołany 2× z tym samym kluczem.
        self.assertEqual(str(pool[0].get("key")), "loot_bandit")
        self.assertEqual(str(pool[1].get("key")), "loot_bandit")

    @patch(
        "app.services.solo_death_service.get_user_llm_settings_full",
        return_value={"provider": "ollama", "base_url": "http://127.0.0.1", "model": "m", "api_key": ""},
    )
    @patch("app.services.solo_death_service.generate_epitaph_llm", return_value="Step81 epitaph.")
    @patch("app.services.combat_service.roll_d20", return_value=20)
    @patch("app.services.combat_service.roll_damage_dice", return_value=25)
    def test_step81_player_death_sql_matches_doc(self, _dmg, _r20, _epi, _llm):
        """STEP 4: active_combat ended_reason player_dead; campaigns death_reason PL combat."""
        cs.initiate_combat(1, 1, ["bandit"])
        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT current_turn FROM active_combat WHERE campaign_id=1").fetchone()
        if row["current_turn"] == "player":
            cs.advance_turn(1)
        cs.resolve_attack(1, 0, attacker="enemy")
        ac = conn.execute(
            "SELECT status, ended_reason FROM active_combat WHERE campaign_id=1"
        ).fetchone()
        camp = conn.execute("SELECT status, death_reason FROM campaigns WHERE id=1").fetchone()
        conn.close()
        self.assertEqual(str(ac["status"]), "ended")
        self.assertEqual(str(ac["ended_reason"]), "player_dead")
        self.assertEqual(str(camp["status"]), "ended")
        self.assertIn("Poległ w walce z", str(camp["death_reason"] or ""))

    def test_step81_unknown_enemy_keys_all_invalid_raises_value_error(self):
        """SC-4 / doc: brak poprawnych kluczy → ValueError (bez nowej logiki)."""
        with self.assertRaises(ValueError):
            cs.initiate_combat(1, 1, ["totally_fake_x", "also_fake_y"])


class TestAtakCommandTurn(unittest.TestCase):
    """Dispatcher POST /turns — /atak i /walka zwracają JSON command bez LLM."""

    def setUp(self):
        import app.api.turns as turns_mod
        import app.services.client_ui_config as client_ui_cfg

        self._turns_mod = turns_mod
        self._tmp = Path(__file__).resolve().parent / "_phase8_atak_turn_test.db"
        if self._tmp.exists():
            self._tmp.unlink()
        conn = sqlite3.connect(str(self._tmp))
        conn.executescript(_schema_sql())
        conn.close()
        self._p_db = patch.object(cs, "COMBAT_DB_PATH", str(self._tmp))
        self._p_turns_db = patch.object(turns_mod, "DB_PATH", str(self._tmp))
        self._p_client_cfg_db = patch.object(client_ui_cfg, "DB_PATH", str(self._tmp))
        self._p_llm = patch.object(
            turns_mod,
            "get_user_llm_settings_full",
            return_value={
                "provider": "ollama",
                "base_url": "http://127.0.0.1:11434",
                "model": "m",
                "api_key": "",
            },
        )
        self._p_db.start()
        self._p_turns_db.start()
        self._p_client_cfg_db.start()
        self._p_llm.start()

    def tearDown(self):
        self._p_llm.stop()
        self._p_client_cfg_db.stop()
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
