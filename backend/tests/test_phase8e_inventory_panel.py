"""Phase 8E-3 — inventory GET, gold GET, equip replaces slot, unequip via null slot."""

import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api import inventory as inventory_api
from app.services import loot_service as ls


def _schema_sql() -> str:
    return """
    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      gold_gp INTEGER NOT NULL DEFAULT 0
    );
    INSERT INTO characters (id, name, gold_gp) VALUES (1, 'Hero', 25);

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

    INSERT INTO game_config_weapons (key, label, is_active) VALUES
      ('sword_a', 'Sword A', 1),
      ('sword_b', 'Sword B', 1);
    INSERT INTO game_config_items (key, label, item_type, description, value_gp, weight, weight_kg, is_active)
    VALUES ('leather1', 'Leather', 'armor', 'x', 10, 0, 5, 1);

    INSERT INTO character_inventory (character_id, weapon_key, quantity, equipped, slot, source)
    VALUES (1, 'sword_a', 1, 1, 'main_hand', 'start');
    INSERT INTO character_inventory (character_id, weapon_key, quantity, equipped, source)
    VALUES (1, 'sword_b', 1, 0, 'start');
    INSERT INTO character_inventory (character_id, item_key, quantity, equipped, source)
    VALUES (1, 'leather1', 1, 0, 'start');
    """


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(inventory_api.router, prefix="/api")
    return TestClient(app)


class TestPhase8eInventoryPanel(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_phase8e_inv_panel.db"
        if self._tmp.exists():
            self._tmp.unlink()
        conn = sqlite3.connect(str(self._tmp))
        conn.executescript(_schema_sql())
        conn.close()
        self._p = patch.object(ls, "LOOT_DB_PATH", str(self._tmp))
        self._p.start()
        self.client = _make_client()

    def tearDown(self):
        self._p.stop()
        if self._tmp.exists():
            self._tmp.unlink()

    def test_get_inventory_shows_rows(self):
        r = self.client.get("/api/inventory/1")
        self.assertEqual(r.status_code, 200)
        data = r.json().get("data") or []
        self.assertEqual(len(data), 3)

    def test_gold_endpoint_returns_correct_value(self):
        r = self.client.get("/api/characters/1/gold")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("data", {}).get("gold_gp"), 25)

    def test_equip_item_sets_slot(self):
        r = self.client.post(
            "/api/inventory/1/equip",
            json={"inventory_id": 2, "slot": "off_hand"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        inv = self.client.get("/api/inventory/1").json()["data"]
        row2 = next(x for x in inv if int(x["id"]) == 2)
        self.assertEqual(int(row2["equipped"]), 1)
        self.assertEqual(str(row2["slot"]).lower(), "off_hand")

    def test_equip_replaces_previous_item_in_slot(self):
        r = self.client.post(
            "/api/inventory/1/equip",
            json={"inventory_id": 2, "slot": "main_hand"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        inv = self.client.get("/api/inventory/1").json()["data"]
        row1 = next(x for x in inv if int(x["id"]) == 1)
        row2 = next(x for x in inv if int(x["id"]) == 2)
        self.assertEqual(int(row1["equipped"]), 0)
        self.assertIsNone(row1.get("slot"))
        self.assertEqual(int(row2["equipped"]), 1)
        self.assertEqual(str(row2["slot"]).lower(), "main_hand")

    def test_unequip_item_clears_slot(self):
        r = self.client.post(
            "/api/inventory/1/equip",
            json={"inventory_id": 1, "slot": None},
        )
        self.assertEqual(r.status_code, 200, r.text)
        inv = self.client.get("/api/inventory/1").json()["data"]
        row1 = next(x for x in inv if int(x["id"]) == 1)
        self.assertEqual(int(row1["equipped"]), 0)
        self.assertIsNone(row1.get("slot"))
