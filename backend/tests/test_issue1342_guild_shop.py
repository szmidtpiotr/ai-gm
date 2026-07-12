"""TDD: Issue #1342 BL-D3 — gildia kupiecka: handel komponentami.

OCHRONA PĘTLI FARMIENIA — akceptacja:
- asymetria cen: gildia SPRZEDAJE komponent za 150%, SKUPUJE za 40% bazy,
- komponenty rzadkie/bossowe (no_trade=1) są niehandlowalne (bind-on-drop),
- rotacja asortymentu deterministyczna per dzień gry (ten sam dzień → ten sam
  zestaw; inny dzień → zwykle inny), niezależna od restartu procesu (md5, nie hash()).
"""
import math
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.migrations_admin import _ensure_item_component_columns, _ensure_guild_merchant_schema
from app.services import guild_shop_service as guild
from app.services import shop_service
from app.services import loot_service

TEST_DB = f"/tmp/guild_test_{os.getpid()}.db"


def _conn():
    c = sqlite3.connect(TEST_DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    for p in (TEST_DB, TEST_DB + "-wal", TEST_DB + "-shm"):
        if os.path.exists(p):
            os.remove(p)
    src = sqlite3.connect("/data/ai_gm.db", timeout=30)
    try:
        src.execute("VACUUM INTO ?", (TEST_DB,))
    finally:
        src.close()
    # shop_service._conn oraz loot_service czytają własne LOOT_DB_PATH — oba na temp.
    monkeypatch.setattr(shop_service, "LOOT_DB_PATH", TEST_DB)
    monkeypatch.setattr(loot_service, "LOOT_DB_PATH", TEST_DB)
    c = _conn()
    try:
        _ensure_item_component_columns(c)   # is_component (żywa DB już ma, idempotentne)
        _ensure_guild_merchant_schema(c)    # no_trade + is_guild_merchant + seed placówek
    finally:
        c.close()
    yield
    for p in (TEST_DB, TEST_DB + "-wal", TEST_DB + "-shm"):
        if os.path.exists(p):
            os.remove(p)


SHEET = '{"stats":{"CHA":10},"level":1}'


def _mk_char(conn, gold=1000):
    cur = conn.execute(
        "INSERT INTO characters (user_id, system_id, name, race, gold_gp, sheet_json) "
        "VALUES (1, 'fantasy', '[GUILDTEST]', 'human', ?, ?)",
        (gold, SHEET),
    )
    conn.commit()
    return cur.lastrowid


def _mk_guild_npc(conn, key="guild_test_npc"):
    cur = conn.execute(
        "INSERT INTO npcs (key, label, npc_type, is_shop, is_guild_merchant, "
        "shop_inventory_json, is_active) VALUES (?, 'Faktor Testowy', 'merchant', 1, 1, '[]', 1)",
        (key,),
    )
    conn.commit()
    return cur.lastrowid


def _base_value(conn, item_key):
    row = conn.execute(
        "SELECT COALESCE(price_gp, value_gp, 0) v FROM game_config_items WHERE key=?", (item_key,)
    ).fetchone()
    return int(row["v"])


# ── asymetria cen ─────────────────────────────────────────────────────────────

def test_asymmetry_buy_150_sell_40():
    c = _conn()
    npc_id = _mk_guild_npc(c)
    cid = _mk_char(c, gold=1000)
    c.close()

    shop = guild.get_guild_shop(npc_id, cid)
    assert shop["is_guild"] is True
    assert shop["items"], "asortyment gildii nie może być pusty"
    item = shop["items"][0]
    base = item["value_gp"]

    # Sprzedaje graczowi za 150% (× rep/haggle = 1.0 dla neutralnego CHA 10 bez rabatu).
    assert item["buy_price_gp"] == max(1, int(math.floor(base * guild.GUILD_BUY_MULT)))
    assert item["is_component"] is True

    # Kup → zapłać ~150%.
    res = guild.buy_component(cid, npc_id, item["key"])
    assert res["paid_gp"] == item["buy_price_gp"]

    # Skupuje od gracza za 40% (< cena kupna → asymetria chroni farmienie).
    c = _conn()
    inv = c.execute(
        "SELECT id FROM character_inventory WHERE character_id=? AND item_key=?",
        (cid, item["key"]),
    ).fetchone()
    c.close()
    sold = guild.sell_component(cid, npc_id, inv["id"])
    assert sold["earned_gp"] == max(1, int(math.floor(base * guild.GUILD_SELL_RATIO)))
    assert sold["earned_gp"] < res["paid_gp"], "skup musi być tańszy niż sprzedaż (asymetria)"


# ── no_trade: bind-on-drop ────────────────────────────────────────────────────

def test_no_trade_component_not_in_assortment_and_unbuyable():
    c = _conn()
    npc_id = _mk_guild_npc(c)
    cid = _mk_char(c)
    # potwierdź, że migracja oflagowała rzadki komponent
    nt = c.execute("SELECT no_trade FROM game_config_items WHERE key='krew_wilkolaka'").fetchone()
    c.close()
    assert nt and int(nt["no_trade"]) == 1

    shop = guild.get_guild_shop(npc_id, cid)
    keys = {i["key"] for i in shop["items"]}
    assert "krew_wilkolaka" not in keys, "no_trade nie może trafić do asortymentu"

    with pytest.raises(ValueError, match="component_no_trade|item_not_in_shop"):
        guild.buy_component(cid, npc_id, "krew_wilkolaka")


def test_no_trade_component_unsellable():
    c = _conn()
    npc_id = _mk_guild_npc(c)
    cid = _mk_char(c)
    c.execute(
        "INSERT INTO character_inventory (character_id, item_key, quantity) VALUES (?, 'krew_wilkolaka', 1)",
        (cid,),
    )
    c.commit()
    inv = c.execute(
        "SELECT id FROM character_inventory WHERE character_id=? AND item_key='krew_wilkolaka'", (cid,)
    ).fetchone()
    c.close()
    with pytest.raises(ValueError, match="component_no_trade"):
        guild.sell_component(cid, npc_id, inv["id"])
    # no_trade nie pojawia się też na liście skupu
    shop = guild.get_guild_shop(npc_id, cid)
    assert all(s["key"] != "krew_wilkolaka" for s in shop["sell_items"])


# ── rotacja deterministyczna ──────────────────────────────────────────────────

def test_rotation_deterministic_same_day():
    c = _conn()
    rows = guild._tradeable_components(c)
    c.close()
    a1 = [r["key"] for r in guild._daily_assortment(rows, day=5)]
    a2 = [r["key"] for r in guild._daily_assortment(rows, day=5)]
    assert a1 == a2, "ten sam dzień → identyczny asortyment"
    assert len(a1) == min(guild.ASSORTMENT_SIZE, len(rows))


def test_rotation_changes_across_days():
    c = _conn()
    rows = guild._tradeable_components(c)
    c.close()
    assert len(rows) > guild.ASSORTMENT_SIZE, "potrzeba > ASSORTMENT_SIZE komponentów, by rotacja miała sens"
    sets = {tuple(r["key"] for r in guild._daily_assortment(rows, day=d)) for d in range(6)}
    assert len(sets) > 1, "asortyment musi się różnić między dniami"


def test_no_trade_excluded_from_tradeable_pool():
    c = _conn()
    rows = guild._tradeable_components(c)
    c.close()
    keys = {r["key"] for r in rows}
    for nt_key in ("krew_wilkolaka", "esencja_cienia", "esencja_upiora", "dragon_scale_shard"):
        assert nt_key not in keys, f"{nt_key} (no_trade) nie może być w puli handlowej"
