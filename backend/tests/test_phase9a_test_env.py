"""Phase 9A-2 — isolated test environment tests."""

import importlib
import json
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
from scripts import seed_ai_test_env as seed_script


def _schema_sql() -> str:
    return """
    CREATE TABLE users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      display_name TEXT NOT NULL,
      is_active INTEGER NOT NULL DEFAULT 1,
      is_admin INTEGER NOT NULL DEFAULT 0
    );
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
      epitaph TEXT
    );
    CREATE TABLE campaign_members (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      role TEXT NOT NULL DEFAULT 'player',
      UNIQUE(campaign_id, user_id)
    );
    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      system_id TEXT NOT NULL,
      sheet_json TEXT NOT NULL,
      location TEXT,
      is_active INTEGER NOT NULL DEFAULT 1,
      gold_gp INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE campaign_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      character_id INTEGER NOT NULL,
      user_text TEXT NOT NULL,
      route TEXT NOT NULL,
      assistant_text TEXT,
      turn_number INTEGER NOT NULL
    );
    CREATE TABLE game_sessions (
      id TEXT PRIMARY KEY,
      campaign_id INTEGER,
      test_run_id TEXT
    );
    CREATE TABLE debug_validation_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      test_run_id TEXT NOT NULL,
      event TEXT NOT NULL,
      is_legal INTEGER NOT NULL DEFAULT 1,
      reason TEXT,
      old_state TEXT,
      new_state TEXT
    );
    """


class TestPhase9ATestEnv(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_phase9a_test_env.db"
        self._cfg = Path(__file__).resolve().parent / "_phase9a_ai_test_config.json"
        if self._tmp.exists():
            self._tmp.unlink()
        if self._cfg.exists():
            self._cfg.unlink()
        conn = sqlite3.connect(str(self._tmp))
        conn.executescript(_schema_sql())
        conn.close()
        self._p_db_debug = patch.object(debug_api, "DB_PATH", str(self._tmp))
        self._p_db_debug.start()
        self._p_db_seed = patch.dict(
            os.environ,
            {
                "AI_TEST_MODE": "1",
                "AI_TEST_DB_PATH": str(self._tmp),
                "AI_TEST_CONFIG_PATH": str(self._cfg),
            },
        )
        self._p_db_seed.start()

    def tearDown(self):
        self._p_db_debug.stop()
        self._p_db_seed.stop()
        if self._tmp.exists():
            self._tmp.unlink()
        if self._cfg.exists():
            self._cfg.unlink()

    def test_seed_creates_player_and_character(self):
        out = seed_script.seed()
        self.assertTrue(self._cfg.exists())
        payload = json.loads(self._cfg.read_text(encoding="utf-8"))
        self.assertEqual(payload["player_id"], out["player_id"])
        self.assertEqual(payload["character_id"], out["character_id"])
        conn = sqlite3.connect(str(self._tmp))
        try:
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            chars = conn.execute("SELECT COUNT(*) FROM characters").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(users, 2)
        self.assertEqual(chars, 1)

    def test_ai_test_mode_uses_separate_db(self):
        with patch.dict(
            os.environ,
            {"AI_TEST_MODE": "1", "AI_TEST_DB_PATH": "/tmp/custom_ai_test.db", "DATABASE_URL": "sqlite:////data/ignored.db"},
            clear=False,
        ):
            import app.db as dbmod
            dbmod = importlib.reload(dbmod)
            self.assertEqual(dbmod.DATABASE_URL, "sqlite:////tmp/custom_ai_test.db")

    def test_reset_endpoint_clears_messages(self):
        out = seed_script.seed()
        campaign_id = out["campaign_id"]
        character_id = out["character_id"]
        conn = sqlite3.connect(str(self._tmp))
        try:
            conn.execute(
                """
                INSERT INTO campaign_turns (campaign_id, character_id, user_text, route, assistant_text, turn_number)
                VALUES (?, ?, 'u', 'narrative', 'a', 1)
                """,
                (campaign_id, character_id),
            )
            conn.execute(
                "INSERT INTO game_sessions (id, campaign_id, test_run_id) VALUES ('sess-1', ?, 'ai_test_run_1')",
                (campaign_id,),
            )
            conn.execute(
                """
                INSERT INTO debug_validation_log (test_run_id, event, is_legal, reason, old_state, new_state)
                VALUES ('ai_test_run_1', 'LOCATION_CHANGE', 1, 'ok', '{}', '{}')
                """
            )
            conn.commit()
        finally:
            conn.close()
        app = FastAPI()
        app.include_router(debug_api.router, prefix="/api")
        client = TestClient(app)
        r = client.post("/api/debug/reset_test_env")
        self.assertEqual(r.status_code, 200, r.text)
        conn = sqlite3.connect(str(self._tmp))
        try:
            turns = conn.execute("SELECT COUNT(*) FROM campaign_turns WHERE campaign_id = ?", (campaign_id,)).fetchone()[0]
            flags = conn.execute("SELECT COUNT(*) FROM debug_validation_log WHERE test_run_id = 'ai_test_run_1'").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(turns, 0)
        self.assertEqual(flags, 0)

    def test_reset_does_not_delete_character(self):
        out = seed_script.seed()
        campaign_id = out["campaign_id"]
        character_id = out["character_id"]
        conn = sqlite3.connect(str(self._tmp))
        try:
            conn.execute(
                "UPDATE characters SET sheet_json = ?, location = ? WHERE id = ?",
                (json.dumps({"current_hp": 3, "max_hp": 10}), "Dungeon", character_id),
            )
            conn.execute(
                "UPDATE campaigns SET status = 'ended', death_reason = 'x', ended_at = 'now', epitaph = 'rip' WHERE id = ?",
                (campaign_id,),
            )
            conn.commit()
        finally:
            conn.close()
        app = FastAPI()
        app.include_router(debug_api.router, prefix="/api")
        client = TestClient(app)
        r = client.post("/api/debug/reset_test_env")
        self.assertEqual(r.status_code, 200, r.text)
        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
        try:
            char_row = conn.execute("SELECT sheet_json, location FROM characters WHERE id = ?", (character_id,)).fetchone()
            camp_row = conn.execute("SELECT status, death_reason, ended_at, epitaph FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(char_row)
        sheet = json.loads(char_row["sheet_json"])
        self.assertEqual(int(sheet.get("current_hp", 0)), 10)
        self.assertEqual(char_row["location"], "Start")
        self.assertEqual(camp_row["status"], "active")
        self.assertIsNone(camp_row["death_reason"])
