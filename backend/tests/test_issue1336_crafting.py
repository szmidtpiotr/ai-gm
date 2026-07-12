"""TDD: Issue #1336 BL-C1 — rzemiosło core (przepisy + crafting_service).

Akceptacja:
- craft konsumuje komponenty
- ulepszenie broni (+1 dmg) NIE kumuluje się
- zniżka krasnoluda działa na koszt usługi
- brak komponentów → CraftError 400
"""
import os
import sys
import json
import sqlite3

import pytest

sys.path.insert(0, "/app")

from app.migrations_admin import _ensure_recipes_schema
from app.services import crafting_service
from app.services import loot_service
from app.services.crafting_service import CraftError, WEAPON_HONE_AFFIX

# Testy piszą do DB — kopiujemy żywą bazę do temp (VACUUM INTO = spójny snapshot
# łącznie z WAL, bez blokowania działającego backendu), potem monkeypatchujemy
# DB_PATH w modułach dotykanych przez craft. Zero kontencji z żywym backendem.
TEST_DB = f"/tmp/craft_test_{os.getpid()}.db"


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
    monkeypatch.setattr(crafting_service, "DB_PATH", TEST_DB)
    monkeypatch.setattr(loot_service, "LOOT_DB_PATH", TEST_DB)
    c = _conn()
    try:
        _ensure_recipes_schema(c)  # idempotentne — snapshot już ma tabelę
    finally:
        c.close()
    yield
    for p in (TEST_DB, TEST_DB + "-wal", TEST_DB + "-shm"):
        if os.path.exists(p):
            os.remove(p)


def _mk_char(conn, race="human", gold=100):
    cur = conn.execute(
        "INSERT INTO characters (user_id, system_id, name, race, gold_gp, sheet_json) VALUES (1, 'fantasy', ?, ?, ?, '{}')",
        (f"[CRAFTTEST] {race}", race, gold),
    )
    conn.commit()
    return cur.lastrowid


def _add_component(conn, cid, item_key, qty):
    conn.execute(
        "INSERT INTO character_inventory (character_id, item_key, quantity) VALUES (?, ?, ?)",
        (cid, item_key, qty),
    )
    conn.commit()


def _add_weapon(conn, cid, weapon_key):
    cur = conn.execute(
        "INSERT INTO character_inventory (character_id, weapon_key, quantity, equipped, slot, affixes_json) "
        "VALUES (?, ?, 1, 1, 'main_hand', '[]')",
        (cid, weapon_key),
    )
    conn.commit()
    return cur.lastrowid


def _cleanup(conn, cid):
    conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (cid,))
    conn.execute("DELETE FROM characters WHERE id = ?", (cid,))
    conn.execute("DELETE FROM character_gold_log WHERE character_id = ?", (cid,))
    conn.commit()


def _first_weapon_key(conn):
    r = conn.execute("SELECT key FROM game_config_weapons LIMIT 1").fetchone()
    return r["key"]


# ─── Seed / schema ───────────────────────────────────────────────────────────

def test_recipes_seeded():
    conn = _conn()
    keys = {r["key"] for r in conn.execute("SELECT key FROM game_config_recipes").fetchall()}
    conn.close()
    for k in ("herbal_potion_minor", "weapon_hone_dmg", "armor_mend_pelt"):
        assert k in keys, f"Brak przepisu {k}"


def test_hone_affix_seeded():
    conn = _conn()
    r = conn.execute(
        "SELECT effect_json FROM game_config_affixes WHERE key = ?", (WEAPON_HONE_AFFIX,)
    ).fetchone()
    conn.close()
    assert r is not None, "afiks craft_hone niesseedowany"
    assert '"damage_bonus"' in r["effect_json"] and '"value":1' in r["effect_json"].replace(" ", "")


# ─── Craft mikstury: konsumpcja komponentów ─────────────────────────────────

