"""TDD: Issue #376 (D1) — Pending flow przedmiotów.

Gdy LLM emituje `Grant Item <label>` z nieznanym kluczem (przedmiot nie-broń,
brak w game_config_items), backend musi utworzyć rekord pending=true
(review_status='pending_review', approved=0, ai_generated=1) w game_config_items
i skierować go do kolejki recenzji admina — analogicznie do broni narracyjnych.
"""
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql


def _schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        """ + table_sql("game_config_items") + """
        INSERT INTO game_config_items (key, label, item_type, is_active, approved)
        VALUES ('healing_herb', 'Zioło lecznicze', 'misc', 1, 1);

        CREATE TABLE character_inventory (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          character_id INTEGER NOT NULL,
          label TEXT,
          item_key TEXT,
          weapon_key TEXT,
          consumable_key TEXT,
          quantity INTEGER NOT NULL DEFAULT 1,
          equipped INTEGER NOT NULL DEFAULT 0,
          source TEXT,
          meta_json TEXT,
          CONSTRAINT inv_xor CHECK (
            (CASE WHEN item_key IS NOT NULL THEN 1 ELSE 0 END +
             CASE WHEN weapon_key IS NOT NULL THEN 1 ELSE 0 END +
             CASE WHEN consumable_key IS NOT NULL THEN 1 ELSE 0 END) = 1
          )
        );
        """
    )
    conn.commit()


# ─── Test główny — nowe zachowanie ───────────────────────────────────────────

class TestPendingItemGrant(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_unknown_item_creates_pending_catalog_record(self):
        """Nieznany przedmiot (nie-broń) → rekord pending=true w game_config_items."""
        from app.api.turns import _grant_pending_item

        key = _grant_pending_item(
            self.conn, campaign_id=1, character_id=7,
            label="Amulet Szeptów", source="gm",
        )
        self.assertIsNotNone(key, "grant must return the new pending item key")
        row = self.conn.execute(
            "SELECT label, review_status, approved, ai_generated, campaign_id "
            "FROM game_config_items WHERE key = ?", (key,),
        ).fetchone()
        self.assertIsNotNone(row, "pending catalog item not inserted")
        self.assertEqual(row["review_status"], "pending_review")
        self.assertEqual(int(row["approved"]), 0)
        self.assertEqual(int(row["ai_generated"]), 1)
        self.assertEqual(int(row["campaign_id"]), 1)
        self.assertEqual(row["label"], "Amulet Szeptów")

    def test_unknown_item_granted_to_inventory_via_item_key(self):
        """Przedmiot pending trafia też do plecaka gracza przez item_key (nie sentinel)."""
        from app.api.turns import _grant_pending_item

        key = _grant_pending_item(
            self.conn, campaign_id=1, character_id=7,
            label="Amulet Szeptów", source="gm",
        )
        inv = self.conn.execute(
            "SELECT item_key, label FROM character_inventory WHERE character_id = 7",
        ).fetchone()
        self.assertIsNotNone(inv, "item not added to inventory")
        self.assertEqual(inv["item_key"], key)
        self.assertEqual(inv["label"], "Amulet Szeptów")

    def test_pending_item_visible_in_admin_review_queue(self):
        """Admin widzi pending przedmiot w kolejce recenzji (get_pending_items)."""
        from app.api.turns import _grant_pending_item
        from app.services.world_service import get_pending_items, get_pending_review_counts

        _grant_pending_item(self.conn, campaign_id=1, character_id=7,
                            label="Amulet Szeptów", source="gm")

        pending = get_pending_items(self.conn)
        labels = {p["label"] for p in pending}
        self.assertIn("Amulet Szeptów", labels)

        counts = get_pending_review_counts(self.conn)
        self.assertGreaterEqual(counts.get("items", 0), 1)


# ─── Edycja przed akceptacją (#376 follow-up) ────────────────────────────────

class TestEditBeforeApprove(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_pending_items_expose_editable_fields(self):
        """Modal 'Edytuj i Zatwierdź' pre-filluje pola → get_pending_items musi je zwracać."""
        from app.api.turns import _grant_pending_item
        from app.services.world_service import get_pending_items

        _grant_pending_item(self.conn, campaign_id=1, character_id=7,
                            label="Amulet Szeptów", source="gm", description="opis")
        pending = get_pending_items(self.conn)
        p = next(x for x in pending if x["label"] == "Amulet Szeptów")
        for field in ("item_type", "description", "value_gp", "note", "weight_kg"):
            self.assertIn(field, p,
                          f"get_pending_items musi zwracać '{field}' dla modala edycji (#376)")

    def test_edit_pending_item_keeps_it_in_queue(self):
        """Edycja pól pending przedmiotu NIE może go usunąć z kolejki (review_status bez zmian).

        Kluczowy inwariant: kolejka filtruje po review_status='pending_review', więc edycja
        pól (nazwa/opis/wartość) musi zostawić review_status nietknięty — `update_item` w
        backendzie nie dotyka tej kolumny (ani campaign_id), co tu sprawdzamy na poziomie SQL
        odzwierciedlającym jego klauzulę SET.
        """
        from app.api.turns import _grant_pending_item

        key = _grant_pending_item(self.conn, campaign_id=1, character_id=7,
                                  label="Surowy klucz", source="gm")
        # update_item SET nie zawiera review_status/campaign_id → tu to samo:
        self.conn.execute(
            "UPDATE game_config_items SET label=?, description=?, value_gp=?, note=? WHERE key=?",
            ("Poprawiona nazwa", "lepszy opis", 25, "rzadki", key),
        )
        row = self.conn.execute(
            "SELECT label, value_gp, review_status FROM game_config_items WHERE key=?",
            (key,),
        ).fetchone()
        self.assertEqual(row["label"], "Poprawiona nazwa")
        self.assertEqual(int(row["value_gp"]), 25)
        self.assertEqual(row["review_status"], "pending_review",
                         "edycja nie może usunąć przedmiotu z kolejki recenzji")

    def test_approve_item_flips_status_and_clears_campaign(self):
        """Po edycji approve → permanent + approved=1 + campaign_id=NULL (globalny)."""
        from app.api.turns import _grant_pending_item
        from app.services.world_service import approve_entity

        key = _grant_pending_item(self.conn, campaign_id=1, character_id=7,
                                  label="Do zatwierdzenia", source="gm")
        ok = approve_entity(self.conn, "item", key)
        self.assertTrue(ok)
        row = self.conn.execute(
            "SELECT review_status, approved, campaign_id FROM game_config_items WHERE key=?",
            (key,),
        ).fetchone()
        self.assertEqual(row["review_status"], "permanent")
        self.assertEqual(int(row["approved"]), 1)
        self.assertIsNone(row["campaign_id"])


# ─── Backward compatibility — stary kod nadal działa ─────────────────────────

class TestKnownItemUnchanged(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_known_item_resolves_to_catalog_key(self):
        """Znany, zatwierdzony przedmiot nadal rozwiązuje się do katalogu (nie pending)."""
        from app.api.turns import _resolve_grant_catalog_item

        resolved = _resolve_grant_catalog_item(self.conn, "Zioło lecznicze")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["item_key"], "healing_herb")

        # i nie powstał żaden nowy pending rekord
        n = self.conn.execute(
            "SELECT COUNT(*) FROM game_config_items WHERE review_status = 'pending_review'",
        ).fetchone()[0]
        self.assertEqual(int(n), 0)


if __name__ == "__main__":
    unittest.main()
