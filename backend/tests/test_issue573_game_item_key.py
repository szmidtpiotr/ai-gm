"""TDD: Issue #573 (part 1) — character_inventory.game_item_key is populated.

The unified FK `game_item_key` was never written (0/N rows). After this fix every granted
item resolves the unified key from game_items, and a backfill covers existing rows.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import loot_service


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE game_items (key TEXT PRIMARY KEY, is_active INTEGER)")
    c.execute("INSERT INTO game_items VALUES ('short_sword', 1), ('bandage', 1), ('inactive_x', 0)")
    c.execute(
        "CREATE TABLE character_inventory (id INTEGER PRIMARY KEY, weapon_key TEXT, "
        "item_key TEXT, consumable_key TEXT, game_item_key TEXT)"
    )
    c.commit()
    return c


def test_resolve_known_key():
    c = _conn()
    assert loot_service._resolve_game_item_key(c, "short_sword") == "short_sword"


def test_resolve_unknown_key_returns_none():
    c = _conn()
    assert loot_service._resolve_game_item_key(c, "does_not_exist") is None


def test_resolve_inactive_key_returns_none():
    c = _conn()
    assert loot_service._resolve_game_item_key(c, "inactive_x") is None


def test_backfill_migration_populates_existing_rows():
    """The idempotent backfill maps the legacy key to game_item_key."""
    c = _conn()
    c.execute("INSERT INTO character_inventory (id, weapon_key, game_item_key) VALUES (1, 'short_sword', NULL)")
    c.execute("INSERT INTO character_inventory (id, consumable_key, game_item_key) VALUES (2, 'bandage', NULL)")
    c.execute("INSERT INTO character_inventory (id, item_key, game_item_key) VALUES (3, 'not_in_catalog', NULL)")
    c.commit()
    # Same SQL as the RAW migration in main.py.
    c.execute(
        "UPDATE character_inventory SET game_item_key = COALESCE(weapon_key, item_key, consumable_key) "
        "WHERE game_item_key IS NULL "
        "AND COALESCE(weapon_key, item_key, consumable_key) IN (SELECT key FROM game_items)"
    )
    c.commit()
    rows = {r["id"]: r["game_item_key"] for r in c.execute("SELECT id, game_item_key FROM character_inventory")}
    assert rows[1] == "short_sword"
    assert rows[2] == "bandage"
    assert rows[3] is None  # not in catalog → stays NULL
