"""TDD: Issue #1340 BL-D1 — sety ekwipunku (bonusy za komplet).

Akceptacja:
- 1 część → brak bonusu (żaden próg nieaktywny)
- 2 części → aktywny próg 2 (bonus w statach/ac)
- 3 części → aktywny próg 3 (mocniejszy bonus)
- zdjęcie części poniżej progu → bonus znika
- silnik #1302 agreguje bonus setu razem z reliktami (get_equipment_bonuses)
"""
import os
import sys
import json
import sqlite3

import pytest

sys.path.insert(0, "/app")

from app.migrations_admin import _ensure_sets_schema
from app.services import equipment_effects_service as ees

# Snapshot żywej bazy → temp (VACUUM INTO = spójny snapshot z WAL bez blokady).
TEST_DB = f"/tmp/sets_test_{os.getpid()}.db"


def _conn():
    c = sqlite3.connect(TEST_DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


@pytest.fixture(autouse=True)
def _isolated_db():
    for p in (TEST_DB, TEST_DB + "-wal", TEST_DB + "-shm"):
        if os.path.exists(p):
            os.remove(p)
    src = sqlite3.connect("/data/ai_gm.db", timeout=30)
    try:
        src.execute("VACUUM INTO ?", (TEST_DB,))
    finally:
        src.close()
    c = _conn()
    try:
        _ensure_sets_schema(c)  # idempotentne
        # Kontrolowany set testowy: 3 części, próg 2 = +2 STR, próg 3 = +2 STR +1 AC.
        c.execute("DELETE FROM game_config_sets WHERE key = 'test_iron_kit'")
        c.execute(
            """INSERT INTO game_config_sets (key, label, pieces_json, bonuses_json, is_active, created_by)
               VALUES ('test_iron_kit', 'Test Iron Kit', ?, ?, 1, 'test')""",
            (
                json.dumps(["tik_helm", "tik_plate", "tik_boots"]),
                json.dumps({
                    "2": [{"type": "static_stat_modifier", "stat": "STR", "value": 2}],
                    "3": [
                        {"type": "static_stat_modifier", "stat": "STR", "value": 2},
                        {"type": "ac_bonus", "value": 1},
                    ],
                }),
            ),
        )
        c.commit()
    finally:
        c.close()
    yield
    for p in (TEST_DB, TEST_DB + "-wal", TEST_DB + "-shm"):
        if os.path.exists(p):
            os.remove(p)


def _mk_char(conn):
    cur = conn.execute(
        "INSERT INTO characters (user_id, system_id, name, sheet_json) "
        "VALUES (1, 'fantasy', '[SETTEST]', '{}')"
    )
    conn.commit()
    return cur.lastrowid


def _equip_piece(conn, cid, item_key, slot):
    conn.execute(
        "INSERT INTO character_inventory (character_id, item_key, quantity, equipped, slot) "
        "VALUES (?, ?, 1, 1, ?)",
        (cid, item_key, slot),
    )
    conn.commit()


def _cleanup(conn, cid):
    conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (cid,))
    conn.execute("DELETE FROM characters WHERE id = ?", (cid,))
    conn.commit()


def test_one_piece_no_bonus():
    conn = _conn()
    cid = _mk_char(conn)
    try:
        _equip_piece(conn, cid, "tik_helm", "head")
        b = ees.get_equipment_bonuses(cid, conn)
        assert b["stats"].get("STR", 0) == 0
        assert b["ac"] == 0
        sets = ees.get_active_sets(cid, conn)
        s = next(x for x in sets if x["key"] == "test_iron_kit")
        assert s["worn"] == 1
        assert s["active_threshold"] is None
        assert s["next_threshold"] == 2
    finally:
        _cleanup(conn, cid)
        conn.close()


def test_two_pieces_threshold_2():
    conn = _conn()
    cid = _mk_char(conn)
    try:
        _equip_piece(conn, cid, "tik_helm", "head")
        _equip_piece(conn, cid, "tik_plate", "chest")
        b = ees.get_equipment_bonuses(cid, conn)
        assert b["stats"].get("STR", 0) == 2  # próg 2 aktywny
        assert b["ac"] == 0                    # próg 3 jeszcze nie
        s = next(x for x in ees.get_active_sets(cid, conn) if x["key"] == "test_iron_kit")
        assert s["worn"] == 2
        assert s["active_threshold"] == 2
        assert s["next_threshold"] == 3
    finally:
        _cleanup(conn, cid)
        conn.close()


def test_three_pieces_threshold_3():
    conn = _conn()
    cid = _mk_char(conn)
    try:
        _equip_piece(conn, cid, "tik_helm", "head")
        _equip_piece(conn, cid, "tik_plate", "chest")
        _equip_piece(conn, cid, "tik_boots", "feet")
        b = ees.get_equipment_bonuses(cid, conn)
        assert b["stats"].get("STR", 0) == 2
        assert b["ac"] == 1  # próg 3 dokłada AC
        s = next(x for x in ees.get_active_sets(cid, conn) if x["key"] == "test_iron_kit")
        assert s["worn"] == 3
        assert s["active_threshold"] == 3
        assert s["next_threshold"] is None
    finally:
        _cleanup(conn, cid)
        conn.close()


def test_removing_piece_deactivates_bonus():
    conn = _conn()
    cid = _mk_char(conn)
    try:
        _equip_piece(conn, cid, "tik_helm", "head")
        _equip_piece(conn, cid, "tik_plate", "chest")
        assert ees.get_equipment_bonuses(cid, conn)["stats"].get("STR", 0) == 2
        # Zdejmij jedną część (unequip) → poniżej progu 2 → bonus znika.
        conn.execute(
            "UPDATE character_inventory SET equipped = 0 WHERE character_id = ? AND item_key = 'tik_plate'",
            (cid,),
        )
        conn.commit()
        b = ees.get_equipment_bonuses(cid, conn)
        assert b["stats"].get("STR", 0) == 0
        s = next(x for x in ees.get_active_sets(cid, conn) if x["key"] == "test_iron_kit")
        assert s["worn"] == 1
        assert s["active_threshold"] is None
    finally:
        _cleanup(conn, cid)
        conn.close()


def test_set_counts_equipped_weapon_slot():
    """Set weapon w main_hand liczy się do kompletu (exclude_slots go nie ukrywa)."""
    conn = _conn()
    cid = _mk_char(conn)
    try:
        conn.execute("DELETE FROM game_config_sets WHERE key = 'test_wpn_kit'")
        conn.execute(
            """INSERT INTO game_config_sets (key, label, pieces_json, bonuses_json, is_active, created_by)
               VALUES ('test_wpn_kit', 'Test Wpn Kit', ?, ?, 1, 'test')""",
            (
                json.dumps(["twk_sword", "twk_shield"]),
                json.dumps({"2": [{"type": "static_stat_modifier", "stat": "DEX", "value": 2}]}),
            ),
        )
        conn.commit()
        conn.execute(
            "INSERT INTO character_inventory (character_id, weapon_key, quantity, equipped, slot) "
            "VALUES (?, 'twk_sword', 1, 1, 'main_hand')", (cid,))
        _equip_piece(conn, cid, "twk_shield", "off_hand")
        conn.commit()
        # Ścieżka walki woła z exclude_slots=('main_hand',) — set nadal kompletny.
        b = ees.get_equipment_bonuses(cid, conn, exclude_slots=("main_hand",))
        assert b["stats"].get("DEX", 0) == 2
    finally:
        _cleanup(conn, cid)
        conn.close()
