"""TDD: Issue #1339 BL-C4 — sweep pętli fazy rzemiosła end-to-end.

Domyka fazę C: jeden test przechodzi całą pętlę gracza w kolejności produkcyjnej —
    loot → zbieranie ziół → craft mikstury → ulepszenie broni
— na żywym silniku (grant_loot_to_character + resolve_gather + crafting_service.craft),
w izolowanym snapshotcie bazy (VACUUM INTO), zero kontencji z backendem.

Każda noga sprawdza konkretny kontrakt fazy C:
  1. LOOT      — komponent (zioło) wpada do ekwipunku prawdziwą ścieżką grantu.
  2. ZBIERANIE — resolve_gather dokłada zioła wg marginesu (sukces = 1–3).
  3. CRAFT     — mikstura konsumuje 2× zioło + 1× korzeń, wynik w ekwipunku, złoto −5.
  4. ULEPSZENIE— +1 dmg na egzemplarzu broni, drugi craft → 400 (nie kumuluje się).
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
from app.services import herb_gathering_service as herb
from app.services.crafting_service import CraftError, WEAPON_HONE_AFFIX

TEST_DB = f"/tmp/phasec_sweep_{os.getpid()}.db"


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
        _ensure_recipes_schema(c)  # idempotentne
    finally:
        c.close()
    yield
    for p in (TEST_DB, TEST_DB + "-wal", TEST_DB + "-shm"):
        if os.path.exists(p):
            os.remove(p)


def _mk_char(conn, race="human", gold=100):
    cur = conn.execute(
        "INSERT INTO characters (user_id, system_id, name, race, gold_gp, sheet_json) "
        "VALUES (1, 'fantasy', ?, ?, ?, '{}')",
        (f"[SWEEP1339] {race}", race, gold),
    )
    conn.commit()
    return cur.lastrowid


def _add_item(conn, cid, item_key, qty):
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


def _qty(conn, cid, item_key):
    return conn.execute(
        "SELECT COALESCE(SUM(quantity),0) n FROM character_inventory "
        "WHERE character_id=? AND item_key=?",
        (cid, item_key),
    ).fetchone()["n"]


def _first_weapon_key(conn):
    return conn.execute("SELECT key FROM game_config_weapons LIMIT 1").fetchone()["key"]


def _cleanup(conn, cid):
    conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (cid,))
    conn.execute("DELETE FROM characters WHERE id = ?", (cid,))
    conn.execute("DELETE FROM character_gold_log WHERE character_id = ?", (cid,))
    conn.commit()


def test_phase_c_full_loop_loot_gather_craft_upgrade():
    conn = _conn()
    cid = _mk_char(conn, race="human", gold=100)
    try:
        # ── 1. LOOT: komponent-zioło wpada prawdziwą ścieżką grantu (loot → ekwipunek).
        loot_service.grant_loot_to_character(
            cid, [{"item_key": "healing_herb", "quantity": 1}], source="loot"
        )
        assert _qty(conn, cid, "healing_herb") >= 1, "loot nie zdeponował komponentu"

        # ── 2. ZBIERANIE: resolve_gather dokłada zioła wg marginesu (sukces margines 5 → ≥2).
        before = _qty(conn, cid, "healing_herb")
        pending = {"hex_key": "0,0", "game_day": 1}
        sf = {}
        result = {"success": True, "nat20": False, "nat1": False, "margin": 5}
        summary = herb.resolve_gather(conn, campaign_id=1, character_id=cid,
                                      pending=pending, result=result, session_flags=sf)
        assert summary["outcome"] == "success"
        after = _qty(conn, cid, "healing_herb")
        assert after > before, "zbieranie nie dodało ziół"
        # cooldown ustawiony na ten heks/dzień
        assert "0,0" in (sf.get("herb_cooldowns") or {})

        # ── 3. CRAFT mikstury: potrzeba 2× zioło + 1× korzeń. Dosyp korzeń (też z łupu).
        # Upewnij się, że masz dokładnie ≥2 zioła (loot+zbieranie już to dały).
        assert _qty(conn, cid, "healing_herb") >= 2
        _add_item(conn, cid, "korzen_zmornika", 1)
        gold_before = conn.execute(
            "SELECT gold_gp FROM characters WHERE id=?", (cid,)
        ).fetchone()["gold_gp"]
        res = crafting_service.craft(cid, "herbal_potion_minor")
        assert res["ok"] is True and res["service_cost_gold"] == 5
        # opłata pobrana
        assert res["gold_after"] == gold_before - 5
        # korzeń skonsumowany, mikstura w ekwipunku
        assert _qty(conn, cid, "korzen_zmornika") == 0
        pot = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) n FROM character_inventory "
            "WHERE character_id=? AND (item_key='potion_healing_minor' OR consumable_key='potion_healing_minor')",
            (cid,),
        ).fetchone()["n"]
        assert pot >= 1, "brak mikstury po craftcie"

        # ── 4. ULEPSZENIE broni: +1 dmg, nie kumuluje się.
        wkey = _first_weapon_key(conn)
        inv_id = _add_weapon(conn, cid, wkey)
        _add_item(conn, cid, "kiel_wilczy", 2)
        _add_item(conn, cid, "ruda_zelaza", 2)
        up = crafting_service.craft(cid, "weapon_hone_dmg")
        assert up["damage_bonus"] == 1
        affixes = json.loads(
            conn.execute("SELECT affixes_json FROM character_inventory WHERE id=?", (inv_id,)).fetchone()["affixes_json"]
        )
        assert affixes.count(WEAPON_HONE_AFFIX) == 1
        # drugi craft na tym samym egzemplarzu → 400, afiks nadal jeden
        with pytest.raises(CraftError) as ei:
            crafting_service.craft(cid, "weapon_hone_dmg")
        assert ei.value.status_code == 400
        affixes2 = json.loads(
            conn.execute("SELECT affixes_json FROM character_inventory WHERE id=?", (inv_id,)).fetchone()["affixes_json"]
        )
        assert affixes2.count(WEAPON_HONE_AFFIX) == 1
        # tylko pierwszy craft skonsumował 1 kieł + 1 rudę
        assert _qty(conn, cid, "kiel_wilczy") == 1
        assert _qty(conn, cid, "ruda_zelaza") == 1
    finally:
        _cleanup(conn, cid)
        conn.close()
