"""TDD: Issue #757 — inventory pokazuje surowy klucz zamiast nazwy narracyjnego itemu.

Root cause: `_grant_pending_item` zapisuje item do `game_config_items` + stawia
`character_inventory.label`, ale lista plecaka (`get_character_inventory`) JOIN-uje
`game_items` (po #573). Klucza nie ma w `game_items` → `item_label` = NULL →
fallback na surowy `item_key` (`label = item_label or item_key`). Wiersz MA poprawną
nazwę w `ci.label` (alias `narrative_label`), ale stara linia jej nie czyta.

Fix:
1. `loot_service.get_character_inventory` — fallback label:
   `item_label or narrative_label or item_key` (czyta ci.label dla pending itemów).
2. Backfill istniejących wierszy (id 485 itp.) gdzie ci.label IS NULL, z game_config_items.
"""
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import loot_service as ls


def _schema_sql() -> str:
    return """
    CREATE TABLE characters (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL);
    INSERT INTO characters (id, name) VALUES (1, 'Mizel');

    CREATE TABLE game_config_items (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      item_type TEXT NOT NULL DEFAULT 'misc',
      description TEXT,
      is_active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE game_items (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      kind TEXT NOT NULL DEFAULT 'item',
      item_data TEXT,
      weapon_data TEXT,
      effect_json TEXT,
      is_active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE character_inventory (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      character_id INTEGER NOT NULL,
      item_key TEXT,
      weapon_key TEXT,
      consumable_key TEXT,
      label TEXT,
      quantity INTEGER NOT NULL DEFAULT 1,
      equipped INTEGER NOT NULL DEFAULT 0,
      slot TEXT,
      acquired_at TEXT NOT NULL DEFAULT (datetime('now')),
      source TEXT,
      meta_json TEXT
    );

    -- Katalog narracyjny (game_config_items) MA komplet, game_items NIE (rozjazd #573).
    INSERT INTO game_config_items (key, label, item_type, description, is_active) VALUES
      ('narrative_item_z_o_ony_pergamin_99791_33345', 'Złożony pergamin', 'misc',
       'Narracyjny przedmiot: Złożony pergamin', 1),
      ('narrative_item_stary_zwoj_99791_00001', 'Stary zwój', 'misc',
       'Narracyjny przedmiot: Stary zwój', 1);

    -- Zwykły katalogowy item ZNAJDUJE się w game_items (backward compat).
    INSERT INTO game_items (key, label, kind, item_data, is_active) VALUES
      ('rope', 'Lina 10m', 'item', '{"item_type":"misc"}', 1);
    """


class TestNarrativeItemLabel(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_issue757_test.db"
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

    def _ins(self, **kw):
        cols = ", ".join(kw.keys())
        qs = ", ".join("?" for _ in kw)
        conn = sqlite3.connect(str(self._tmp))
        conn.execute(f"INSERT INTO character_inventory ({cols}) VALUES ({qs})", tuple(kw.values()))
        conn.commit()
        conn.close()

    # ─── Test główny ─────────────────────────────────────────────────────────

    def test_new_pending_item_with_label_shows_name_not_key(self):
        """NOWY pending item: ci.label ustawiony przez _grant_pending_item.
        Lista plecaka MUSI pokazać 'Złożony pergamin', nie surowy klucz."""
        self._ins(character_id=1,
                  item_key="narrative_item_z_o_ony_pergamin_99791_33345",
                  label="Złożony pergamin",
                  source="gm")
        inv = ls.get_character_inventory(1)
        self.assertEqual(len(inv), 1)
        self.assertEqual(inv[0]["label"], "Złożony pergamin")
        self.assertNotIn("narrative_item_", inv[0]["label"])

    # ─── Backfill istniejących wierszy (id 485 / #99791) ─────────────────────

    def test_backfill_resolves_label_for_legacy_null_label_row(self):
        """Istniejący wiersz: ci.label IS NULL (granted przed fixem).
        Po backfillu z game_config_items lista pokazuje nazwę."""
        self._ins(character_id=1,
                  item_key="narrative_item_stary_zwoj_99791_00001",
                  label=None, source="gm")
        # Backfill (ten sam SQL co RAW migracja).
        conn = sqlite3.connect(str(self._tmp))
        conn.execute(
            "UPDATE character_inventory SET label = ("
            "  SELECT label FROM game_config_items WHERE key = character_inventory.item_key) "
            "WHERE (label IS NULL OR TRIM(label) = '') "
            "AND item_key LIKE 'narrative_item_%' "
            "AND item_key IN (SELECT key FROM game_config_items)"
        )
        conn.commit()
        conn.close()
        inv = ls.get_character_inventory(1)
        self.assertEqual(inv[0]["label"], "Stary zwój")

    # ─── Backward compatibility ──────────────────────────────────────────────

    def test_catalog_item_in_game_items_still_resolves_label(self):
        """Zwykły item z wpisem w game_items nadal rozwiązuje gi.label (bez regresji)."""
        self._ins(character_id=1, item_key="rope", label=None, source="loot")
        inv = ls.get_character_inventory(1)
        self.assertEqual(inv[0]["label"], "Lina 10m")

    def test_unknown_item_without_label_falls_back_to_key(self):
        """Brak w game_items I brak ci.label → fallback na klucz (ostateczny bezpiecznik)."""
        self._ins(character_id=1, item_key="totally_unknown_key", label=None, source="gm")
        inv = ls.get_character_inventory(1)
        self.assertEqual(inv[0]["label"], "totally_unknown_key")


if __name__ == "__main__":
    unittest.main()
