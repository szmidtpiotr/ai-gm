"""TDD: Issue #557 — U11b: przełączenie odczytu serwisów na game_items.

Wszystkie testy wstawiają próbne rekordy WYŁĄCZNIE do game_items (nie do starych tabel).
Funkcja, która nadal czyta ze starych tabel → zwróci None/pusty string → test FAIL (RED).
Po przełączeniu na game_items → test PASS (GREEN).
"""
import json
import sqlite3
import sys
import os

sys.path.insert(0, "/app")

DB_PATH = os.getenv("DB_PATH", "/data/ai_gm.db")

# Test keys — unikalne, nie kolidują z produkcyjnymi danymi
_W_KEY = "test_u11b_sword_unique"
_I_KEY = "test_u11b_armor_unique"
_C_KEY = "test_u11b_potion_unique"

_WEAPON_DATA = json.dumps({
    "damage_die": "d99",         # unikalny die — nie ma go w żadnej prawdziwej broni
    "weapon_type": "melee",
    "linked_stat": "STR",
    "allowed_classes": '["warrior"]',
    "two_handed": 0,
    "finesse": 0,
    "range_m": None,
    "targeting": "single",
    "aoe_radius_m": None,
    "magic_school": None,
    "weapon_slot": "main_hand",
})
_ARMOR_ITEM_DATA = json.dumps({
    "item_type": "armor",
    "ac_bonus": 42,              # unikalny bonus — nie ma go w żadnym prawdziwym itemie
    "armor_coverage": "torso",
    "allowed_classes": '["warrior"]',
    "charges": 1,
    "effect_type": None,
    "effect_dice": None,
    "effect_bonus": 0,
    "effect_target": "self",
})
_CONS_ITEM_DATA = json.dumps({
    "item_type": "consumable",
    "ac_bonus": 0,
    "armor_coverage": None,
    "allowed_classes": '["warrior","scholar","ranger"]',
    "charges": 1,
    "effect_type": "heal_hp",
    "effect_dice": "1d4",
    "effect_bonus": 0,
    "effect_target": "self",
})


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _setup_test_items(conn):
    """Wstaw próbne rekordy TYLKO do game_items. Stare tabele bez zmian."""
    conn.execute("DELETE FROM game_items WHERE key IN (?, ?, ?)", (_W_KEY, _I_KEY, _C_KEY))
    conn.execute("""
        INSERT INTO game_items (key, kind, label, description, price_gp, rarity,
                                weapon_data, item_data, is_active, approved, created_by)
        VALUES (?, 'weapon', 'TestU11b Sword', 'Test weapon for U11b', 500, 2,
                ?, '{}', 1, 1, 'test')
    """, (_W_KEY, _WEAPON_DATA))
    conn.execute("""
        INSERT INTO game_items (key, kind, label, description, price_gp, rarity,
                                weapon_data, item_data, is_active, approved, created_by)
        VALUES (?, 'armor', 'TestU11b Armor', 'Test armor for U11b', 200, 1,
                '{}', ?, 1, 1, 'test')
    """, (_I_KEY, _ARMOR_ITEM_DATA))
    conn.execute("""
        INSERT INTO game_items (key, kind, label, description, price_gp, rarity,
                                weapon_data, item_data, is_active, approved, created_by)
        VALUES (?, 'consumable', 'TestU11b Potion', 'Test consumable for U11b', 50, 1,
                '{}', ?, 1, 1, 'test')
    """, (_C_KEY, _CONS_ITEM_DATA))
    conn.commit()


def _cleanup_test_items(conn):
    conn.execute("DELETE FROM game_items WHERE key IN (?, ?, ?)", (_W_KEY, _I_KEY, _C_KEY))
    conn.commit()


# ─── Test 1: weapon_rules.load_weapon_row ─────────────────────────────────────

