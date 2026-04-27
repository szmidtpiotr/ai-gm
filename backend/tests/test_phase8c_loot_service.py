"""Phase 8C — loot_service basic flow tests."""

import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import loot_service as ls


def _schema_sql() -> str:
    return """
    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL
    );
    INSERT INTO characters (id, name) VALUES (1, 'Hero');

    CREATE TABLE game_config_items (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      item_type TEXT NOT NULL DEFAULT 'misc',
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
    CREATE TABLE game_config_loot_tables (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      gold_min INTEGER NOT NULL DEFAULT 0,
      gold_max INTEGER NOT NULL DEFAULT 0,
      is_active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE game_config_loot_entries (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      loot_table_key TEXT NOT NULL,
      item_key TEXT,
      consumable_key TEXT,
      weapon_key TEXT,
      weight INTEGER NOT NULL DEFAULT 10,
      qty_min INTEGER NOT NULL DEFAULT 1,
      qty_max INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE game_config_enemies (
      key TEXT PRIMARY KEY,
      loot_table_key TEXT,
      drop_chance REAL NOT NULL DEFAULT 1.0
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

    INSERT INTO game_config_items (key, label, item_type, is_active)
    VALUES ('rope', 'Rope', 'misc', 1), ('armor_leather', 'Leather Armor', 'armor', 1);
    INSERT INTO game_config_weapons (key, label, is_active)
    VALUES ('shortsword', 'Short Sword', 1);
    INSERT INTO game_config_consumables (key, label, is_active)
    VALUES ('potion_small', 'Small Potion', 1);

    INSERT INTO game_config_loot_tables (key, label, gold_min, gold_max, is_active) VALUES ('bandit_loot', 'Bandit Loot', 5, 15, 1);
    INSERT INTO game_config_loot_entries (loot_table_key, item_key, consumable_key, weapon_key, weight, qty_min, qty_max)
    VALUES
      ('bandit_loot', 'rope', NULL, NULL, 80, 1, 2),
      ('bandit_loot', NULL, 'potion_small', NULL, 15, 1, 1),
      ('bandit_loot', NULL, NULL, 'shortsword', 5, 1, 1);

    INSERT INTO game_config_enemies (key, loot_table_key, drop_chance)
    VALUES ('bandit', 'bandit_loot', 1.0), ('ghost', NULL, 1.0);
    """


