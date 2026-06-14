"""TDD: Issue #576 — U26: centralna change_gold() + telemetria ekonomii.

Acceptance:
- change_gold(conn, cid, delta, source) mutuje characters.gold_gp ORAZ zapisuje
  wiersz do character_gold_log; działa na conn właściciela, BEZ commitu.
- Saldo po sekwencji operacji == suma delt w logu.
- Odmowa zejścia poniżej 0 (chyba że allow_negative); delta 0 = no-op bez wiersza.
- campaign_id zapisywany do nowej kolumny character_gold_log.campaign_id.
- categorize_source() mapuje surowe nazwy źródeł na kubełki ENUM (sell/buy/repair...).
- get_economy_7d(conn) agreguje wpływy/wydatki per kubełek źródła w oknie dni.
- db_lint._check_gold_drift wykrywa rozjazd saldo vs suma delt.
"""
import sys
sys.path.insert(0, "/app")

import json
import sqlite3
import pytest

from app.services.economy_service import (
    change_gold,
    categorize_source,
    get_economy_7d,
)
from app.services.db_lint_service import _check_gold_drift


# ─── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            gold_gp INTEGER NOT NULL DEFAULT 0,
            campaign_id INTEGER
        );
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            delta INTEGER,
            source TEXT,
            campaign_id INTEGER,
            meta_json TEXT,
            game_clock_day INTEGER DEFAULT 1,
            wall_clock_at TEXT NOT NULL DEFAULT (datetime('now')),
            reverted_at TEXT
        );
        INSERT INTO characters (id, gold_gp, campaign_id) VALUES (1, 100, 42);
        INSERT INTO characters (id, gold_gp, campaign_id) VALUES (2, 0, NULL);
    """)
    conn.commit()
    yield conn
    conn.close()


def _gold(db, cid=1):
    return db.execute("SELECT gold_gp FROM characters WHERE id = ?", (cid,)).fetchone()["gold_gp"]


def _log_rows(db, cid=1):
    return db.execute(
        "SELECT delta, source, campaign_id, meta_json FROM character_gold_log "
        "WHERE character_id = ? ORDER BY id", (cid,)
    ).fetchall()


# ─── Test główny: mutate + journal atomowo ───────────────────────────────────

def test_change_gold_gain_mutates_and_journals(db):
    new_bal = change_gold(db, 1, 50, "loot")
    assert new_bal == 150
    assert _gold(db) == 150
    rows = _log_rows(db)
    assert len(rows) == 1
    assert rows[0]["delta"] == 50
    assert rows[0]["source"] == "loot"


def test_change_gold_spend_deducts(db):
    new_bal = change_gold(db, 1, -30, "buy")
    assert new_bal == 70
    assert _gold(db) == 70
    assert _log_rows(db)[0]["delta"] == -30


def test_change_gold_does_not_commit(db):
    # change_gold operuje na conn właściciela i NIE commituje — rollback cofa wszystko
    change_gold(db, 1, 50, "loot")
    db.rollback()
    assert _gold(db) == 100
    assert len(_log_rows(db)) == 0


def test_change_gold_refuses_below_zero(db):
    with pytest.raises(ValueError):
        change_gold(db, 2, -10, "buy")  # char 2 ma 0 zł
    assert _gold(db, 2) == 0
    assert len(_log_rows(db, 2)) == 0


def test_change_gold_allow_negative(db):
    new_bal = change_gold(db, 2, -10, "robbery", allow_negative=True)
    assert new_bal == -10


def test_change_gold_zero_is_noop(db):
    new_bal = change_gold(db, 1, 0, "other")
    assert new_bal == 100
    assert len(_log_rows(db)) == 0  # zero delta = brak wiersza


def test_change_gold_stores_campaign_id(db):
    # jawny campaign_id ma pierwszeństwo
    change_gold(db, 1, 10, "quest_reward", campaign_id=99)
    assert _log_rows(db)[0]["campaign_id"] == 99
    # bez jawnego — fallback do characters.campaign_id
    change_gold(db, 1, 10, "loot")
    assert _log_rows(db)[1]["campaign_id"] == 42


def test_change_gold_persists_meta(db):
    change_gold(db, 1, -14, "buy", meta={"item_key": "shortsword"})
    meta = json.loads(_log_rows(db)[0]["meta_json"])
    assert meta["item_key"] == "shortsword"


# ─── Inwariant: saldo == suma delt ───────────────────────────────────────────

def test_balance_equals_sum_of_deltas(db):
    change_gold(db, 1, 50, "loot")
    change_gold(db, 1, -14, "buy")
    change_gold(db, 1, 5, "sell")
    change_gold(db, 1, -20, "repair")
    sum_deltas = db.execute(
        "SELECT COALESCE(SUM(delta),0) AS s FROM character_gold_log WHERE character_id = 1"
    ).fetchone()["s"]
    # 100 + 50 - 14 + 5 - 20 = 121; suma delt = 21 (zmiana od startu 100)
    assert _gold(db) == 100 + sum_deltas


# ─── categorize_source: surowe nazwy → kubełki ENUM ──────────────────────────

def test_categorize_source_buckets():
    assert categorize_source("shop_sell") == "sell"
    assert categorize_source("shop_purchase") == "buy"
    assert categorize_source("shop_purchase_refund") == "buy"
    assert categorize_source("repair_durability") == "repair"
    assert categorize_source("robbery") == "robbery"
    assert categorize_source("resurrection_gold") == "resurrection"
    assert categorize_source("starter_gold") == "starter_gold"
    assert categorize_source("admin_cheat_add") == "admin_cheat"
    assert categorize_source("loot") == "loot"
    assert categorize_source("quest_reward") == "quest_reward"
    assert categorize_source("totally_unknown_thing") == "other"


# ─── get_economy_7d: agregacja per kubełek ───────────────────────────────────

def test_get_economy_7d_aggregates_by_bucket(db):
    change_gold(db, 1, 50, "loot")
    change_gold(db, 1, 30, "loot")
    change_gold(db, 1, -14, "shop_purchase")
    change_gold(db, 1, 5, "shop_sell")
    db.commit()
    rep = get_economy_7d(db, days=7)
    by = {r["source"]: r for r in rep["rows"]}
    assert by["loot"]["income"] == 80
    assert by["loot"]["count"] == 2
    assert by["buy"]["expense"] == 14
    assert by["sell"]["income"] == 5
    assert rep["total_income"] == 85
    assert rep["total_expense"] == 14
    assert rep["net"] == 71


# ─── db_lint: drift detection ────────────────────────────────────────────────

def test_gold_drift_clean_no_warning(db):
    # char 2: 0 zł, brak wpisów → spójne (0 == 0)
    change_gold(db, 1, 50, "loot")  # char 1: 100 -> 150, log delta 50
    db.commit()
    warnings = _check_gold_drift(db)
    # char 1 saldo 150, suma delt 50 → drift 100 (start 100 nie zalogowany)
    # ten test sprawdza KSZTAŁT: drift wykrywa rozjazd, nie zgłasza zgodnych
    assert any("1" in w for w in warnings)  # char 1 ma drift


def test_gold_drift_consistent_character(db):
    # char 2 zaczyna od 0 i każdy ruch logowany → saldo == suma delt, brak warna
    change_gold(db, 2, 40, "loot")
    change_gold(db, 2, -10, "buy")
    db.commit()
    warnings = _check_gold_drift(db)
    assert not any("character 2 " in w or "character_id=2" in w or " id=2 " in w for w in warnings)