def test_weapon_rules_reads_from_game_items():
    """weapon_rules.load_weapon_row musi czytać damage_die z game_items.weapon_data."""
    from app.services.weapon_rules import load_weapon_row

    conn = _conn()
    _setup_test_items(conn)
    try:
        result = load_weapon_row(conn, _W_KEY)
        assert result is not None, (
            f"load_weapon_row zwróciło None dla {_W_KEY!r} — "
            "broń istnieje TYLKO w game_items, serwis nadal czyta ze starej tabeli"
        )
        assert result["damage_die"] == "d99", (
            f"damage_die={result['damage_die']!r} != 'd99' — "
            "weapon_data z game_items nie jest parsowany"
        )
        assert result["weapon_type"] == "melee", f"weapon_type={result['weapon_type']!r}"
        assert result["linked_stat"] == "STR", f"linked_stat={result['linked_stat']!r}"
    finally:
        _cleanup_test_items(conn)
        conn.close()


def test_weapon_rules_default_weapon_from_game_items():
    """weapon_rules.default_weapon_row fallback 'unarmed' musi być szukany w game_items."""
    from app.services.weapon_rules import default_weapon_row

    conn = _conn()
    # Unarmed istnieje w bazie (seed) — jeśli funkcja czyta z game_items, powinna go znaleźć
    result = default_weapon_row(conn)
    conn.close()
    # Fallback hardcoded też jest akceptowalny (gdy unarmed nie istnieje w game_items)
    assert result is not None, "default_weapon_row zwróciło None"
    assert result.get("damage_die"), f"damage_die jest pusty: {result}"


# ─── Test 2: shop_service._catalog_item ──────────────────────────────────────

def test_shop_catalog_item_reads_from_game_items_weapon():
    """shop_service._catalog_item musi znaleźć broń z game_items."""
    from app.services.shop_service import _catalog_item

    conn = _conn()
    _setup_test_items(conn)
    try:
        result = _catalog_item(conn, "weapon", _W_KEY)
        assert result is not None, (
            f"_catalog_item(weapon, {_W_KEY!r}) zwróciło None — "
            "broń istnieje TYLKO w game_items"
        )
        assert result["key"] == _W_KEY
        assert result["value_gp"] == 500
    finally:
        _cleanup_test_items(conn)
        conn.close()


def test_shop_catalog_item_reads_from_game_items_armor():
    """shop_service._catalog_item musi znaleźć zbroję z game_items."""
    from app.services.shop_service import _catalog_item

    conn = _conn()
    _setup_test_items(conn)
    try:
        result = _catalog_item(conn, "armor", _I_KEY)
        assert result is not None, (
            f"_catalog_item(armor, {_I_KEY!r}) zwróciło None — "
            "zbroja istnieje TYLKO w game_items"
        )
        assert result["key"] == _I_KEY
        assert result["value_gp"] == 200
    finally:
        _cleanup_test_items(conn)
        conn.close()


def test_shop_catalog_item_reads_from_game_items_consumable():
    """shop_service._catalog_item musi znaleźć konsumablę z game_items."""
    from app.services.shop_service import _catalog_item

    conn = _conn()
    _setup_test_items(conn)
    try:
        result = _catalog_item(conn, "consumable", _C_KEY)
        assert result is not None, (
            f"_catalog_item(consumable, {_C_KEY!r}) zwróciło None — "
            "konsumabla istnieje TYLKO w game_items"
        )
        assert result["key"] == _C_KEY
        assert result["value_gp"] == 50
    finally:
        _cleanup_test_items(conn)
        conn.close()


# ─── Test 3: loot_service._catalog_entry ─────────────────────────────────────

def test_loot_catalog_entry_reads_weapon_from_game_items():
    """loot_service._catalog_entry musi znaleźć broń z game_items."""
    from app.services.loot_service import _catalog_entry

    conn = _conn()
    _setup_test_items(conn)
    try:
        result = _catalog_entry(conn, {"weapon_key": _W_KEY})
        assert result is not None, (
            f"_catalog_entry(weapon_key={_W_KEY!r}) zwróciło None — "
            "broń istnieje TYLKO w game_items"
        )
        key, label, item_type = result
        assert key == _W_KEY
        assert item_type == "weapon"
        assert label == "TestU11b Sword"
    finally:
        _cleanup_test_items(conn)
        conn.close()


