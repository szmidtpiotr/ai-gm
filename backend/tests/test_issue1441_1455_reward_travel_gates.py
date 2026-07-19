"""Krok 7 AUDIT — blokada farmienia nagród + luk w podróżach (batch 1, P1).

Pokrywa 5 issue (dungeon / rest / travel-gate):

#1441 — loch: re-entry bez /exit stempluje cooldown (fraction=0.5); skrzynia
        otwierana tylko raz (_action_open_chest early-return na chest_state.opened).
#1442 — jeden long rest / dzień gry (fatigue_last_rest_day vs day).
#1443 — execute_travel + enter lochu: bramka śmierci / aktywnej walki / turn_lock.
#1454 — local-travel: obcy sub-hex odrzucony (400); /world-map wymaga odkrytego
        rodzica; advance_clock z conn=conn.
#1455 — świeży /travel z wiszącą zasadzką → 409; build_camp 409 przy zasadzce;
        combat_seen PO initiate_combat; ford na resume; camp_encounter → walka;
        12h hard-cap pre-check.
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if "httpx" not in sys.modules:
    sys.modules["httpx"] = MagicMock()

from fastapi import HTTPException  # noqa: E402

from app.services import dungeon_service as ds  # noqa: E402
from app.services import dungeon_tile_service as dts  # noqa: E402
from app.services import combat_service as cs  # noqa: E402
from app.services import hex_travel_service as hts  # noqa: E402
from app.services import rest_service as rs  # noqa: E402
from app.services import clock_service as clk  # noqa: E402
from app.services import turn_lock  # noqa: E402
from app.routers import local_map as lm  # noqa: E402


# ───────────────────────────── schema helpers ─────────────────────────────

_CORE_SQL = """
CREATE TABLE characters (
  id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, user_id INTEGER,
  name TEXT, status TEXT DEFAULT 'active', sheet_json TEXT
);
CREATE TABLE game_sessions (
  id TEXT PRIMARY KEY, campaign_id INTEGER, current_location_id INTEGER,
  session_flags TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE world_hexes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, q INTEGER, r INTEGER,
  hex_type TEXT DEFAULT 'plains', label TEXT, atmosphere TEXT,
  location_key TEXT, is_active INTEGER DEFAULT 1,
  parent_hex_id INTEGER, map_level INTEGER DEFAULT 0
);
CREATE TABLE game_locations (
  id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, label TEXT,
  parent_id INTEGER, parent_key TEXT, location_type TEXT DEFAULT 'macro',
  is_active INTEGER DEFAULT 1, safe_for_rest INTEGER DEFAULT 0
);
CREATE TABLE game_dungeons (
  id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, label TEXT,
  cooldown_hours INTEGER DEFAULT 6, is_active INTEGER DEFAULT 1
);
CREATE TABLE character_dungeon_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, location_key TEXT,
  cleared_at TEXT, cooldown_until TEXT, run_count INTEGER DEFAULT 0,
  UNIQUE(character_id, location_key)
);
"""


def _fresh_db(name: str) -> Path:
    tmp = Path("/tmp") / name
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(tmp))
    conn.executescript(_CORE_SQL)
    conn.close()
    return tmp


def _seed_char(tmp: Path, *, hp=20, status="active", campaign_id=1, cid=1):
    conn = sqlite3.connect(str(tmp))
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name, status, sheet_json) VALUES (?,?,1,'H',?,?)",
        (cid, campaign_id, status, json.dumps({"current_hp": hp, "max_hp": 20, "current_mana": 0, "max_mana": 0})),
    )
    conn.commit()
    conn.close()


def _seed_session(tmp: Path, flags: dict, *, campaign_id=1, current_location_id=None):
    conn = sqlite3.connect(str(tmp))
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, current_location_id, session_flags) VALUES (?,?,?,?)",
        (f"s{campaign_id}", campaign_id, current_location_id, json.dumps(flags)),
    )
    conn.commit()
    conn.close()


def _patch_all_db(monkeypatch, tmp):
    p = str(tmp)
    monkeypatch.setattr(ds, "DB_PATH", p)
    monkeypatch.setattr(hts, "DB_PATH", p)
    monkeypatch.setattr(cs, "COMBAT_DB_PATH", p)
    monkeypatch.setattr(clk, "DB_PATH", Path(p))
    monkeypatch.setattr(lm, "DB_PATH", p)


# ═══════════════════════════ #1441 — dungeon farming ═══════════════════════════

def test_chest_open_once(monkeypatch):
    """Skrzynia grantuje łup RAZ. Drugie 'open_chest' na tym samym kafelku → loot=[]
    (bez re-rolla), nawet gdy rzut > DC."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    monkeypatch.setattr(dts, "_get_char_dex_modifier", lambda *a, **k: 0)
    monkeypatch.setattr(dts, "_roll_chest_loot_for_run", lambda *a, **k: [{"item_key": "gem"}])
    monkeypatch.setattr(dts.random, "randint", lambda *a, **k: 20)  # gwarantowany sukces

    node = {"chest_state": {}}
    run = {"dungeon_key": "crypt"}
    first = dts._action_open_chest(conn, node, {}, 1, 1, run)
    assert first["success"] is True
    assert first["loot"] == [{"item_key": "gem"}]
    assert node["chest_state"]["opened"] is True

    second = dts._action_open_chest(conn, node, {}, 1, 1, run)
    assert second.get("chest_already_opened") is True
    assert second["loot"] == []
    conn.close()


