"""WL-4 (#1504) — testy silnika rejsów port↔port (Wybrzeże Łez).

Dwa poziomy:
  • TestVoyageLogic — czyste funkcje (bez DB): porty, gating skrótów, ryzyko/noc,
    ważenie zdarzeń z Mapą Smolnego.
  • TestVoyageExecute — pełny skok port→port na minimalnym schemacie SQLite +
    monkeypatch ciężkich usług zewnętrznych (walka/scena/zegar).
"""

from __future__ import annotations

import json
import random
import sqlite3

import pytest

from app.services import sea_voyage_service as svc


# ── Poziom 1: logika bez DB ───────────────────────────────────────────────────

class TestVoyageLogic:
    def test_ports_are_route_endpoints(self):
        assert svc.is_sail_port("czarnogrod_port")
        assert svc.is_sail_port("zatoka_topielcow")
        assert not svc.is_sail_port("kresy_wioska")
        assert not svc.is_sail_port(None)

    def test_dest_of_bidirectional(self):
        route = next(r for r in svc.SEA_ROUTES if r["key"] == "czarnogrod_zatoka")
        assert svc._dest_of(route, "czarnogrod_port") == "zatoka_topielcow"
        assert svc._dest_of(route, "zatoka_topielcow") == "czarnogrod_port"
        assert svc._dest_of(route, "gdzies_indziej") is None

    def test_shortcut_gated_by_map(self):
        without = svc._routes_from("czarnogrod_port", has_map=False)
        with_map = svc._routes_from("czarnogrod_port", has_map=True)
        keys_without = {r[0]["key"] for r in without}
        keys_with = {r[0]["key"] for r in with_map}
        assert "czarnogrod_zatoka" in keys_without          # zwykła trasa zawsze
        assert "czarnogrod_zatoka_skrot" not in keys_without  # skrót ukryty bez mapy
        assert "czarnogrod_zatoka_skrot" in keys_with         # skrót widoczny z mapą

    def test_night_raises_risk(self):
        day = svc._voyage_event_chance(is_night=False)
        night = svc._voyage_event_chance(is_night=True)
        assert night > day
        assert night == pytest.approx(min(0.95, svc.VOYAGE_EVENT_CHANCE * svc.VOYAGE_NIGHT_MULT))

    def test_risk_label_scales(self):
        assert svc._risk_label(is_night=False) in ("niskie", "umiarkowane", "wysokie")
        # noc daje wyższą (lub równą) etykietę ryzyka
        order = {"niskie": 0, "umiarkowane": 1, "wysokie": 2}
        assert order[svc._risk_label(True)] >= order[svc._risk_label(False)]

    def test_map_reduces_reef_frequency(self):
        rng = random.Random(1588)
        n = 4000
        reef_no_map = sum(svc._pick_event_kind(False, rng) == "rafa" for _ in range(n))
        reef_map = sum(svc._pick_event_kind(True, rng) == "rafa" for _ in range(n))
        # Mapa Smolnego ma wyraźnie obniżyć liczbę raf.
        assert reef_map < reef_no_map * 0.5

    def test_roll_dice_bounds(self):
        rng = random.Random(7)
        for _ in range(200):
            v = svc._roll("1d6", rng)
            assert 1 <= v <= 6
        assert svc._roll("bad", rng) == 0


# ── Poziom 2: pełny rejs na minimalnym DB ──────────────────────────────────────

