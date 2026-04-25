"""Phase 8C — inventory API endpoint tests."""

import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.inventory import router as inventory_router
from app.services import loot_service as ls


def _schema_sql() -> str:
    return """
    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL
    );
    INSERT INTO characters (id, name) VALUES (1, 'Hero');

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
    CREATE TABLE game_config_weapons (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      is_active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE game_config_consumables (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      is_active INTEGER NOT NULL DEFAULT 1
    );
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

    INSERT INTO game_config_items (key, label, item_type, description, value_gp, weight, weight_kg, is_active)
    VALUES ('rope', 'Rope', 'misc', 'simple rope', 5, 1.0, 1.0, 1);
    INSERT INTO game_config_weapons (key, label, is_active) VALUES ('shortsword', 'Short Sword', 1);
    INSERT INTO game_config_consumables (key, label, is_active) VALUES ('potion_small', 'Small Potion', 1);

    INSERT INTO character_inventory (character_id, weapon_key, quantity, equipped, slot, source)
    VALUES (1, 'shortsword', 1, 1, 'main_hand', 'start');
    INSERT INTO character_inventory (character_id, item_key, quantity, equipped, source)
    VALUES (1, 'rope', 2, 0, 'loot');
    """


class TestInventoryApi(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_phase8c_inventory_api.db"
        if self._tmp.exists():
            self._tmp.unlink()
        conn = sqlite3.connect(str(self._tmp))
        conn.executescript(_schema_sql())
        conn.close()

        self._p_db = patch.object(ls, "LOOT_DB_PATH", str(self._tmp))
        self._p_db.start()

        app = FastAPI()
        app.include_router(inventory_router, prefix="/api")
        self.client = TestClient(app)

    def tearDown(self):
        self._p_db.stop()
        if self._tmp.exists():
            self._tmp.unlink()

    def test_get_inventory_ok(self):
        r = self.client.get("/api/inventory/1")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(len(body["data"]), 2)

    def test_get_inventory_character_not_found(self):
        r = self.client.get("/api/inventory/999")
        self.assertEqual(r.status_code, 404)

    def test_equip_invalid_slot_400(self):
        r = self.client.post("/api/inventory/1/equip", json={"inventory_id": 1, "slot": "head"})
        self.assertEqual(r.status_code, 400)

    def test_delete_equipped_requires_force(self):
        r = self.client.delete("/api/inventory/1/1")
        self.assertEqual(r.status_code, 400)
        r2 = self.client.delete("/api/inventory/1/1?force=true")
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()["ok"])

    def test_get_items_and_filter(self):
        r = self.client.get("/api/items")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        r2 = self.client.get("/api/items?item_type=misc")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(len(r2.json()["data"]), 1)
        r3 = self.client.get("/api/items?item_type=invalid")
        self.assertEqual(r3.status_code, 400)

    def test_get_item_details(self):
        r = self.client.get("/api/items/rope")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"]["key"], "rope")
        r2 = self.client.get("/api/items/missing_key")
        self.assertEqual(r2.status_code, 404)

    def test_delete_inventory_item_200(self):
        r = self.client.delete("/api/inventory/1/2")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        inv = self.client.get("/api/inventory/1").json()["data"]
        self.assertEqual(len(inv), 1)

    def test_delete_equipped_item_blocked(self):
        r = self.client.delete("/api/inventory/1/1")
        self.assertEqual(r.status_code, 400)

    def test_delete_equipped_item_with_force(self):
        r = self.client.delete("/api/inventory/1/1?force=true")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def test_equip_invalid_slot_returns_400(self):
        r = self.client.post(
            "/api/inventory/1/equip",
            json={"inventory_id": 1, "slot": "invalid_slot"},
        )
        self.assertEqual(r.status_code, 400)

    def test_get_items_filter_by_type(self):
        conn = sqlite3.connect(str(self._tmp))
        try:
            conn.execute(
                """
                INSERT INTO game_config_items
                (key, label, item_type, description, value_gp, weight, weight_kg, is_active)
                VALUES ('armor_test_plate', 'Test Plate', 'armor', 'heavy', 100, 0, 15.0, 1)
                """
            )
            conn.commit()
        finally:
            conn.close()
        r = self.client.get("/api/items?item_type=armor")
        self.assertEqual(r.status_code, 200)
        data = r.json()["data"]
        self.assertGreaterEqual(len(data), 1)
        for row in data:
            self.assertEqual(str(row.get("item_type")).lower(), "armor")
