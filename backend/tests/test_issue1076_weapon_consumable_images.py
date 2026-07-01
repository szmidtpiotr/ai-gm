"""TDD: Issue #1076 — image_url dla broni i konsumpcji.

1. Schema: game_config_weapons + game_config_consumables mają kolumny image_url + image_gen_prompt
2. loot_service.get_character_inventory() zwraca image_url dla broni i konsumpcji
3. loot_service.get_inventory_item_detail() zwraca image_url dla broni i konsumpcji
4. Endpoint GET /api/admin/images/weapon/missing istnieje (sprawdzany przez Playwright)
5. Endpoint GET /api/admin/images/consumable/missing istnieje
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

_TEST_WEAPON_KEY = "__tdd1076_weapon__"
_TEST_CONSUMABLE_KEY = "__tdd1076_consumable__"
_TEST_CHAR_ID = 9991076
_TEST_WEAPON_IMAGE = "https://example.com/weapons/test_sword.webp"
_TEST_CONSUMABLE_IMAGE = "https://example.com/potions/test_potion.webp"


def _setup(conn):
    conn.execute("""
        INSERT OR IGNORE INTO characters
            (id, user_id, name, system_id, sheet_json, status)
        VALUES (?, 1, '[TDD1076]', 'tdd', '{}', 'idle')
    """, (_TEST_CHAR_ID,))
    # weapon with image_url
    conn.execute("""
        INSERT OR REPLACE INTO game_config_weapons
            (key, label, damage_die, weapon_type, linked_stat, allowed_classes, image_url, is_active)
        VALUES (?, 'Miecz Testowy TDD1076', '1d8', 'melee', 'STR', 'all', ?, 1)
    """, (_TEST_WEAPON_KEY, _TEST_WEAPON_IMAGE))
    # consumable with image_url
    conn.execute("""
        INSERT OR REPLACE INTO game_config_consumables
            (key, label, effect_type, effect_dice, image_url, is_active)
        VALUES (?, 'Mikstura Testowa TDD1076', 'heal', '2d6', ?, 1)
    """, (_TEST_CONSUMABLE_KEY, _TEST_CONSUMABLE_IMAGE))
    # inventory rows
    conn.execute("""
        INSERT OR REPLACE INTO character_inventory
            (character_id, weapon_key, quantity, equipped, source)
        VALUES (?, ?, 1, 0, 'tdd')
    """, (_TEST_CHAR_ID, _TEST_WEAPON_KEY))
    conn.execute("""
        INSERT OR REPLACE INTO character_inventory
            (character_id, consumable_key, quantity, equipped, source)
        VALUES (?, ?, 2, 0, 'tdd')
    """, (_TEST_CHAR_ID, _TEST_CONSUMABLE_KEY))
    conn.commit()


def _teardown(conn):
    conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (_TEST_CHAR_ID,))
    conn.execute("DELETE FROM characters WHERE id = ?", (_TEST_CHAR_ID,))
    conn.execute("DELETE FROM game_config_weapons WHERE key = ?", (_TEST_WEAPON_KEY,))
    conn.execute("DELETE FROM game_config_consumables WHERE key = ?", (_TEST_CONSUMABLE_KEY,))
    conn.commit()


# ─── SCHEMA TESTS ────────────────────────────────────────────────────────────

def test_game_config_weapons_has_image_url_column():
    """game_config_weapons musi mieć kolumnę image_url (migracja #1076)."""
    conn = _conn()
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(game_config_weapons)").fetchall()]
    finally:
        conn.close()
    assert "image_url" in cols, (
        f"Brak kolumny image_url w game_config_weapons. "
        f"Kolumny: {cols}. Wymagana migracja #1076."
    )


def test_game_config_weapons_has_image_gen_prompt_column():
    """game_config_weapons musi mieć kolumnę image_gen_prompt (migracja #1076)."""
    conn = _conn()
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(game_config_weapons)").fetchall()]
    finally:
        conn.close()
    assert "image_gen_prompt" in cols, (
        f"Brak kolumny image_gen_prompt w game_config_weapons. Kolumny: {cols}."
    )


def test_game_config_consumables_has_image_url_column():
    """game_config_consumables musi mieć kolumnę image_url (migracja #1076)."""
    conn = _conn()
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(game_config_consumables)").fetchall()]
    finally:
        conn.close()
    assert "image_url" in cols, (
        f"Brak kolumny image_url w game_config_consumables. Kolumny: {cols}."
    )


def test_game_config_consumables_has_image_gen_prompt_column():
    """game_config_consumables musi mieć kolumnę image_gen_prompt (migracja #1076)."""
    conn = _conn()
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(game_config_consumables)").fetchall()]
    finally:
        conn.close()
    assert "image_gen_prompt" in cols, (
        f"Brak kolumny image_gen_prompt w game_config_consumables. Kolumny: {cols}."
    )


# ─── LOOT SERVICE — lista ekwipunku ──────────────────────────────────────────

def test_get_character_inventory_returns_image_url_for_weapon():
    """get_character_inventory() musi zwracać image_url dla broni."""
    conn = _conn()
    try:
        _setup(conn)
    finally:
        conn.close()

    from app.services.loot_service import get_character_inventory
    try:
        items = get_character_inventory(_TEST_CHAR_ID)
        weapon = next((i for i in items if i.get("key") == _TEST_WEAPON_KEY), None)
        assert weapon is not None, f"Broń {_TEST_WEAPON_KEY!r} nie widoczna. Keys: {[i.get('key') for i in items]}"
        assert "image_url" in weapon, f"Brak image_url w wierszu broni. Klucze: {list(weapon.keys())}"
        assert weapon["image_url"] == _TEST_WEAPON_IMAGE, (
            f"image_url = {weapon['image_url']!r}, oczekiwano {_TEST_WEAPON_IMAGE!r}"
        )
    finally:
        conn2 = _conn()
        _teardown(conn2)
        conn2.close()


def test_get_character_inventory_returns_image_url_for_consumable():
    """get_character_inventory() musi zwracać image_url dla konsumpcji."""
    conn = _conn()
    try:
        _setup(conn)
    finally:
        conn.close()

    from app.services.loot_service import get_character_inventory
    try:
        items = get_character_inventory(_TEST_CHAR_ID)
        consumable = next((i for i in items if i.get("key") == _TEST_CONSUMABLE_KEY), None)
        assert consumable is not None, f"Konsumpcja {_TEST_CONSUMABLE_KEY!r} nie widoczna."
        assert "image_url" in consumable, f"Brak image_url w wierszu konsumpcji. Klucze: {list(consumable.keys())}"
        assert consumable["image_url"] == _TEST_CONSUMABLE_IMAGE, (
            f"image_url = {consumable['image_url']!r}, oczekiwano {_TEST_CONSUMABLE_IMAGE!r}"
        )
    finally:
        conn2 = _conn()
        _teardown(conn2)
        conn2.close()


# ─── LOOT SERVICE — detail modal ─────────────────────────────────────────────

def test_get_inventory_item_detail_returns_image_url_for_weapon():
    """get_inventory_item_detail() musi zwracać image_url dla broni."""
    conn = _conn()
    try:
        _setup(conn)
        row = conn.execute(
            "SELECT id FROM character_inventory WHERE character_id = ? AND weapon_key = ?",
            (_TEST_CHAR_ID, _TEST_WEAPON_KEY),
        ).fetchone()
        assert row, "fixture: brak wiersza weapon inventory"
        inv_id = int(row["id"])
    finally:
        conn.close()

    from app.services.loot_service import get_inventory_item_detail
    try:
        detail = get_inventory_item_detail(_TEST_CHAR_ID, inv_id)
        assert "image_url" in detail, (
            f"get_inventory_item_detail() nie zwraca image_url dla broni. "
            f"Klucze: {list(detail.keys())}"
        )
        assert detail["image_url"] == _TEST_WEAPON_IMAGE, (
            f"image_url = {detail['image_url']!r}, oczekiwano {_TEST_WEAPON_IMAGE!r}"
        )
    finally:
        conn2 = _conn()
        _teardown(conn2)
        conn2.close()


def test_get_inventory_item_detail_returns_image_url_for_consumable():
    """get_inventory_item_detail() musi zwracać image_url dla konsumpcji."""
    conn = _conn()
    try:
        _setup(conn)
        row = conn.execute(
            "SELECT id FROM character_inventory WHERE character_id = ? AND consumable_key = ?",
            (_TEST_CHAR_ID, _TEST_CONSUMABLE_KEY),
        ).fetchone()
        assert row, "fixture: brak wiersza consumable inventory"
        inv_id = int(row["id"])
    finally:
        conn.close()

    from app.services.loot_service import get_inventory_item_detail
    try:
        detail = get_inventory_item_detail(_TEST_CHAR_ID, inv_id)
        assert "image_url" in detail, (
            f"get_inventory_item_detail() nie zwraca image_url dla konsumpcji. "
            f"Klucze: {list(detail.keys())}"
        )
        assert detail["image_url"] == _TEST_CONSUMABLE_IMAGE, (
            f"image_url = {detail['image_url']!r}, oczekiwano {_TEST_CONSUMABLE_IMAGE!r}"
        )
    finally:
        conn2 = _conn()
        _teardown(conn2)
        conn2.close()


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_existing_item_image_url_still_works():
    """Przedmioty (game_config_items) nadal zwracają image_url — #1049 nie zepsute."""
    from app.services.loot_service import get_character_inventory
    conn = _conn()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO characters
                (id, user_id, name, system_id, sheet_json, status)
            VALUES (9991077, 1, '[TDD1077bc]', 'tdd', '{}', 'idle')
        """)
        conn.execute("""
            INSERT OR REPLACE INTO game_config_items
                (key, label, item_type, description, image_url, is_active)
            VALUES ('__tdd1076_item_bc__', 'Item BC', 'misc', 'test', 'https://example.com/item.webp', 1)
        """)
        conn.execute("""
            INSERT OR REPLACE INTO character_inventory
                (character_id, item_key, quantity, equipped, source)
            VALUES (9991077, '__tdd1076_item_bc__', 1, 0, 'tdd')
        """)
        conn.commit()
    finally:
        conn.close()

    try:
        items = get_character_inventory(9991077)
        item = next((i for i in items if i.get("key") == "__tdd1076_item_bc__"), None)
        assert item is not None, "Item BC nie widoczny"
        assert item.get("image_url") == "https://example.com/item.webp", (
            f"image_url zepsute po #1076: {item.get('image_url')!r}"
        )
    finally:
        conn3 = _conn()
        conn3.execute("DELETE FROM character_inventory WHERE character_id = 9991077")
        conn3.execute("DELETE FROM characters WHERE id = 9991077")
        conn3.execute("DELETE FROM game_config_items WHERE key = '__tdd1076_item_bc__'")
        conn3.commit()
        conn3.close()
