"""TDD: Issue #1341 BL-D2 — eksperymenty gracza: ukryte receptury + fuszerki.

ZASADA ŻELAZNA: wynik eksperymentu ZAWSZE pochodzi z receptury autorowanej przez
admina (is_hidden=1). LLM nigdy nie generuje statów. Kombinacja spoza puli = tylko
fuszerka — NIGDY przedmiot.

Akceptacja:
- trafienie+sukces → przedmiot + trwałe odkrycie (character_recipes)
- trafienie+porażka → strata połowy komponentów, brak odkrycia
- pudło (brak dopasowania) → tabela fuszerek
- odkrycie trwałe (idempotentne, widoczne na liście)
- Nat 1 na trafieniu → fuszerka (nie zwykła porażka)
- test negatywny: niemożliwe uzyskanie przedmiotu spoza receptur
"""
import os
import sys
import sqlite3

import pytest

sys.path.insert(0, "/app")

from app.migrations_admin import _ensure_recipes_schema, _ensure_experiment_schema
from app.services import crafting_service
from app.services import loot_service
from app.services import dice
from app.services.crafting_service import CraftError

TEST_DB = f"/tmp/experiment_test_{os.getpid()}.db"


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
        _ensure_recipes_schema(c)
        _ensure_experiment_schema(c)  # idempotentne — dodaje craft_tier + character_recipes + seed
    finally:
        c.close()
    yield
    for p in (TEST_DB, TEST_DB + "-wal", TEST_DB + "-shm"):
        if os.path.exists(p):
            os.remove(p)


SHEET = '{"stats":{"INT":10},"skills":{"trade_craft":0},"current_hp":30,"max_hp":30}'


def _mk_char(conn, gold=100):
    cur = conn.execute(
        "INSERT INTO characters (user_id, system_id, name, race, gold_gp, sheet_json) "
        "VALUES (1, 'fantasy', '[EXPTEST]', 'human', ?, ?)",
        (gold, SHEET),
    )
    conn.commit()
    return cur.lastrowid


def _add(conn, cid, item_key, qty):
    conn.execute(
        "INSERT INTO character_inventory (character_id, item_key, quantity) VALUES (?, ?, ?)",
        (cid, item_key, qty),
    )
    conn.commit()


def _qty(conn, cid, item_key):
    r = conn.execute(
        "SELECT COALESCE(SUM(quantity),0) n FROM character_inventory "
        "WHERE character_id=? AND item_key=?",
        (cid, item_key),
    ).fetchone()
    return int(r["n"])


def _cleanup(conn, cid):
    conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (cid,))
    conn.execute("DELETE FROM characters WHERE id = ?", (cid,))
    conn.execute("DELETE FROM character_gold_log WHERE character_id = ?", (cid,))
    conn.execute("DELETE FROM character_recipes WHERE character_id = ?", (cid,))
    conn.commit()


# Komponenty ukrytej receptury 'hidden_maslo_troki' (easy DC8): wolf_pelt + sadlo_niedzwiedzie.
_MASLO = [{"item_key": "wolf_pelt", "qty": 1}, {"item_key": "sadlo_niedzwiedzie", "qty": 1}]


# ─── Seed ────────────────────────────────────────────────────────────────────

def test_hidden_recipes_seeded():
    conn = _conn()
    rows = {r["key"]: r for r in conn.execute(
        "SELECT key, is_hidden, craft_tier FROM game_config_recipes WHERE is_hidden=1"
    ).fetchall()}
    conn.close()
    for k in ("hidden_maslo_troki", "hidden_elixir_zywotnosci", "hidden_eliksir_cienia"):
        assert k in rows, f"Brak ukrytej receptury {k}"
    assert rows["hidden_maslo_troki"]["craft_tier"] == "easy"
    assert rows["hidden_eliksir_cienia"]["craft_tier"] == "hard"


# ─── Trafienie + sukces ──────────────────────────────────────────────────────

