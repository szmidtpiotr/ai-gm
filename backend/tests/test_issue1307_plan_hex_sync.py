"""TDD: Issue #1307 — mirror placed macro-location hexes back into
gm_plan_json.key_locations[].hex_q/hex_r.

After placement the coords live in world_hexes.location_key (canon); the plan JSON
still showed None. `sync_plan_location_hexes` writes them back for the template
(and, when given, the launching campaign copy). Idempotent.
"""
import json
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.services.template_start_anchor import sync_plan_location_hexes  # noqa: E402


SCHEMA = """
CREATE TABLE campaign_templates (id INTEGER PRIMARY KEY, gm_plan_json TEXT);
CREATE TABLE campaigns (id INTEGER PRIMARY KEY, gm_plan_json TEXT);
CREATE TABLE world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER, r INTEGER, location_key TEXT,
    is_active INTEGER DEFAULT 1, map_level INTEGER DEFAULT 0
);
CREATE TABLE game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT, world_hex_q INTEGER, world_hex_r INTEGER, is_active INTEGER DEFAULT 1
);
"""

PLAN = {
    "key_locations": [
        {"key": "wilczburg", "name": "Wilczburg"},
        {"key": "spalona_kaplica", "name": "Spalona Kaplica"},
        {"key": "no_hex", "name": "Nieumieszczona"},
    ],
}


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    c.execute("INSERT INTO campaign_templates (id, gm_plan_json) VALUES (1, ?)",
              (json.dumps(PLAN),))
    c.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (55, ?)",
              (json.dumps(PLAN),))
    # canon: wilczburg at (6,8), kaplica at (1,7); no_hex placed nowhere
    c.execute("INSERT INTO world_hexes (q, r, location_key) VALUES (6, 8, 'wilczburg')")
    c.execute("INSERT INTO world_hexes (q, r, location_key) VALUES (1, 7, 'spalona_kaplica')")
    c.commit()
    return c


def _plan(c, table, rid):
    return json.loads(c.execute(f"SELECT gm_plan_json FROM {table} WHERE id=?", (rid,)).fetchone()[0])


def test_syncs_template_plan(conn):
    res = sync_plan_location_hexes(conn, 1)
    assert res["synced"] == 2
    locs = {l["key"]: l for l in _plan(conn, "campaign_templates", 1)["key_locations"]}
    assert (locs["wilczburg"]["hex_q"], locs["wilczburg"]["hex_r"]) == (6, 8)
    assert (locs["spalona_kaplica"]["hex_q"], locs["spalona_kaplica"]["hex_r"]) == (1, 7)
    # unplaced location left untouched
    assert locs["no_hex"].get("hex_q") is None


def test_syncs_campaign_copy_too(conn):
    res = sync_plan_location_hexes(conn, 1, campaign_id=55)
    assert res["synced"] == 4  # 2 template + 2 campaign
    locs = {l["key"]: l for l in _plan(conn, "campaigns", 55)["key_locations"]}
    assert (locs["wilczburg"]["hex_q"], locs["wilczburg"]["hex_r"]) == (6, 8)


def test_idempotent(conn):
    sync_plan_location_hexes(conn, 1)
    res2 = sync_plan_location_hexes(conn, 1)
    assert res2["synced"] == 0, "drugi przebieg nic nie zmienia"
