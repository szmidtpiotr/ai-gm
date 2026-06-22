"""TDD: Issue #469 — Dynamic shop inventory filtered by location + player level."""
import json
import sqlite3
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixtures_schema as fx

import pytest
from app.services.shop_service import (
    get_shop_inventory,
    _catalog_item,
    _get_character_level,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_db():
    """In-memory DB with minimal schema for shop + level/location tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # game_config_* przez helper (#928 — pełny schemat z price_gp/min_level/etc.)
    fx.create_tables(conn, "game_config_weapons", "game_config_items", "game_config_consumables")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS game_items (
            id INTEGER PRIMARY KEY,
            key TEXT NOT NULL,
            kind TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            description TEXT DEFAULT '',
            price_gp REAL DEFAULT 0,
            effect_json TEXT DEFAULT NULL,
            equip_slot TEXT DEFAULT NULL,
            rarity INTEGER DEFAULT 1,
            min_level INTEGER DEFAULT 1,
            location_tags TEXT DEFAULT '[]',
            created_by TEXT DEFAULT 'seed',
            approved INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            weapon_data TEXT DEFAULT '{}',
            item_data TEXT DEFAULT '{}',
            weight_kg REAL DEFAULT 0,
            note TEXT DEFAULT NULL,
            locked_at TEXT DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            gold_gp INTEGER NOT NULL DEFAULT 0,
            sheet_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY,
            key TEXT NOT NULL,
            label TEXT NOT NULL,
            npc_type TEXT NOT NULL DEFAULT 'neutral',
            is_shop INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            is_crafter INTEGER NOT NULL DEFAULT 0,
            shop_inventory_json TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY,
            character_id INTEGER NOT NULL,
            item_key TEXT,
            weapon_key TEXT,
            consumable_key TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            source TEXT DEFAULT '',
            equipped INTEGER NOT NULL DEFAULT 0
        );

        -- Weapons: one basic (level 1, everywhere), one high-level, one city-only
        INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, allowed_classes, is_active, description, weapon_type, two_handed, finesse, weight_kg, value_gp, approved, rarity, min_level, location_tags) VALUES
            ('sword_basic', 'Miecz zwykły', '1d6', 'STR', '[]', 1, 'Tani miecz', 'melee', 0, 0, 1.5, 50, 1, 1, 1, NULL),
            ('sword_elite', 'Miecz elitarny', '1d10', 'STR', '[]', 1, 'Miecz dla weteranów', 'melee', 0, 0, 2.0, 500, 1, 3, 10, NULL),
            ('sword_city', 'Miecz miejski', '1d8', 'STR', '[]', 1, 'Sprzedawany tylko w mieście', 'melee', 0, 0, 2.0, 200, 1, 2, 1, '["city","town"]');

        -- Consumable: basic (everywhere), forest-only
        INSERT INTO game_config_consumables (key, label, description, base_price, is_active, approved, rarity, min_level, location_tags) VALUES
            ('potion_heal', 'Mikstura leczenia', 'Leczy 2k6+2 HP', 30, 1, 1, 1, 1, NULL),
            ('herb_forest', 'Zioło leśne', 'Tylko w lesie dostępne', 15, 1, 1, 1, 1, '["forest","wilderness"]');

        -- Shop NPC selling all items
        INSERT INTO npcs (id, key, label, npc_type, is_shop, is_active, is_crafter, shop_inventory_json) VALUES
            (1, 'blacksmith', 'Kowal', 'merchant', 1, 1, 0,
             '[{"type":"weapon","key":"sword_basic"},{"type":"weapon","key":"sword_elite"},{"type":"weapon","key":"sword_city"},{"type":"consumable","key":"potion_heal"},{"type":"consumable","key":"herb_forest"}]');

        -- Character: level 3
        INSERT INTO characters VALUES
            (1, 200, '{"level": 3, "stats": {"CHA": 10}}');

        -- Character: level 12
        INSERT INTO characters VALUES
            (2, 1000, '{"level": 12, "stats": {"CHA": 10}}');
    """)
    return conn


# ─── Test _catalog_item returns min_level + location_tags ────────────────────

def test_catalog_item_returns_min_level():
    conn = _make_db()
    cat = _catalog_item(conn, "weapon", "sword_elite")
    assert cat is not None
    assert cat.get("min_level") == 10, f"expected min_level=10, got {cat.get('min_level')}"


def test_catalog_item_returns_location_tags():
    conn = _make_db()
    cat = _catalog_item(conn, "weapon", "sword_city")
    assert cat is not None
    tags = cat.get("location_tags")
    assert tags is not None
    parsed = json.loads(tags) if isinstance(tags, str) else tags
    assert "city" in parsed, f"expected 'city' in location_tags, got {parsed}"


def test_catalog_item_null_location_tags_for_universal_item():
    conn = _make_db()
    cat = _catalog_item(conn, "weapon", "sword_basic")
    assert cat is not None
    assert cat.get("location_tags") is None, "universal item should have NULL location_tags"


# ─── Test _get_character_level ───────────────────────────────────────────────

def test_get_character_level_reads_sheet_json():
    conn = _make_db()
    level = _get_character_level(conn, 1)
    assert level == 3, f"expected 3, got {level}"