def test_dungeon_reenter_without_exit_sets_cooldown(monkeypatch):
    """Re-entry bez /exit: porzucony run stempluje cooldown (fraction=0.5), więc
    check_cooldown blokuje kolejne wejście do TEGO SAMEGO lochu."""
    tmp = _fresh_db("_k7_1441_reenter.db")
    monkeypatch.setattr(ds, "DB_PATH", str(tmp))
    conn = sqlite3.connect(str(tmp))
    conn.execute("INSERT INTO game_dungeons (key, label, cooldown_hours, is_active) VALUES ('crypt','Krypta',6,1)")
    conn.commit()
    conn.close()

    # brak cooldownu na starcie
    assert ds.check_cooldown(1, "crypt")["on_cooldown"] is False
    # porzucony run → guard woła start_dungeon_cooldown(fraction=0.5)
    res = ds.start_dungeon_cooldown(1, "crypt", fraction=0.5)
    assert res["cooldown_hours"] == 3.0
    # teraz wejście do tego samego lochu jest zablokowane
    assert ds.check_cooldown(1, "crypt")["on_cooldown"] is True

    # guard wpięty w enter_dungeon_tiles
    src = Path(dts.__file__).read_text()
    assert "start_dungeon_cooldown" in src
    assert 'not _existing_run.get("completed")' in src


# ═══════════════════════════ #1442 — long rest daily cap ═══════════════════════

def test_long_rest_once_per_game_day(monkeypatch):
    """Drugi long rest tego samego dnia gry → odmowa (already_rested_today)."""
    tmp = _fresh_db("_k7_1442_rest.db")
    _seed_char(tmp)
    # ingame_hours=10 → dzień 1; fatigue_last_rest_day już = 1 (symulacja pierwszego odpoczynku)
    _seed_session(tmp, {"ingame_hours": 10, "fatigue_last_rest_day": 1})
    monkeypatch.setattr(clk, "DB_PATH", Path(str(tmp)))
    monkeypatch.setattr(rs, "_has_active_combat", lambda *a, **k: False)
    monkeypatch.setattr(rs, "_is_safe_for_character", lambda *a, **k: True)

    conn = sqlite3.connect(str(tmp))
    conn.row_factory = sqlite3.Row
    out = rs.perform_long_rest(conn, 1, 1)
    conn.close()
    assert out["ok"] is False
    assert out["error"] == "already_rested_today"
    assert out["rest_day"] == 1


