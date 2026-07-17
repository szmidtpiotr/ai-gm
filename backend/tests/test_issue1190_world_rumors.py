"""TDD: #1190 R2/R3 — pula plotek per region + draw dla bohatera + parser AI.

world_rumors = ambient plotki regionu (admin/AI). Gdy bohater nadstawia ucha,
pula regionu zasila character_rumors (kopia z world_rumor_id → dedup + confirm/debunk).
"""
import sqlite3

import pytest

from app.services import world_rumor_service as wrs
from app.services import rumor_service as rs


class _RNG:
    def __init__(self, val):
        self.val = val

    def random(self):
        return self.val


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE world_rumors (
            id INTEGER PRIMARY KEY AUTOINCREMENT, region TEXT NOT NULL, rumor_text TEXT NOT NULL,
            truth_flag INTEGER NOT NULL DEFAULT 1, target_type TEXT, target_key TEXT,
            created_by TEXT NOT NULL DEFAULT 'manual', is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT);
        CREATE TABLE character_rumors (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, campaign_id INTEGER,
            rumor_text TEXT, target_type TEXT, target_key TEXT, status TEXT DEFAULT 'heard',
            heard_at TEXT, confirmed_at TEXT, truth_flag INTEGER NOT NULL DEFAULT 1,
            source_type TEXT NOT NULL DEFAULT 'encounter', region TEXT,
            suspected INTEGER NOT NULL DEFAULT 0, world_rumor_id INTEGER);
        CREATE TABLE world_hexes (id INTEGER PRIMARY KEY AUTOINCREMENT, q INTEGER, r INTEGER,
            map_level INTEGER DEFAULT 0, region TEXT);
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, gm_plan_json TEXT);
        CREATE TABLE game_locations (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, label TEXT,
            is_active INTEGER DEFAULT 1, world_hex_q INTEGER, world_hex_r INTEGER);
        CREATE TABLE game_dungeons (key TEXT PRIMARY KEY, label TEXT, location_key TEXT, is_active INTEGER DEFAULT 1);
        """
    )
    c.execute("INSERT INTO world_hexes (q,r,map_level,region) VALUES (0,0,0,'kresy')")
    c.execute("INSERT INTO world_hexes (q,r,map_level,region) VALUES (1,0,0,'siwe_granie')")
    c.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (100, '{}')")
    c.commit()
    yield c
    c.close()


# ── CRUD + regiony ────────────────────────────────────────────────────────────

def test_list_regions(conn):
    assert wrs.list_regions(conn=conn) == ["kresy", "siwe_granie"]


def test_create_and_list(conn):
    rid = wrs.create_world_rumor("kresy", "Zbójcy na trakcie", 1, conn=conn)
    assert rid
    items = wrs.list_world_rumors("kresy", conn=conn)
    assert len(items) == 1 and items[0]["created_by"] == "manual"
    assert wrs.list_world_rumors("siwe_granie", conn=conn) == []


def test_create_rejects_empty(conn):
    assert wrs.create_world_rumor("", "x", conn=conn) is None
    assert wrs.create_world_rumor("kresy", "  ", conn=conn) is None


def test_delete(conn):
    rid = wrs.create_world_rumor("kresy", "x", conn=conn)
    assert wrs.delete_world_rumor(rid, conn=conn) is True
    assert wrs.list_world_rumors("kresy", conn=conn) == []


# ── draw_for_region ───────────────────────────────────────────────────────────

def test_draw_returns_unheard(conn):
    wrs.create_world_rumor("kresy", "plotka A", 1, conn=conn)
    d = wrs.draw_for_region(conn, 1, "kresy")
    assert d and d["rumor_text"] == "plotka A"


def test_draw_skips_already_heard(conn):
    rid = wrs.create_world_rumor("kresy", "plotka A", 1, conn=conn)
    conn.execute("INSERT INTO character_rumors (character_id, campaign_id, rumor_text, world_rumor_id) "
                 "VALUES (1, 100, 'plotka A', ?)", (rid,))
    conn.commit()
    assert wrs.draw_for_region(conn, 1, "kresy") is None  # jedyna już słyszana


def test_draw_none_for_empty_region(conn):
    assert wrs.draw_for_region(conn, 1, "siwe_granie") is None
    assert wrs.draw_for_region(conn, 1, None) is None


# ── eavesdrop czerpie z puli ──────────────────────────────────────────────────

def test_eavesdrop_prefers_world_pool(conn, monkeypatch):
    monkeypatch.setattr("app.services.reputation_service.resolve_region", lambda c, cid: "kresy")
    rid = wrs.create_world_rumor("kresy", "Świński Targ ponoć płonie", 0,
                                 target_type="location", target_key="loc_x", conn=conn)
    r = rs.eavesdrop_rumor(100, 1, paid=False, conn=conn, rng=_RNG(0.1))  # 0.1 < 0.6 → pula
    assert r["rumor_text"] == "Świński Targ ponoć płonie"
    assert r["truth_flag"] == 0
    row = conn.execute("SELECT source_type, world_rumor_id FROM character_rumors WHERE id=?",
                       (r["rumor_id"],)).fetchone()
    assert row["source_type"] == "world" and row["world_rumor_id"] == rid


def test_eavesdrop_world_dedup(conn, monkeypatch):
    monkeypatch.setattr("app.services.reputation_service.resolve_region", lambda c, cid: "kresy")
    wrs.create_world_rumor("kresy", "jedyna plotka", 1, conn=conn)
    r1 = rs.eavesdrop_rumor(100, 1, conn=conn, rng=_RNG(0.1))
    assert r1["rumor_text"] == "jedyna plotka"
    # druga próba: pula wyczerpana dla tego bohatera → auto-fallback (nie ta sama world)
    r2 = rs.eavesdrop_rumor(100, 1, conn=conn, rng=_RNG(0.1))
    row2 = conn.execute("SELECT source_type FROM character_rumors WHERE id=?", (r2["rumor_id"],)).fetchone()
    assert row2["source_type"] != "world"


def test_eavesdrop_confirm_debunk_from_world(conn, monkeypatch):
    monkeypatch.setattr("app.services.reputation_service.resolve_region", lambda c, cid: "kresy")
    wrs.create_world_rumor("kresy", "fałsz o loc_x", 0,
                           target_type="location", target_key="loc_x", conn=conn)
    r = rs.eavesdrop_rumor(100, 1, conn=conn, rng=_RNG(0.1))
    n = rs.confirm_rumors_for(100, "location", "loc_x", conn=conn)
    assert n == 1
    assert conn.execute("SELECT status FROM character_rumors WHERE id=?",
                        (r["rumor_id"],)).fetchone()["status"] == "debunked"


# ── parser AI ─────────────────────────────────────────────────────────────────

def test_parse_plain_json():
    out = wrs._parse_rumors_json('{"rumors":[{"text":"a","truth":false}]}')
    assert out == [{"text": "a", "truth": False}]


def test_parse_fenced_json():
    raw = 'Oto plotki:\n```json\n{"rumors":[{"text":"b","truth":true}]}\n```\n'
    out = wrs._parse_rumors_json(raw)
    assert out and out[0]["text"] == "b"


def test_parse_garbage_returns_empty():
    assert wrs._parse_rumors_json("nie ma tu jsona") == []
    assert wrs._parse_rumors_json("") == []


def test_valid_target_closed_vocab():
    facts = {"locations": [{"key": "loc_x", "label": "X"}], "dungeons": []}
    assert wrs._valid_target(facts, "location", "loc_x") == ("location", "loc_x")
    assert wrs._valid_target(facts, "location", "HALLUCINATED") == (None, None)
    assert wrs._valid_target(facts, None, None) == (None, None)