def _hp(conn: sqlite3.Connection, char_id: int = 999) -> int:
    row = conn.execute("SELECT sheet_json FROM characters WHERE id=?", (char_id,)).fetchone()
    return int(json.loads(row["sheet_json"])["current_hp"])


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, status TEXT,
            gold_gp INTEGER DEFAULT 0, sheet_json TEXT
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER,
            item_key TEXT, weapon_key TEXT, consumable_key TEXT, quantity INTEGER DEFAULT 1
        );
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, delta INTEGER,
            source TEXT, campaign_id INTEGER, game_clock_day INTEGER, meta_json TEXT
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, session_flags TEXT,
            current_location_id INTEGER
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY, key TEXT, label TEXT,
            world_hex_q INTEGER, world_hex_r INTEGER, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, q INTEGER, r INTEGER,
            location_key TEXT, map_level INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, character_id INTEGER,
            user_text TEXT, route TEXT, assistant_text TEXT, turn_number INTEGER
        );
        """
    )
    # dwa porty na hexach
    conn.execute("INSERT INTO game_locations (id,key,label,world_hex_q,world_hex_r) VALUES (1,'czarnogrod_port','Czarnogród, Port',-24,65)")
    conn.execute("INSERT INTO game_locations (id,key,label,world_hex_q,world_hex_r) VALUES (2,'zatoka_topielcow','Zatoka Topielców',-25,102)")
    conn.execute("INSERT INTO world_hexes (q,r,location_key) VALUES (-24,65,'czarnogrod_port')")
    conn.execute("INSERT INTO world_hexes (q,r,location_key) VALUES (-25,102,'zatoka_topielcow')")
    # bohater w Czarnogrodzie, 100 zł, 20 HP
    conn.execute(
        "INSERT INTO characters (id,campaign_id,status,gold_gp,sheet_json) VALUES (?,?,?,?,?)",
        (999, 1, "active", 100, json.dumps({"current_hp": 20, "max_hp": 20})),
    )
    conn.execute(
        "INSERT INTO game_sessions (id,campaign_id,session_flags,current_location_id) VALUES (?,?,?,?)",
        (1, 1, json.dumps({"current_hex": {"q": -24, "r": 65}}), 1),
    )
    conn.commit()
    return conn


@pytest.fixture
def patched(monkeypatch):
    """Zneutralizuj ciężkie usługi zewnętrzne, zostaw czyste ścieżki DB."""
    import app.services.combat_service as combat
    import app.services.clock_service as clock
    import app.services.world_state_service as world_state

    monkeypatch.setattr(combat, "get_active_combat", lambda cid: None, raising=False)
    monkeypatch.setattr(clock, "advance_clock",
                        lambda cid, hours=0.0, reason="", conn=None, **kw: {"day": 1, "hour": 12, "period": "Popołudnie", "advanced": hours},
                        raising=False)
    monkeypatch.setattr(clock, "get_clock_state",
                        lambda cid, conn=None: {"day": 1, "hour": 12, "period": "Popołudnie", "ingame_hours": 12},
                        raising=False)
    monkeypatch.setattr(world_state, "enter_location_scene", lambda cid, key: {"location_key": key}, raising=False)
    monkeypatch.setattr(world_state, "exit_location_scene", lambda cid: None, raising=False)
    yield


class TestVoyageExecute:
    def test_basic_voyage_costs_gold_and_moves(self, patched):
        conn = _make_db()
        # RNG bez zdarzenia (random()>=chance): 0.99 → brak eventu
        rng = _StubRng(random_values=[0.99])
        res = svc.execute_sea_voyage(conn, 1, 999, "czarnogrod_zatoka", rng=rng)

        assert res["ok"] is True
        assert res["dest_key"] == "zatoka_topielcow"
        assert res["fare_gp"] == 40
        assert res["gold"] == 60                       # 100 - 40
        assert res["event"] is None
        # pozycja przeniesiona na hex Zatoki
        sf = json.loads(conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()["session_flags"])
        assert sf["current_hex"] == {"q": -25, "r": 102}
        assert conn.execute("SELECT current_location_id FROM game_sessions WHERE campaign_id=1").fetchone()[0] == 2
        # syntetyczna tura zapisana
        assert conn.execute("SELECT COUNT(*) FROM campaign_turns WHERE campaign_id=1").fetchone()[0] == 1

    def test_not_enough_gold(self, patched):
        conn = _make_db()
        conn.execute("UPDATE characters SET gold_gp=10 WHERE id=999")
        conn.commit()
        with pytest.raises(svc.VoyageError) as e:
            svc.execute_sea_voyage(conn, 1, 999, "czarnogrod_zatoka", rng=_StubRng([0.99]))
        assert e.value.code == "not_enough_gold"
        # złoto nietknięte (opłata cofnięta przez wyjątek przed commitem)
        assert conn.execute("SELECT gold_gp FROM characters WHERE id=999").fetchone()[0] == 10

    def test_shortcut_needs_map(self, patched):
        conn = _make_db()
        with pytest.raises(svc.VoyageError) as e:
            svc.execute_sea_voyage(conn, 1, 999, "czarnogrod_zatoka_skrot", rng=_StubRng([0.99]))
        assert e.value.code == "needs_map"

    def test_shortcut_works_with_map(self, patched):
        conn = _make_db()
        conn.execute("INSERT INTO character_inventory (character_id,item_key,quantity) VALUES (999,'mapa_smolnego',1)")
        conn.commit()
        res = svc.execute_sea_voyage(conn, 1, 999, "czarnogrod_zatoka_skrot", rng=_StubRng([0.99]))
        assert res["ok"] is True
        assert res["fare_gp"] == 25
        assert res["used_map"] is True

    def test_storm_event_applies_hp_and_hours(self, patched):
        conn = _make_db()
        # random()<chance → event; choices → sztorm; _roll 1d4 → deterministyczne
        rng = _StubRng(random_values=[0.01], choice_pick="sztorm", randint_val=3)
        res = svc.execute_sea_voyage(conn, 1, 999, "czarnogrod_zatoka", rng=rng)
        assert res["event"]["kind"] == "sztorm"
        assert res["event"]["hp_loss"] == 3
        assert res["hours"] == 8.0 + svc.STORM_EXTRA_HOURS
        assert _hp(conn) == 17

    def test_pirates_take_gold(self, patched):
        conn = _make_db()
        rng = _StubRng(random_values=[0.01], choice_pick="piraci")
        res = svc.execute_sea_voyage(conn, 1, 999, "czarnogrod_zatoka", rng=rng)
        assert res["event"]["kind"] == "piraci"
        # 100-40 fare = 60; danina = max(10, 20% z 60) = 12 → 48
        assert res["event"]["gold_loss"] == 12
        assert res["gold"] == 48

    def test_reef_never_kills(self, patched):
        conn = _make_db()
        conn.execute("UPDATE characters SET sheet_json=? WHERE id=999",
                     (json.dumps({"current_hp": 2, "max_hp": 20}),))
        conn.commit()
        rng = _StubRng(random_values=[0.01], choice_pick="rafa", randint_val=6)
        res = svc.execute_sea_voyage(conn, 1, 999, "czarnogrod_zatoka", rng=rng)
        assert res["event"]["kind"] == "rafa"
        assert _hp(conn) == 1  # min 1

    def test_not_in_port_rejected(self, patched):
        conn = _make_db()
        conn.execute("UPDATE game_sessions SET current_location_id=NULL WHERE campaign_id=1")
        conn.commit()
        with pytest.raises(svc.VoyageError) as e:
            svc.execute_sea_voyage(conn, 1, 999, "czarnogrod_zatoka", rng=_StubRng([0.99]))
        assert e.value.code == "not_in_port"


class _StubRng:
    """Deterministyczny RNG: kolejne random(), stały wybór choices(), stały randint()."""
    def __init__(self, random_values, choice_pick=None, randint_val=1):
        self._vals = list(random_values)
        self._choice_pick = choice_pick
        self._randint_val = randint_val

    def random(self):
        return self._vals.pop(0) if self._vals else 0.99

    def choices(self, population, weights=None, k=1):
        if self._choice_pick is not None:
            return [self._choice_pick]
        return [population[0]]

    def randint(self, a, b):
        return min(self._randint_val, b)
