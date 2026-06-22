"""Issue #743 — armor_coverage='hands' raises ValueError in equip_item.

Red: equip_item raises ValueError / 'invalid slot' before fix.
Green: hands slot added; equip works, inventory reflects slot='hands'.
"""

import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql

from app.services import loot_service as ls


_SCHEMA = """
CREATE TABLE characters (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  gold_gp INTEGER NOT NULL DEFAULT 0
);
INSERT INTO characters VALUES (1, 'Eldric', 100);

""" + table_sql("game_config_items") + """
INSERT INTO game_config_items (key, label, item_type, armor_coverage)
  VALUES ('leather_gloves', 'Skórzane rękawice', 'armor', 'hands');
INSERT INTO game_config_items (key, label, item_type, armor_coverage)
  VALUES ('plate_gauntlets', 'Stalowe rękawice płytowe', 'armor', 'hands');
INSERT INTO game_config_items (key, label, item_type, armor_coverage)
  VALUES ('leather_helmet', 'Skórzany helm', 'armor', 'head');

""" + table_sql("game_config_weapons") + """
""" + table_sql("game_config_consumables") + """

CREATE TABLE character_inventory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id INTEGER NOT NULL,
  item_key TEXT,
  weapon_key TEXT,
  consumable_key TEXT,
  quantity INTEGER NOT NULL DEFAULT 1,
  equipped INTEGER NOT NULL DEFAULT 0,
  slot TEXT,
  source TEXT,
  meta_json TEXT,
  acquired_at TEXT DEFAULT (datetime('now'))
);
INSERT INTO character_inventory (character_id, item_key, quantity)
  VALUES (1, 'leather_gloves', 1);
INSERT INTO character_inventory (character_id, item_key, quantity)
  VALUES (1, 'plate_gauntlets', 1);
INSERT INTO character_inventory (character_id, item_key, quantity)
  VALUES (1, 'leather_helmet', 1);
"""


class TestHandsSlotEquip(unittest.TestCase):

    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_issue743_hands.db"
        if self._tmp.exists():
            self._tmp.unlink()
        conn = sqlite3.connect(str(self._tmp))
        conn.executescript(_SCHEMA)
        conn.close()
        self._patch = patch.object(ls, "LOOT_DB_PATH", str(self._tmp))
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        if self._tmp.exists():
            self._tmp.unlink()

    def test_leather_gloves_equip_to_hands(self):
        """leather_gloves with armor_coverage='hands' must equip to slot 'hands'."""
        result = ls.equip_item(1, 1, "hands")
        self.assertEqual(result["slot"], "hands")
        self.assertEqual(result["equipped"], 1)

    def test_plate_gauntlets_equip_to_hands(self):
        """plate_gauntlets with armor_coverage='hands' must equip to slot 'hands'."""
        result = ls.equip_item(1, 2, "hands")
        self.assertEqual(result["slot"], "hands")
        self.assertEqual(result["equipped"], 1)

    def test_hands_not_valid_for_head_armor(self):
        """head armor must NOT be equipable in hands slot."""
        with self.assertRaises(ValueError):
            ls.equip_item(1, 3, "hands")

    def test_hands_coverage_not_valid_for_head_slot(self):
        """hands armor must NOT be equipable in head slot."""
        with self.assertRaises(ValueError):
            ls.equip_item(1, 1, "head")

    def test_hands_in_slot_values(self):
        """'hands' must be present in _SLOT_VALUES."""
        self.assertIn("hands", ls._SLOT_VALUES)

    def test_hands_in_armor_coverage(self):
        """'hands' must be present in _ARMOR_COVERAGE_TO_SLOTS."""
        self.assertIn("hands", ls._ARMOR_COVERAGE_TO_SLOTS)

    def test_hands_in_valid_coverage(self):
        """'hands' must be present in _VALID_ARMOR_COVERAGE."""
        self.assertIn("hands", ls._VALID_ARMOR_COVERAGE)

    def test_no_regression_other_slots(self):
        """Equipping head armor to head must still work."""
        result = ls.equip_item(1, 3, "head")
        self.assertEqual(result["slot"], "head")
        self.assertEqual(result["equipped"], 1)


if __name__ == "__main__":
    unittest.main()