def test_get_character_level_defaults_to_1_for_missing():
    conn = _make_db()
    # Character with no level in sheet
    conn.execute("INSERT INTO characters VALUES (99, 0, '{}')")
    level = _get_character_level(conn, 99)
    assert level == 1, f"expected 1 default, got {level}"


# ─── Test level filtering in get_shop_inventory ──────────────────────────────

def test_low_level_char_cannot_see_high_level_items(monkeypatch):
    """Character level 3 should NOT see sword_elite (min_level=10)."""
    conn = _make_db()

    def _mock_conn():
        return conn

    monkeypatch.setattr("app.services.shop_service._conn", _mock_conn)
    monkeypatch.setattr("app.services.shop_service.get_character_gold", lambda cid: 200)

    result = get_shop_inventory(1, 1)  # npc_id=1, char_id=1 (level 3)
    item_keys = [it["key"] for it in result["items"]]
    assert "sword_elite" not in item_keys, f"sword_elite should be hidden from level 3 char, got {item_keys}"
    assert "sword_basic" in item_keys, f"sword_basic should be visible, got {item_keys}"


def test_high_level_char_can_see_high_level_items(monkeypatch):
    """Character level 12 SHOULD see sword_elite (min_level=10)."""
    conn = _make_db()

    def _mock_conn():
        return conn

    monkeypatch.setattr("app.services.shop_service._conn", _mock_conn)
    monkeypatch.setattr("app.services.shop_service.get_character_gold", lambda cid: 1000)

    result = get_shop_inventory(1, 2)  # npc_id=1, char_id=2 (level 12)
    item_keys = [it["key"] for it in result["items"]]
    assert "sword_elite" in item_keys, f"sword_elite should be visible for level 12 char, got {item_keys}"


# ─── Test location filtering in get_shop_inventory ──────────────────────────

def test_city_location_shows_city_items(monkeypatch):
    """With location_key='city', sword_city (location_tags=[city,town]) SHOULD appear."""
    conn = _make_db()

    def _mock_conn():
        return conn

    monkeypatch.setattr("app.services.shop_service._conn", _mock_conn)
    monkeypatch.setattr("app.services.shop_service.get_character_gold", lambda cid: 200)

    result = get_shop_inventory(1, 1, location_key="city")
    item_keys = [it["key"] for it in result["items"]]
    assert "sword_city" in item_keys, f"sword_city should appear in city, got {item_keys}"


def test_forest_location_hides_city_items(monkeypatch):
    """With location_key='forest', sword_city (location_tags=[city,town]) should NOT appear."""
    conn = _make_db()

    def _mock_conn():
        return conn

    monkeypatch.setattr("app.services.shop_service._conn", _mock_conn)
    monkeypatch.setattr("app.services.shop_service.get_character_gold", lambda cid: 200)

    result = get_shop_inventory(1, 1, location_key="forest")
    item_keys = [it["key"] for it in result["items"]]
    assert "sword_city" not in item_keys, f"sword_city should be hidden in forest, got {item_keys}"
    assert "herb_forest" in item_keys, f"herb_forest should appear in forest, got {item_keys}"


def test_no_location_key_shows_universal_items_only(monkeypatch):
    """Without location_key, location-restricted items should NOT appear."""
    conn = _make_db()

    def _mock_conn():
        return conn

    monkeypatch.setattr("app.services.shop_service._conn", _mock_conn)
    monkeypatch.setattr("app.services.shop_service.get_character_gold", lambda cid: 200)

    result = get_shop_inventory(1, 1, location_key=None)
    item_keys = [it["key"] for it in result["items"]]
    assert "sword_city" not in item_keys, f"city item should be hidden with no location, got {item_keys}"
    assert "herb_forest" not in item_keys, f"forest item should be hidden with no location, got {item_keys}"
    assert "sword_basic" in item_keys, "universal items should always show"
    assert "potion_heal" in item_keys, "universal consumable should show"


def test_null_location_tags_item_shows_everywhere(monkeypatch):
    """Items with NULL location_tags appear in any location."""
    conn = _make_db()

    def _mock_conn():
        return conn

    monkeypatch.setattr("app.services.shop_service._conn", _mock_conn)
    monkeypatch.setattr("app.services.shop_service.get_character_gold", lambda cid: 200)

    for loc in ["city", "forest", "dungeon"]:
        result = get_shop_inventory(1, 1, location_key=loc)
        item_keys = [it["key"] for it in result["items"]]
        assert "sword_basic" in item_keys, f"sword_basic (no location restriction) should appear at {loc}"
        assert "potion_heal" in item_keys, f"potion_heal should appear at {loc}"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_get_shop_inventory_without_location_key_still_works(monkeypatch):
    """Old call signature (npc_id, char_id) still works — no location_key."""
    conn = _make_db()

    def _mock_conn():
        return conn

    monkeypatch.setattr("app.services.shop_service._conn", _mock_conn)
    monkeypatch.setattr("app.services.shop_service.get_character_gold", lambda cid: 200)

    result = get_shop_inventory(1, 1)  # no location_key — no crash
    assert "items" in result
    assert "npc" in result
    assert result["npc"]["key"] == "blacksmith"
