"""TDD: Issue #1158 — sell_item nieatomowy (awaria niszczy przedmiot bez wypłaty).

Stary kod: DELETE inventory + commit (osobna transakcja), potem kredyt złota w DRUGIM
połączeniu. Awaria między nimi = przedmiot zniknął, brak złota, brak kompensacji.
Fix: usunięcie + kredyt + tag w JEDNEJ transakcji (jedno połączenie, jeden commit) —
gdy kredyt rzuci, DELETE się rolluje i przedmiot zostaje.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixtures_schema as fx  # noqa: E402


def _seed(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        fx.create_tables(conn, "game_config_weapons", "game_config_items", "game_config_consumables")
        conn.executescript(
            """
            CREATE TABLE characters (id INTEGER PRIMARY KEY, name TEXT, gold_gp INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE game_items (
                id INTEGER PRIMARY KEY, key TEXT NOT NULL, kind TEXT NOT NULL,
                label TEXT DEFAULT '', description TEXT DEFAULT '', price_gp REAL DEFAULT 0,
                effect_json TEXT DEFAULT NULL, equip_slot TEXT DEFAULT NULL, rarity INTEGER DEFAULT 1,
                min_level INTEGER DEFAULT 1, location_tags TEXT DEFAULT '[]', created_by TEXT DEFAULT 'seed',
                approved INTEGER DEFAULT 1, is_active INTEGER DEFAULT 1, weapon_data TEXT DEFAULT '{}',
                item_data TEXT DEFAULT '{}', weight_kg REAL DEFAULT 0, note TEXT DEFAULT NULL);
            CREATE TABLE character_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL,
                item_key TEXT, weapon_key TEXT, consumable_key TEXT,
                quantity INTEGER NOT NULL DEFAULT 1, equipped INTEGER NOT NULL DEFAULT 0,
                slot TEXT, source TEXT, meta_json TEXT, label TEXT);
            """
        )
        conn.execute("INSERT INTO characters(id, name, gold_gp) VALUES (1, 'Hero', 100)")
        conn.execute(
            "INSERT INTO game_config_consumables(key, label, description, base_price, is_active) VALUES ('health_potion','Mikstura','Leczy',10,1)"
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def shop(tmp_path):
    p = str(tmp_path / "sell_atomic.db")
    _seed(p)
    from app.services import loot_service, shop_service
    old_loot, old_shop = loot_service.LOOT_DB_PATH, shop_service.LOOT_DB_PATH
    loot_service.LOOT_DB_PATH = p
    shop_service.LOOT_DB_PATH = p
    try:
        yield shop_service, p
    finally:
        loot_service.LOOT_DB_PATH = old_loot
        shop_service.LOOT_DB_PATH = old_shop


def _add_potion(path):
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO character_inventory(character_id, consumable_key, quantity, source) VALUES (1,'health_potion',1,'loot')"
        )
        inv_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        return inv_id
    finally:
        conn.close()


def _inv_exists(path, inv_id):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM character_inventory WHERE id = ?", (inv_id,)
        ).fetchone()[0] == 1
    finally:
        conn.close()


# ─── Test główny (atomowość) ─────────────────────────────────────────────────

def test_credit_failure_does_not_orphan_item(shop, monkeypatch):
    """Gdy kredyt złota rzuci wyjątek, przedmiot NIE może zniknąć (rollback)."""
    shop_service, path = shop
    inv_id = _add_potion(path)

    from app.services import economy_service

    def _boom(*a, **k):
        raise RuntimeError("credit failed mid-transaction")

    monkeypatch.setattr(economy_service, "change_gold", _boom)

    with pytest.raises(RuntimeError):
        shop_service.sell_item(character_id=1, inventory_id=inv_id)

    assert _inv_exists(path, inv_id), "przedmiot zniknął mimo nieudanej wypłaty (#1158)"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_normal_sell_credits_and_removes(shop):
    """Udana sprzedaż: przedmiot usunięty, złoto dopisane (5 = połowa z 10)."""
    shop_service, path = shop
    inv_id = _add_potion(path)

    out = shop_service.sell_item(character_id=1, inventory_id=inv_id)

    assert out["earned_gp"] == 5
    assert out["gold_gp"] == 105
    assert not _inv_exists(path, inv_id)
