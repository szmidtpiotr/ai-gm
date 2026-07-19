"""AUDIT #1438 (P1) — atomic change_gold + double-sell race.

1. change_gold now mutates with a single conditional UPDATE (`gold_gp = gold_gp + ?`
   guarded by `... >= 0`) — two concurrent debits can no longer both read the same
   balance and both write 0 (lost update = two items for the price of one).
2. sell_item does a compare-and-swap decrement + rowcount check BEFORE crediting —
   two concurrent sells of the same inventory row pay out exactly once.
"""
import os
import sqlite3
import sys
import threading

import pytest

sys.path.insert(0, "/app")

from app.services import loot_service, shop_service
from app.services.economy_service import change_gold


# ─── change_gold atomic concurrent ────────────────────────────────────────────

def _mk_gold_db(path: str, start: int = 100) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY, gold_gp INTEGER NOT NULL DEFAULT 0, campaign_id INTEGER
            );
            CREATE TABLE character_gold_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, delta INTEGER,
                source TEXT, campaign_id INTEGER, meta_json TEXT, game_clock_day INTEGER DEFAULT 1,
                wall_clock_at TEXT NOT NULL DEFAULT (datetime('now')), reverted_at TEXT
            );
            """
        )
        conn.execute("INSERT INTO characters(id, gold_gp, campaign_id) VALUES (1, ?, NULL)", (start,))
        conn.commit()
    finally:
        conn.close()


def test_change_gold_atomic_concurrent(tmp_path):
    p = str(tmp_path / "gold.db")
    _mk_gold_db(p, start=100)

    results: list[str] = []
    barrier = threading.Barrier(2)

    def worker():
        c = sqlite3.connect(p, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout = 5000")
        try:
            barrier.wait()
            change_gold(c, 1, -100, "buy")
            c.commit()
            results.append("ok")
        except ValueError:
            results.append("rejected")
        except sqlite3.OperationalError:
            results.append("locked")
        finally:
            c.close()

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start(); t2.start(); t1.join(); t2.join()

    # Exactly one debit of 100 succeeds; the other is rejected (would go negative).
    assert results.count("ok") == 1, results
    assert results.count("rejected") == 1, results
    conn = sqlite3.connect(p)
    final = conn.execute("SELECT gold_gp FROM characters WHERE id = 1").fetchone()[0]
    conn.close()
    assert final == 0  # never -100 (lost update would have allowed it)


# ─── double-sell race ─────────────────────────────────────────────────────────

def _mk_shop_db(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY, gold_gp INTEGER NOT NULL DEFAULT 0,
                sheet_json TEXT, race TEXT DEFAULT 'human', campaign_id INTEGER
            );
            CREATE TABLE character_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL,
                item_key TEXT, weapon_key TEXT, consumable_key TEXT,
                quantity INTEGER NOT NULL DEFAULT 1, source TEXT
            );
            CREATE TABLE game_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL, kind TEXT NOT NULL,
                label TEXT DEFAULT '', description TEXT DEFAULT '', price_gp REAL DEFAULT 0,
                min_level INTEGER DEFAULT 1, location_tags TEXT DEFAULT NULL, item_data TEXT DEFAULT '{}',
                is_active INTEGER DEFAULT 1
            );
            CREATE TABLE character_gold_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, delta INTEGER,
                source TEXT, campaign_id INTEGER, meta_json TEXT, game_clock_day INTEGER DEFAULT 1,
                wall_clock_at TEXT NOT NULL DEFAULT (datetime('now')), reverted_at TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO characters(id, gold_gp, sheet_json, race, campaign_id) "
            "VALUES (1, 0, '{\"stats\":{\"CHA\":10},\"level\":1}', 'human', NULL)"
        )
        conn.execute(
            "INSERT INTO game_items(key, kind, label, price_gp, min_level, is_active) "
            "VALUES ('trinket', 'item', 'Trinket', 100, 1, 1)"
        )
        conn.execute(
            "INSERT INTO character_inventory(character_id, item_key, quantity, source) "
            "VALUES (1, 'trinket', 1, 'loot')"
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def shop_db(tmp_path, monkeypatch):
    p = str(tmp_path / "shop.db")
    _mk_shop_db(p)
    monkeypatch.setattr(shop_service, "LOOT_DB_PATH", p)
    monkeypatch.setattr(loot_service, "LOOT_DB_PATH", p)
    return p


def test_sell_same_row_twice_pays_once(shop_db):
    inv_id = 1
    results: list[str] = []
    barrier = threading.Barrier(2)

    def worker():
        try:
            barrier.wait()
            shop_service.sell_item(1, inv_id, npc_id=None)
            results.append("ok")
        except ValueError:
            results.append("rejected")
        except sqlite3.OperationalError:
            results.append("locked")

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start(); t2.start(); t1.join(); t2.join()

    assert results.count("ok") == 1, results
    conn = sqlite3.connect(shop_db)
    gold = conn.execute("SELECT gold_gp FROM characters WHERE id = 1").fetchone()[0]
    rows = conn.execute("SELECT COUNT(*) FROM character_inventory WHERE id = 1").fetchone()[0]
    credits = conn.execute(
        "SELECT COUNT(*) FROM character_gold_log WHERE source='shop_sell' AND delta > 0"
    ).fetchone()[0]
    conn.close()
    assert rows == 0            # the single physical item is gone
    assert credits == 1         # credited exactly once
    assert gold == 50           # CHA10 → 0.5 ratio × base 100 (capped below buy price)
