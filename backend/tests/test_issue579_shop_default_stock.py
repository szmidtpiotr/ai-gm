"""TDD: Issue #579 — shops with empty shop_inventory_json get role-based default stock.

Village smiths/healers/merchants were seeded with an empty `shop_inventory_json` and
therefore showed nothing to buy. When stock is empty, a role-appropriate default is drawn
from the catalog. Explicit stock always wins.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import shop_service


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE npcs (id INTEGER PRIMARY KEY, key TEXT, label TEXT, is_crafter INTEGER, "
        "shop_inventory_json TEXT)"
    )
    c.execute(
        "CREATE TABLE game_items (key TEXT PRIMARY KEY, kind TEXT, price_gp INTEGER, is_active INTEGER)"
    )
    for k, kind, price in [
        ("short_sword", "weapon", 14), ("dagger", "weapon", 8),
        ("leather_armor", "armor", 20), ("bandage", "consumable", 2),
        ("healing_potion", "consumable", 25), ("rope", "item", 3),
    ]:
        c.execute("INSERT INTO game_items VALUES (?,?,?,1)", (k, kind, price))
    c.commit()
    return c


def _npc(c, key="kowal_x", label="Kowal", is_crafter=1, stock="[]"):
    c.execute(
        "INSERT INTO npcs (key, label, is_crafter, shop_inventory_json) VALUES (?,?,?,?)",
        (key, label, is_crafter, stock),
    )
    return c.execute("SELECT * FROM npcs WHERE key=?", (key,)).fetchone()


def test_smith_gets_default_weapons_and_armor():
    c = _conn()
    npc = _npc(c, "kowal_brzezino", "Stary Paweł Kowal", is_crafter=1, stock="[]")
    entries = shop_service._effective_shop_entries(c, npc)
    assert len(entries) > 0, "smith default stock empty"
    types = {e["type"] for e in entries}
    assert "weapon" in types and "armor" in types


def test_healer_gets_consumables():
    c = _conn()
    npc = _npc(c, "zielarka_brzezino", "Zielarka Agata", is_crafter=0, stock="[]")
    entries = shop_service._effective_shop_entries(c, npc)
    assert len(entries) > 0
    assert all(e["type"] == "consumable" for e in entries)


def test_explicit_stock_always_wins():
    c = _conn()
    explicit = json.dumps([{"type": "item", "key": "rope"}])
    npc = _npc(c, "kupiec_x", "Kupiec", is_crafter=0, stock=explicit)
    entries = shop_service._effective_shop_entries(c, npc)
    assert entries == [{"type": "item", "key": "rope"}]