# ═══════════════════════════ #1443 — travel gates ═════════════════════════════

def test_travel_blocked_when_dead(monkeypatch):
    tmp = _fresh_db("_k7_1443_dead.db")
    _seed_char(tmp, hp=0, status="dead")
    _seed_session(tmp, {"ingame_hours": 10, "current_hex": {"q": 0, "r": 0}})
    _patch_all_db(monkeypatch, tmp)
    monkeypatch.setattr(cs, "get_active_combat", lambda *a, **k: None)

    conn = sqlite3.connect(str(tmp))
    conn.row_factory = sqlite3.Row
    with pytest.raises(hts.TravelError) as ei:
        hts.execute_travel(conn, 1, {"hex": {"q": 1, "r": 0}}, actor=1)
    conn.close()
    assert ei.value.code == "dead"


def test_travel_blocked_in_combat(monkeypatch):
    tmp = _fresh_db("_k7_1443_combat.db")
    _seed_char(tmp, hp=20, status="active")
    _seed_session(tmp, {"ingame_hours": 10, "current_hex": {"q": 0, "r": 0}})
    _patch_all_db(monkeypatch, tmp)
    monkeypatch.setattr(cs, "get_active_combat", lambda *a, **k: {"id": 1})

    conn = sqlite3.connect(str(tmp))
    conn.row_factory = sqlite3.Row
    with pytest.raises(hts.TravelError) as ei:
        hts.execute_travel(conn, 1, {"hex": {"q": 1, "r": 0}}, actor=1)
    conn.close()
    assert ei.value.code == "in_combat"


def test_travel_409_when_turn_in_flight():
    """Endpointy podróży serializowane turn_lockiem — trzymany lock → 409."""
    turn_lock._reset_for_tests()
    key = turn_lock.acquire(1)
    try:
        with pytest.raises(HTTPException) as ei:
            turn_lock.acquire_or_409(1)
        assert ei.value.status_code == 409
    finally:
        turn_lock.release(key)

    import inspect
    from app.api import turns as _t
    src = inspect.getsource(_t.player_travel) + inspect.getsource(_t.player_hex_travel)
    assert src.count("turn_lock.acquire_or_409(campaign_id)") == 2
    assert src.count("turn_lock.release(_lock_key)") == 2


# ═══════════════════════════ #1454 — local travel / FOW ═══════════════════════

def test_local_travel_foreign_hex_rejected(monkeypatch):
    """Sub-hex należący do INNEGO huba → 400 (koniec teleportu rest-anywhere)."""
    tmp = _fresh_db("_k7_1454_local.db")
    conn = sqlite3.connect(str(tmp))
    # hub A = hex 1, hub B = hex 2 (map_level 0); sub-hexy map_level 1
    conn.execute("INSERT INTO world_hexes (id,q,r,map_level,parent_hex_id) VALUES (1,0,0,0,NULL)")
    conn.execute("INSERT INTO world_hexes (id,q,r,map_level,parent_hex_id) VALUES (2,5,5,0,NULL)")
    conn.execute("INSERT INTO world_hexes (id,q,r,map_level,parent_hex_id,is_active) VALUES (10,0,1,1,1,1)")  # sub huba A
    conn.execute("INSERT INTO world_hexes (id,q,r,map_level,parent_hex_id,is_active) VALUES (20,5,6,1,2,1)")  # sub huba B
    conn.commit()
    conn.close()
    # party stoi w hubie A (local_hex = sub-hex 10, parent 1); brak current_location_id
    _seed_session(tmp, {"local_hex": {"hex_id": 10}})
    monkeypatch.setattr(lm, "DB_PATH", str(tmp))

    with pytest.raises(HTTPException) as ei:
        lm.local_travel(1, lm.LocalTravelRequest(hex_id=20))
    assert ei.value.status_code == 400


