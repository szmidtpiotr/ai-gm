"""Phase 8E-5 — GM narrative items endpoint and Grant Item cue parser."""

import json
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api import characters as characters_api
from app.api import turns as turns_api


def _schema_sql() -> str:
    return """
    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL DEFAULT 1,
      user_id INTEGER NOT NULL DEFAULT 1,
      name TEXT NOT NULL DEFAULT 'Hero',
      system_id TEXT NOT NULL DEFAULT 'fantasy',
      sheet_json TEXT NOT NULL DEFAULT '{}',
      location TEXT,
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      gold_gp INTEGER NOT NULL DEFAULT 0
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
      meta_json TEXT
    );

    INSERT INTO characters (id, sheet_json) VALUES
      (1, '{"archetype":"warrior","narrative_items":[]}'),
      (2, '{"archetype":"warrior"}');
    INSERT INTO character_inventory (character_id, item_key, quantity, equipped)
      VALUES (1, 'quest_note', 1, 0);
    """


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(characters_api.router, prefix="/api")
    return TestClient(app)


class TestPhase8eGmItems(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_phase8e_gm_items.db"
        if self._tmp.exists():
            self._tmp.unlink()
        conn = sqlite3.connect(str(self._tmp))
        conn.executescript(_schema_sql())
        conn.close()
        self._p_ch = patch.object(characters_api, "DB_PATH", str(self._tmp))
        self._p_ch.start()
        self.client = _make_client()

    def tearDown(self):
        self._p_ch.stop()
        if self._tmp.exists():
            self._tmp.unlink()

    def _sheet(self, cid: int) -> dict:
        conn = sqlite3.connect(str(self._tmp))
        row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (cid,)).fetchone()
        conn.close()
        return json.loads(row[0] or "{}") if row else {}

    def test_narrative_item_endpoint_adds_to_sheet_json(self):
        r = self.client.post(
            "/api/characters/1/narrative-item",
            json={"label": "Złamany Amulet", "source": "gm", "given_at": "turn:9"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        sheet = self._sheet(1)
        items = sheet.get("narrative_items") or []
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get("label"), "Złamany Amulet")
        self.assertEqual(items[0].get("source"), "gm")
        self.assertEqual(items[0].get("given_at"), "turn:9")

    def test_narrative_item_endpoint_initializes_if_missing(self):
        r = self.client.post(
            "/api/characters/2/narrative-item",
            json={"label": "Tajna Mapa Krypty"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        sheet = self._sheet(2)
        items = sheet.get("narrative_items") or []
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get("label"), "Tajna Mapa Krypty")

    def test_narrative_item_does_not_affect_character_inventory(self):
        before = self._inventory_count(1)
        r = self.client.post(
            "/api/characters/1/narrative-item",
            json={"label": "Pieczęć Zakonu"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        after = self._inventory_count(1)
        self.assertEqual(before, after)

    def _inventory_count(self, cid: int) -> int:
        conn = sqlite3.connect(str(self._tmp))
        n = conn.execute(
            "SELECT COUNT(*) FROM character_inventory WHERE character_id = ?",
            (cid,),
        ).fetchone()[0]
        conn.close()
        return int(n)

    def test_grant_item_cue_parser_detects_label(self):
        label = turns_api.parse_grant_item_cue("Krótki opis.\nGrant Item Złamany Amulet")
        self.assertEqual(label, "Złamany Amulet")

    def test_grant_item_cue_removed_from_gm_text(self):
        txt = "Mrok gęstnieje wokół ciebie.\nGrant Item Tajna Mapa Krypty"
        cleaned = turns_api.strip_last_grant_item_cue(txt)
        self.assertEqual(cleaned, "Mrok gęstnieje wokół ciebie.")