def test_craft_consumes_components_and_gold():
    conn = _conn()
    cid = _mk_char(conn, race="human", gold=100)
    try:
        _add_component(conn, cid, "healing_herb", 2)
        _add_component(conn, cid, "korzen_zmornika", 1)
        res = crafting_service.craft(cid, "herbal_potion_minor")
        assert res["ok"] is True
        assert res["service_cost_gold"] == 5
        assert res["gold_after"] == 95
        # komponenty skonsumowane
        left_herb = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) n FROM character_inventory WHERE character_id=? AND item_key='healing_herb'",
            (cid,),
        ).fetchone()["n"]
        left_root = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) n FROM character_inventory WHERE character_id=? AND item_key='korzen_zmornika'",
            (cid,),
        ).fetchone()["n"]
        assert left_herb == 0 and left_root == 0
        # mikstura w ekwipunku (model game_items — ląduje w item_key lub consumable_key)
        pot = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) n FROM character_inventory "
            "WHERE character_id=? AND (item_key='potion_healing_minor' OR consumable_key='potion_healing_minor')",
            (cid,),
        ).fetchone()["n"]
        assert pot >= 1
    finally:
        _cleanup(conn, cid)
        conn.close()


def test_missing_components_400():
    conn = _conn()
    cid = _mk_char(conn, race="human", gold=100)
    try:
        _add_component(conn, cid, "healing_herb", 1)  # potrzeba 2
        with pytest.raises(CraftError) as ei:
            crafting_service.craft(cid, "herbal_potion_minor")
        assert ei.value.status_code == 400
        # nic nie skonsumowane przy porażce walidacji
        left = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) n FROM character_inventory WHERE character_id=? AND item_key='healing_herb'",
            (cid,),
        ).fetchone()["n"]
        assert left == 1
    finally:
        _cleanup(conn, cid)
        conn.close()


# ─── Ulepszenie broni: nie kumuluje się ──────────────────────────────────────

def test_weapon_upgrade_not_cumulative():
    conn = _conn()
    cid = _mk_char(conn, race="human", gold=100)
    try:
        wkey = _first_weapon_key(conn)
        inv_id = _add_weapon(conn, cid, wkey)
        _add_component(conn, cid, "kiel_wilczy", 2)
        _add_component(conn, cid, "ruda_zelaza", 2)
        res = crafting_service.craft(cid, "weapon_hone_dmg")
        assert res["damage_bonus"] == 1
        affixes = json.loads(
            conn.execute("SELECT affixes_json FROM character_inventory WHERE id=?", (inv_id,)).fetchone()["affixes_json"]
        )
        assert affixes.count(WEAPON_HONE_AFFIX) == 1
        # drugi craft → 400, afiks nadal jeden, drugi komplet komponentów nietknięty
        with pytest.raises(CraftError) as ei:
            crafting_service.craft(cid, "weapon_hone_dmg")
        assert ei.value.status_code == 400
        affixes2 = json.loads(
            conn.execute("SELECT affixes_json FROM character_inventory WHERE id=?", (inv_id,)).fetchone()["affixes_json"]
        )
        assert affixes2.count(WEAPON_HONE_AFFIX) == 1
        left_fang = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) n FROM character_inventory WHERE character_id=? AND item_key='kiel_wilczy'",
            (cid,),
        ).fetchone()["n"]
        assert left_fang == 1  # tylko pierwszy craft skonsumował 1
    finally:
        _cleanup(conn, cid)
        conn.close()


# ─── Zniżka krasnoluda ───────────────────────────────────────────────────────

def test_dwarf_discount_on_service_cost():
    conn = _conn()
    dwarf = _mk_char(conn, race="dwarf", gold=100)
    human = _mk_char(conn, race="human", gold=100)
    try:
        wkey = _first_weapon_key(conn)
        for cid in (dwarf, human):
            _add_weapon(conn, cid, wkey)
            _add_component(conn, cid, "kiel_wilczy", 1)
            _add_component(conn, cid, "ruda_zelaza", 1)
        res_d = crafting_service.craft(dwarf, "weapon_hone_dmg")
        res_h = crafting_service.craft(human, "weapon_hone_dmg")
        # baza 15; krasnolud round(15*0.85)=13; człowiek 15
        assert res_h["service_cost_gold"] == 15
        assert res_d["service_cost_gold"] == 13
        assert res_d["dwarf_discount"] is True
        assert res_d["service_cost_gold"] < res_h["service_cost_gold"]
    finally:
        _cleanup(conn, dwarf)
        _cleanup(conn, human)
        conn.close()
