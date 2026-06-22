"""TDD: Issue #470 — CHA modifier affects buy price (discount/markup), symmetric to sell."""
import sqlite3
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixtures_schema as fx

import math
import pytest
from app.services.shop_service import (
    _cha_buy_multiplier,
    _buy_price,
    get_shop_inventory,
)


# ─── _cha_buy_multiplier — formula price_gp × (1 - CHA_mod × 0.05) ───────────

def test_buy_multiplier_neutral_cha_is_one():
    """CHA 10 → mod 0 → multiplier 1.0 (no change)."""
    assert _cha_buy_multiplier(10) == 1.0


def test_buy_multiplier_high_cha_gives_discount():
    """CHA 18 → mod +4 → multiplier 1 - 0.2 = 0.8 (20% discount)."""
    assert _cha_buy_multiplier(18) == pytest.approx(0.8)


def test_buy_multiplier_low_cha_gives_markup():
    """CHA 6 → mod -2 → multiplier 1 + 0.1 = 1.1 (10% markup)."""
    assert _cha_buy_multiplier(6) == pytest.approx(1.1)


def test_buy_multiplier_clamped_min_50pct():
    """Very high CHA cannot drop price below 50% of base."""
    assert _cha_buy_multiplier(30) >= 0.5
    # CHA 30 → mod 10 → 1 - 0.5 = 0.5 exactly (clamp floor)
    assert _cha_buy_multiplier(30) == pytest.approx(0.5)
    # Even absurd CHA stays at 0.5 floor
    assert _cha_buy_multiplier(50) == pytest.approx(0.5)


# ─── _buy_price — applies multiplier to base price ───────────────────────────

def test_buy_price_high_cha_cheaper():
    """100 gp item with CHA 18 → 80 gp."""
    assert _buy_price(100, 18) == 80


def test_buy_price_low_cha_more_expensive():
    """100 gp item with CHA 6 → 110 gp."""
    assert _buy_price(100, 6) == 110


def test_buy_price_neutral_cha_unchanged():
    """100 gp item with CHA 10 → 100 gp."""
    assert _buy_price(100, 10) == 100


def test_buy_price_min_1_for_priced_item():
    """A 1 gp item never rounds to 0 even with max discount."""
    assert _buy_price(1, 30) >= 1


# ─── get_shop_inventory exposes buy_price_gp per item ────────────────────────

def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # game_config_* przez helper (#928 — pełny schemat z price_gp/etc.)
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
        CREATE TABLE characters (id INTEGER PRIMARY KEY, gold_gp INTEGER DEFAULT 0, sheet_json TEXT DEFAULT '{}');
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY, key TEXT NOT NULL, label TEXT NOT NULL, npc_type TEXT DEFAULT 'neutral',
            is_shop INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1, is_crafter INTEGER DEFAULT 0, shop_inventory_json TEXT DEFAULT '[]'
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY, character_id INTEGER NOT NULL, item_key TEXT, weapon_key TEXT,
            consumable_key TEXT, quantity INTEGER DEFAULT 1, source TEXT DEFAULT '', equipped INTEGER DEFAULT 0
        );

        INSERT INTO game_config_weapons (key, label, value_gp) VALUES ('sword_basic', 'Miecz', 100);
        INSERT INTO npcs (id, key, label, npc_type, is_shop, is_active, is_crafter, shop_inventory_json) VALUES
            (1, 'blacksmith', 'Kowal', 'merchant', 1, 1, 0, '[{"type":"weapon","key":"sword_basic"}]');
        -- high CHA char (18)
        INSERT INTO characters VALUES (1, 1000, '{"level": 3, "stats": {"CHA": 18}}');
        -- neutral CHA char (10)
        INSERT INTO characters VALUES (2, 1000, '{"level": 3, "stats": {"CHA": 10}}');
    """)
    return conn


def test_get_shop_inventory_includes_buy_price_for_high_cha(monkeypatch):
    conn = _make_db()
    monkeypatch.setattr("app.services.shop_service._conn", lambda: conn)
    monkeypatch.setattr("app.services.shop_service.get_character_gold", lambda cid: 1000)

    result = get_shop_inventory(1, 1)  # char 1 = CHA 18
    item = next(it for it in result["items"] if it["key"] == "sword_basic")
    assert "buy_price_gp" in item, "shop item must expose buy_price_gp (#470)"
    assert item["buy_price_gp"] == 80, f"CHA 18 → 80 gp, got {item['buy_price_gp']}"
    # base value_gp still present for reference
    assert item["value_gp"] == 100


def test_get_shop_inventory_buy_price_neutral_cha(monkeypatch):
    conn = _make_db()
    monkeypatch.setattr("app.services.shop_service._conn", lambda: conn)
    monkeypatch.setattr("app.services.shop_service.get_character_gold", lambda cid: 1000)

    result = get_shop_inventory(1, 2)  # char 2 = CHA 10
    item = next(it for it in result["items"] if it["key"] == "sword_basic")
    assert item["buy_price_gp"] == 100, f"CHA 10 → 100 gp, got {item['buy_price_gp']}"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_get_shop_inventory_still_has_sell_ratio(monkeypatch):
    """Sell-side CHA logic untouched."""
    conn = _make_db()
    monkeypatch.setattr("app.services.shop_service._conn", lambda: conn)
    monkeypatch.setattr("app.services.shop_service.get_character_gold", lambda cid: 1000)

    result = get_shop_inventory(1, 1)
    assert "sell_ratio" in result
    assert "cha" in result
    assert result["cha"] == 18
