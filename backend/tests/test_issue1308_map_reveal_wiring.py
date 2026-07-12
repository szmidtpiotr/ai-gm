"""TDD: Issue #1308 — map reward reveal wiring.

The reveal ENGINE already existed (#1123 map_reveal_service). This covers the new
wiring: a `location` mode (reveal by location_key, drift-proof), reveal_hexes also
setting FOW `known` + world_hexes.discovered_in_campaign_id, and the Kuźnia
materializing a map reward into an item whose effect_json carries the payload.
"""
import json
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.services import map_reveal_service as mrs  # noqa: E402


SCHEMA = """
CREATE TABLE world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER, r INTEGER, location_key TEXT, region TEXT DEFAULT 'kresy',
    is_active INTEGER DEFAULT 1, map_level INTEGER DEFAULT 0,
    discovered_in_campaign_id INTEGER
);
CREATE TABLE campaign_hex_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL, hex_q INTEGER NOT NULL, hex_r INTEGER NOT NULL,
    discovered INTEGER DEFAULT 0, known INTEGER DEFAULT 0,
    UNIQUE(campaign_id, hex_q, hex_r)
);
CREATE TABLE game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT, world_hex_q INTEGER, world_hex_r INTEGER, is_active INTEGER DEFAULT 1
);
CREATE TABLE meta (k TEXT, v TEXT);
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    c.execute("INSERT INTO world_hexes (q, r, location_key) VALUES (1, 7, 'spalona_kaplica')")
    c.execute("INSERT INTO world_hexes (q, r, location_key) VALUES (4, 9, 'cmentarz')")
    c.execute("INSERT INTO world_hexes (q, r, location_key) VALUES (6, 8, 'wilczburg')")
    c.commit()
    return c


# ── location mode ────────────────────────────────────────────────────────────

def test_location_mode_resolves_keys_to_hexes(conn):
    hexes = mrs.compute_reveal_hexes(conn, {"mode": "location", "list": ["spalona_kaplica", "cmentarz"]})
    assert set(hexes) == {(1, 7), (4, 9)}


def test_location_mode_ignores_unknown_keys(conn):
    hexes = mrs.compute_reveal_hexes(conn, {"mode": "location", "list": ["nope", "spalona_kaplica"]})
    assert hexes == [(1, 7)]


def test_extract_payload_accepts_location_mode(conn):
    p = mrs.extract_map_payload(json.dumps(
        {"effects": [{"type": "map_reveal", "mode": "location", "list": ["spalona_kaplica"]}]}))
    assert p and p["mode"] == "location"


# ── reveal_hexes sets discovered + known + world overlay ─────────────────────

def test_reveal_sets_discovered_known_and_overlay(conn):
    res = mrs.reveal_from_payload(9998883, {"mode": "location", "list": ["spalona_kaplica"]}, conn=conn)
    assert res["count"] == 1
    row = conn.execute(
        "SELECT discovered, known FROM campaign_hex_data WHERE campaign_id=9998883 AND hex_q=1 AND hex_r=7"
    ).fetchone()
    assert row["discovered"] == 1 and row["known"] == 1
    wh = conn.execute("SELECT discovered_in_campaign_id FROM world_hexes WHERE q=1 AND r=7").fetchone()
    assert wh["discovered_in_campaign_id"] == 9998883


def test_reveal_is_idempotent(conn):
    mrs.reveal_from_payload(1, {"mode": "location", "list": ["spalona_kaplica"]}, conn=conn)
    mrs.reveal_from_payload(1, {"mode": "location", "list": ["spalona_kaplica"]}, conn=conn)
    n = conn.execute("SELECT COUNT(*) FROM campaign_hex_data WHERE campaign_id=1").fetchone()[0]
    assert n == 1


def test_reveal_does_not_clobber_existing_overlay(conn):
    conn.execute("UPDATE world_hexes SET discovered_in_campaign_id=42 WHERE q=1 AND r=7")
    conn.commit()
    mrs.reveal_from_payload(99, {"mode": "location", "list": ["spalona_kaplica"]}, conn=conn)
    wh = conn.execute("SELECT discovered_in_campaign_id FROM world_hexes WHERE q=1 AND r=7").fetchone()
    assert wh["discovered_in_campaign_id"] == 42, "nie nadpisuje pierwszego odkrywcy"


# ── backward-compat: minimal #1123 schema (no known / no overlay col) ────────

def test_reveal_works_on_legacy_schema_without_known():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        "CREATE TABLE world_hexes (id INTEGER PRIMARY KEY, q INTEGER, r INTEGER,"
        " region TEXT, is_active INTEGER DEFAULT 1, map_level INTEGER DEFAULT 0);"
        "CREATE TABLE campaign_hex_data (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " campaign_id INTEGER, hex_q INTEGER, hex_r INTEGER, discovered INTEGER DEFAULT 0,"
        " UNIQUE(campaign_id, hex_q, hex_r));"
    )
    c.execute("INSERT INTO world_hexes (q, r, region) VALUES (0,0,'kresy'),(1,0,'kresy')")
    c.commit()
    n = mrs.reveal_hexes(c, 5, [(0, 0), (1, 0)])
    assert n == 2
    assert c.execute("SELECT COUNT(*) FROM campaign_hex_data WHERE discovered=1").fetchone()[0] == 2