def test_hit_success_discovers_and_grants(monkeypatch):
    monkeypatch.setattr(dice, "roll_d20", lambda *a, **k: 20)  # Nat20 → auto-sukces
    conn = _conn()
    cid = _mk_char(conn, gold=100)
    try:
        _add(conn, cid, "wolf_pelt", 1)
        _add(conn, cid, "sadlo_niedzwiedzie", 1)
        res = crafting_service.experiment(cid, _MASLO)
        assert res["outcome"] == "discovery"
        assert res["matched"] is True
        assert res["recipe_key"] == "hidden_maslo_troki"
        assert res["gold_after"] == 90  # 100 - 10 opłata
        # komponenty w całości skonsumowane
        assert _qty(conn, cid, "wolf_pelt") == 0
        assert _qty(conn, cid, "sadlo_niedzwiedzie") == 0
        # przedmiot z receptury w ekwipunku
        pot = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) n FROM character_inventory WHERE character_id=? "
            "AND (item_key='potion_stamina' OR consumable_key='potion_stamina')", (cid,),
        ).fetchone()["n"]
        assert pot >= 1
        # trwałe odkrycie
        disc = crafting_service.list_character_recipes(cid)["discovered"]
        assert any(d["recipe_key"] == "hidden_maslo_troki" for d in disc)
    finally:
        _cleanup(conn, cid)
        conn.close()


# ─── Trafienie + porażka ─────────────────────────────────────────────────────

def test_hit_failure_loses_half_no_discovery(monkeypatch):
    monkeypatch.setattr(dice, "roll_d20", lambda *a, **k: 2)  # total 2 < DC8, brak Nat1
    conn = _conn()
    cid = _mk_char(conn, gold=100)
    try:
        _add(conn, cid, "wolf_pelt", 1)
        _add(conn, cid, "sadlo_niedzwiedzie", 1)
        res = crafting_service.experiment(cid, _MASLO)
        assert res["outcome"] == "failure"
        assert res["discovered"] is False
        # strata połowy (ceil) — qty=1 → zabiera 1
        assert _qty(conn, cid, "wolf_pelt") == 0
        assert _qty(conn, cid, "sadlo_niedzwiedzie") == 0
        # BRAK przedmiotu z receptury
        pot = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) n FROM character_inventory WHERE character_id=? "
            "AND (item_key='potion_stamina' OR consumable_key='potion_stamina')", (cid,),
        ).fetchone()["n"]
        assert pot == 0
        # brak odkrycia
        disc = crafting_service.list_character_recipes(cid)["discovered"]
        assert not any(d["recipe_key"] == "hidden_maslo_troki" for d in disc)
    finally:
        _cleanup(conn, cid)
        conn.close()


def test_hit_failure_half_of_larger_stack(monkeypatch):
    monkeypatch.setattr(dice, "roll_d20", lambda *a, **k: 3)  # medium DC12 fail
    conn = _conn()
    cid = _mk_char(conn, gold=100)
    try:
        # hidden_elixir_zywotnosci: healing_herb x2, korzen_zmornika x1, ruda_miedzi x1
        _add(conn, cid, "healing_herb", 2)
        _add(conn, cid, "korzen_zmornika", 1)
        _add(conn, cid, "ruda_miedzi", 1)
        combo = [{"item_key": "healing_herb", "qty": 2},
                 {"item_key": "korzen_zmornika", "qty": 1},
                 {"item_key": "ruda_miedzi", "qty": 1}]
        res = crafting_service.experiment(cid, combo)
        assert res["outcome"] == "failure"
        # ceil(2/2)=1 zabrane z healing_herb → zostaje 1; z x1 → ceil=1 → 0
        assert _qty(conn, cid, "healing_herb") == 1
        assert _qty(conn, cid, "korzen_zmornika") == 0
        assert _qty(conn, cid, "ruda_miedzi") == 0
    finally:
        _cleanup(conn, cid)
        conn.close()


# ─── Nat 1 na trafieniu → fuszerka ───────────────────────────────────────────

def test_nat1_on_match_is_fumble(monkeypatch):
    monkeypatch.setattr(dice, "roll_d20", lambda *a, **k: 1)
    monkeypatch.setattr(crafting_service.random, "randint", lambda a, b: a)  # fumble → 'loss'
    conn = _conn()
    cid = _mk_char(conn, gold=100)
    try:
        _add(conn, cid, "wolf_pelt", 1)
        _add(conn, cid, "sadlo_niedzwiedzie", 1)
        res = crafting_service.experiment(cid, _MASLO)
        assert res["outcome"] == "fumble"
        assert res["roll"]["is_nat1"] is True
        # Nat1 zjada WSZYSTKIE komponenty (nie połowę)
        assert _qty(conn, cid, "wolf_pelt") == 0
        assert _qty(conn, cid, "sadlo_niedzwiedzie") == 0
        assert res["discovered"] is False
    finally:
        _cleanup(conn, cid)
        conn.close()


# ─── Pudło → fuszerka; test negatywny ────────────────────────────────────────

