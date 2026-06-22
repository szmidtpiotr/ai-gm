"""Phase 8E — starter items + gold on character create and gold API."""

import json
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql

from app.api import characters as characters_api
from app.api import inventory as inventory_api
from app.services import loot_service as ls
from app.services import location_validator as lv


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
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
      gold_gp INTEGER NOT NULL DEFAULT 0
    );

    """ + table_sql("game_config_weapons") + """
    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, allowed_classes, is_active) VALUES
      ('shortsword', 'Shortsword', 'd6', 'STR', '["warrior"]', 1),
      ('wooden_shield', 'Shield', 'd4', 'STR', '["warrior"]', 1),
      ('shortbow', 'Shortbow', 'd6', 'DEX', '["warrior","ranger"]', 1),
      ('quarterstaff', 'Staff', 'd6', 'STR', '["scholar"]', 1);

    """ + table_sql("game_config_items") + """
    INSERT INTO game_config_items (key, label, item_type, description, value_gp, weight, weight_kg, is_active)
    VALUES ('leatherarmor', 'Leather', 'armor', 'armor', 10, 0, 5, 1);

    """ + table_sql("game_config_consumables") + """
    INSERT INTO game_config_consumables (key, label, is_active)
    VALUES ('health_potion_small', 'HP', 1), ('mana_potion', 'Mana', 1);

    CREATE TABLE game_locations (
      id INTEGER PRIMARY KEY,
      key TEXT UNIQUE NOT NULL,
      label TEXT NOT NULL,
      description TEXT,
      parent_id INTEGER REFERENCES game_locations(id),
      location_type TEXT DEFAULT 'macro',
      rules TEXT,
      enemy_keys TEXT DEFAULT '[]',
      npc_keys TEXT DEFAULT '[]',
      is_active INTEGER DEFAULT 1,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now')),
      ai_generated INTEGER DEFAULT 0,
      approved INTEGER DEFAULT 1
    );

    """ + table_sql("game_config_archetypes") + """
    INSERT INTO game_config_archetypes (key, label, description, starter_items_json, starter_gold_gp, is_active)
    VALUES
    ('warrior', 'W', 'x',
     '[{"weapon_key":"shortsword"},{"weapon_key":"wooden_shield"},{"weapon_key":"shortbow"},{"item_key":"leatherarmor"}]',
     10, 1),
    ('scholar', 'S', 'y',
     '[{"weapon_key":"quarterstaff"},{"consumable_key":"health_potion_small"},{"consumable_key":"mana_potion"}]',
     15, 1);

    CREATE TABLE character_inventory (
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

    CREATE TABLE campaign_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      character_id INTEGER,
      user_text TEXT,
      route TEXT,
      assistant_text TEXT,
      turn_number INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE game_sessions (
      id TEXT PRIMARY KEY,
      campaign_id INTEGER,
      current_location_id INTEGER REFERENCES game_locations(id),
      session_flags TEXT DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """


class TestPhase8ePaths(unittest.TestCase):
    """Doc 8E-1: same DB file for character create and loot/inventory."""

    def test_db_path_same_as_loot_db_path(self):
        self.assertEqual(characters_api.DB_PATH, ls.LOOT_DB_PATH)


class TestPhase8eStarterItems(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_phase8e_starter.db"
        if self._tmp.exists():
            self._tmp.unlink()
        conn = sqlite3.connect(str(self._tmp))
        conn.executescript(_schema_sql())
        conn.close()
        self._p_ls = patch.object(ls, "LOOT_DB_PATH", str(self._tmp))
        self._p_ls.start()
        self._p_ch = patch.object(characters_api, "DB_PATH", str(self._tmp))
        self._p_ch.start()
        self._p_lv = patch.object(lv, "DB_PATH", str(self._tmp))
        self._p_lv.start()

        app = FastAPI()
        app.include_router(characters_api.router, prefix="/api")
        app.include_router(inventory_api.router, prefix="/api")
        self.client = TestClient(app)

    def tearDown(self):
        self._p_ch.stop()
        self._p_ls.stop()
        self._p_lv.stop()
        if self._tmp.exists():
            self._tmp.unlink()

    @patch("app.api.characters.generate_chat", return_value="")
    def test_create_character_warrior_grants_starter_items(self, _gc):
        r = self.client.post(
            "/api/campaigns/1/characters",
            json={
                "user_id": 1,
                "name": "W1",
                "system_id": "fantasy",
                "sheet_json": {"archetype": "warrior", "background": "b"},
                "location": "here",
                "is_active": 1,
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        cid = r.json()["id"]
        inv = ls.get_character_inventory(cid)
        keys = {(x.get("item_type"), x.get("key")) for x in inv}
        self.assertIn(("weapon", "shortsword"), keys)
        self.assertIn(("weapon", "wooden_shield"), keys)
        self.assertIn(("weapon", "shortbow"), keys)
        self.assertIn(("armor", "leatherarmor"), keys)

    @patch("app.api.characters.generate_chat", return_value="")
    def test_create_character_warrior_grants_gold(self, _gc):
        r = self.client.post(
            "/api/campaigns/1/characters",
            json={
                "user_id": 1,
                "name": "W2",
                "system_id": "fantasy",
                "sheet_json": {"archetype": "warrior"},
                "location": "here",
                "is_active": 1,
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        cid = r.json()["id"]
        self.assertEqual(r.json().get("gold_gp"), 10)
        conn = sqlite3.connect(str(self._tmp))
        row = conn.execute("SELECT gold_gp FROM characters WHERE id = ?", (cid,)).fetchone()
        conn.close()
        self.assertEqual(int(row[0]), 10)

    @patch("app.api.characters.generate_chat", return_value="")
    def test_create_character_scholar_starter_items(self, _gc):
        r = self.client.post(
            "/api/campaigns/1/characters",
            json={
                "user_id": 1,
                "name": "S1",
                "system_id": "fantasy",
                "sheet_json": {"archetype": "scholar"},
                "location": "here",
                "is_active": 1,
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        cid = r.json()["id"]
        inv = ls.get_character_inventory(cid)
        keys = {(x.get("item_type"), x.get("key")) for x in inv}
        self.assertIn(("weapon", "quarterstaff"), keys)
        self.assertIn(("consumable", "health_potion_small"), keys)
        self.assertIn(("consumable", "mana_potion"), keys)

    @patch("app.api.characters.generate_chat", return_value="")
    def test_create_character_scholar_gold(self, _gc):
        r = self.client.post(
            "/api/campaigns/1/characters",
            json={
                "user_id": 1,
                "name": "S2",
                "system_id": "fantasy",
                "sheet_json": {"archetype": "scholar"},
                "location": "here",
                "is_active": 1,
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json().get("gold_gp"), 15)

    @patch("app.api.characters.generate_chat", return_value="")
    def test_gold_endpoint_get_and_delta(self, _gc):
        r = self.client.post(
            "/api/campaigns/1/characters",
            json={
                "user_id": 1,
                "name": "G1",
                "system_id": "fantasy",
                "sheet_json": {"archetype": "warrior"},
                "location": "here",
                "is_active": 1,
            },
        )
        cid = r.json()["id"]
        g0 = self.client.get(f"/api/characters/{cid}/gold")
        self.assertEqual(g0.status_code, 200)
        self.assertGreaterEqual(g0.json()["data"]["gold_gp"], 0)
        g1 = self.client.post(f"/api/characters/{cid}/gold", json={"delta": 50, "reason": "test"})
        self.assertEqual(g1.status_code, 200)
        self.assertEqual(g1.json()["data"]["gold_gp"], 60)
        bad = self.client.post(f"/api/characters/{cid}/gold", json={"delta": -999, "reason": "x"})
        self.assertEqual(bad.status_code, 400)
        z = self.client.post(f"/api/characters/{cid}/gold", json={"delta": 0, "reason": "x"})
        self.assertEqual(z.status_code, 400)

    @patch("app.api.characters.generate_chat", return_value="")
    def test_create_character_unknown_archetype_no_crash(self, _gc):
        r = self.client.post(
            "/api/campaigns/1/characters",
            json={
                "user_id": 1,
                "name": "N1",
                "system_id": "fantasy",
                "sheet_json": {"archetype": "nomad"},
                "location": "here",
                "is_active": 1,
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        cid = r.json()["id"]
        self.assertEqual(ls.get_character_inventory(cid), [])
        self.assertEqual(r.json().get("gold_gp"), 0)

    @patch("app.api.characters.generate_chat")
    def test_opening_scene_creates_pending_location(self, mock_gc):
        mock_gc.return_value = json.dumps({
            "narrative": "Mgła unosi się nad drogą, zmierzacie w stronę rogatek.",
            "location_intent": {
                "action": "create",
                "target_label": "Rozmokła droga przy rogatkach wioski",
                "parent_key": "start",
                "description": "Błotnisty trakt, mgła, zniszczony wóz"
            }
        })
        r = self.client.post(
            "/api/campaigns/1/characters",
            json={
                "user_id": 1,
                "name": "L1",
                "system_id": "fantasy",
                "sheet_json": {"archetype": "warrior"},
                "location": "here",
                "is_active": 1,
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM game_locations WHERE label = ?",
            ("Rozmokła droga przy rogatkach wioski",),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row, "pending location missing")
        self.assertEqual(row["ai_generated"], 1)
        self.assertEqual(row["approved"], 0)

    @patch("app.api.characters.generate_chat")
    def test_opening_scene_without_intent_creates_fallback_start_location(self, mock_gc):
        mock_gc.return_value = json.dumps({
            "narrative": "Wilgotny poranek i zimny wiatr na starcie kampanii.",
            "location_intent": None
        })
        r = self.client.post(
            "/api/campaigns/1/characters",
            json={
                "user_id": 1,
                "name": "L2",
                "system_id": "fantasy",
                "sheet_json": {"archetype": "warrior"},
                "location": "here",
                "is_active": 1,
            },
        )
        self.assertEqual(r.status_code, 200, r.text)

        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
        loc = conn.execute(
            "SELECT id, key, label, ai_generated, approved FROM game_locations WHERE key = ?",
            ("campaign_1_start",),
        ).fetchone()
        sess = conn.execute(
            "SELECT current_location_id FROM game_sessions WHERE id = ?",
            ("1",),
        ).fetchone()
        conn.close()

        self.assertIsNotNone(loc, "fallback start location missing")
        self.assertIsNotNone(sess, "game_session missing")
        self.assertEqual(int(sess["current_location_id"]), int(loc["id"]))
