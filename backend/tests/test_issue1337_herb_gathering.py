"""#1337 BL-C2 — zbieranie ziół w podróży.

Testy jednostkowe herb_gathering_service: wykrycie intencji, DC wg terenu,
cooldown per hex/dzień, oraz rozstrzygnięcie sukces / porażka / Nat20 / Nat1.
"""
import json
import sqlite3

import pytest

from app.services import herb_gathering_service as herb


# ── DB fixture — minimalny schemat pod service ─────────────────────────────────
def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT);
        CREATE TABLE world_hexes (q INTEGER, r INTEGER, hex_type TEXT, map_level INTEGER);
        CREATE TABLE game_config_items (key TEXT, component_type TEXT, rarity INTEGER, is_active INTEGER DEFAULT 1);
        CREATE TABLE game_items (key TEXT, is_active INTEGER DEFAULT 1);
        CREATE TABLE characters (id INTEGER, sheet_json TEXT);
        """
    )
    return conn


def _seed_session(conn, campaign_id=1, hex_q=0, hex_r=0, ingame_hours=30, flags=None):
    sf = flags or {}
    sf.setdefault("current_hex", {"q": hex_q, "r": hex_r})
    sf.setdefault("ingame_hours", ingame_hours)
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?,?)",
        (campaign_id, json.dumps(sf)),
    )
    conn.commit()


def _seed_hex(conn, q, r, hex_type, map_level=0):
    conn.execute(
        "INSERT INTO world_hexes (q,r,hex_type,map_level) VALUES (?,?,?,?)",
        (q, r, hex_type, map_level),
    )
    conn.commit()


def _seed_herbs(conn, with_rare=False):
    conn.execute("INSERT INTO game_config_items VALUES ('healing_herb','herb',1,1)")
    conn.execute("INSERT INTO game_config_items VALUES ('korzen_zmornika','herb',1,1)")
    conn.execute("INSERT INTO game_items VALUES ('healing_herb',1)")
    conn.execute("INSERT INTO game_items VALUES ('korzen_zmornika',1)")
    if with_rare:
        conn.execute("INSERT INTO game_config_items VALUES ('kwiat_swiatla','herb',3,1)")
        conn.execute("INSERT INTO game_items VALUES ('kwiat_swiatla',1)")
    conn.commit()


# ── is_gather_intent ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "zbieram zioła z poszycia",
    "Zrywam zioła nad strumieniem",
    "szukam ziół leczniczych",
    "zbieram rośliny na skraju lasu",
    "nazbierać grzybów",
])
def test_intent_positive(text):
    assert herb.is_gather_intent(text) is True


@pytest.mark.parametrize("text", [
    "atakuję wilka",
    "zioła leżą w mojej torbie",   # obiekt bez czasownika
    "biegnę przez las",            # czasownik-ruch, brak obiektu zielnego
    "",
])
def test_intent_negative(text):
    assert herb.is_gather_intent(text) is False


# ── DC wg terenu ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("terrain,expected", [
    ("forest", 8), ("swamp", 8),
    ("plains", 12), ("hills", 12), ("heath", 12),
    ("mountain", 16), ("ruins", 16),
])
def test_terrain_dc(terrain, expected):
    conn = _make_db()
    _seed_session(conn, hex_q=2, hex_r=3)
    _seed_hex(conn, 2, 3, terrain)
    plan = herb.prepare_gather(conn, 1)
    assert plan["cooldown_hit"] is False
    assert plan["dc"] == expected
    assert plan["hex_key"] == "2,3"


def test_terrain_unknown_defaults_medium():
    conn = _make_db()
    _seed_session(conn, hex_q=9, hex_r=9)  # brak hexa w world_hexes
    plan = herb.prepare_gather(conn, 1)
    assert plan["dc"] == herb.DEFAULT_DC == 12


# ── cooldown per hex/dzień ─────────────────────────────────────────────────────
def test_cooldown_hit_same_day():
    conn = _make_db()
    # ingame_hours=30 → dzień 1; cooldown już ustawiony na dzień 1 dla hexa 0,0
    _seed_session(conn, ingame_hours=30, flags={"herb_cooldowns": {"0,0": 1}})
    _seed_hex(conn, 0, 0, "forest")
    plan = herb.prepare_gather(conn, 1)
    assert plan["cooldown_hit"] is True
    assert "ogołocone" in plan["msg"]


def test_cooldown_clears_next_day():
    conn = _make_db()
    # ingame_hours=54 → dzień 2; cooldown z dnia 1 nie blokuje
    _seed_session(conn, ingame_hours=54, flags={"herb_cooldowns": {"0,0": 1}})
    _seed_hex(conn, 0, 0, "forest")
    plan = herb.prepare_gather(conn, 1)
    assert plan["cooldown_hit"] is False
    assert plan["dc"] == 8


# ── rozstrzygnięcie ────────────────────────────────────────────────────────────
def _pending(hex_key="0,0", game_day=1):
    return {"source": "herb_gathering", "hex_key": hex_key, "game_day": game_day}


def _patch_grant(monkeypatch):
    captured = {}

    def _fake_grant(character_id, grant, source="loot"):
        captured["grant"] = grant
        captured["source"] = source
        return grant

    monkeypatch.setattr(
        "app.services.loot_service.grant_loot_to_character", _fake_grant
    )
    return captured


@pytest.mark.parametrize("margin,expected_count", [(0, 1), (4, 1), (5, 2), (9, 2), (10, 3), (25, 3)])
def test_success_herb_count_by_margin(monkeypatch, margin, expected_count):
    conn = _make_db()
    _seed_session(conn)
    _seed_herbs(conn)
    cap = _patch_grant(monkeypatch)
    sf = {}
    result = {"success": True, "nat20": False, "nat1": False, "margin": margin}
    summary = herb.resolve_gather(conn, 1, 100, _pending(), result, sf)
    assert summary["outcome"] == "success"
    total = sum(int(g["quantity"]) for g in cap["grant"])
    assert total == expected_count
    # cooldown ustawiony
    assert sf["herb_cooldowns"]["0,0"] == 1


def test_nat20_grants_rare(monkeypatch):
    conn = _make_db()
    _seed_session(conn)
    _seed_herbs(conn, with_rare=True)
    cap = _patch_grant(monkeypatch)
    sf = {}
    result = {"success": True, "nat20": True, "nat1": False, "margin": 12}
    summary = herb.resolve_gather(conn, 1, 100, _pending(), result, sf)
    assert summary["outcome"] == "nat20"
    assert summary["rare"] == "kwiat_swiatla"
    keys = {g["item_key"] for g in cap["grant"]}
    assert "kwiat_swiatla" in keys


def test_nat1_poison_damage(monkeypatch):
    conn = _make_db()
    _seed_session(conn)
    _seed_herbs(conn)
    conn.execute(
        "INSERT INTO characters (id, sheet_json) VALUES (100, ?)",
        (json.dumps({"current_hp": 10, "max_hp": 10}),),
    )
    conn.commit()
    _patch_grant(monkeypatch)
    sf = {}
    result = {"success": False, "nat20": False, "nat1": True, "margin": -5}
    summary = herb.resolve_gather(conn, 1, 100, _pending(), result, sf)
    assert summary["outcome"] == "nat1"
    assert summary["damage"] == 1
    assert summary["herbs"] == []
    hp = json.loads(conn.execute("SELECT sheet_json FROM characters WHERE id=100").fetchone()[0])["current_hp"]
    assert hp == 9
    assert sf["herb_cooldowns"]["0,0"] == 1  # cooldown mimo porażki


def test_plain_failure_no_herbs(monkeypatch):
    conn = _make_db()
    _seed_session(conn)
    _seed_herbs(conn)
    _patch_grant(monkeypatch)
    sf = {}
    result = {"success": False, "nat20": False, "nat1": False, "margin": -3}
    summary = herb.resolve_gather(conn, 1, 100, _pending(), result, sf)
    assert summary["outcome"] == "fail"
    assert summary["herbs"] == []
    assert sf["herb_cooldowns"]["0,0"] == 1  # ogołocone po nieudanej próbie
