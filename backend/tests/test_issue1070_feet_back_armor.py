"""Issue #1070 — armor_coverage 'feet' (buty) and 'back' (płaszcz) rejected by validation;
player anatomy doll has no cell for them. Entire item class (boots, cloaks) was dead content.

Red: equip_item(.., 'feet'/'back') → 'invalid armor_coverage'; admin_config item create/update
     with coverage='feet'/'back' → 'invalid_armor_coverage'.
Green: both coverages get real anatomical slots ('feet'/'back'), equip + admin validation accept
       them, and the 'armor'/'auto' sentinel auto-resolves to the right slot.
"""

import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql

from app.services import loot_service as ls
from app.services import admin_config as ac
from app.routers import admin_cheat as ach


_SCHEMA = """
CREATE TABLE characters (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  gold_gp INTEGER NOT NULL DEFAULT 0
);
INSERT INTO characters VALUES (1, 'Eldric', 100);

""" + table_sql("game_config_items") + """
INSERT INTO game_config_items (key, label, item_type, armor_coverage) VALUES
  ('leather_boots', 'Skórzane buty',   'armor', 'feet'),
  ('travel_cloak',  'Płaszcz podróżny', 'armor', 'back'),
  ('leather_cap',   'Skórzany hełm',    'armor', 'head');

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
INSERT INTO character_inventory (character_id, item_key, quantity) VALUES
  (1, 'leather_boots', 1),
  (1, 'travel_cloak',  1),
  (1, 'leather_cap',   1);
"""


class TestFeetBackArmorEquip(unittest.TestCase):

    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_issue1070_feetback.db"
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

    def test_equip_boots_to_feet_slot(self):
        res = ls.equip_item(1, 1, "feet")
        self.assertEqual(res["slot"], "feet")
        self.assertEqual(res["equipped"], 1)

    def test_equip_cloak_to_back_slot(self):
        res = ls.equip_item(1, 2, "back")
        self.assertEqual(res["slot"], "back")
        self.assertEqual(res["equipped"], 1)

    def test_boots_reject_wrong_slot(self):
        with self.assertRaises(ValueError):
            ls.equip_item(1, 1, "torso")

    def test_sentinel_armor_boots_auto_to_feet(self):
        """'armor'/'auto' sentinel must auto-resolve feet coverage to slot 'feet'."""
        res = ls.equip_item(1, 1, "armor")
        self.assertEqual(res["slot"], "feet")

    def test_sentinel_armor_cloak_auto_to_back(self):
        res = ls.equip_item(1, 2, "auto")
        self.assertEqual(res["slot"], "back")

    def test_helper_maps_feet_and_back(self):
        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
        try:
            self.assertEqual(ls._auto_pick_armor_slot(conn, 1, "feet"), "feet")
            self.assertEqual(ls._auto_pick_armor_slot(conn, 1, "back"), "back")
        finally:
            conn.close()

    def test_backward_compat_head_still_works(self):
        """Pre-existing coverage kinds unaffected by this change."""
        res = ls.equip_item(1, 3, "head")
        self.assertEqual(res["slot"], "head")


class TestAdminCheatAutoEquipFeetBack(unittest.TestCase):
    """A third copy of the coverage→slot map lives in admin_cheat.py (cheat 'add item'
    auto-equip). Same class of gap — must stay in sync with loot_service."""

    def test_armor_auto_slot_maps_feet_and_back(self):
        self.assertEqual(ach._armor_auto_slot(None, 1, "feet"), "feet")
        self.assertEqual(ach._armor_auto_slot(None, 1, "back"), "back")

    def test_armor_auto_slot_backward_compat(self):
        self.assertEqual(ach._armor_auto_slot(None, 1, "head"), "head")
        self.assertEqual(ach._armor_auto_slot(None, 1, "hands"), "hands")
        self.assertEqual(ach._armor_auto_slot(None, 1, "torso"), "torso")
        self.assertEqual(ach._armor_auto_slot(None, 1, "full"), "torso")
        self.assertIsNone(ach._armor_auto_slot(None, 1, "unknown_coverage"))


class TestAdminConfigFeetBackValidation(unittest.TestCase):
    """admin_config.py has its own copy of _VALID_ARMOR_COVERAGE (create/update item)."""

    def test_valid_armor_coverage_includes_feet_and_back(self):
        self.assertIn("feet", ac._VALID_ARMOR_COVERAGE)
        self.assertIn("back", ac._VALID_ARMOR_COVERAGE)
        # 'hands' was already equip-able (loot_service) but missing from this
        # second copy — same class of gap, closed alongside feet/back.
        self.assertIn("hands", ac._VALID_ARMOR_COVERAGE)

    def test_backward_compat_existing_coverages_still_valid(self):
        for cov in ("head", "torso", "limb_arm", "limb_leg", "full"):
            self.assertIn(cov, ac._VALID_ARMOR_COVERAGE)


if __name__ == "__main__":
    unittest.main()