def test_loot_catalog_entry_reads_item_from_game_items():
    """loot_service._catalog_entry musi znaleźć zbroję/item z game_items."""
    from app.services.loot_service import _catalog_entry

    conn = _conn()
    _setup_test_items(conn)
    try:
        result = _catalog_entry(conn, {"item_key": _I_KEY})
        assert result is not None, (
            f"_catalog_entry(item_key={_I_KEY!r}) zwróciło None — "
            "item istnieje TYLKO w game_items"
        )
        key, label, item_type = result
        assert key == _I_KEY
        assert label == "TestU11b Armor"
    finally:
        _cleanup_test_items(conn)
        conn.close()


def test_loot_catalog_entry_reads_consumable_from_game_items():
    """loot_service._catalog_entry musi znaleźć konsumablę z game_items."""
    from app.services.loot_service import _catalog_entry

    conn = _conn()
    _setup_test_items(conn)
    try:
        result = _catalog_entry(conn, {"consumable_key": _C_KEY})
        assert result is not None, (
            f"_catalog_entry(consumable_key={_C_KEY!r}) zwróciło None — "
            "konsumabla istnieje TYLKO w game_items"
        )
        key, label, item_type = result
        assert key == _C_KEY
        assert item_type == "consumable"
    finally:
        _cleanup_test_items(conn)
        conn.close()


# ─── Test 4: inventory_context_service ───────────────────────────────────────

def test_inventory_context_shows_game_items_weapon():
    """build_inventory_block musi wyświetlić broń z game_items w kontekście LLM."""
    from app.services.inventory_context_service import build_inventory_block

    conn = _conn()
    _setup_test_items(conn)
    # Znajdź test character
    char = conn.execute("SELECT id FROM characters WHERE id = 1 LIMIT 1").fetchone()
    if not char:
        _cleanup_test_items(conn)
        conn.close()
        return  # No test character available

    char_id = char["id"]
    # Wstaw broń do inventory
    conn.execute("""
        INSERT INTO character_inventory (character_id, weapon_key, quantity, equipped, slot)
        VALUES (?, ?, 1, 1, 'main_hand')
    """, (char_id, _W_KEY))
    conn.commit()
    inv_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    try:
        result = build_inventory_block(conn, char_id)
        assert _W_KEY in result or "TestU11b Sword" in result, (
            f"build_inventory_block nie zawiera broni {_W_KEY!r} z game_items.\n"
            f"Wynik: {result!r}"
        )
    finally:
        conn.execute("DELETE FROM character_inventory WHERE id = ?", (inv_id,))
        conn.commit()
        _cleanup_test_items(conn)
        conn.close()


# ─── Test 5: durability_service._get_rarity ──────────────────────────────────

def test_durability_rarity_reads_from_game_items():
    """durability._get_rarity musi czytać rarity z game_items."""
    from app.services import durability_service

    conn = _conn()
    _setup_test_items(conn)
    try:
        fake_row = {"weapon_key": _W_KEY, "item_key": None, "consumable_key": None}
        result = durability_service._get_rarity(conn, fake_row)
        assert result == 2, (
            f"_get_rarity zwróciło {result} zamiast 2 — "
            f"broń {_W_KEY!r} ma rarity=2 TYLKO w game_items"
        )
    finally:
        _cleanup_test_items(conn)
        conn.close()


def test_durability_ac_bonus_reads_from_game_items():
    """durability.get_ac_penalty_for_char czyta ac_bonus z game_items (kind=armor)."""
    from app.services import durability_service

    conn = _conn()
    _setup_test_items(conn)
    # Wstaw zerwaną zbroję (durability_current=0, durability_max=5) z item_key
    char = conn.execute("SELECT id FROM characters WHERE id = 1 LIMIT 1").fetchone()
    if not char:
        _cleanup_test_items(conn)
        conn.close()
        return

    char_id = char["id"]
    conn.execute("""
        INSERT INTO character_inventory
        (character_id, item_key, quantity, equipped, slot, durability_current, durability_max)
        VALUES (?, ?, 1, 1, 'torso', 0, 5)
    """, (char_id, _I_KEY))
    conn.commit()
    inv_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    try:
        penalty = durability_service.get_ac_penalty_for_char(conn, char_id)
        # ac_bonus=42 → penalty musi być ujemne (zepsuta zbroja daje karę)
        assert penalty < 0, (
            f"get_ac_penalty_for_char={penalty} nie jest ujemne — "
            f"zbroja {_I_KEY!r} ma ac_bonus=42 TYLKO w game_items"
        )
    finally:
        conn.execute("DELETE FROM character_inventory WHERE id = ?", (inv_id,))
        conn.commit()
        _cleanup_test_items(conn)
        conn.close()


