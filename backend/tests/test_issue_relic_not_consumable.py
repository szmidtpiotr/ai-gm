"""TDD: Relikt (np. „Totem wilczej watahy") pokazywał się w plecaku jako
przedmiot ZUŻYWALNY z przyciskiem „Użyj" zamiast dawać się ZAŁOŻYĆ.

Root cause: `loot_service` ma heurystykę, która przy MIS-otagowanym itemie
(item_type='quest'/'item', ale efekt = mechanika mikstury) podnosi item_type do
'consumable'. Sygnał czerpie z `legacy_effect_fields_from_json`, które mapuje
`static_stat_modifier` → legacy `stat_buff`. `stat_buff` należy do
`_CONSUMABLE_EFFECT_SIGNAL`, więc PASYWNY relikt (effect_category='gear_bonus')
był błędnie klasyfikowany jako consumable:
  - lista plecaka: `item_type='consumable'`, `can_use=True` → przycisk „Użyj"
    zamiast „Załóż" (frontend `targetSlotFor` zwracał null),
  - gorzej: `use_inventory_item` pozwalało go ZUŻYĆ (skasować relikt).

Fix: kind ze zbioru `_EQUIPPABLE_GEAR_KINDS` (weapon/armor/shield/relic/...) jest
zwolniony z heurystyki consumable — poprawnie otagowany relikt zostaje reliktem.
"""
import json
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql

from app.services import loot_service as ls

RELIC_EFFECT = json.dumps(
    {
        "schema_version": 1,
        "effect_category": "gear_bonus",
        "effects": [{"type": "static_stat_modifier", "stat": "CHA", "value": 1}],
    }
)
POTION_EFFECT = json.dumps(
    {
        "schema_version": 1,
        "effect_category": "consumable",
        "effects": [{"type": "heal_hp", "value": 8}],
    }
)


def _schema_sql() -> str:
    return (
        """
    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
      campaign_id INTEGER, sheet_json TEXT
    );
    INSERT INTO characters (id, name, sheet_json)
      VALUES (1, 'Mizel', '{"current_hp":10,"max_hp":20}');

    CREATE TABLE game_items (
      key TEXT PRIMARY KEY, label TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'item',
      item_data TEXT, weapon_data TEXT, effect_json TEXT, is_active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE character_inventory (
      id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL,
      item_key TEXT, weapon_key TEXT, consumable_key TEXT, label TEXT,
      quantity INTEGER NOT NULL DEFAULT 1, equipped INTEGER NOT NULL DEFAULT 0,
      slot TEXT, acquired_at TEXT NOT NULL DEFAULT (datetime('now')),
      source TEXT, meta_json TEXT
    );
    """
        + table_sql("game_config_items")
        + table_sql("game_config_weapons")
        + table_sql("game_config_consumables")
        + """
    -- Relikt: poprawnie otagowany w OBU katalogach (item_type='relic'), efekt = gear_bonus.
    INSERT INTO game_config_items (key, label, item_type, effect_json, is_active)
      VALUES ('wolf_totem_charm', 'Totem wilczej watahy', 'relic', '"""
        + RELIC_EFFECT.replace("'", "''")
        + """', 1);
    INSERT INTO game_items (key, label, kind, item_data, effect_json, is_active)
      VALUES ('wolf_totem_charm', 'Totem wilczej watahy', 'item',
              '{"item_type":"relic"}', '"""
        + RELIC_EFFECT.replace("'", "''")
        + """', 1);

    -- Kontrola regresji: item MIS-otagowany jako 'quest', ale efekt = leczenie →
    -- heurystyka NADAL musi go podnieść do consumable.
    INSERT INTO game_config_items (key, label, item_type, effect_json, is_active)
      VALUES ('mystery_vial', 'Tajemniczy flakon', 'quest', '"""
        + POTION_EFFECT.replace("'", "''")
        + """', 1);
    INSERT INTO game_items (key, label, kind, item_data, effect_json, is_active)
      VALUES ('mystery_vial', 'Tajemniczy flakon', 'item',
              '{"item_type":"quest"}', '"""
        + POTION_EFFECT.replace("'", "''")
        + """', 1);
    """
    )


class TestRelicNotConsumable(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_relic_consumable_test.db"
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

    def _ins(self, **kw) -> int:
        cols = ", ".join(kw.keys())
        qs = ", ".join("?" for _ in kw)
        conn = sqlite3.connect(str(self._tmp))
        cur = conn.execute(
            f"INSERT INTO character_inventory ({cols}) VALUES ({qs})", tuple(kw.values())
        )
        conn.commit()
        iid = int(cur.lastrowid)
        conn.close()
        return iid

    def _row(self, inv, key):
        return next(r for r in inv if r["key"] == key)

    # ─── Test główny: relikt zostaje reliktem (equippable, nie „Użyj") ──────────

    def test_relic_stays_equippable_not_consumable(self):
        self._ins(character_id=1, item_key="wolf_totem_charm", source="loot")
        inv = ls.get_character_inventory(1)
        relic = self._row(inv, "wolf_totem_charm")
        self.assertEqual(relic["item_type"], "relic",
                         f"relik sklasyfikowany jako {relic['item_type']} (heurystyka consumable)")
        self.assertFalse(relic["can_use"],
                         "relik nie moze miec can_use=True (przycisk Uzyj skasowalby relikt)")

    # ─── Regresja: prawdziwy mis-tagged eliksir DALEJ jest consumable ───────────

    def test_mistagged_potion_still_becomes_consumable(self):
        self._ins(character_id=1, item_key="mystery_vial", source="loot")
        inv = ls.get_character_inventory(1)
        vial = self._row(inv, "mystery_vial")
        self.assertEqual(vial["item_type"], "consumable",
                         "mis-otagowany eliksir (heal_hp) musi zostać consumable")
        self.assertTrue(vial["can_use"])

    # ─── use_inventory_item: nie wolno ZUŻYĆ reliktu ────────────────────────────

    def test_using_relic_raises_not_usable(self):
        iid = self._ins(character_id=1, item_key="wolf_totem_charm", source="loot")
        with self.assertRaises(ValueError):
            ls.use_inventory_item(1, iid)

    def test_using_mistagged_potion_is_allowed(self):
        iid = self._ins(character_id=1, item_key="mystery_vial", source="loot")
        # Nie rzuca „not usable" — dojdzie do właściwej mechaniki leczenia.
        try:
            ls.use_inventory_item(1, iid)
        except ValueError as e:
            self.assertNotIn("not usable", str(e),
                             "eliksir nie powinien być odrzucony jako niezuzywalny")


if __name__ == "__main__":
    unittest.main()
