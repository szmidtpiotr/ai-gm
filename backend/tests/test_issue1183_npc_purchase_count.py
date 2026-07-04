"""TDD: Issue #1183 — podpiąć increment_npc_purchase_count w ścieżce zakupu u NPC.

Martwy feature "NPC pamięta zakupy": increment_npc_purchase_count było zdefiniowane,
ale nigdy wołane → purchase_count zawsze 0. Ten fix wpina inkrement w buy_item, żeby
kupiec-NPC "pamiętał" stałego klienta (narracja przez format_known_npcs_block).

Kryteria (z issue):
- 3× zakup u tego samego NPC → purchase_count == 3 w DB
- zakup u innego NPC nie miesza liczników
- purchase_count wykorzystany w narracji (kupiec rozpoznaje stałego klienta)
"""
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from app.services import npc_memory_service
from app.services import shop_service
from app.services.npc_memory_service import (
    format_known_npcs_block,
    get_recent_known_npcs,
    increment_npc_purchase_count,
)

CAMPAIGN_ID = 991183


def _seed_db(path: str) -> None:
    """File-based DB: characters + npcs + campaign_known_npcs (roster w/ purchase_count).

    A real file (not :memory:) so each managed _conn() open/close cycle — including the
    one inside increment_npc_purchase_count — sees the same persisted rows."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            gold_gp INTEGER NOT NULL DEFAULT 0,
            sheet_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY,
            key TEXT NOT NULL,
            label TEXT NOT NULL,
            npc_type TEXT NOT NULL DEFAULT 'merchant',
            is_shop INTEGER NOT NULL DEFAULT 1,
            is_active INTEGER NOT NULL DEFAULT 1,
            is_crafter INTEGER NOT NULL DEFAULT 0,
            shop_inventory_json TEXT NOT NULL DEFAULT '[]',
            description TEXT DEFAULT NULL,
            personality_json TEXT DEFAULT NULL
        );
        CREATE TABLE campaign_known_npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            npc_id INTEGER,
            npc_name TEXT NOT NULL,
            role TEXT,
            first_met_location TEXT,
            first_met_turn INTEGER,
            notes TEXT,
            relation_status TEXT NOT NULL DEFAULT 'neutral',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            purchase_count INTEGER NOT NULL DEFAULT 0,
            stats_json TEXT,
            UNIQUE(campaign_id, npc_name)
        );

        INSERT INTO characters (id, campaign_id, gold_gp, sheet_json) VALUES
            (1, 991183, 100000, '{"level": 3, "stats": {"CHA": 10}}');

        INSERT INTO npcs (id, key, label, is_shop, is_active) VALUES
            (10, 'kowal', 'Kowal', 1, 1),
            (20, 'zielarka', 'Zielarka', 1, 1);
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture
def db_path(tmp_path):
    p = str(tmp_path / "issue1183.db")
    _seed_db(p)
    return p


def _read_conn(path):
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    return c


def _wire(monkeypatch, path):
    """Point both services at the shared file DB and stub the heavy buy helpers, so
    buy_item reaches the purchase-count increment deterministically (no night econ,
    haggle, reputation, catalog or economy tables required)."""
    def _conn():
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr(shop_service, "_conn", _conn)
    monkeypatch.setattr(npc_memory_service, "_conn", _conn)
    monkeypatch.setattr(shop_service, "_shop_open_state", lambda c, npc, cid: {"open": True, "is_black_market": False, "reason": None})
    monkeypatch.setattr(shop_service, "_effective_shop_entries", lambda c, npc: [{"type": "weapon", "key": "sword_basic"}])
    monkeypatch.setattr(shop_service, "_catalog_item", lambda c, t, k: {"type": "weapon", "key": "sword_basic", "label": "Miecz", "value_gp": 50})
    monkeypatch.setattr(shop_service, "_get_character_cha", lambda c, cid: 10)
    monkeypatch.setattr(shop_service, "_consume_haggle_for_character", lambda c, cid: 0.0)
    monkeypatch.setattr(shop_service, "_get_character_race", lambda c, cid: "human")
    monkeypatch.setattr(shop_service, "_reputation_buy_multiplier", lambda c, cid, npc_id=None: 1.0)
    monkeypatch.setattr(shop_service, "get_character_gold", lambda cid: 100000)
    monkeypatch.setattr(shop_service, "apply_character_gold_delta", lambda cid, delta, reason: 100000 + delta)
    monkeypatch.setattr(shop_service, "grant_loot_to_character", lambda cid, payload, source="": None)


# ─── Test główny: 3× zakup u tego samego NPC → purchase_count == 3 ───────────

def test_buy_three_times_bumps_purchase_count_to_three(monkeypatch, db_path):
    _wire(monkeypatch, db_path)

    for _ in range(3):
        shop_service.buy_item(character_id=1, npc_id=10, item_type="weapon", item_key="sword_basic")

    row = _read_conn(db_path).execute(
        "SELECT purchase_count, npc_name FROM campaign_known_npcs WHERE campaign_id = ? AND npc_id = ?",
        (CAMPAIGN_ID, 10),
    ).fetchone()
    assert row is not None, "kupno u NPC nie utworzyło wpisu w roster — increment nie wołany"
    assert row["purchase_count"] == 3, f"oczekiwano purchase_count==3, jest {row['purchase_count']}"
    assert row["npc_name"] == "Kowal"


# ─── Test izolacji: inny NPC nie miesza liczników ────────────────────────────

def test_buying_at_other_npc_keeps_counters_separate(monkeypatch, db_path):
    _wire(monkeypatch, db_path)

    for _ in range(3):
        shop_service.buy_item(character_id=1, npc_id=10, item_type="weapon", item_key="sword_basic")
    shop_service.buy_item(character_id=1, npc_id=20, item_type="weapon", item_key="sword_basic")

    rc = _read_conn(db_path)
    kowal = rc.execute(
        "SELECT purchase_count FROM campaign_known_npcs WHERE campaign_id = ? AND npc_id = ?",
        (CAMPAIGN_ID, 10),
    ).fetchone()["purchase_count"]
    zielarka = rc.execute(
        "SELECT purchase_count FROM campaign_known_npcs WHERE campaign_id = ? AND npc_id = ?",
        (CAMPAIGN_ID, 20),
    ).fetchone()["purchase_count"]
    assert kowal == 3, "licznik Kowala zaburzony przez zakup u Zielarki"
    assert zielarka == 1, "licznik Zielarki powinien być 1"


# ─── Test narracji: purchase_count trafia do bloku znanych NPC ───────────────

def test_purchase_count_surfaces_in_narration_block(monkeypatch, db_path):
    _wire(monkeypatch, db_path)

    for _ in range(5):
        shop_service.buy_item(character_id=1, npc_id=10, item_type="weapon", item_key="sword_basic")

    rows = get_recent_known_npcs(CAMPAIGN_ID, conn=_read_conn(db_path))
    block = format_known_npcs_block(rows)
    assert "stały klient" in block, f"kupiec nie rozpoznaje stałego klienta w narracji:\n{block}"


# ─── Backward compat: increment liczy izolowanie także wołane wprost ─────────

def test_increment_directly_isolated_per_npc(monkeypatch, db_path):
    def _conn():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr(npc_memory_service, "_conn", _conn)

    for _ in range(3):
        increment_npc_purchase_count(campaign_id=CAMPAIGN_ID, npc_id=10, npc_name="Kowal")
    increment_npc_purchase_count(campaign_id=CAMPAIGN_ID, npc_id=20, npc_name="Zielarka")

    rc = _read_conn(db_path)
    kowal = rc.execute(
        "SELECT purchase_count FROM campaign_known_npcs WHERE campaign_id = ? AND npc_id = ?",
        (CAMPAIGN_ID, 10),
    ).fetchone()["purchase_count"]
    zielarka = rc.execute(
        "SELECT purchase_count FROM campaign_known_npcs WHERE campaign_id = ? AND npc_id = ?",
        (CAMPAIGN_ID, 20),
    ).fetchone()["purchase_count"]
    assert kowal == 3
    assert zielarka == 1


# ─── Backward compat: zakup bez kampanii nie wysypuje buy_item ───────────────

def test_buy_without_campaign_does_not_crash(monkeypatch, db_path):
    rc = sqlite3.connect(db_path)
    rc.execute("UPDATE characters SET campaign_id = NULL WHERE id = 1")
    rc.commit()
    rc.close()
    _wire(monkeypatch, db_path)

    res = shop_service.buy_item(character_id=1, npc_id=10, item_type="weapon", item_key="sword_basic")
    assert res["paid_gp"] > 0, "zakup powinien się udać nawet bez kampanii (increment pomijany)"
