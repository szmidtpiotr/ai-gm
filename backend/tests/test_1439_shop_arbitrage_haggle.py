"""AUDIT #1439 (P1) — kill buy-low/sell-high arbitrage, cap haggle per scene,
enforce buy-side filters (min_level + NPC presence).

Covers:
- combined_buy_multiplier assembles ALL multipliers and clamps ONCE at [0.4, 2.0]
  (no more early-clamp-then-multiply below the floor).
- sell payout is capped strictly below the buy-back price for the same item.
- haggle attempts are capped per scene (mirror gamble = 3), reset on location change.
- direct POST /buy respects min_level and rejects remote NPCs.
- a failed (insufficient_gold) purchase does NOT consume the one-shot haggle discount.
"""
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.services import haggle_service, loot_service, shop_service
from app.services import night_economy_service as night_econ
from app.services.shop_service import combined_buy_multiplier


# ─── unit: single clamp after ALL multipliers ─────────────────────────────────

def _mem_char(cha: int = 10, race: str = "human", campaign_id=None) -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT, race TEXT, campaign_id INTEGER)")
    c.execute(
        "INSERT INTO characters(id, sheet_json, race, campaign_id) VALUES (1, ?, ?, ?)",
        (f'{{"stats":{{"CHA":{cha}}},"level":1}}', race, campaign_id),
    )
    c.commit()
    return c


def test_final_buy_multiplier_floor_after_all_mults():
    # CHA20 dwarf with a 40% haggle discount:
    #   cha_buy_mult 0.75 × (1-0.40) 0.60 × dwarf 0.85 = 0.3825  → BELOW the 0.40 floor.
    # The old early-clamp-then-multiply path produced 0.3825; a single final clamp = 0.40.
    conn = _mem_char(cha=20, race="dwarf")
    mult = combined_buy_multiplier(conn, 1, None, "weapon", is_black_market=False, haggle_discount=0.40)
    conn.close()
    raw = 0.75 * 0.60 * (1.0 - 0.15)
    assert raw < 0.40                          # would breach the floor un-clamped
    assert mult == round(max(0.40, min(2.0, raw)), 4)
    assert mult == 0.40


# ─── shop DB fixture ──────────────────────────────────────────────────────────

