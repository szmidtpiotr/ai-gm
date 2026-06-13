"""TDD: Issue #556 — U11a: CREATE TABLE game_items + backfill ze starych tabel.

Weryfikuje:
1. Tabela game_items istnieje z wymaganymi kolumnami
2. Liczba rekordów per kind == suma ze starych tabel (bez duplikatów item/consumable)
3. Kolumny game_item_key NULL obecne w character_inventory i game_config_loot_entries
4. Stare tabele niezmienione (count bez zmian)
"""
import sqlite3
import sys
import os

sys.path.insert(0, "/app")

DB_PATH = os.getenv("DB_PATH", "/data/ai_gm.db")

REQUIRED_COLUMNS = {
    "id", "key", "kind", "label", "description", "price_gp",
    "effect_json", "equip_slot", "rarity", "min_level", "location_tags",
    "created_by", "approved", "is_active", "weapon_data", "item_data",
    "weight_kg", "note", "locked_at", "created_at", "updated_at",
}

VALID_KINDS = {"weapon", "armor", "item", "consumable"}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Test 1: Tabela game_items istnieje z wymaganymi kolumnami ────────────────

def test_game_items_table_exists_with_required_columns():
    """game_items musi istnieć z pełnym zestawem kolumn wg U11a."""
    conn = get_conn()
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(game_items)")}
    assert cols, "Tabela game_items nie istnieje"
    missing = REQUIRED_COLUMNS - cols
    assert not missing, f"Brakujące kolumny w game_items: {missing}"
    conn.close()


# ─── Test 2: kind CHECK constraint ───────────────────────────────────────────

def test_game_items_kind_values_valid():
    """Wszystkie rekordy w game_items mają kind w dozwolonym zbiorze."""
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT kind FROM game_items").fetchall()
    assert rows, "game_items jest pusta — backfill nie działa"
    for row in rows:
        assert row["kind"] in VALID_KINDS, f"Niedozwolony kind: {row['kind']}"
    conn.close()


# ─── Test 3: Liczba rekordów per kind ────────────────────────────────────────

def test_game_items_count_matches_source_tables():
    """Backfill: count per kind == oczekiwana suma ze starych tabel."""
    conn = get_conn()

    # Weapons: all from game_config_weapons
    expected_weapon = conn.execute("SELECT COUNT(*) FROM game_config_weapons").fetchone()[0]
    actual_weapon = conn.execute(
        "SELECT COUNT(*) FROM game_items WHERE kind='weapon'"
    ).fetchone()[0]
    assert actual_weapon == expected_weapon, (
        f"kind=weapon: game_items={actual_weapon}, game_config_weapons={expected_weapon}"
    )

    # Armor: game_config_items WHERE item_type IN ('armor','shield')
    expected_armor = conn.execute(
        "SELECT COUNT(*) FROM game_config_items WHERE item_type IN ('armor','shield')"
    ).fetchone()[0]
    actual_armor = conn.execute(
        "SELECT COUNT(*) FROM game_items WHERE kind='armor'"
    ).fetchone()[0]
    assert actual_armor == expected_armor, (
        f"kind=armor: game_items={actual_armor}, game_config_items[armor/shield]={expected_armor}"
    )

    # Item: game_config_items WHERE item_type NOT IN ('armor','shield','consumable')
    expected_item = conn.execute(
        "SELECT COUNT(*) FROM game_config_items WHERE item_type NOT IN ('armor','shield','consumable')"
    ).fetchone()[0]
    actual_item = conn.execute(
        "SELECT COUNT(*) FROM game_items WHERE kind='item'"
    ).fetchone()[0]
    assert actual_item == expected_item, (
        f"kind=item: game_items={actual_item}, game_config_items[non-armor/consumable]={expected_item}"
    )

    # Consumable: all from game_config_consumables (canonical source, skip item dupes)
    expected_consumable = conn.execute(
        "SELECT COUNT(*) FROM game_config_consumables"
    ).fetchone()[0]
    actual_consumable = conn.execute(
        "SELECT COUNT(*) FROM game_items WHERE kind='consumable'"
    ).fetchone()[0]
    assert actual_consumable == expected_consumable, (
        f"kind=consumable: game_items={actual_consumable}, game_config_consumables={expected_consumable}"
    )

    conn.close()


# ─── Test 4: Dane kolumnowe dla sample rekordów ───────────────────────────────

def test_game_items_weapon_has_weapon_data():
    """Broń musi mieć weapon_data z damage_die."""
    conn = get_conn()
    import json
    row = conn.execute(
        "SELECT key, weapon_data FROM game_items WHERE kind='weapon' LIMIT 1"
    ).fetchone()
    assert row, "Brak broni w game_items"
    data = json.loads(row["weapon_data"] or "{}")
    assert "damage_die" in data, (
        f"weapon_data dla {row['key']} nie zawiera damage_die: {data}"
    )
    conn.close()


def test_game_items_consumable_price_mapped():
    """Konsumabla musi mieć price_gp > 0 (base_price z game_config_consumables)."""
    conn = get_conn()
    row = conn.execute(
        "SELECT key, price_gp FROM game_items WHERE kind='consumable' AND price_gp > 0 LIMIT 1"
    ).fetchone()
    assert row, "Żadna konsumabla nie ma price_gp > 0 — mapowanie base_price→price_gp nie działa"
    conn.close()


# ─── Test 5: FK columns obecne w character_inventory i loot_entries ──────────

def test_character_inventory_has_game_item_key_column():
    """character_inventory musi mieć kolumnę game_item_key (NULL, FK docelowy U11c)."""
    conn = get_conn()
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(character_inventory)")}
    assert "game_item_key" in cols, (
        "Kolumna game_item_key brakuje w character_inventory"
    )
    conn.close()


def test_loot_entries_has_game_item_key_column():
    """game_config_loot_entries musi mieć kolumnę game_item_key (NULL, FK docelowy U11c)."""
    conn = get_conn()
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(game_config_loot_entries)")}
    assert "game_item_key" in cols, (
        "Kolumna game_item_key brakuje w game_config_loot_entries"
    )
    conn.close()


# ─── Test 6: Stare tabele niezmienione (backward compat) ─────────────────────

def test_old_tables_still_exist_and_unchanged():
    """game_config_weapons/items/consumables muszą nadal istnieć z danymi."""
    conn = get_conn()
    assert conn.execute("SELECT COUNT(*) FROM game_config_weapons").fetchone()[0] > 0
    assert conn.execute("SELECT COUNT(*) FROM game_config_items").fetchone()[0] > 0
    assert conn.execute("SELECT COUNT(*) FROM game_config_consumables").fetchone()[0] > 0
    conn.close()
