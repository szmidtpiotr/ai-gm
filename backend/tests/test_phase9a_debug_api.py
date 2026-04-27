"""Phase 9A-1 — debug API tests."""

import os
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.routers import debug as debug_api


def _schema_sql() -> str:
    return """
    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      location TEXT,
      sheet_json TEXT,
      gold_gp INTEGER NOT NULL DEFAULT 0
    );
    INSERT INTO characters (id, location, sheet_json, gold_gp)
    VALUES (1, 'StartTown', '{"current_hp": 9, "max_hp": 12, "quests_completed": ["intro"], "quests_active": ["main_quest"]}', 23);

    CREATE TABLE character_inventory (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      character_id INTEGER NOT NULL,
      item_key TEXT,
      weapon_key TEXT,
      consumable_key TEXT,
      slot TEXT
    );
    INSERT INTO character_inventory (character_id, item_key, slot) VALUES (1, 'rope', NULL);
    INSERT INTO character_inventory (character_id, weapon_key, slot) VALUES (1, 'shortsword', 'main_hand');

    CREATE TABLE campaign_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      turn_number INTEGER NOT NULL,
      route TEXT,
      user_text TEXT,
      assistant_text TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE debug_validation_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      test_run_id TEXT NOT NULL,
      event TEXT NOT NULL,
      is_legal INTEGER NOT NULL DEFAULT 1,
      reason TEXT,
      old_state TEXT,
      new_state TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """


def _make_client_with_flag() -> TestClient:
    app = FastAPI()
    if os.getenv("AI_TEST_MODE") == "1":
        app.include_router(debug_api.router, prefix="/api")
    return TestClient(app)


class TestPhase9ADebugApi(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_phase9a_debug_api.db"
        if self._tmp.exists():
            self._tmp.unlink()
        conn = sqlite3.connect(str(self._tmp))
        conn.executescript(_schema_sql())
        conn.close()
        self._p_db = patch.object(debug_api, "DB_PATH", str(self._tmp))
        self._p_db.start()

    def tearDown(self):
        self._p_db.stop()
        if self._tmp.exists():
            self._tmp.unlink()

    def test_debug_disabled_without_env_flag(self):
        with patch.dict(os.environ, {"AI_TEST_MODE": "0"}):
            client = _make_client_with_flag()
            r = client.get("/api/debug/player_state?character_id=1")
            self.assertEqual(r.status_code, 404)

    def test_player_state_returns_correct_data(self):
        with patch.dict(os.environ, {"AI_TEST_MODE": "1"}):
            client = _make_client_with_flag()
            r = client.get("/api/debug/player_state?character_id=1")
            self.assertEqual(r.status_code, 200, r.text)
            body = r.json()
            self.assertEqual(body["character_id"], 1)
            self.assertEqual(body["location"], "StartTown")
            self.assertEqual(body["hp"], 9)
            self.assertEqual(body["max_hp"], 12)
            self.assertEqual(body["gold_gp"], 23)
            self.assertEqual(len(body["inventory"]), 2)
            self.assertEqual(body["quests_completed"], ["intro"])
            self.assertEqual(body["quests_active"], ["main_quest"])

    def test_gm_decisions_empty_session(self):
        with patch.dict(os.environ, {"AI_TEST_MODE": "1"}):
            client = _make_client_with_flag()
            r = client.get("/api/debug/gm_decisions?session_id=999&limit=20")
            self.assertEqual(r.status_code, 200, r.text)
            body = r.json()
            self.assertEqual(body["session_id"], "999")
            self.assertEqual(body["decisions"], [])

    def test_validation_flags_empty_run(self):
        with patch.dict(os.environ, {"AI_TEST_MODE": "1"}):
            client = _make_client_with_flag()
            r = client.get("/api/debug/validation_flags?test_run_id=run-empty")
            self.assertEqual(r.status_code, 200, r.text)
            body = r.json()
            self.assertEqual(body["test_run_id"], "run-empty")
            self.assertEqual(body["flags"], [])
