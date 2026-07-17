"""TDD: #1190 — System plotek w karczmach.

Rozszerza plotki Atlasu (#1191): nadstaw ucha (darmo, szansa) / postaw kolejkę
(5 zł, pewniak + bonus wyczucia). Plotki bywają FAŁSZYWE (60/40 dla celów-miejsc);
wizyta w celu fałszywki → debunked. Udany test wyczucia oznacza plotkę „podejrzaną".

Nowe cele dystrybucji: loch (game_dungeons) + wydarzenie regionalne (#1193).
"""
import json
import sqlite3

import pytest

from app.services import rumor_service as rs
from app.api import turns as T


# ── rng shim: deterministyczny truth-roll ─────────────────────────────────────
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
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER,
            is_active INTEGER DEFAULT 1, gold_gp INTEGER DEFAULT 0, sheet_json TEXT);
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, gm_plan_json TEXT);
        CREATE TABLE character_rumors (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, campaign_id INTEGER,
            rumor_text TEXT, target_type TEXT, target_key TEXT, status TEXT DEFAULT 'heard',
            heard_at TEXT, confirmed_at TEXT,
            truth_flag INTEGER NOT NULL DEFAULT 1, source_type TEXT NOT NULL DEFAULT 'encounter',
            region TEXT, suspected INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE game_dungeons (key TEXT PRIMARY KEY, label TEXT, location_key TEXT,
            is_active INTEGER DEFAULT 1);
        CREATE TABLE character_dungeon_runs (id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, location_key TEXT);
        """
    )
    c.execute("INSERT INTO characters (id, campaign_id, gold_gp, sheet_json) VALUES "
              "(1, 100, 50, ?)", (json.dumps({"stats": {"WIS": 16, "CHA": 8}}),))
    # plan z jedną nieodwiedzoną lokacją (cel-miejsce, może być fałszywy)
    plan = {"key_locations": [{"key": "loc_x", "name": "Zapomniana Wieża", "visited": False}]}
    c.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (100, ?)", (json.dumps(plan),))
    c.commit()
    yield c
    c.close()


# ── Prawda / fałsz ────────────────────────────────────────────────────────────

def test_eavesdrop_true_rumor_when_rng_low(conn):
    r = rs.eavesdrop_rumor(100, 1, paid=False, conn=conn, rng=_RNG(0.1))  # 0.1 < 0.6 → prawda
    assert r["truth_flag"] == 1
    assert r["target_type"] == "location"
    assert "Zapomniana Wieża" in r["rumor_text"]
    row = conn.execute("SELECT source_type FROM character_rumors WHERE id=?",
                       (r["rumor_id"],)).fetchone()
    assert row["source_type"] == "eavesdrop"


def test_eavesdrop_false_rumor_when_rng_high(conn):
    r = rs.eavesdrop_rumor(100, 1, paid=True, conn=conn, rng=_RNG(0.9))  # 0.9 >= 0.6 → fałsz
    assert r["truth_flag"] == 0
    assert conn.execute("SELECT source_type FROM character_rumors WHERE id=?",
                        (r["rumor_id"],)).fetchone()["source_type"] == "round"


def test_visit_confirms_true_rumor(conn):
    r = rs.eavesdrop_rumor(100, 1, conn=conn, rng=_RNG(0.1))  # prawda
    n = rs.confirm_rumors_for(100, "location", "loc_x", conn=conn)
    assert n == 1
    assert conn.execute("SELECT status FROM character_rumors WHERE id=?",
                        (r["rumor_id"],)).fetchone()["status"] == "confirmed"


def test_visit_debunks_false_rumor(conn):
    r = rs.eavesdrop_rumor(100, 1, conn=conn, rng=_RNG(0.9))  # fałsz
    n = rs.confirm_rumors_for(100, "location", "loc_x", conn=conn)
    assert n == 1
    assert conn.execute("SELECT status FROM character_rumors WHERE id=?",
                        (r["rumor_id"],)).fetchone()["status"] == "debunked"


def test_mark_suspected(conn):
    r = rs.eavesdrop_rumor(100, 1, conn=conn, rng=_RNG(0.9))
    assert rs.mark_suspected(r["rumor_id"], conn=conn) is True
    assert conn.execute("SELECT suspected FROM character_rumors WHERE id=?",
                        (r["rumor_id"],)).fetchone()["suspected"] == 1


def test_encounter_rumor_always_true(conn):
    # legacy path (#1191) — nawet gdy „random" byłby wysoki, encounter zawsze prawda
    r = rs.create_rumor(100, 1, conn=conn)
    assert r["truth_flag"] == 1
    assert conn.execute("SELECT source_type FROM character_rumors WHERE id=?",
                        (r["rumor_id"],)).fetchone()["source_type"] == "encounter"


# ── Nowe cele: loch + event ───────────────────────────────────────────────────

def test_target_dungeon_when_no_location(conn):
    conn.execute("UPDATE campaigns SET gm_plan_json=? WHERE id=100",
                 (json.dumps({"key_locations": []}),))
    conn.execute("INSERT INTO game_dungeons (key, label, location_key) VALUES "
                 "('krypta', 'Zapadła Krypta', 'loc_krypta')")
    conn.commit()
    r = rs.eavesdrop_rumor(100, 1, conn=conn, rng=_RNG(0.1))
    assert r["target_type"] == "dungeon"
    assert r["target_key"] == "krypta"
    assert "Zapadła Krypta" in r["rumor_text"]


def test_cleared_dungeon_skipped(conn):
    conn.execute("UPDATE campaigns SET gm_plan_json=? WHERE id=100",
                 (json.dumps({"key_locations": []}),))
    conn.execute("INSERT INTO game_dungeons (key, label, location_key) VALUES "
                 "('krypta', 'Krypta', 'loc_krypta')")
    conn.execute("INSERT INTO character_dungeon_runs (character_id, location_key) VALUES "
                 "(1, 'loc_krypta')")
    conn.commit()
    r = rs.eavesdrop_rumor(100, 1, conn=conn, rng=_RNG(0.1))
    # brak lokacji, loch ukończony → spada do enemy/None (nie dungeon)
    assert r["target_type"] != "dungeon"


def test_target_event_always_true(conn, monkeypatch):
    conn.execute("UPDATE campaigns SET gm_plan_json=? WHERE id=100",
                 (json.dumps({"key_locations": []}),))
    conn.commit()
    monkeypatch.setattr("app.services.reputation_service.resolve_region",
                        lambda c, cid: "kresy")
    monkeypatch.setattr("app.services.world_event_service.get_active_event",
                        lambda c, region: {"id": 7, "label": "zaraza w okolicy"})
    r = rs.eavesdrop_rumor(100, 1, conn=conn, rng=_RNG(0.9))  # nawet high rng → event prawda
    assert r["target_type"] == "event"
    assert r["truth_flag"] == 1
    assert "zaraza w okolicy" in r["rumor_text"]


# ── Intent karczemny (regex, odporność na brak ogonków) ───────────────────────

@pytest.mark.parametrize("txt", [
    "stawiam kolejkę przy barze", "funduję rundkę dla zwiadowcy",
    "postaw wszystkim piwo", "stawiam kolejke",  # bez ogonka
])
def test_rumor_intent_paid(txt):
    assert T._rumor_intent(txt) == "paid"


@pytest.mark.parametrize("txt", [
    "nadstawiam ucha", "przysłuchuję się rozmowom", "podsłuchuję gości",
    "nadstawiam ucha przy stole",  # bez ogonków
])
def test_rumor_intent_free(txt):
    assert T._rumor_intent(txt) == "free"


@pytest.mark.parametrize("txt", ["idę dalej drogą", "atakuję goblina", "kupuję miecz"])
def test_rumor_intent_none(txt):
    assert T._rumor_intent(txt) is None


def test_at_tavern_by_noun(conn):
    assert T._at_tavern(conn, 100, "rozglądam się po karczmie") is True
    assert T._at_tavern(conn, 100, "stoję na polanie") is False
