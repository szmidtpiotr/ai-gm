"""TDD: Issue #1084 — forge generate-plan auto-assigns reward items scaled to difficulty."""
import json
import sqlite3
import sys
import os

sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

import pytest


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_db() -> sqlite3.Connection:
    """In-memory DB with minimal schema for testing reward-item logic."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        """ + table_sql("game_config_weapons") + """
        """ + table_sql("game_config_items") + """
        """ + table_sql("game_config_consumables") + """
    """)
    # Seed global pool (no template_id)
    conn.execute("INSERT INTO game_config_weapons (key,label,rarity) VALUES ('sword','Miecz',1)")
    conn.execute("INSERT INTO game_config_weapons (key,label,rarity) VALUES ('dagger','Sztylet',2)")
    conn.execute("INSERT INTO game_config_weapons (key,label,rarity) VALUES ('rare_sword','Magiczny Miecz',3)")
    conn.execute("INSERT INTO game_config_items (key,label,rarity) VALUES ('pouch','Sakwa',1)")
    conn.execute("INSERT INTO game_config_items (key,label,rarity) VALUES ('scroll','Zwój',2)")
    conn.execute("INSERT INTO game_config_items (key,label,rarity) VALUES ('rare_ring','Magiczny Pierścień',3)")
    conn.execute("INSERT INTO game_config_consumables (key,label,rarity) VALUES ('potion','Eliksir Zdrowia',1)")
    conn.execute("INSERT INTO game_config_consumables (key,label,rarity) VALUES ('mana_pot','Eliksir Many',2)")
    conn.execute("INSERT INTO game_config_consumables (key,label,rarity) VALUES ('rare_elixir','Eliksir Mocy',4)")
    conn.commit()
    return conn


def _import_helper():
    from app.routers.adventure_forge import _auto_assign_reward_items
    return _auto_assign_reward_items


# ─── Test główny ──────────────────────────────────────────────────────────────

def test_auto_assign_creates_template_scoped_items():
    """After auto-assign, each category has ≥1 row with template_id set."""
    auto_assign = _import_helper()
    conn = _make_db()
    template_id = 42

    result = auto_assign(conn, template_id, difficulty_rating=2)

    assert len(result) >= 1, "Should assign at least 1 item"
    # Check weapon linked
    w = conn.execute(
        "SELECT key FROM game_config_weapons WHERE template_id=? AND hidden=1", (template_id,)
    ).fetchone()
    assert w is not None, "Expected weapon with template_id=42 and hidden=1"
    # Check item linked
    it = conn.execute(
        "SELECT key FROM game_config_items WHERE template_id=? AND hidden=1", (template_id,)
    ).fetchone()
    assert it is not None, "Expected item with template_id=42 and hidden=1"
    # Check consumable linked
    c = conn.execute(
        "SELECT key FROM game_config_consumables WHERE template_id=? AND hidden=1", (template_id,)
    ).fetchone()
    assert c is not None, "Expected consumable with template_id=42 and hidden=1"
    conn.close()


def test_rarity_mapping_difficulty_low():
    """difficulty 1-2 → rarity ≤ 2 (common/uncommon)."""
    auto_assign = _import_helper()
    conn = _make_db()

    result = auto_assign(conn, template_id=10, difficulty_rating=1)

    weapons = conn.execute(
        "SELECT rarity FROM game_config_weapons WHERE template_id=10"
    ).fetchall()
    assert all(r["rarity"] <= 2 for r in weapons), "Low difficulty should pull rarity 1-2 weapons"
    conn.close()


def test_rarity_mapping_difficulty_medium():
    """difficulty 3-4 → rarity 3 (rare)."""
    auto_assign = _import_helper()
    conn = _make_db()

    result = auto_assign(conn, template_id=11, difficulty_rating=3)

    weapons = conn.execute(
        "SELECT rarity FROM game_config_weapons WHERE template_id=11"
    ).fetchall()
    assert all(r["rarity"] == 3 for r in weapons), "Medium difficulty should pull rarity 3 weapons"
    conn.close()


def test_rarity_mapping_difficulty_epic():
    """difficulty 5 → rarity 4+ (epic)."""
    auto_assign = _import_helper()
    conn = _make_db()

    result = auto_assign(conn, template_id=12, difficulty_rating=5)

    cons = conn.execute(
        "SELECT rarity FROM game_config_consumables WHERE template_id=12"
    ).fetchall()
    assert all(r["rarity"] >= 4 for r in cons), "Epic difficulty should pull rarity 4+ consumables"
    conn.close()


def test_no_items_no_crash():
    """If DB has no items at that rarity tier, returns empty list (no crash)."""
    auto_assign = _import_helper()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        """ + table_sql("game_config_weapons") + """
        """ + table_sql("game_config_items") + """
        """ + table_sql("game_config_consumables") + """
    """)
    # No items in DB — should return empty list, no exception
    result = auto_assign(conn, template_id=99, difficulty_rating=2)
    assert result == [], f"Expected [], got {result}"
    conn.close()


def test_global_pool_not_polluted():
    """Original global items must NOT have template_id set after auto-assign."""
    auto_assign = _import_helper()
    conn = _make_db()

    auto_assign(conn, template_id=77, difficulty_rating=2)

    # Global pool items must still have template_id=NULL
    global_weapons = conn.execute(
        "SELECT key FROM game_config_weapons WHERE template_id IS NULL"
    ).fetchall()
    assert len(global_weapons) > 0, "Global pool weapons should remain unaffected"
    conn.close()


def test_response_includes_auto_assigned_items_field():
    """_auto_assign_reward_items returns [{category, key, name}] list."""
    auto_assign = _import_helper()
    conn = _make_db()

    result = auto_assign(conn, template_id=55, difficulty_rating=2)

    for entry in result:
        assert "category" in entry, f"Missing 'category' in {entry}"
        assert "key" in entry, f"Missing 'key' in {entry}"
        assert "name" in entry, f"Missing 'name' in {entry}"
        assert entry["category"] in ("weapon", "item", "consumable"), f"Unknown category: {entry['category']}"
    conn.close()