class TestLootService(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_phase8c_loot_test.db"
        if self._tmp.exists():
            self._tmp.unlink()
        conn = sqlite3.connect(str(self._tmp))
        conn.executescript(_schema_sql())
        conn.close()
        self._p_db = patch.object(ls, "LOOT_DB_PATH", str(self._tmp))
        self._p_db.start()

    def tearDown(self):
        self._p_db.stop()
        if self._tmp.exists():
            self._tmp.unlink()

    def test_get_loot_table_for_enemy(self):
        rows = ls.get_loot_table("bandit")
        self.assertEqual(len(rows), 3)
        total = sum(r.get("chance", 0.0) for r in rows)
        self.assertGreater(total, 0.99)
        self.assertLess(total, 1.01)

    def test_roll_loot_missing_table_returns_empty(self):
        self.assertEqual(ls.roll_loot("ghost"), [])
        self.assertEqual(ls.roll_loot("unknown_enemy"), [])

    def test_roll_gold_drop_returns_zero_when_no_table(self):
        self.assertEqual(ls.roll_gold_drop("ghost"), 0)
        self.assertEqual(ls.roll_gold_drop("unknown_enemy"), 0)

    @patch("app.services.loot_service.random.randint", return_value=11)
    def test_roll_gold_drop_within_range(self, _randint):
        g = ls.roll_gold_drop("bandit")
        self.assertGreaterEqual(g, 5)
        self.assertLessEqual(g, 15)

    @patch("app.services.loot_service.random.random", side_effect=[0.10, 0.90, 0.04])
    @patch("app.services.loot_service.random.randint", side_effect=[2, 1])
    def test_roll_loot_rolls_each_entry_independently(self, _randint, _random):
        rolled = ls.roll_loot("bandit")
        self.assertEqual(len(rolled), 2)
        self.assertEqual(rolled[0].get("item_key"), "rope")
        self.assertEqual(int(rolled[0].get("quantity") or 0), 2)
        self.assertEqual(rolled[1].get("weapon_key"), "shortsword")
        self.assertEqual(int(rolled[1].get("quantity") or 0), 1)

    def test_grant_loot_stacks_item_and_consumable(self):
        granted = ls.grant_loot_to_character(
            1,
            [
                {"item_key": "rope", "quantity": 1},
                {"item_key": "rope", "quantity": 2},
                {"consumable_key": "potion_small", "quantity": 1},
                {"consumable_key": "potion_small", "quantity": 2},
            ],
        )
        self.assertEqual(len(granted), 4)
        inv = ls.get_character_inventory(1)
        rope = next(x for x in inv if x["item_type"] == "misc")
        pot = next(x for x in inv if x["item_type"] == "consumable")
        self.assertEqual(rope["quantity"], 3)
        self.assertEqual(pot["quantity"], 3)

    def test_grant_weapon_inserts_separate_rows(self):
        ls.grant_loot_to_character(
            1,
            [{"weapon_key": "shortsword", "quantity": 1}, {"weapon_key": "shortsword", "quantity": 1}],
        )
        inv = [x for x in ls.get_character_inventory(1) if x["item_type"] == "weapon"]
        self.assertEqual(len(inv), 2)

    def test_grant_missing_character_raises(self):
        with self.assertRaises(ValueError):
            ls.grant_loot_to_character(999, [{"item_key": "rope", "quantity": 1}])

    def test_equip_item_sets_slot_and_unequips_previous(self):
        ls.grant_loot_to_character(
            1,
            [{"weapon_key": "shortsword", "quantity": 1}, {"item_key": "armor_leather", "quantity": 1}],
        )
        inv = ls.get_character_inventory(1)
        weapon = next(x for x in inv if x["item_type"] == "weapon")
        armor = next(x for x in inv if x["item_type"] == "armor")

        updated_weapon = ls.equip_item(1, int(weapon["id"]), "main_hand")
        self.assertEqual(updated_weapon["slot"], "main_hand")
        self.assertEqual(updated_weapon["equipped"], 1)

        updated_armor = ls.equip_item(1, int(armor["id"]), "armor")
        self.assertEqual(updated_armor["slot"], "armor")
        self.assertEqual(updated_armor["equipped"], 1)

    def test_equip_item_rejects_invalid_slot(self):
        ls.grant_loot_to_character(1, [{"weapon_key": "shortsword", "quantity": 1}])
        inv_id = int(ls.get_character_inventory(1)[0]["id"])
        with self.assertRaises(ValueError):
            ls.equip_item(1, inv_id, "helmet")

    def test_equip_item_rejects_literal_invalid_slot_string(self):
        """Same rule as ``helmet`` — slot must be in main_hand/off_hand/armor (doc: invalid_slot)."""
        ls.grant_loot_to_character(1, [{"weapon_key": "shortsword", "quantity": 1}])
        inv_id = int(ls.get_character_inventory(1)[0]["id"])
        with self.assertRaises(ValueError) as ctx:
            ls.equip_item(1, inv_id, "invalid_slot")
        self.assertIn("invalid slot", str(ctx.exception).lower())

    def test_xor_constraint_raises(self):
        conn = sqlite3.connect(str(self._tmp))
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                conn.execute("PRAGMA check_constraint = ON")
            except sqlite3.OperationalError:
                pass
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO character_inventory
                    (character_id, item_key, weapon_key, consumable_key, quantity, equipped, slot, source)
                    VALUES (1, 'rope', 'shortsword', NULL, 1, 0, NULL, 'test')
                    """
                )
                conn.commit()
        finally:
            conn.close()

    @patch("app.services.loot_service.logger")
    def test_grant_loot_skips_unknown_key_with_warning(self, mock_logger: MagicMock):
        granted = ls.grant_loot_to_character(1, [{"item_key": "totally_unknown_catalog_key", "quantity": 1}])
        self.assertEqual(granted, [])
        self.assertEqual(ls.get_character_inventory(1), [])
        mock_logger.warning.assert_called()
        call_kw = mock_logger.warning.call_args[1]
        self.assertEqual(call_kw.get("character_id"), 1)
