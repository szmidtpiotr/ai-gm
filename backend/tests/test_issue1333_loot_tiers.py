"""BL-B1 (#1333) — tier loot tables + per-enemy uniques union.

Covers:
- get_loot_table() returns UNION of per-enemy table + tier table
- de-dup by catalog key (per-enemy signature entry wins on collision)
- tier resolved from enemy.loot_tier override, else enemy.tier enum
- graceful no-op when tier table missing / tier unknown
- roll_loot() drops from the tier portion of the union
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

-- per-enemy unique table (signature drop: trophy + bandage collision)
INSERT INTO game_config_loot_tables (key, label) VALUES ('loot_orc', 'Orc');
INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES ('loot_orc', 'orc_tusk_trophy', 50, 1, 1),
       ('loot_orc', 'bandage', 99, 1, 1);   -- collides with tier 'bandage'

-- shared tier tables
INSERT INTO game_config_loot_tables (key, label) VALUES
  ('loot_tier_standard', 'Tier standard'), ('loot_tier_boss', 'Tier boss');
INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES ('loot_tier_standard', 'bandage', 40, 1, 1),
       ('loot_tier_standard', 'torch', 30, 1, 1),
       ('loot_tier_boss', 'potion_healing_standard', 45, 1, 1);

-- enemies
INSERT INTO game_config_enemies (key, loot_table_key, tier, loot_tier) VALUES
  ('orc', 'loot_orc', 'standard', NULL),          -- resolves via tier enum
  ('orc_boss', 'loot_orc', 'standard', 'boss'),   -- loot_tier override wins
  ('orc_odd', 'loot_orc', 'mythic', NULL),        -- unknown tier -> no tier table
  ('orc_poor', 'loot_orc', 'standard', 'poor');   -- polluted loot_tier -> fall back to tier enum
"""


class TestLootTiers(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_issue1333_loot.db"
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

    def _keys(self, rows):
        return [r.get("weapon_key") or r.get("item_key") or r.get("consumable_key") for r in rows]

    def test_union_per_enemy_plus_tier(self):
        rows = ls.get_loot_table("orc")
        keys = self._keys(rows)
        # per-enemy uniques + tier generics, deduped
        self.assertIn("orc_tusk_trophy", keys)
        self.assertIn("bandage", keys)
        self.assertIn("torch", keys)  # from tier table
        # no duplicate 'bandage' despite being in both tables
        self.assertEqual(keys.count("bandage"), 1)

    def test_dedup_per_enemy_weight_wins(self):
        rows = ls.get_loot_table("orc")
        bandage = next(r for r in rows if r.get("item_key") == "bandage")
        # per-enemy weight 99 (chance ~1.0), not the tier weight 40
        self.assertGreater(bandage["chance"], 0.9)

    def test_loot_tier_override_beats_enemy_tier(self):
        rows = ls.get_loot_table("orc_boss")
        keys = self._keys(rows)
        # boss override -> boss tier table, NOT standard
        self.assertIn("potion_healing_standard", keys)
        self.assertNotIn("torch", keys)

    def test_unknown_tier_no_tier_table(self):
        rows = ls.get_loot_table("orc_odd")
        keys = self._keys(rows)
        # only per-enemy entries survive
        self.assertIn("orc_tusk_trophy", keys)
        self.assertNotIn("torch", keys)
        self.assertNotIn("potion_healing_standard", keys)

    def test_polluted_loot_tier_falls_back_to_enemy_tier(self):
        # loot_tier='poor' (dungeon word, not a tier band) -> use tier='standard'
        rows = ls.get_loot_table("orc_poor")
        keys = self._keys(rows)
        self.assertIn("torch", keys)          # standard tier table applied
        self.assertNotIn("potion_healing_standard", keys)  # not boss

    @patch("app.services.loot_service.random.random",
           side_effect=[0.0,    # drop_chance gate pass
                        0.99,   # orc_tusk_trophy -> skip
                        0.0,    # bandage -> hit
                        0.0,    # torch -> hit
                        ])
    @patch("app.services.loot_service.random.randint", return_value=1)
    def test_roll_loot_includes_tier_drop(self, _ri, _rr):
        rolled = ls.roll_loot("orc")
        keys = [r.get("weapon_key") or r.get("item_key") or r.get("consumable_key") for r in rolled]
        self.assertIn("torch", keys)   # tier entry actually dropped
        self.assertIn("bandage", keys)


if __name__ == "__main__":
    unittest.main()
