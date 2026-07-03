"""TDD: Issue #1127 (PT14) — Night economy: shops closed 21-5, tavern open,
black-market fence (paser) trades only at night with ×1.3 buy / ×0.6 sell.

Two layers:
  * pure functions in night_economy_service (no DB)
  * integration through shop_service.buy_item / sell_item (clock-aware gate)
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


# ─── Pure functions ───────────────────────────────────────────────────────────

def test_night_closed_hours():
    """Closing window is 21:00-05:00 (inclusive 21, reopen at 05)."""
    from app.services import night_economy_service as ne

    assert ne.is_night_closed_hour(23) is True
    assert ne.is_night_closed_hour(3) is True
    assert ne.is_night_closed_hour(21) is True   # closes at 21
    assert ne.is_night_closed_hour(4) is True
    assert ne.is_night_closed_hour(5) is False   # reopens at 05
    assert ne.is_night_closed_hour(10) is False
    assert ne.is_night_closed_hour(20) is False


def test_classify_shop_by_keywords():
    """NPC key/label/type keywords → shop kind."""
    from app.services import night_economy_service as ne

    assert ne.classify_shop(key="paser_nocny", label="Paser", npc_type="merchant") == "black_market"
    assert ne.classify_shop(key="karczmarz_bela", label="Karczmarz Bela", npc_type="merchant") == "tavern"
    assert ne.classify_shop(key="merchant_aldric", label="Aldric", npc_type="merchant") == "normal"


def test_shop_open_state_matrix():
    """open/closed + black-market flag per kind and hour."""
    from app.services import night_economy_service as ne

    # normal shop: open by day, closed at night
    assert ne.shop_open_state("normal", 10)["open"] is True
    assert ne.shop_open_state("normal", 23)["open"] is False

    # tavern: always open
    assert ne.shop_open_state("tavern", 23)["open"] is True
    assert ne.shop_open_state("tavern", 3)["open"] is True

    # black market: only at night, flagged
    bm_night = ne.shop_open_state("black_market", 23)
    assert bm_night["open"] is True
    assert bm_night["is_black_market"] is True
    assert ne.shop_open_state("black_market", 10)["open"] is False

    # unknown clock (None) never blocks
    assert ne.shop_open_state("normal", None)["open"] is True


def test_black_market_multipliers_are_starting_values():
    from app.services import night_economy_service as ne

    assert ne.BLACK_MARKET_BUY_MULT == 1.3
    assert ne.BLACK_MARKET_SELL_MULT == 0.6


# ─── Integration through shop_service ─────────────────────────────────────────

def _seed_db(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY,
                name TEXT,
                gold_gp INTEGER NOT NULL DEFAULT 0,
                campaign_id INTEGER
            );
            CREATE TABLE game_sessions (
                id INTEGER PRIMARY KEY,
                campaign_id INTEGER,
                session_flags TEXT
            );
            CREATE TABLE npcs (
                id INTEGER PRIMARY KEY,
                key TEXT UNIQUE,
                label TEXT,
                npc_type TEXT,
                is_shop INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_crafter INTEGER NOT NULL DEFAULT 0,
                shop_inventory_json TEXT
            );
            CREATE TABLE game_items (
                id INTEGER PRIMARY KEY,
                key TEXT NOT NULL,
                kind TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                description TEXT DEFAULT '',
                price_gp REAL DEFAULT 0,
                min_level INTEGER DEFAULT 1,
                location_tags TEXT DEFAULT NULL,
                item_data TEXT DEFAULT '{}',
                is_active INTEGER DEFAULT 1
            );
            CREATE TABLE character_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL,
                item_key TEXT,
                weapon_key TEXT,
                consumable_key TEXT,
                quantity INTEGER NOT NULL DEFAULT 1,
                equipped INTEGER NOT NULL DEFAULT 0,
                slot TEXT,
                acquired_at TEXT DEFAULT (datetime('now')),
                source TEXT,
                meta_json TEXT,
                label TEXT,
                durability_max INTEGER,
                durability_current INTEGER,
                game_item_key TEXT,
                affixes_json TEXT
            );
            CREATE TABLE character_gold_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER,
                delta INTEGER,
                source TEXT,
                meta_json TEXT,
                game_clock_day INTEGER,
                reverted_at TEXT
            );
            """
        )
        # hero in campaign 1
        conn.execute("INSERT INTO characters(id, name, gold_gp, campaign_id) VALUES (1, 'Hero', 500, 1)")
        # clock starts at hour 23 (night) — tests override per-case
        conn.execute("INSERT INTO game_sessions(id, campaign_id, session_flags) VALUES (1, 1, '{\"ingame_hours\": 23}')")
        # normal shop
        conn.execute(
            "INSERT INTO npcs(id, key, label, npc_type, is_shop, shop_inventory_json) "
            "VALUES (1, 'merchant_aldric', 'Aldric', 'merchant', 1, '[{\"type\":\"weapon\",\"key\":\"shortsword\"}]')"
        )
        # black-market fence
        conn.execute(
            "INSERT INTO npcs(id, key, label, npc_type, is_shop, shop_inventory_json) "
            "VALUES (2, 'paser_nocny', 'Paser', 'merchant', 1, '[{\"type\":\"weapon\",\"key\":\"shortsword\"}]')"
        )
        # tavern
        conn.execute(
            "INSERT INTO npcs(id, key, label, npc_type, is_shop, shop_inventory_json) "
            "VALUES (3, 'karczmarz_bela', 'Karczmarz Bela', 'merchant', 1, '[{\"type\":\"weapon\",\"key\":\"shortsword\"}]')"
        )
        conn.execute(
            "INSERT INTO game_items(key, kind, label, price_gp, is_active) VALUES ('shortsword', 'weapon', 'Krótki miecz', 100, 1)"
        )
        conn.commit()
    finally:
        conn.close()


