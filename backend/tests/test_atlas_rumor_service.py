"""TDD: #1191 E3/E4 — Atlas Kresów aggregation + persistent rumors.

Atlas aggregates hex discovery across ALL of a hero's campaigns (current +
completed) — hex discovery itself is per-campaign. Rumors: successful
quest_rumor records a deterministic-target rumor; discovering the target
confirms it.
"""
from _fixtures_schema import table_sql
import json
import sqlite3
import pytest

from app.services import atlas_service as at
from app.services import rumor_service as rs


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, is_active INTEGER DEFAULT 1);
        CREATE TABLE character_campaign_history (id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, campaign_id INTEGER);
        CREATE TABLE campaign_hex_data (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, hex_q INTEGER, hex_r INTEGER, discovered INTEGER DEFAULT 0);
        CREATE TABLE world_hexes (id INTEGER PRIMARY KEY AUTOINCREMENT, q INTEGER, r INTEGER, map_level INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1, region TEXT, location_key TEXT);
        CREATE TABLE game_locations (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, is_active INTEGER DEFAULT 1, world_hex_q INTEGER, world_hex_r INTEGER);
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, gm_plan_json TEXT);
        """ + table_sql("game_config_enemies") + """
        CREATE TABLE character_bestiary (id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, enemy_key TEXT, kills INTEGER, unlocked_tier INTEGER, first_kill_at TEXT, last_kill_at TEXT);
        CREATE TABLE character_rumors (id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, campaign_id INTEGER, rumor_text TEXT, target_type TEXT, target_key TEXT, status TEXT DEFAULT 'heard', heard_at TEXT, confirmed_at TEXT, truth_flag INTEGER NOT NULL DEFAULT 1, source_type TEXT NOT NULL DEFAULT 'encounter', region TEXT, suspected INTEGER NOT NULL DEFAULT 0);
        """
    )
    # hero 1: current campaign 100, past campaign 101
    c.execute("INSERT INTO characters (id, campaign_id) VALUES (1, 100)")
    c.execute("INSERT INTO character_campaign_history (character_id, campaign_id) VALUES (1, 101)")
    # overworld: 5 hexes total
    for q, r, reg in [(0, 0, "wolanka"), (1, 0, "wolanka"), (2, 0, "grania"), (3, 0, "grania"), (4, 0, None)]:
        c.execute("INSERT INTO world_hexes (q, r, map_level, region) VALUES (?, ?, 0, ?)", (q, r, reg))
    # discovered: camp100 → (0,0),(1,0) ; camp101 → (1,0) dup + (2,0)
    for camp, q, r in [(100, 0, 0), (100, 1, 0), (101, 1, 0), (101, 2, 0)]:
        c.execute("INSERT INTO campaign_hex_data (campaign_id, hex_q, hex_r, discovered) VALUES (?, ?, ?, 1)", (camp, q, r))
    # a location on a discovered hex
    c.execute("INSERT INTO game_locations (key, world_hex_q, world_hex_r) VALUES ('loc_a', 0, 0)")
    c.execute("INSERT INTO game_locations (key, world_hex_q, world_hex_r) VALUES ('loc_undisc', 9, 9)")
    # plan with unvisited location
    plan = {"key_locations": [
        {"key": "loc_visited", "name": "Odwiedzone", "visited": True},
        {"key": "loc_target", "name": "Zapomniana Wieża", "visited": False},
    ]}
    c.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (100, ?)", (json.dumps(plan),))
    c.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (101, NULL)")
    c.executemany("INSERT INTO game_config_enemies (key,label,tier) VALUES (?,?,?)",
                  [("goblin", "Goblin", "1"), ("dragon", "Smok", "boss")])
    c.commit()
    yield c
    c.close()


# ── Atlas aggregation ────────────────────────────────────────────────────────

def test_atlas_dedups_hexes_across_campaigns(conn):
    a = at.get_atlas(1, conn=conn)
    # unique discovered pairs: (0,0),(1,0),(2,0) = 3 (dup (1,0) counted once)
    assert a["hexes"]["discovered"] == 3
    assert a["hexes"]["total"] == 5
    assert a["hexes"]["pct"] == 60


def test_atlas_region_breakdown(conn):
    a = at.get_atlas(1, conn=conn)
    regs = {r["region"]: r["discovered"] for r in a["hexes"]["regions"]}
    assert regs.get("wolanka") == 2   # (0,0),(1,0)
    assert regs.get("grania") == 1    # (2,0)


def test_atlas_counts_locations_on_discovered_hexes(conn):
    a = at.get_atlas(1, conn=conn)
    assert a["locations"]["discovered"] == 1  # loc_a on (0,0); loc_undisc excluded


def test_atlas_unknown_hero_empty(conn):
    a = at.get_atlas(999, conn=conn)
    assert a["hexes"]["discovered"] == 0
    assert a["hexes"]["total"] == 5
    assert a["rumors"]["heard"] == 0


def test_atlas_bad_input_no_raise(conn):
    assert at.get_atlas(None, conn=conn)["hexes"]["discovered"] == 0


# ── Rumors ───────────────────────────────────────────────────────────────────

def test_create_rumor_targets_unvisited_plan_location(conn):
    r = rs.create_rumor(100, 1, conn=conn)
    assert r["target_type"] == "location"
    assert r["target_key"] == "loc_target"
    assert "Zapomniana Wieża" in r["rumor_text"]
    row = conn.execute("SELECT status FROM character_rumors WHERE character_id=1").fetchone()
    assert row["status"] == "heard"


def test_create_rumor_dedup_same_target(conn):
    rs.create_rumor(100, 1, conn=conn)
    rs.create_rumor(100, 1, conn=conn)  # only one unvisited loc → 2nd falls through to enemy
    targets = [r["target_type"] for r in conn.execute(
        "SELECT target_type FROM character_rumors WHERE character_id=1").fetchall()]
    # first = location, second must NOT duplicate the location target
    assert targets.count("location") == 1


def test_create_rumor_falls_back_to_enemy(conn):
    # mark the only unvisited plan location as visited → no location candidate
    plan = {"key_locations": [{"key": "loc_target", "name": "X", "visited": True}]}
    conn.execute("UPDATE campaigns SET gm_plan_json=? WHERE id=100", (json.dumps(plan),))
    r = rs.create_rumor(100, 1, conn=conn)
    assert r["target_type"] == "enemy"
    assert r["target_key"] == "goblin"  # non-boss, not yet hunted


def test_confirm_rumor_flips_status(conn):
    rs.create_rumor(100, 1, conn=conn)  # location loc_target
    n = rs.confirm_rumors_for(100, "location", "loc_target", conn=conn)
    assert n == 1
    row = conn.execute("SELECT status, confirmed_at FROM character_rumors WHERE character_id=1").fetchone()
    assert row["status"] == "confirmed"
    assert row["confirmed_at"] is not None


def test_confirm_scoped_to_campaign_and_target(conn):
    rs.create_rumor(100, 1, conn=conn)
    assert rs.confirm_rumors_for(100, "location", "other_key", conn=conn) == 0
    assert rs.confirm_rumors_for(999, "location", "loc_target", conn=conn) == 0
    assert conn.execute("SELECT status FROM character_rumors WHERE character_id=1").fetchone()["status"] == "heard"


def test_confirm_noop_bad_input(conn):
    assert rs.confirm_rumors_for(100, "", "x", conn=conn) == 0
    assert rs.confirm_rumors_for(100, "location", "", conn=conn) == 0


def test_atlas_includes_rumor_summary(conn):
    rs.create_rumor(100, 1, conn=conn)
    rs.confirm_rumors_for(100, "location", "loc_target", conn=conn)
    rs.create_rumor(100, 1, conn=conn)  # enemy, stays heard
    a = at.get_atlas(1, conn=conn)
    assert a["rumors"]["confirmed"] == 1
    assert a["rumors"]["heard"] == 1
    assert len(a["rumors"]["entries"]) == 2
