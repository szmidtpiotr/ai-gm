"""#1196 Mapy skarbów — treasure_service unit tests (E2 core)."""

import json
import sqlite3

import pytest

from app.services import treasure_service as ts


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE world_treasures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            map_key TEXT, label TEXT, hex_q INTEGER NOT NULL, hex_r INTEGER NOT NULL,
            map_level INTEGER NOT NULL DEFAULT 0, region TEXT, loot_table_key TEXT,
            loot_snapshot_json TEXT, gold_snapshot INTEGER NOT NULL DEFAULT 0,
            gold_bonus INTEGER NOT NULL DEFAULT 0, guardian_enemy_key TEXT,
            dc INTEGER NOT NULL DEFAULT 12, total_parts INTEGER NOT NULL DEFAULT 1,
            loot_tier_bonus INTEGER NOT NULL DEFAULT 0, gold_mult REAL NOT NULL DEFAULT 1.0,
            extra_loot_rolls INTEGER NOT NULL DEFAULT 0, character_id INTEGER,
            campaign_id INTEGER, state TEXT NOT NULL DEFAULT 'buried',
            created_by TEXT NOT NULL DEFAULT 'generated', created_at TEXT,
            found_at TEXT, found_by_character_id INTEGER
        );
        CREATE TABLE character_map_fragments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL,
            campaign_id INTEGER, treasure_id INTEGER NOT NULL, part_no INTEGER NOT NULL,
            acquired_at TEXT, source TEXT DEFAULT 'loot',
            UNIQUE(character_id, treasure_id, part_no)
        );
        CREATE TABLE world_hexes (
            q INTEGER, r INTEGER, map_level INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            location_key TEXT, region TEXT, encounter_pool TEXT
        );
        CREATE TABLE game_config_loot_tables (
            key TEXT PRIMARY KEY, is_active INTEGER DEFAULT 1,
            gold_min INTEGER DEFAULT 0, gold_max INTEGER DEFAULT 0
        );
        CREATE TABLE game_config_loot_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, loot_table_key TEXT, item_key TEXT,
            consumable_key TEXT, weapon_key TEXT, weight INTEGER, qty_min INTEGER,
            qty_max INTEGER, game_item_key TEXT
        );
        CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY, tier TEXT DEFAULT 'standard', is_active INTEGER DEFAULT 1,
            loot_table_key TEXT
        );
        CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT);
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, gold INTEGER DEFAULT 0);
        """
    )
    # player stands on (5,5); free overworld hexes elsewhere for burying treasure
    conn.execute("INSERT INTO world_hexes (q,r,map_level,is_active,location_key,region,encounter_pool) "
                 "VALUES (5,5,0,1,NULL,'kresy','[]')")
    for q, r in ((6, 6), (7, 7), (8, 8)):
        conn.execute("INSERT INTO world_hexes (q,r,map_level,is_active,location_key,region,encounter_pool) "
                     "VALUES (?,?,0,1,NULL,'kresy','[]')", (q, r))
    conn.execute("INSERT INTO game_config_loot_tables (key,is_active,gold_min,gold_max) "
                 "VALUES ('loot_goblin',1,10,10)")
    conn.execute("INSERT INTO game_config_loot_entries (loot_table_key,item_key,weight,qty_min,qty_max) "
                 "VALUES ('loot_goblin','ruda_zelaza',100,1,1)")
    conn.execute("INSERT INTO game_config_enemies (key,tier,is_active,loot_table_key) "
                 "VALUES ('goblin','weak',1,'loot_goblin')")
    conn.execute("INSERT INTO characters (id,campaign_id,gold) VALUES (900,7,0)")
    conn.execute("INSERT INTO game_sessions (campaign_id,session_flags) VALUES (7,?)",
                 (json.dumps({"current_hex": {"q": 5, "r": 5}}),))
    conn.commit()
    return conn


def test_is_treasure_map_key():
    assert ts.is_treasure_map_key("treasure_map")
    assert ts.is_treasure_map_key("fragment_mapy_skarbow")
    assert ts.is_treasure_map_key("tm_szlak_1")
    assert ts.is_treasure_map_key("whatever", "treasure_map")
    assert not ts.is_treasure_map_key("miecz")
    assert not ts.is_treasure_map_key("")


def test_whole_map_from_npc_completes_instantly():
    conn = _make_db()
    out = ts.grant_map_item(conn, 900, 7, "treasure_map", source="npc")
    assert out is not None
    assert out["total_parts"] == 1
    assert out["complete"] is True
    assert out["collected"] == 1
    assert "hex" in out and out["hex"]["q"] in (6, 7, 8)  # buried elsewhere, not under player
    # one buried treasure, loot frozen
    t = conn.execute("SELECT * FROM world_treasures").fetchone()
    assert t["state"] == "buried"
    assert t["loot_snapshot_json"] is not None
    assert t["gold_snapshot"] == 10  # gold_mult 1.0 for 1 part


def test_generic_fragments_accumulate_same_map():
    conn = _make_db()
    first = ts.grant_map_item(conn, 900, 7, "fragment_mapy_skarbow")
    second = ts.grant_map_item(conn, 900, 7, "fragment_mapy_skarbow")
    third = ts.grant_map_item(conn, 900, 7, "fragment_mapy_skarbow")
    assert first["total_parts"] == ts.DEFAULT_GENERIC_PARTS == 3
    # all three land on the SAME treasure_id (grouping by id, not name)
    assert first["treasure_id"] == second["treasure_id"] == third["treasure_id"]
    assert [first["collected"], second["collected"], third["collected"]] == [1, 2, 3]
    assert first["complete"] is False
    assert third["complete"] is True
    assert conn.execute("SELECT COUNT(*) FROM world_treasures").fetchone()[0] == 1


def test_authored_maps_grouped_by_map_key_not_name():
    conn = _make_db()
    pa = {"treasure_map": {"map_key": "m_a", "part_no": 1, "total_parts": 2,
                           "loot_table_key": "loot_goblin"}}
    pb = {"treasure_map": {"map_key": "m_b", "part_no": 1, "total_parts": 2,
                           "loot_table_key": "loot_goblin"}}
    a = ts.grant_map_item(conn, 900, 7, "tm_m_a_1", effect_json=pa)
    b = ts.grant_map_item(conn, 900, 7, "tm_m_b_1", effect_json=pb)
    assert a["treasure_id"] != b["treasure_id"]
    assert a["collected"] == 1 and a["complete"] is False
    assert b["collected"] == 1 and b["complete"] is False
    assert conn.execute("SELECT COUNT(*) FROM world_treasures").fetchone()[0] == 2


def test_loot_scaling_by_parts():
    gm1, ex1, tb1 = ts._scaling_for_parts(1)
    gm4, ex4, tb4 = ts._scaling_for_parts(4)
    assert (gm1, ex1) == (1.0, 0)
    assert gm4 == pytest.approx(2.5)
    assert ex4 == 1


def test_attempt_dig_gating():
    conn = _make_db()
    # nothing collected → not eligible
    assert ts.attempt_dig(conn, 7, 900)["eligible"] is False
    # complete a whole map, then simulate travelling to its hex
    out = ts.grant_map_item(conn, 900, 7, "treasure_map", source="npc")
    conn.execute("UPDATE game_sessions SET session_flags = ? WHERE campaign_id = 7",
                 (json.dumps({"current_hex": out["hex"]}),))
    conn.commit()
    res = ts.attempt_dig(conn, 7, 900)
    assert res["eligible"] is True
    assert res["skill_key"] == ts.DIG_SKILL_KEY
    assert res["dc"] == ts.DEFAULT_DIG_DC


def test_payout_no_guardian(monkeypatch):
    conn = _make_db()
    out = ts.grant_map_item(conn, 900, 7, "treasure_map", source="npc")
    tid = out["treasure_id"]
    # no guardian on this treasure (whole map generator may add one 50%) — force none
    conn.execute("UPDATE world_treasures SET guardian_enemy_key = NULL WHERE id = ?", (tid,))
    conn.commit()

    grants = {}
    def _fake_grant(character_id, loot, source="loot", **kw):
        grants["loot"] = loot
        grants["source"] = source
        return [{"label": "Ruda żelaza", "quantity": 1}]
    import app.services.loot_service as ls
    monkeypatch.setattr(ls, "grant_loot_to_character", _fake_grant)

    res = ts.resolve_dig_success(conn, 7, 900, tid)
    assert res["resolved"] is True
    assert res["gold"] == 10
    t = conn.execute("SELECT state, found_by_character_id FROM world_treasures WHERE id = ?", (tid,)).fetchone()
    assert t["state"] == "found"
    assert t["found_by_character_id"] == 900
    # gold credited to the hero
    g = conn.execute("SELECT gold FROM characters WHERE id = 900").fetchone()["gold"]
    assert g == 10
    # one-time: second payout attempt finds nothing
    res2 = ts.resolve_dig_success(conn, 7, 900, tid)
    assert res2["resolved"] is False


def test_get_treasure_maps_hides_hex_until_complete():
    conn = _make_db()
    ts.grant_map_item(conn, 900, 7, "fragment_mapy_skarbow")  # 1/3
    maps = ts.get_treasure_maps(conn, 900)["maps"]
    assert len(maps) == 1
    assert maps[0]["collected"] == 1 and maps[0]["complete"] is False
    assert "hex" not in maps[0]