def _set_hour(path: str, hour: int) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = 1",
            (f'{{"ingame_hours": {hour}}}',),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def shop(tmp_path):
    from app.services import loot_service, shop_service

    p = str(tmp_path / "night_econ.db")
    _seed_db(p)
    old_loot, old_shop = loot_service.LOOT_DB_PATH, shop_service.LOOT_DB_PATH
    loot_service.LOOT_DB_PATH = p
    shop_service.LOOT_DB_PATH = p
    try:
        yield shop_service, p
    finally:
        loot_service.LOOT_DB_PATH = old_loot
        shop_service.LOOT_DB_PATH = old_shop


def test_buy_rejected_at_night_normal_shop(shop):
    """23:00 — normal shop refuses the sale."""
    svc, p = shop
    _set_hour(p, 23)
    with pytest.raises(ValueError, match="shop_closed_night"):
        svc.buy_item(character_id=1, npc_id=1, item_type="weapon", item_key="shortsword")


def test_buy_at_day_normal_shop_ok(shop):
    """10:00 — normal shop sells at base price (CHA 10 → mult 1.0)."""
    svc, p = shop
    _set_hour(p, 10)
    out = svc.buy_item(character_id=1, npc_id=1, item_type="weapon", item_key="shortsword")
    assert out["paid_gp"] == 100
    assert out["buy_multiplier"] == 1.0


def test_black_market_at_night_applies_1_3(shop):
    """23:00 — paser sells at ×1.3 (100 → 130)."""
    svc, p = shop
    _set_hour(p, 23)
    out = svc.buy_item(character_id=1, npc_id=2, item_type="weapon", item_key="shortsword")
    assert out["buy_multiplier"] == 1.3
    assert out["paid_gp"] == 130


def test_black_market_closed_by_day(shop):
    """10:00 — paser refuses (only trades after dark)."""
    svc, p = shop
    _set_hour(p, 10)
    with pytest.raises(ValueError, match="black_market_day"):
        svc.buy_item(character_id=1, npc_id=2, item_type="weapon", item_key="shortsword")


def test_tavern_open_at_night(shop):
    """23:00 — tavern still serves."""
    svc, p = shop
    _set_hour(p, 23)
    out = svc.buy_item(character_id=1, npc_id=3, item_type="weapon", item_key="shortsword")
    assert out["paid_gp"] == 100  # no night surcharge for a tavern


def test_black_market_sell_ratio_0_6(shop):
    """Selling to the fence at night pays ×0.6 of the normal sell price."""
    svc, p = shop
    _set_hour(p, 23)
    conn = sqlite3.connect(p)
    conn.execute(
        "INSERT INTO character_inventory(character_id, weapon_key, quantity, source) VALUES (1, 'shortsword', 1, 'loot')"
    )
    inv_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    out = svc.sell_item(character_id=1, inventory_id=inv_id, npc_id=2)
    # base sell = 100 * 0.5 (SELL_RATIO, CHA 10) = 50; black market ×0.6 = 30
    assert out["base_sell_gp"] == 30


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_buy_without_campaign_not_gated(shop):
    """Hero with no campaign (clock unknown) is never night-gated — old behavior."""
    svc, p = shop
    _set_hour(p, 23)
    conn = sqlite3.connect(p)
    conn.execute("UPDATE characters SET campaign_id = NULL WHERE id = 1")
    conn.commit()
    conn.close()
    out = svc.buy_item(character_id=1, npc_id=1, item_type="weapon", item_key="shortsword")
    assert out["paid_gp"] == 100  # sells despite the hour — no clock to check


def test_sell_item_without_npc_id_still_works(shop):
    """Old sell_item(character_id, inventory_id) signature keeps working."""
    svc, p = shop
    _set_hour(p, 10)  # day, so even if gated it would pass
    conn = sqlite3.connect(p)
    conn.execute(
        "INSERT INTO character_inventory(character_id, weapon_key, quantity, source) VALUES (1, 'shortsword', 1, 'loot')"
    )
    inv_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    out = svc.sell_item(character_id=1, inventory_id=inv_id)
    assert out["base_sell_gp"] == 50  # 100 * 0.5, no black-market mult
