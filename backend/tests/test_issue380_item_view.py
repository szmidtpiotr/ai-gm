"""TDD: Issue #380 (D5) — Item VIEW (podgląd przedmiotu w inventory).

Gracz klika przedmiot → modal z pełnym opisem. Backend musi udostępnić pełne
detale per typ: broń (damage_die, linked_stat), zbroja (ac_bonus), konsumpcja
(effect), + wspólne (nazwa, opis, typ, wartość). Lista inventory ich nie zwraca.
"""
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import loot_service as ls


def _make_db(tmp: Path) -> None:
    conn = sqlite3.connect(str(tmp))
    conn.executescript(
        """
        CREATE TABLE characters (id INTEGER PRIMARY KEY, name TEXT);
        INSERT INTO characters (id, name) VALUES (7, 'Hero');

        CREATE TABLE game_config_weapons (
          key TEXT PRIMARY KEY, label TEXT, weapon_type TEXT, damage_die TEXT,
          linked_stat TEXT, description TEXT, value_gp INTEGER DEFAULT 0, note TEXT
        );
        INSERT INTO game_config_weapons (key,label,weapon_type,damage_die,linked_stat,description,value_gp,note)
        VALUES ('rusty_sword','Zardzewiały miecz','melee','1d8','STR','Stary, ale ostry.',12,'krwawienie');

        CREATE TABLE game_config_items (
          key TEXT PRIMARY KEY, label TEXT, item_type TEXT, description TEXT,
          value_gp INTEGER DEFAULT 0, ac_bonus INTEGER DEFAULT 0, armor_coverage TEXT,
          effect_type TEXT, effect_dice TEXT, effect_bonus INTEGER DEFAULT 0,
          effect_target TEXT, note TEXT
        );
        INSERT INTO game_config_items (key,label,item_type,description,value_gp,ac_bonus,armor_coverage)
        VALUES ('leather_armor','Skórzana zbroja','armor','Lekka ochrona torsu.',20,2,'torso');

        CREATE TABLE game_config_consumables (
          key TEXT PRIMARY KEY, label TEXT, description TEXT, effect_type TEXT,
          effect_dice TEXT, effect_bonus INTEGER DEFAULT 0, effect_target TEXT,
          base_price INTEGER DEFAULT 0, note TEXT
        );
        INSERT INTO game_config_consumables (key,label,description,effect_type,effect_dice,effect_target,base_price)
        VALUES ('health_potion','Mikstura zdrowia','Przywraca HP.','heal','2d4','self',15);

        CREATE TABLE character_inventory (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          character_id INTEGER NOT NULL,
          label TEXT, item_key TEXT, weapon_key TEXT, consumable_key TEXT,
          quantity INTEGER DEFAULT 1, equipped INTEGER DEFAULT 0,
          slot TEXT, acquired_at TEXT, source TEXT, meta_json TEXT
        );
        INSERT INTO character_inventory (id,character_id,weapon_key,quantity,equipped) VALUES (1,7,'rusty_sword',1,1);
        INSERT INTO character_inventory (id,character_id,item_key,quantity) VALUES (2,7,'leather_armor',1);
        INSERT INTO character_inventory (id,character_id,consumable_key,quantity) VALUES (3,7,'health_potion',3);
        INSERT INTO character_inventory (id,character_id,item_key,label,meta_json,quantity)
        VALUES (4,7,'__narrative__','Amulet Babci','{"description":"Pamiątka rodzinna."}',1);
        """
    )
    conn.commit()
    conn.close()


class TestItemDetail(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_d5_itemview.db"
        if self._tmp.exists():
            self._tmp.unlink()
        _make_db(self._tmp)
        self._p = patch.object(ls, "LOOT_DB_PATH", str(self._tmp))
        self._p.start()

    def tearDown(self):
        self._p.stop()
        if self._tmp.exists():
            self._tmp.unlink()

    def test_weapon_detail(self):
        d = ls.get_inventory_item_detail(7, 1)
        self.assertEqual(d["kind"], "weapon")
        self.assertEqual(d["name"], "Zardzewiały miecz")
        self.assertEqual(d["weapon"]["damage_die"], "1d8")
        self.assertEqual(d["weapon"]["linked_stat"], "STR")
        self.assertEqual(d["description"], "Stary, ale ostry.")
        self.assertEqual(int(d["value_gp"]), 12)

    def test_armor_detail(self):
        d = ls.get_inventory_item_detail(7, 2)
        self.assertEqual(d["item_type"], "armor")
        self.assertEqual(d["armor"]["ac_bonus"], 2)
        self.assertEqual(d["description"], "Lekka ochrona torsu.")

    def test_consumable_detail(self):
        d = ls.get_inventory_item_detail(7, 3)
        self.assertEqual(d["kind"], "consumable")
        self.assertEqual(d["consumable"]["effect_type"], "heal")
        self.assertEqual(d["consumable"]["effect_dice"], "2d4")
        self.assertEqual(int(d["quantity"]), 3)

    def test_narrative_detail(self):
        d = ls.get_inventory_item_detail(7, 4)
        self.assertEqual(d["name"], "Amulet Babci")
        self.assertEqual(d["description"], "Pamiątka rodzinna.")

    def test_missing_item_raises(self):
        with self.assertRaises(ValueError):
            ls.get_inventory_item_detail(7, 999)


if __name__ == "__main__":
    unittest.main()