def _mk_db(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY, gold_gp INTEGER NOT NULL DEFAULT 0,
                sheet_json TEXT, race TEXT DEFAULT 'human', campaign_id INTEGER
            );
            CREATE TABLE npcs (
                id INTEGER PRIMARY KEY, key TEXT UNIQUE, label TEXT, npc_type TEXT,
                is_shop INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1,
                is_crafter INTEGER NOT NULL DEFAULT 0, is_guild_merchant INTEGER NOT NULL DEFAULT 0,
                shop_inventory_json TEXT
            );
            CREATE TABLE game_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL, kind TEXT NOT NULL,
                label TEXT DEFAULT '', description TEXT DEFAULT '', price_gp REAL DEFAULT 0,
                min_level INTEGER DEFAULT 1, location_tags TEXT DEFAULT NULL, item_data TEXT DEFAULT '{}',
                is_active INTEGER DEFAULT 1
            );
            CREATE TABLE character_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL,
                item_key TEXT, weapon_key TEXT, consumable_key TEXT,
                quantity INTEGER NOT NULL DEFAULT 1, source TEXT
            );
            CREATE TABLE character_gold_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, delta INTEGER,
                source TEXT, campaign_id INTEGER, meta_json TEXT, game_clock_day INTEGER DEFAULT 1,
                wall_clock_at TEXT NOT NULL DEFAULT (datetime('now')), reverted_at TEXT
            );
            CREATE TABLE game_sessions (
                campaign_id INTEGER PRIMARY KEY, session_flags TEXT, current_location_id INTEGER,
                scene_enemies TEXT
            );
            CREATE TABLE game_locations (id INTEGER PRIMARY KEY, key TEXT);
            CREATE TABLE npc_locations (npc_id INTEGER, location_key TEXT);
            CREATE TABLE location_npc_assignments (location_key TEXT, npc_key TEXT, is_active INTEGER DEFAULT 1);
            """
        )
        # a stocking NPC (no location assignment = global by default)
        conn.execute(
            "INSERT INTO npcs(id, key, label, npc_type, is_shop, is_active, shop_inventory_json) "
            "VALUES (1, 'merchant', 'Kupiec', 'merchant', 1, 1, ?)",
            ('[{"type":"item","key":"trinket"},{"type":"item","key":"greatsword"}]',),
        )
        conn.execute(
            "INSERT INTO game_items(key, kind, label, price_gp, min_level, is_active) "
            "VALUES ('trinket', 'item', 'Trinket', 100, 1, 1)"
        )
        conn.execute(
            "INSERT INTO game_items(key, kind, label, price_gp, min_level, is_active) "
            "VALUES ('greatsword', 'item', 'Wielki miecz', 500, 10, 1)"
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "shop1439.db")
    _mk_db(p)
    monkeypatch.setattr(shop_service, "LOOT_DB_PATH", p)
    monkeypatch.setattr(loot_service, "LOOT_DB_PATH", p)
    return p


def _exec(db, sql, params=()):
    c = sqlite3.connect(db)
    try:
        c.execute(sql, params)
        c.commit()
    finally:
        c.close()


# ─── arbitrage: sell always < buy-back ────────────────────────────────────────

def test_no_buy_sell_arbitrage(db):
    # CHA20 dwarf = the strongest discount profile in the game.
    _exec(db, "INSERT INTO characters(id, gold_gp, sheet_json, race, campaign_id) "
              "VALUES (1, 1000, '{\"stats\":{\"CHA\":20},\"level\":1}', 'dwarf', NULL)")
    _exec(db, "INSERT INTO character_inventory(character_id, item_key, quantity, source) "
              "VALUES (1, 'trinket', 1, 'loot')")

    sold = shop_service.sell_item(1, 1, npc_id=None)
    earned = int(sold["earned_gp"])

    conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
    buy_mult = combined_buy_multiplier(conn, 1, None, "item", is_black_market=False)
    conn.close()
    import math
    buy_price = max(1, int(math.floor(100 * buy_mult)))

    assert earned > 0
    assert earned < buy_price, f"arbitrage: earned {earned} >= buy-back {buy_price}"


# ─── min_level enforced on the direct buy path ────────────────────────────────

def test_buy_respects_min_level(db):
    _exec(db, "INSERT INTO characters(id, gold_gp, sheet_json, race, campaign_id) "
              "VALUES (1, 10000, '{\"stats\":{\"CHA\":10},\"level\":1}', 'human', NULL)")
    with pytest.raises(ValueError) as ei:
        shop_service.buy_item(1, 1, "item", "greatsword")   # min_level 10, hero is level 1
    assert "item_not_available" in str(ei.value)


# ─── shopping at an NPC in another region is rejected ─────────────────────────

def test_buy_from_remote_npc_rejected(db):
    _exec(db, "INSERT INTO game_locations(id, key) VALUES (1, 'town_a')")
    _exec(db, "INSERT INTO game_sessions(campaign_id, session_flags, current_location_id) "
              "VALUES (99, '{}', 1)")
    _exec(db, "INSERT INTO characters(id, gold_gp, sheet_json, race, campaign_id) "
              "VALUES (1, 10000, '{\"stats\":{\"CHA\":10},\"level\":1}', 'human', 99)")
    # NPC id 1 is assigned only to town_b — the hero stands in town_a.
    _exec(db, "INSERT INTO npc_locations(npc_id, location_key) VALUES (1, 'town_b')")

    with pytest.raises(ValueError) as ei:
        shop_service.buy_item(1, 1, "item", "trinket")
    assert "npc_not_here" in str(ei.value)


# ─── failed purchase keeps the haggle discount ────────────────────────────────

def test_haggle_discount_survives_insufficient_gold(db):
    _exec(db, "INSERT INTO game_sessions(campaign_id, session_flags, current_location_id) "
              "VALUES (99, '{\"haggle_discount\": 0.15}', NULL)")
    _exec(db, "INSERT INTO characters(id, gold_gp, sheet_json, race, campaign_id) "
              "VALUES (1, 0, '{\"stats\":{\"CHA\":10},\"level\":1}', 'human', 99)")

    with pytest.raises(ValueError) as ei:
        shop_service.buy_item(1, 1, "item", "trinket")   # price 85 > gold 0
    assert "insufficient_gold" in str(ei.value)

    conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
    remaining = shop_service._peek_haggle_for_character(conn, 1)
    conn.close()
    assert remaining == 0.15   # NOT consumed by the failed buy


# ─── per-scene haggle cap ─────────────────────────────────────────────────────

def test_haggle_per_scene_cap():
    flags: dict = {}
    assert not haggle_service.is_haggle_capped(flags)
    haggle_service.increment_haggle_attempts(flags)   # 1
    haggle_service.increment_haggle_attempts(flags)   # 2
    assert not haggle_service.is_haggle_capped(flags)  # under cap (3)
    haggle_service.increment_haggle_attempts(flags)   # 3
    assert haggle_service.is_haggle_capped(flags)     # cap reached → further tags stripped
    # location change resets the scene
    haggle_service.reset_haggle_scene(flags)
    assert not haggle_service.is_haggle_capped(flags)
    assert haggle_service.haggle_attempts(flags) == 0
