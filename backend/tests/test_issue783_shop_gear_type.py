"""TDD: Issue #783 — Shop buy handler must accept item_type='gear' (alias for 'item').

game_config_items.item_type can be 'gear'. GET /shop returns type='gear' for such items
(catalog reads item_type_raw from the row). Frontend sends item_type='gear' on buy.
The allowed check compared stored 'item' with requested 'gear' → mismatch → 404.
Fix: add _norm_item_type() that maps 'gear' → 'item' and use it in allowed check.
"""
import sqlite3
import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import shop_service


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_db() -> sqlite3.Connection:
    """In-memory DB: torch stored as item_type='gear' in catalog, type='item' in shop JSON."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY, key TEXT NOT NULL, label TEXT NOT NULL,
            npc_type TEXT DEFAULT 'neutral', is_shop INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1, is_crafter INTEGER DEFAULT 0,
            shop_inventory_json TEXT DEFAULT '[]'
        );
        CREATE TABLE game_items (
            key TEXT PRIMARY KEY, label TEXT, description TEXT DEFAULT '',
            price_gp INTEGER DEFAULT 0, min_level INTEGER DEFAULT 1,
            location_tags TEXT DEFAULT NULL, kind TEXT DEFAULT 'item',
            item_data TEXT DEFAULT '{}', is_active INTEGER DEFAULT 1
        );
        CREATE TABLE game_config_items (
            key TEXT PRIMARY KEY, label TEXT NOT NULL, item_type TEXT DEFAULT 'misc',
            description TEXT DEFAULT '', price_gp INTEGER DEFAULT NULL,
            value_gp INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            approved INTEGER DEFAULT 1, rarity INTEGER DEFAULT 1,
            allowed_classes TEXT DEFAULT '[]', min_level INTEGER DEFAULT 1,
            location_tags TEXT DEFAULT NULL
        );
        CREATE TABLE game_config_weapons (
            key TEXT PRIMARY KEY, label TEXT NOT NULL, damage_die TEXT DEFAULT '1d6',
            linked_stat TEXT DEFAULT 'STR', allowed_classes TEXT DEFAULT '[]',
            is_active INTEGER DEFAULT 1, description TEXT DEFAULT '',
            weapon_type TEXT DEFAULT 'melee', value_gp INTEGER DEFAULT 0,
            price_gp INTEGER DEFAULT 0, min_level INTEGER DEFAULT 1,
            location_tags TEXT DEFAULT NULL
        );
        CREATE TABLE game_config_consumables (
            key TEXT PRIMARY KEY, label TEXT NOT NULL, description TEXT DEFAULT '',
            base_price INTEGER DEFAULT 0, price_gp INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1, approved INTEGER DEFAULT 1,
            rarity INTEGER DEFAULT 1, min_level INTEGER DEFAULT 1,
            location_tags TEXT DEFAULT NULL
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, gold_gp INTEGER DEFAULT 0,
            sheet_json TEXT DEFAULT '{}', campaign_id INTEGER DEFAULT NULL
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY, character_id INTEGER NOT NULL,
            item_key TEXT, weapon_key TEXT, consumable_key TEXT,
            quantity INTEGER DEFAULT 1, source TEXT DEFAULT ''
        );

        -- Torch: stored as item_type='gear' in old catalog (this is the root cause)
        INSERT INTO game_config_items (key, label, item_type, value_gp)
        VALUES ('torch', 'Pochodnia', 'gear', 1);

        -- Aldrica's shop: torch stored as type='item' (canonical), dagger as weapon
        INSERT INTO npcs VALUES (
            1, 'aldrica', 'Aldrica Kupiec', 'merchant', 1, 1, 0,
            '[{"type":"item","key":"torch"},{"type":"weapon","key":"dagger"}]'
        );

        -- Test character with gold (not Piotr's — never use 999420)
        INSERT INTO characters (id, gold_gp, sheet_json)
        VALUES (42, 100, '{"stats":{"CHA":10}}');
    """)
    return conn


# ─── _norm_item_type helper ───────────────────────────────────────────────────

def test_norm_item_type_function_exists():
    """_norm_item_type must be importable — AttributeError before fix."""
    assert hasattr(shop_service, "_norm_item_type"), (
        "add _norm_item_type(t: str) -> str to shop_service.py"
    )


def test_norm_item_type_gear_maps_to_item():
    """'gear' must normalize to 'item' — this is the core of the fix."""
    from app.services.shop_service import _norm_item_type
    assert _norm_item_type("gear") == "item", "'gear' should map to 'item'"


def test_norm_item_type_item_unchanged():
    """'item' stays 'item' — backward compat."""
    from app.services.shop_service import _norm_item_type
    assert _norm_item_type("item") == "item"


def test_norm_item_type_weapon_unchanged():
    """'weapon' stays 'weapon' — other canonical types unaffected."""
    from app.services.shop_service import _norm_item_type
    assert _norm_item_type("weapon") == "weapon"


# ─── Test główny: buy z item_type='gear' musi przejść ────────────────────────

def test_buy_item_gear_type_accepted(monkeypatch):
    """buy_item z item_type='gear' NIE może rzucać 'item_not_in_shop'.

    Sklep ma torch jako type='item'. GET /shop zwraca type='gear' (z katalogu).
    Frontend wysyła type='gear' → allowed check powinien zaakceptować po fixie.
    """
    conn = _make_db()
    monkeypatch.setattr("app.services.shop_service._conn", lambda: conn)
    monkeypatch.setattr("app.services.shop_service.get_character_gold", lambda cid: 100)
    monkeypatch.setattr("app.services.shop_service.apply_character_gold_delta", lambda cid, delta, src: 99)
    monkeypatch.setattr("app.services.shop_service.grant_loot_to_character", lambda cid, items, source: None)

    result = shop_service.buy_item(
        character_id=42,
        npc_id=1,
        item_type="gear",
        item_key="torch",
    )
    assert result["paid_gp"] == 1, f"torch costs 1 gp, got {result['paid_gp']}"
    assert result["item"]["key"] == "torch"


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_buy_item_item_type_still_works(monkeypatch):
    """item_type='item' (stary sposób) nadal kupuje Pochodnię."""
    conn = _make_db()
    monkeypatch.setattr("app.services.shop_service._conn", lambda: conn)
    monkeypatch.setattr("app.services.shop_service.get_character_gold", lambda cid: 100)
    monkeypatch.setattr("app.services.shop_service.apply_character_gold_delta", lambda cid, delta, src: 99)
    monkeypatch.setattr("app.services.shop_service.grant_loot_to_character", lambda cid, items, source: None)

    result = shop_service.buy_item(
        character_id=42,
        npc_id=1,
        item_type="item",
        item_key="torch",
    )
    assert result["paid_gp"] == 1, "item_type=item must still work after fix"


def test_buy_item_unknown_key_still_rejected(monkeypatch):
    """Klucz spoza sklepu nadal odrzucany — allowed check nie omija security."""
    conn = _make_db()
    monkeypatch.setattr("app.services.shop_service._conn", lambda: conn)
    monkeypatch.setattr("app.services.shop_service.get_character_gold", lambda cid: 100)
    monkeypatch.setattr("app.services.shop_service.apply_character_gold_delta", lambda cid, delta, src: 99)
    monkeypatch.setattr("app.services.shop_service.grant_loot_to_character", lambda cid, items, source: None)

    with pytest.raises(ValueError, match="item_not_in_shop"):
        shop_service.buy_item(
            character_id=42,
            npc_id=1,
            item_type="gear",
            item_key="magic_orb_of_doom",  # nie ma w sklepie
        )