def test_miss_is_fumble_never_grants_item(monkeypatch):
    monkeypatch.setattr(crafting_service.random, "randint", lambda a, b: a)  # 'loss'
    conn = _conn()
    cid = _mk_char(conn, gold=100)
    try:
        # kombinacja spoza jakiejkolwiek ukrytej receptury
        _add(conn, cid, "kiel_szczurzy", 1)
        _add(conn, cid, "bone_dust", 1)
        combo = [{"item_key": "kiel_szczurzy", "qty": 1}, {"item_key": "bone_dust", "qty": 1}]
        res = crafting_service.experiment(cid, combo)
        assert res["outcome"] == "fumble"
        assert res["matched"] is False
        assert "roll" not in res  # brak testu — bez dopasowania nie ma rzutu
        # komponenty przepadły, nic nie odkryte
        assert _qty(conn, cid, "kiel_szczurzy") == 0
        disc = crafting_service.list_character_recipes(cid)["discovered"]
        assert disc == []
    finally:
        _cleanup(conn, cid)
        conn.close()


def test_negative_no_item_from_outside_recipes(monkeypatch):
    """Test negatywny akceptacji: żadna kombinacja spoza puli nie tworzy przedmiotu.
    Bez względu na rzut — brak dopasowania = brak grantu (wynik tylko z receptury)."""
    monkeypatch.setattr(dice, "roll_d20", lambda *a, **k: 20)  # nawet Nat20 nie pomoże
    monkeypatch.setattr(crafting_service.random, "randint", lambda a, b: a)
    conn = _conn()
    cid = _mk_char(conn, gold=100)
    try:
        _add(conn, cid, "luska_jaszczura", 3)
        _add(conn, cid, "bear_hide", 2)
        combo = [{"item_key": "luska_jaszczura", "qty": 3}, {"item_key": "bear_hide", "qty": 2}]
        inv_before = conn.execute(
            "SELECT COUNT(*) n FROM character_inventory WHERE character_id=?", (cid,)
        ).fetchone()["n"]
        res = crafting_service.experiment(cid, combo)
        assert res["outcome"] == "fumble"
        assert res.get("matched") is False
        assert "granted" not in res or not res.get("granted")
        # nie przybył ŻADEN nowy stos (komponenty przepadły, nic nie granted)
        inv_after = conn.execute(
            "SELECT COUNT(*) n FROM character_inventory WHERE character_id=?", (cid,)
        ).fetchone()["n"]
        assert inv_after <= inv_before
    finally:
        _cleanup(conn, cid)
        conn.close()


# ─── Odkrycie trwałe / idempotentne ──────────────────────────────────────────

def test_discovery_persistent_idempotent(monkeypatch):
    monkeypatch.setattr(dice, "roll_d20", lambda *a, **k: 20)
    conn = _conn()
    cid = _mk_char(conn, gold=100)
    try:
        for _ in range(2):
            _add(conn, cid, "wolf_pelt", 1)
            _add(conn, cid, "sadlo_niedzwiedzie", 1)
            crafting_service.experiment(cid, _MASLO)
        # dwa udane eksperymenty → dokładnie JEDEN wiersz odkrycia (UNIQUE)
        n = conn.execute(
            "SELECT COUNT(*) n FROM character_recipes WHERE character_id=? AND recipe_key='hidden_maslo_troki'",
            (cid,),
        ).fetchone()["n"]
        assert n == 1
    finally:
        _cleanup(conn, cid)
        conn.close()


# ─── Walidacja wejścia ───────────────────────────────────────────────────────

def test_component_count_bounds():
    conn = _conn()
    cid = _mk_char(conn, gold=100)
    try:
        _add(conn, cid, "wolf_pelt", 5)
        with pytest.raises(CraftError) as ei:
            crafting_service.experiment(cid, [{"item_key": "wolf_pelt", "qty": 1}])
        assert ei.value.status_code == 400
    finally:
        _cleanup(conn, cid)
        conn.close()


def test_insufficient_gold_blocks_before_mutation():
    conn = _conn()
    cid = _mk_char(conn, gold=5)  # opłata 10 > 5
    try:
        _add(conn, cid, "wolf_pelt", 1)
        _add(conn, cid, "sadlo_niedzwiedzie", 1)
        with pytest.raises(CraftError) as ei:
            crafting_service.experiment(cid, _MASLO)
        assert ei.value.status_code == 400
        # nic nie skonsumowane
        assert _qty(conn, cid, "wolf_pelt") == 1
    finally:
        _cleanup(conn, cid)
        conn.close()
