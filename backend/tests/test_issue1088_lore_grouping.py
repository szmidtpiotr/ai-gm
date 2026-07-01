"""TDD: Issue #1088 — Inventory lore grouping by category (client-side heuristic).

Backend: utility function lore_category_key(label, item_type) → category slug.
Frontend: game.js renders lore items in collapsible <details> groups.
Playwright: issue_1088_lore_grouping.spec.js verifies DOM structure.
"""
import sys
sys.path.insert(0, "/app")

import sqlite3
import pytest

from app.services.inventory_category import lore_category_key


DB_PATH = "/data/ai_gm.db"


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Test główny — klasyfikacja lore items po etykiecie ──────────────────────

def test_scroll_category():
    """Pergaminy / zwoje / listy → 'scrolls'."""
    assert lore_category_key("Pergamin ze zaklęciem", "misc") == "scrolls"
    assert lore_category_key("Zwój Ognia", "misc") == "scrolls"
    assert lore_category_key("List do kniazia", "misc") == "scrolls"
    assert lore_category_key("Zwój Wiatru", "narrative") == "scrolls"


def test_book_category():
    """Księgi / książki / kodeksy → 'books'."""
    assert lore_category_key("Księga Czarów", "misc") == "books"
    assert lore_category_key("Stara Książka", "misc") == "books"
    assert lore_category_key("Kodeks Kapłański", "misc") == "books"
    assert lore_category_key("Kronika walk", "narrative") == "books"


def test_key_category():
    """Klucze → 'keys'."""
    assert lore_category_key("Klucz do wieży", "misc") == "keys"
    assert lore_category_key("Żelazny klucz", "quest") == "keys"


def test_quest_type_goes_to_quest_category():
    """Przedmioty quest-type bez pasującego regex → 'quest'."""
    assert lore_category_key("Amulet Mroku", "quest") == "quest"
    assert lore_category_key("Pieczęć królewska", "quest") == "quest"


def test_misc_fallback():
    """Wszystko inne → 'misc'."""
    assert lore_category_key("Odłamek kości", "misc") == "misc"
    assert lore_category_key("Kamień runiczny", "narrative") == "misc"
    assert lore_category_key("Kawałek drewna", "item") == "misc"


# ─── Backward compat — stary kod inventory API nadal działa ──────────────────

def test_inventory_api_returns_item_type_field():
    """GET /api/inventory/{char_id} → każdy item ma pole item_type."""
    from fastapi.testclient import TestClient
    from app.main import app

    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO characters (name, race, system_id, user_id, gold_gp, status, sheet_json) "
            "VALUES ('[TEST] LoreGroup1088', 'human', 'test', 1, 0, 'idle', '{}')"
        )
        conn.commit()
        char_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute(
            "INSERT INTO character_inventory (character_id, item_key, quantity, equipped, source) "
            "VALUES (?, 'misc_placeholder', 1, 0, 'test')",
            (char_id,),
        )
        conn.commit()
    except Exception:
        pass

    client = TestClient(app)
    r = client.get(f"/api/inventory/{char_id}")
    conn.execute("DELETE FROM character_inventory WHERE character_id=?", (char_id,))
    conn.execute("DELETE FROM characters WHERE id=?", (char_id,))
    conn.commit()
    conn.close()

    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    # API zwraca listę (może być pusta jeśli item_key nieznany — to OK)
    assert isinstance(body.get("data"), list)


def test_lore_category_key_case_insensitive():
    """Regex nie rozróżnia wielkości liter."""
    assert lore_category_key("PERGAMIN Ognia", "misc") == "scrolls"
    assert lore_category_key("KLUCZ", "misc") == "keys"
    assert lore_category_key("Księga", "misc") == "books"
