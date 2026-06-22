"""Phase 8F-3 — CHA-based sell ratio in shop service."""

from __future__ import annotations
from _fixtures_schema import table_sql

import sqlite3

import pytest


def _seed_db(path: str, cha: int, item_value: int = 10) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY,
                name TEXT,
                gold_gp INTEGER NOT NULL DEFAULT 0,
                sheet_json TEXT
            );
            CREATE TABLE npcs (
                id INTEGER PRIMARY KEY,
                key TEXT UNIQUE,
                label TEXT,
                npc_type TEXT,
                is_shop INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                shop_inventory_json TEXT
            );
            CREATE TABLE character_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL,
                item_key TEXT,
                weapon_key TEXT,
                consumable_key TEXT,
                quantity INTEGER NOT NULL DEFAULT 1,
                source TEXT
            );
            """ + table_sql("game_config_items") + """
            """ + table_sql("game_config_weapons") + """
            """ + table_sql("game_config_consumables") + """
            """
        )
        sheet = (
            '{"stats":{"STR":10,"DEX":10,"CON":10,"INT":10,"WIS":10,"CHA":%d},"current_hp":10,"max_hp":10}'
            % int(cha)
        )
        conn.execute(
            "INSERT INTO characters(id, name, gold_gp, sheet_json) VALUES (1, 'Hero', 100, ?)",
            (sheet,),
        )
        conn.execute(
            """
            INSERT INTO npcs(id, key, label, npc_type, is_shop, is_active, shop_inventory_json)
            VALUES (1, 'merchant_aldric', 'Aldric', 'merchant', 1, 1, '[{"type":"item","key":"test_item"}]')
            """
        )
        conn.execute(
            "INSERT INTO game_config_items(key, label, description, value_gp, is_active) VALUES ('test_item', 'Test item', 'Desc', ?, 1)",
            (int(item_value),),
        )
        conn.execute(
            "INSERT INTO character_inventory(character_id, item_key, quantity, source) VALUES (1, 'test_item', 1, 'loot')"
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def cha_db_factory(tmp_path):
    def _make(cha: int, item_value: int = 10):
        db_path = str(tmp_path / f"phase8f_cha_{cha}_{item_value}.db")
        _seed_db(db_path, cha, item_value=item_value)
        return db_path

    return _make


def _with_patched_db(db_path: str):
    from app.services import loot_service, shop_service

    old_loot = loot_service.LOOT_DB_PATH
    old_shop = shop_service.LOOT_DB_PATH
    loot_service.LOOT_DB_PATH = db_path
    shop_service.LOOT_DB_PATH = db_path
    return shop_service, old_loot, old_shop, loot_service


def test_cha_sell_ratio_10_is_50_percent():
    from app.services.shop_service import _cha_sell_ratio

    assert _cha_sell_ratio(10) == 0.5


def test_cha_sell_ratio_14_is_58_percent():
    from app.services.shop_service import _cha_sell_ratio

    assert _cha_sell_ratio(14) == 0.58


def test_cha_sell_ratio_8_is_46_percent():
    from app.services.shop_service import _cha_sell_ratio

    assert _cha_sell_ratio(8) == 0.46


def test_cha_sell_ratio_20_capped_at_70_percent():
    from app.services.shop_service import _cha_sell_ratio

    assert _cha_sell_ratio(20) == 0.7


def test_cha_sell_ratio_1_is_32_percent_with_linear_rule():
    from app.services.shop_service import _cha_sell_ratio

    assert _cha_sell_ratio(1) == 0.32


def test_sell_minimum_1gp_even_low_value(cha_db_factory):
    db_path = cha_db_factory(cha=1, item_value=1)
    shop_service, old_loot, old_shop, loot_service = _with_patched_db(db_path)
    try:
        row = sqlite3.connect(db_path).execute(
            "SELECT id FROM character_inventory WHERE character_id = 1 LIMIT 1"
        ).fetchone()
        out = shop_service.sell_item(character_id=1, inventory_id=int(row[0]))
        assert out["earned_gp"] == 1
    finally:
        loot_service.LOOT_DB_PATH = old_loot
        shop_service.LOOT_DB_PATH = old_shop


def test_sell_response_contains_cha_and_ratio(cha_db_factory):
    db_path = cha_db_factory(cha=14, item_value=10)
    shop_service, old_loot, old_shop, loot_service = _with_patched_db(db_path)
    try:
        row = sqlite3.connect(db_path).execute(
            "SELECT id FROM character_inventory WHERE character_id = 1 LIMIT 1"
        ).fetchone()
        out = shop_service.sell_item(character_id=1, inventory_id=int(row[0]))
        assert out["cha"] == 14
        assert out["sell_ratio"] == 0.58
        assert out["earned_gp"] == 5
    finally:
        loot_service.LOOT_DB_PATH = old_loot
        shop_service.LOOT_DB_PATH = old_shop


def test_shop_inventory_response_contains_sell_ratio(cha_db_factory):
    db_path = cha_db_factory(cha=18, item_value=10)
    shop_service, old_loot, old_shop, loot_service = _with_patched_db(db_path)
    try:
        out = shop_service.get_shop_inventory(npc_id=1, character_id=1)
        assert out["cha"] == 18
        assert out["sell_ratio"] == 0.66
        assert out["sell_items"][0]["sell_price_gp"] == 6
    finally:
        loot_service.LOOT_DB_PATH = old_loot
        shop_service.LOOT_DB_PATH = old_shop