def test_world_map_requires_discovered_parent():
    """/world-map submap bramkowany FOW — rodzic musi być odkryty/bieżący."""
    import inspect
    from app.api import turns as _t
    src = inspect.getsource(_t.get_campaign_world_map)
    assert "campaign_hex_data" in src and "discovered=1" in src
    assert "Ten rejon nie został jeszcze odkryty" in src
    assert "status_code=403" in src


def test_local_travel_advances_clock_shared_conn():
    """advance_clock wołany z conn=conn (nested-conn #1390) — inaczej cichy brak +15 min."""
    import inspect
    src = inspect.getsource(lm.local_travel)
    assert 'reason="local_travel", conn=conn' in src


# ═══════════════════════════ #1455 — encounter dodge cluster ═══════════════════

def test_fresh_travel_blocks_pending_encounter(monkeypatch):
    tmp = _fresh_db("_k7_1455_pending.db")
    _seed_char(tmp, hp=20, status="active")
    _seed_session(tmp, {
        "ingame_hours": 10, "current_hex": {"q": 0, "r": 0},
        "travel_plan": {"interrupt_reason": "encounter", "enemy_key": "wolf"},
    })
    _patch_all_db(monkeypatch, tmp)
    monkeypatch.setattr(cs, "get_active_combat", lambda *a, **k: None)

    conn = sqlite3.connect(str(tmp))
    conn.row_factory = sqlite3.Row
    with pytest.raises(hts.TravelError) as ei:
        hts.execute_travel(conn, 1, {"hex": {"q": 1, "r": 0}}, actor=1)
    conn.close()
    assert ei.value.code == "pending_encounter"


def test_march_hard_cap_blocks_fresh_travel(monkeypatch):
    tmp = _fresh_db("_k7_1455_march.db")
    _seed_char(tmp, hp=20, status="active")
    _seed_session(tmp, {
        "ingame_hours": 10, "current_hex": {"q": 0, "r": 0},
        "march_day": 1, "hours_marched_today": 13.0, "night_march": False,
    })
    _patch_all_db(monkeypatch, tmp)
    monkeypatch.setattr(cs, "get_active_combat", lambda *a, **k: None)

    conn = sqlite3.connect(str(tmp))
    conn.row_factory = sqlite3.Row
    with pytest.raises(hts.TravelError) as ei:
        hts.execute_travel(conn, 1, {"hex": {"q": 1, "r": 0}}, actor=1)
    conn.close()
    assert ei.value.code == "forced_camp"


def test_build_camp_blocked_during_ambush(monkeypatch):
    """Rozbicie obozu przy niepokonanej zasadzce → 409."""
    tmp = _fresh_db("_k7_1455_camp.db")
    _seed_session(tmp, {
        "current_hex": {"q": 0, "r": 0},
        "travel_plan": {"interrupt_reason": "encounter", "enemy_key": "wolf"},
    })
    from app.api import campaigns as _c
    monkeypatch.setattr(_c, "DB_PATH", str(tmp))
    monkeypatch.setattr(cs, "get_active_combat", lambda *a, **k: None)

    with pytest.raises(HTTPException) as ei:
        _c.build_camp(1)
    assert ei.value.status_code == 409


def test_combat_seen_after_initiate():
    """travel_resume: initiate_combat PRZED stemplem combat_seen (nieudany spawn nie
    oznacza 'walka odbyta')."""
    import inspect
    from app.api import campaigns as _c
    src = inspect.getsource(_c.travel_resume)
    i_init = src.index("initiate_combat(campaign_id, int(char")
    i_seen = src.index('tp["combat_seen"] = True')
    assert i_init < i_seen


def test_ford_hazard_on_resume():
    import inspect
    from app.api import campaigns as _c
    src = inspect.getsource(_c.travel_resume)
    assert "maybe_ford_hazard" in src


def test_camp_encounter_starts_combat():
    import inspect
    src = inspect.getsource(rs.perform_long_rest)
    assert "initiate_combat" in src
    assert '"combat_started"' in src
