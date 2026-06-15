"""#640 — Narracja walki skrócona do 2-3 zdań.

Kontrakt: blok kontekstu aktywnej walki (`get_combat_context_for_prompt`) niesie
dyrektywę długości narracji „2-3 zdania", która NADPISUJE globalny styl 4-6 zdań.
Poza walką blok nie powstaje (brak dyrektywy). Front/LLM nic nie liczy — to czysty
prompt-context. ZERO zmian mechaniki.
"""

import json
import os
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import combat_service as cs


_SCHEMA = """
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
"""


def _insert_active_combat(db_path: str, campaign_id: int, status: str = "active") -> None:
    conn = sqlite3.connect(db_path)
    combatants = [
        {"id": "player", "name": "Bohater", "type": "player", "hp_current": 20,
         "hp_max": 20, "defense": 12, "conditions": []},
        {"id": "bandit_01", "name": "Bandyta", "type": "enemy", "hp_current": 12,
         "hp_max": 12, "defense": 13, "conditions": []},
    ]
    conn.execute(
        "INSERT INTO active_combat (campaign_id, character_id, round, turn_order, "
        "current_turn, combatants, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (campaign_id, 1, 1, json.dumps(["player", "bandit_01"]), "player",
         json.dumps(combatants), status),
    )
    conn.commit()
    conn.close()


class TestCombatNarrationLength(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_combat_narr_len_test.db"
        if self._tmp.exists():
            self._tmp.unlink()
        conn = sqlite3.connect(str(self._tmp))
        conn.executescript(_SCHEMA)
        conn.close()
        self._p_db = patch.object(cs, "COMBAT_DB_PATH", str(self._tmp))
        self._p_db.start()

    def tearDown(self):
        self._p_db.stop()
        if self._tmp.exists():
            self._tmp.unlink()

    def test_active_combat_block_carries_2_3_sentence_directive(self):
        _insert_active_combat(str(self._tmp), 1)
        block = cs.get_combat_context_for_prompt(1)
        self.assertIsNotNone(block)
        # Dyrektywa długości obecna i wskazuje 2-3 zdania.
        self.assertIn("2-3", block)
        low = block.lower()
        self.assertIn("zdani", low)  # "zdania"/"zdań"
        # Jawnie zaznacza nadpisanie globalnego stylu 4-6.
        self.assertIn("4-6", block)

    def test_no_active_combat_no_directive(self):
        # Brak wiersza walki → blok None → żadnej dyrektywy długości.
        block = cs.get_combat_context_for_prompt(1)
        self.assertIsNone(block)

    def test_ended_combat_no_directive(self):
        _insert_active_combat(str(self._tmp), 1, status="ended")
        block = cs.get_combat_context_for_prompt(1)
        self.assertIsNone(block)


if __name__ == "__main__":
    unittest.main()
