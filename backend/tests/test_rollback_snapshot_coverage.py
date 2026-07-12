"""Rollback snapshot coverage — pełen zrzut wg rejestru tabel.

Weryfikuje, że system cofania tur odtwarza CAŁY stan tury (nie tylko HP/gold):
- questy (character_quests) — bug: ukończone questy zostawały po cofnięciu
- czary (character_spells) — nauczone czary przeżywały cofnięcie
- scena (game_sessions.scene_* kolumny) — captured ale nie restore
- lokacja/hex (game_sessions.session_flags + current_location_id)

Testuje capture_snapshot_tables + restore_snapshot bezpośrednio na scratch DB
(obie funkcje przyjmują `conn`, więc nie potrzebują pełnego appu).
"""
import sqlite3

import pytest

from app.services.world_state_service import (
    capture_snapshot_tables,
    restore_snapshot,
)


def _mk_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, name TEXT,
            sheet_json TEXT, gold_gp INTEGER, location TEXT,
            visited_location_keys TEXT, hero_status TEXT,
            legend_digest TEXT, legend_digest_count INTEGER, status TEXT
        );
        CREATE TABLE character_quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER,
            campaign_id INTEGER, title TEXT, status TEXT, completed_turn INTEGER
        );
        CREATE TABLE character_spells (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER,
            spell_key TEXT, rank INTEGER, use_count INTEGER
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER,
            item_key TEXT, quantity INTEGER, durability_current INTEGER
        );
        CREATE TABLE character_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER,
            condition_type TEXT, severity INTEGER
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER,
            current_location_id INTEGER, session_flags TEXT,
            scene_enemies TEXT, scene_npcs TEXT, scene_cleared INTEGER,
            active_quests TEXT, player_conditions TEXT, ingame_hours INTEGER
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, gm_plan_json TEXT, engine_private_json TEXT,
            party_hex_q INTEGER, party_hex_r INTEGER, plan_degraded INTEGER,
            finale_available INTEGER
        );
        """
    )
    # Seed: kampania 1, postać 7 w lokacji A (hex 3,4), 1 aktywny quest, 1 czar.
    conn.execute("INSERT INTO characters (id,campaign_id,name,sheet_json,gold_gp,location,status) "
                 "VALUES (7,1,'Hero','{\"hp\":10}',50,'karczma','active')")
    conn.execute("INSERT INTO character_quests (character_id,campaign_id,title,status,completed_turn) "
                 "VALUES (7,1,'Odbij wioskę','active',NULL)")
    conn.execute("INSERT INTO character_spells (character_id,spell_key,rank,use_count) "
                 "VALUES (7,'magic_bolt',1,0)")
    conn.execute("INSERT INTO character_inventory (character_id,item_key,quantity,durability_current) "
                 "VALUES (7,'sword',1,100)")
    conn.execute("INSERT INTO game_sessions "
                 "(campaign_id,current_location_id,session_flags,scene_enemies,scene_npcs,"
                 " scene_cleared,active_quests,player_conditions,ingame_hours) "
                 "VALUES (1,55,'{\"current_hex\":{\"q\":3,\"r\":4}}','[{\"key\":\"goblin\"}]',"
                 "'[]',0,'[]','[]',9)")
    conn.execute("INSERT INTO campaigns (id,gm_plan_json) VALUES (1,'{\"scene\":1}')")
    conn.commit()
    return conn


def _snap(conn) -> dict:
    tables = capture_snapshot_tables(conn, campaign_id=1, char_id=7)
    return {"campaign_id": 1, "char_id": 7, "tables": tables}


def test_quest_completion_reverted_on_rollback():
    conn = _mk_db()
    snap = _snap(conn)  # quest aktywny w snapshocie

    # Gracz kończy quest w kolejnej turze.
    conn.execute("UPDATE character_quests SET status='completed', completed_turn=50 WHERE character_id=7")
    conn.commit()
    assert conn.execute("SELECT status FROM character_quests WHERE character_id=7").fetchone()[0] == "completed"

    restore_snapshot(conn, snap, campaign_id=1)
    conn.commit()
    # Bug 1 fix: quest wraca do aktywnego (nie zostaje jako complete → powtórki).
    row = conn.execute("SELECT status, completed_turn FROM character_quests WHERE character_id=7").fetchone()
    assert row["status"] == "active"
    assert row["completed_turn"] is None


def test_learned_spell_removed_on_rollback():
    conn = _mk_db()
    snap = _snap(conn)  # tylko magic_bolt

    conn.execute("INSERT INTO character_spells (character_id,spell_key,rank,use_count) VALUES (7,'fireball',1,0)")
    conn.execute("UPDATE character_spells SET use_count=3 WHERE spell_key='magic_bolt'")
    conn.commit()

    restore_snapshot(conn, snap, campaign_id=1)
    conn.commit()
    spells = {r["spell_key"]: r["use_count"] for r in
              conn.execute("SELECT spell_key,use_count FROM character_spells WHERE character_id=7")}
    # Bug 4 fix: nauczony fireball zniknął, use_count magic_bolt cofnięty.
    assert "fireball" not in spells
    assert spells == {"magic_bolt": 0}


def test_scene_and_location_reverted_on_rollback():
    conn = _mk_db()
    snap = _snap(conn)  # goblin na scenie, lokacja 55, hex 3,4

    # Gracz czyści scenę i idzie gdzie indziej (inny hex/lokacja).
    conn.execute("UPDATE game_sessions SET scene_enemies='[]', scene_cleared=1, "
                 "current_location_id=99, session_flags='{\"current_hex\":{\"q\":9,\"r\":9}}' "
                 "WHERE campaign_id=1")
    conn.commit()

    restore_snapshot(conn, snap, campaign_id=1)
    conn.commit()
    gs = conn.execute("SELECT current_location_id,session_flags,scene_enemies,scene_cleared "
                      "FROM game_sessions WHERE campaign_id=1").fetchone()
    # Bug 2 + Bug 3 fix: lokacja/hex ORAZ scena wracają do stanu ze snapshotu.
    assert gs["current_location_id"] == 55
    assert '"q": 3' in gs["session_flags"] or '"q":3' in gs["session_flags"]
    assert gs["scene_enemies"] == '[{"key":"goblin"}]'
    assert gs["scene_cleared"] == 0


def test_identity_columns_not_clobbered():
    conn = _mk_db()
    snap = _snap(conn)
    # Status/campaign/name postaci nie mogą zostać nadpisane rollbackiem.
    conn.execute("UPDATE characters SET gold_gp=999 WHERE id=7")
    conn.commit()
    restore_snapshot(conn, snap, campaign_id=1)
    conn.commit()
    ch = conn.execute("SELECT gold_gp,status,campaign_id,name FROM characters WHERE id=7").fetchone()
    assert ch["gold_gp"] == 50          # zmienna kolumna cofnięta
    assert ch["status"] == "active"     # tożsamość nietknięta
    assert ch["campaign_id"] == 1
    assert ch["name"] == "Hero"


def test_optional_missing_table_skipped():
    """character_reputation/active_combat są optional — brak tabeli nie wywala."""
    conn = _mk_db()  # bez character_reputation ani active_combat
    snap = _snap(conn)
    # Nie powinno rzucić mimo braku optional tabel.
    out = restore_snapshot(conn, snap, campaign_id=1)
    conn.commit()
    assert "restored" in out
    assert "character_reputation" not in out["restored"]


def test_legacy_snapshot_without_tables():
    conn = _mk_db()
    out = restore_snapshot(conn, {"campaign_id": 1, "char_id": 7}, campaign_id=1)
    assert out == {"legacy": True}
