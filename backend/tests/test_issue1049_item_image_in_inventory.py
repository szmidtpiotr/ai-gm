"""TDD: Issue #1049 — image_url przedmiotu widoczny w ekwipunku gracza.

Backend zwraca image_url z game_config_items w:
- get_inventory_item_detail() → modal szczegółów
- get_character_inventory()  → lista ekwipunku (miniatura w wierszu)
"""
import sqlite3
import sys

sys.path.insert(0, "/app")

DB_PATH = "/data/ai_gm.db"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Fixtures ────────────────────────────────────────────────────────────────

_TEST_ITEM_KEY = "__tdd1049_item__"
_TEST_CHAR_ID = 9990049
_TEST_IMAGE_URL = "https://example.com/items/sword_of_test.webp"


def _setup_fixtures(conn):
    conn.execute("""
        INSERT OR REPLACE INTO game_config_items
            (key, label, item_type, description, image_url, is_active)
        VALUES (?, 'Miecz Testowy TDD1049', 'weapon', 'Przedmiot testowy', ?, 1)
    """, (_TEST_ITEM_KEY, _TEST_IMAGE_URL))
    # minimal character row (id=9990049 unlikely to collide)
    conn.execute("""
        INSERT OR IGNORE INTO characters
            (id, user_id, name, system_id, sheet_json, status)
        VALUES (?, 1, '[TDD1049]', 'tdd', '{}', 'idle')
    """, (_TEST_CHAR_ID,))
    conn.execute("""
        INSERT OR REPLACE INTO character_inventory
            (character_id, item_key, quantity, equipped, source)
        VALUES (?, ?, 1, 0, 'tdd')
    """, (_TEST_CHAR_ID, _TEST_ITEM_KEY))
    conn.commit()


def _teardown_fixtures(conn):
    conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (_TEST_CHAR_ID,))
    conn.execute("DELETE FROM characters WHERE id = ?", (_TEST_CHAR_ID,))
    conn.execute("DELETE FROM game_config_items WHERE key = ?", (_TEST_ITEM_KEY,))
    conn.commit()


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_get_inventory_item_detail_returns_image_url():
    """get_inventory_item_detail() musi zawierać image_url z game_config_items."""
    conn = _conn()
    try:
        _setup_fixtures(conn)
        inv_row = conn.execute(
            "SELECT id FROM character_inventory WHERE character_id = ? AND item_key = ?",
            (_TEST_CHAR_ID, _TEST_ITEM_KEY),
        ).fetchone()
        assert inv_row, "fixture: brak wiersza inventory"
        inv_id = int(inv_row["id"])
    finally:
        conn.close()

    from app.services.loot_service import get_inventory_item_detail
    try:
        detail = get_inventory_item_detail(_TEST_CHAR_ID, inv_id)
        assert "image_url" in detail, (
            f"get_inventory_item_detail() nie zwraca 'image_url'. "
            f"Klucze: {list(detail.keys())}"
        )
        assert detail["image_url"] == _TEST_IMAGE_URL, (
            f"image_url = {detail['image_url']!r}, oczekiwano {_TEST_IMAGE_URL!r}"
        )
    finally:
        conn2 = _conn()
        _teardown_fixtures(conn2)
        conn2.close()


def test_get_character_inventory_returns_image_url():
    """get_character_inventory() musi zawierać image_url per wiersz (dla miniatur w liście)."""
    conn = _conn()
    try:
        _setup_fixtures(conn)
    finally:
        conn.close()

    from app.services.loot_service import get_character_inventory
    try:
        items = get_character_inventory(_TEST_CHAR_ID)
        assert items, "fixture: lista ekwipunku pusta"
        item = next((i for i in items if i.get("key") == _TEST_ITEM_KEY), None)
        assert item is not None, (
            f"Przedmiot {_TEST_ITEM_KEY!r} nie widoczny w ekwipunku. "
            f"Keys: {[i.get('key') for i in items]}"
        )
        assert "image_url" in item, (
            f"get_character_inventory() nie zawiera 'image_url' w wierszu. "
            f"Klucze: {list(item.keys())}"
        )
        assert item["image_url"] == _TEST_IMAGE_URL, (
            f"image_url = {item['image_url']!r}, oczekiwano {_TEST_IMAGE_URL!r}"
        )
    finally:
        conn2 = _conn()
        _teardown_fixtures(conn2)
        conn2.close()


def test_get_inventory_item_detail_backward_compat_no_image():
    """Przedmiot bez image_url zwraca None (nie KeyError) — backward compat."""
    from app.services.loot_service import get_inventory_item_detail
    conn = _conn()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO game_config_items
                (key, label, item_type, description, image_url, is_active)
            VALUES ('__tdd1049_noimg__', 'Brak Obrazka TDD', 'misc', 'test', NULL, 1)
        """)
        conn.execute("""
            INSERT OR IGNORE INTO characters
                (id, user_id, name, system_id, sheet_json, status)
            VALUES (9990050, 1, '[TDD1049b]', 'tdd', '{}', 'idle')
        """)
        conn.execute("""
            INSERT OR REPLACE INTO character_inventory
                (character_id, item_key, quantity, equipped, source)
            VALUES (9990050, '__tdd1049_noimg__', 1, 0, 'tdd')
        """)
        conn.commit()
        inv_row = conn.execute(
            "SELECT id FROM character_inventory WHERE character_id = 9990050"
        ).fetchone()
        assert inv_row
        inv_id = int(inv_row["id"])
    finally:
        conn.close()

    try:
        detail = get_inventory_item_detail(9990050, inv_id)
        assert "image_url" in detail, "image_url key musi być obecny nawet gdy NULL"
        assert detail["image_url"] is None, f"oczekiwano None, got {detail['image_url']!r}"
    finally:
        conn3 = _conn()
        conn3.execute("DELETE FROM character_inventory WHERE character_id = 9990050")
        conn3.execute("DELETE FROM characters WHERE id = 9990050")
        conn3.execute("DELETE FROM game_config_items WHERE key = '__tdd1049_noimg__'")
        conn3.commit()
        conn3.close()
