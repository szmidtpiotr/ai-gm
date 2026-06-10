"""TDD: Issue #471 — F11 price unification: single price_gp column + affix pricing."""
import sqlite3
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.shop_service import _catalog_item


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_config_weapons (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL DEFAULT '',
            damage_die TEXT NOT NULL DEFAULT 'd6',
            weapon_type TEXT NOT NULL DEFAULT 'melee',
            linked_stat TEXT NOT NULL DEFAULT 'STR',
            allowed_classes TEXT NOT NULL DEFAULT '[]',
            two_handed INTEGER NOT NULL DEFAULT 0,
            finesse INTEGER NOT NULL DEFAULT 0,
            weight_kg REAL NOT NULL DEFAULT 0.0,
            description TEXT NOT NULL DEFAULT '',
            value_gp INTEGER NOT NULL DEFAULT 0,
            price_gp INTEGER DEFAULT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            min_level INTEGER DEFAULT 1,
            location_tags TEXT DEFAULT NULL
        );
        CREATE TABLE game_config_items (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL DEFAULT '',
            item_type TEXT NOT NULL DEFAULT 'misc',
            description TEXT NOT NULL DEFAULT '',
            value_gp INTEGER NOT NULL DEFAULT 0,
            price_gp INTEGER DEFAULT NULL,
            effect_json TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            note TEXT,
            weight_kg REAL NOT NULL DEFAULT 0.0,
            ac_bonus INTEGER NOT NULL DEFAULT 0,
            charges INTEGER NOT NULL DEFAULT 1,
            allowed_classes TEXT NOT NULL DEFAULT '[]',
            min_level INTEGER DEFAULT 1,
            location_tags TEXT DEFAULT NULL
        );
        CREATE TABLE game_config_consumables (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            effect_type TEXT NOT NULL DEFAULT 'misc',
            effect_dice TEXT,
            effect_bonus INTEGER NOT NULL DEFAULT 0,
            effect_target TEXT NOT NULL DEFAULT 'self',
            weight_kg REAL NOT NULL DEFAULT 0.0,
            charges INTEGER NOT NULL DEFAULT 1,
            base_price INTEGER NOT NULL DEFAULT 0,
            price_gp INTEGER DEFAULT NULL,
            note TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            min_level INTEGER DEFAULT 1,
            location_tags TEXT DEFAULT NULL
        );
        CREATE TABLE game_config_affixes (
            key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tier INTEGER NOT NULL DEFAULT 1,
            allowed_item_types TEXT NOT NULL DEFAULT 'weapon',
            effect_json TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    # Weapons: one with price_gp set, one with only value_gp (migration compat)
    conn.execute("""INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, allowed_classes, value_gp, price_gp)
                   VALUES ('sword_iron', 'Żelazny miecz', 'd8', 'STR', '[]', 50, 60)""")
    conn.execute("""INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, allowed_classes, value_gp, price_gp)
                   VALUES ('dagger_basic', 'Sztylet', 'd4', 'DEX', '[]', 20, NULL)""")
    # Items
    conn.execute("""INSERT INTO game_config_items (key, label, item_type, description, value_gp, price_gp)
                   VALUES ('shield_wood', 'Drewniana tarcza', 'armor', '', 30, 35)""")
    conn.execute("""INSERT INTO game_config_items (key, label, item_type, description, value_gp, price_gp)
                   VALUES ('rope_hemp', 'Konopna lina', 'misc', '', 5, NULL)""")
    # Consumables
    conn.execute("""INSERT INTO game_config_consumables (key, label, description, base_price, price_gp)
                   VALUES ('potion_hp_minor', 'Mikstura leczenia', '', 40, 45)""")
    conn.execute("""INSERT INTO game_config_consumables (key, label, description, base_price, price_gp)
                   VALUES ('torch', 'Pochodnia', '', 2, NULL)""")
    # Affixes
    conn.execute("INSERT INTO game_config_affixes (key, name, tier) VALUES ('affix_sharp', 'Ostry', 1)")
    conn.execute("INSERT INTO game_config_affixes (key, name, tier) VALUES ('affix_blazing', 'Płonący', 2)")
    conn.execute("INSERT INTO game_config_affixes (key, name, tier) VALUES ('affix_legendary', 'Legendarny', 3)")
    conn.commit()
    return conn


# ─── price_gp preferred over value_gp when set ───────────────────────────────

def test_weapon_uses_price_gp_when_set():
    conn = _make_db()
    cat = _catalog_item(conn, "weapon", "sword_iron")
    assert cat is not None
    assert cat["value_gp"] == 60, f"expected price_gp=60 to win, got {cat['value_gp']}"


def test_weapon_falls_back_to_value_gp_when_price_gp_null():
    conn = _make_db()
    cat = _catalog_item(conn, "weapon", "dagger_basic")
    assert cat is not None
    assert cat["value_gp"] == 20, f"expected fallback to value_gp=20, got {cat['value_gp']}"


def test_item_uses_price_gp_when_set():
    conn = _make_db()
    cat = _catalog_item(conn, "item", "shield_wood")
    assert cat is not None
    assert cat["value_gp"] == 35


def test_item_falls_back_to_value_gp_when_price_gp_null():
    conn = _make_db()
    cat = _catalog_item(conn, "item", "rope_hemp")
    assert cat is not None
    assert cat["value_gp"] == 5


def test_consumable_uses_price_gp_when_set():
    conn = _make_db()
    cat = _catalog_item(conn, "consumable", "potion_hp_minor")
    assert cat is not None
    assert cat["value_gp"] == 45


def test_consumable_falls_back_to_base_price_when_price_gp_null():
    conn = _make_db()
    cat = _catalog_item(conn, "consumable", "torch")
    assert cat is not None
    assert cat["value_gp"] == 2


# ─── _affix_price_bonus ───────────────────────────────────────────────────────

def test_affix_price_bonus_no_affixes():
    from app.services.shop_service import _affix_price_bonus
    conn = _make_db()
    assert _affix_price_bonus(conn, []) == 0


def test_affix_price_bonus_tier1():
    from app.services.shop_service import _affix_price_bonus
    conn = _make_db()
    bonus = _affix_price_bonus(conn, ["affix_sharp"])
    assert bonus == 25, f"T1 bonus expected 25, got {bonus}"


def test_affix_price_bonus_tier2():
    from app.services.shop_service import _affix_price_bonus
    conn = _make_db()
    bonus = _affix_price_bonus(conn, ["affix_blazing"])
    assert bonus == 75, f"T2 bonus expected 75, got {bonus}"


def test_affix_price_bonus_tier3():
    from app.services.shop_service import _affix_price_bonus
    conn = _make_db()
    bonus = _affix_price_bonus(conn, ["affix_legendary"])
    assert bonus == 200, f"T3 bonus expected 200, got {bonus}"


def test_affix_price_bonus_multiple_affixes():
    from app.services.shop_service import _affix_price_bonus
    conn = _make_db()
    bonus = _affix_price_bonus(conn, ["affix_sharp", "affix_blazing"])
    assert bonus == 100, f"T1+T2 = 25+75 = 100, got {bonus}"


def test_affix_price_bonus_unknown_key_skipped():
    from app.services.shop_service import _affix_price_bonus
    conn = _make_db()
    bonus = _affix_price_bonus(conn, ["nonexistent_affix"])
    assert bonus == 0


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_catalog_item_still_returns_value_gp_key():
    """_catalog_item API unchanged — returns 'value_gp' key in dict."""
    conn = _make_db()
    cat = _catalog_item(conn, "weapon", "sword_iron")
    assert "value_gp" in cat