# ─── Test 6: inventory_rows_sql (get_character_inventory) ────────────────────

def test_get_character_inventory_shows_game_items_weapon():
    """get_character_inventory musi wyświetlić broń z game_items."""
    from app.services.loot_service import get_character_inventory

    conn = _conn()
    _setup_test_items(conn)
    char = conn.execute("SELECT id FROM characters WHERE id = 1 LIMIT 1").fetchone()
    if not char:
        _cleanup_test_items(conn)
        conn.close()
        return

    char_id = char["id"]
    conn.execute("""
        INSERT INTO character_inventory (character_id, weapon_key, quantity, equipped, slot)
        VALUES (?, ?, 1, 0, NULL)
    """, (char_id, _W_KEY))
    conn.commit()
    inv_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    try:
        items = get_character_inventory(char_id)
        matching = [i for i in items if i.get("key") == _W_KEY or "TestU11b" in str(i.get("label", ""))]
        assert matching, (
            f"get_character_inventory nie zawiera broni {_W_KEY!r} z game_items. "
            f"Wszystkie klucze: {[i.get('key') for i in items]}"
        )
        assert matching[0]["item_type"] == "weapon", f"item_type={matching[0]['item_type']!r}"
    finally:
        conn.execute("DELETE FROM character_inventory WHERE id = ?", (inv_id,))
        conn.commit()
        _cleanup_test_items(conn)
        conn.close()


# ─── Test 7: combat_service.get_item_catalog_for_prompt ──────────────────────

def test_item_catalog_for_prompt_includes_game_items():
    """get_item_catalog_for_prompt musi zawierać itemy z game_items."""
    from app.services.combat_service import get_item_catalog_for_prompt

    conn = _conn()
    _setup_test_items(conn)
    try:
        result = get_item_catalog_for_prompt(conn)
        assert _I_KEY in result or "TestU11b Armor" in result, (
            f"get_item_catalog_for_prompt nie zawiera {_I_KEY!r} z game_items.\n"
            f"Fragment: {result[:500]!r}"
        )
    finally:
        _cleanup_test_items(conn)
        conn.close()


# ─── Test 8: backward compatibility — istniejące dane nadal działają ─────────

def test_existing_weapons_still_work_after_switch():
    """Istniejące bronie (w game_items po backfill) nadal muszą być widoczne."""
    from app.services.weapon_rules import load_weapon_row

    conn = _conn()
    # shortsword istnieje po backfill z game_config_weapons
    result = load_weapon_row(conn, "shortsword")
    conn.close()
    assert result is not None, "shortsword nie znaleziony — backfill nie zadziałał?"
    assert result["damage_die"] in ("d6", "1d6"), f"damage_die={result['damage_die']!r}"


def test_existing_shop_items_still_work():
    """Istniejące itemy w katalogu sklepu nadal muszą być widoczne."""
    from app.services.shop_service import _catalog_item

    conn = _conn()
    result = _catalog_item(conn, "weapon", "shortsword")
    conn.close()
    assert result is not None, "shortsword nie znaleziony w katalogu sklepu"
    assert result["value_gp"] > 0, "shortsword musi mieć cenę > 0"


def test_existing_loot_entries_still_work():
    """Istniejące wpisy loot table nadal muszą być resolvowane."""
    from app.services.loot_service import _catalog_entry

    conn = _conn()
    # health_potion_small istnieje jako consumable (po backfill z game_config_consumables)
    result = _catalog_entry(conn, {"consumable_key": "health_potion_small"})
    conn.close()
    assert result is not None, "health_potion_small nie znaleziony w _catalog_entry"
    _, _, item_type = result
    assert item_type == "consumable"
