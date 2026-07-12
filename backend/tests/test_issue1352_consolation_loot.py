"""TDD: Issue #1352 (WALKA-T6) — gwarantowany drop minimalny + znacznik rolled/consolation.

Po zwycięstwie loot modal ma być ZAWSZE niepusty. Gdy losowanie wroga daje zero
(nietrafiony drop_chance albo każdy wpis spudłował), `roll_loot_with_consolation`
dorzuca jedną pozycję z puli narracyjnych drobiazgów (`loot_trash_common`),
oznaczoną `origin='consolation'`. Trafione łupy z tabeli wroga → `origin='rolled'`.

Czyste, izolowane od /data: temp sqlite + patch LOOT_DB_PATH (wzór z #1333).
"""

import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import loot_service as ls


_SCHEMA = """
CREATE TABLE game_config_loot_tables (
  key TEXT PRIMARY KEY, label TEXT, description TEXT DEFAULT '',
  is_active INTEGER DEFAULT 1, gold_min INTEGER DEFAULT 0, gold_max INTEGER DEFAULT 0
);
CREATE TABLE game_config_loot_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  loot_table_key TEXT NOT NULL,
  item_key TEXT, consumable_key TEXT, weapon_key TEXT,
  weight INTEGER DEFAULT 10, qty_min INTEGER DEFAULT 1, qty_max INTEGER DEFAULT 1
);
CREATE TABLE game_config_enemies (
  key TEXT PRIMARY KEY, loot_table_key TEXT, drop_chance REAL DEFAULT 1.0,
  tier TEXT DEFAULT 'standard', loot_tier TEXT
);
CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, label TEXT, is_active INTEGER DEFAULT 1, allowed_classes TEXT);

-- per-enemy table (only a single low-weight entry so a miss is easy to force)
INSERT INTO game_config_loot_tables (key, label) VALUES ('loot_bandit', 'Bandyta');
INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES ('loot_bandit', 'rusty_dagger', 20, 1, 1);

-- consolation pool (T6)
INSERT INTO game_config_loot_tables (key, label) VALUES ('loot_trash_common', 'Drobiazgi');
INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES ('loot_trash_common', 'broken_pouch', 100, 1, 1),
       ('loot_trash_common', 'chipped_knife', 100, 1, 1);

-- enemies
INSERT INTO game_config_enemies (key, loot_table_key, drop_chance, tier) VALUES
  ('bandit', 'loot_bandit', 0.8, 'standard'),
  ('bandit_nodrop', 'loot_bandit', 0.0, 'standard');
"""

_CONSOLATION_KEYS = {"broken_pouch", "chipped_knife"}


def _key(entry):
    return entry.get("weapon_key") or entry.get("item_key") or entry.get("consumable_key")


class TestConsolationLoot(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_issue1352_loot.db"
        if self._tmp.exists():
            self._tmp.unlink()
        conn = sqlite3.connect(str(self._tmp))
        conn.executescript(_SCHEMA)
        conn.close()
        self._p = patch.object(ls, "LOOT_DB_PATH", str(self._tmp))
        self._p.start()

    def tearDown(self):
        self._p.stop()
        if self._tmp.exists():
            self._tmp.unlink()

    # ─── Test główny — pudło drop_chance → consolation ──────────────────────────

    def test_empty_roll_yields_consolation(self):
        """drop_chance=0.0 (pewne pudło) → wrapper zwraca 1 pozycję consolation."""
        rolled = ls.roll_loot_with_consolation("bandit_nodrop")
        self.assertTrue(rolled, "pool nie może być pusty po zwycięstwie (#1352)")
        self.assertTrue(
            all(e.get("origin") == "consolation" for e in rolled),
            "przy pustym losowaniu wszystkie pozycje muszą być consolation",
        )
        self.assertIn(_key(rolled[0]), _CONSOLATION_KEYS)

    @patch("app.services.loot_service.random.random",
           side_effect=[0.0,    # drop_chance gate pass
                        0.99])  # rusty_dagger -> miss (empty roll)
    @patch("app.services.loot_service.random.randint", return_value=1)
    def test_all_entries_miss_yields_consolation(self, _ri, _rr):
        """Gate przechodzi, ale każdy wpis pudłuje → i tak dostajemy consolation."""
        rolled = ls.roll_loot_with_consolation("bandit")
        self.assertTrue(rolled)
        self.assertEqual(rolled[0].get("origin"), "consolation")

    # ─── Trafiony łup → origin='rolled', bez consolation ────────────────────────

    @patch("app.services.loot_service.random.random",
           side_effect=[0.0,    # drop_chance gate pass
                        0.0])    # rusty_dagger -> hit
    @patch("app.services.loot_service.random.randint", return_value=1)
    def test_real_drop_marked_rolled(self, _ri, _rr):
        """Trafiony łup z tabeli wroga → origin='rolled', brak consolation."""
        rolled = ls.roll_loot_with_consolation("bandit")
        keys = [_key(e) for e in rolled]
        self.assertIn("rusty_dagger", keys)
        self.assertTrue(all(e.get("origin") == "rolled" for e in rolled))
        self.assertNotIn("broken_pouch", keys)
        self.assertNotIn("chipped_knife", keys)

    # ─── Backward compat — czyste roll_loot niezmienione ────────────────────────

    def test_plain_roll_loot_still_empty_on_miss(self):
        """Stare roll_loot() NADAL zwraca [] przy pudle (kontrakt #568 niezmieniony)."""
        self.assertEqual(ls.roll_loot("bandit_nodrop"), [])

    def test_blank_key_returns_empty(self):
        """Pusty/nieznany klucz → [] (bez consolation dla nie-wroga)."""
        self.assertEqual(ls.roll_loot_with_consolation(""), [])
        self.assertEqual(ls.roll_loot_with_consolation(None), [])


if __name__ == "__main__":
    unittest.main()
