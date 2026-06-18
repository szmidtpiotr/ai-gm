"""Issue #769 — admin-added armor stored with generic slot='armor' is invisible in the
player anatomy doll (no 'armor' cell). Fix: 'armor'/'auto' equip sentinel + admin auto-equip
both derive the anatomical slot from armor_coverage.

Red: equip_item(.., 'armor') for hands-coverage gloves → 'invalid slot'; admin add stores
     slot='armor' (doll can't render).
Green: sentinel auto-picks 'hands' (and head/torso/limbs); _auto_pick_armor_slot maps coverage.
"""

import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import loot_service as ls


_SCHEMA = """
CREATE TABLE characters (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  gold_gp INTEGER NOT NULL DEFAULT 0
);
INSERT INTO characters VALUES (1, 'Eldric', 100);

CREATE TABLE game_config_items (
  key TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  item_type TEXT NOT NULL DEFAULT 'misc',
  description TEXT NOT NULL DEFAULT '',
  value_gp INTEGER NOT NULL DEFAULT 0,
  weight REAL NOT NULL DEFAULT 0.0,
  weight_kg REAL NOT NULL DEFAULT 0.0,
  effect_json TEXT,
  armor_coverage TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  item_data TEXT
);
INSERT INTO game_config_items (key, label, item_type, armor_coverage) VALUES
  ('leather_gloves', 'Skórzane rękawice', 'armor', 'hands'),
  ('leather_armor',  'Skórzana zbroja',   'armor', 'torso'),
  ('leather_cap',    'Skórzany hełm',     'armor', 'head'),
  ('arm_guard',      'Naramiennik',       'armor', 'limb_arm'),
  ('leather_boots',  'Skórzane buty',     'armor', 'feet');

CREATE TABLE game_config_weapons (
  key TEXT PRIMARY KEY, label TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1,
  weapon_slot TEXT, damage_dice TEXT, weight_kg REAL DEFAULT 0
);
CREATE TABLE game_config_consumables (
  key TEXT PRIMARY KEY, label TEXT NOT NULL,
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
  source TEXT,
  meta_json TEXT,
  acquired_at TEXT DEFAULT (datetime('now'))
);
INSERT INTO character_inventory (character_id, item_key, quantity) VALUES
  (1, 'leather_gloves', 1),
  (1, 'leather_armor',  1),
  (1, 'leather_cap',    1),
  (1, 'arm_guard',      1);
"""


class TestArmorAutoSlot(unittest.TestCase):

    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_issue769_auto.db"
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

    def test_sentinel_armor_gloves_to_hands(self):
        """equip_item(.., 'armor') for hands coverage must auto-resolve to slot 'hands'."""
        res = ls.equip_item(1, 1, "armor")
        self.assertEqual(res["slot"], "hands")
        self.assertEqual(res["equipped"], 1)

    def test_sentinel_auto_alias(self):
        """'auto' behaves like 'armor' sentinel."""
        res = ls.equip_item(1, 3, "auto")  # head armor
        self.assertEqual(res["slot"], "head")

    def test_sentinel_body_to_torso(self):
        res = ls.equip_item(1, 2, "armor")
        self.assertEqual(res["slot"], "torso")

    def test_sentinel_limb_picks_free_side(self):
        res = ls.equip_item(1, 4, "armor")  # limb_arm
        self.assertIn(res["slot"], ("l_arm", "r_arm"))

    def test_helper_maps_coverage(self):
        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
        try:
            self.assertEqual(ls._auto_pick_armor_slot(conn, 1, "hands"), "hands")
            self.assertEqual(ls._auto_pick_armor_slot(conn, 1, "head"), "head")
            self.assertEqual(ls._auto_pick_armor_slot(conn, 1, "torso"), "torso")
            self.assertEqual(ls._auto_pick_armor_slot(conn, 1, "full"), "torso")
            self.assertEqual(ls._auto_pick_armor_slot(conn, 1, "limb_leg"), "l_leg")
        finally:
            conn.close()

    def test_helper_rejects_unmapped_coverage(self):
        """feet/back/unknown have no anatomical doll slot → ValueError (caller skips equip)."""
        conn = sqlite3.connect(str(self._tmp))
        conn.row_factory = sqlite3.Row
        try:
            with self.assertRaises(ValueError):
                ls._auto_pick_armor_slot(conn, 1, "feet")
        finally:
            conn.close()

    def test_sentinel_rejected_for_non_armor(self):
        """'armor' sentinel on a non-armor row must raise (no silent generic slot)."""
        conn = sqlite3.connect(str(self._tmp))
        conn.execute(
            "INSERT INTO game_config_consumables (key, label) VALUES ('potion', 'Mikstura')"
        )
        conn.execute(
            "INSERT INTO character_inventory (character_id, consumable_key, quantity) "
            "VALUES (1, 'potion', 1)"
        )
        conn.commit()
        rid = conn.execute(
            "SELECT id FROM character_inventory WHERE consumable_key = 'potion'"
        ).fetchone()[0]
        conn.close()
        with self.assertRaises(ValueError):
            ls.equip_item(1, rid, "armor")


if __name__ == "__main__":
    unittest.main()
