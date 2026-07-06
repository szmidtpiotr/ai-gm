"""TDD: PM4 #1223 — route mode (direct vs road) for long descriptive travel.

When the hero heads for a KNOWN destination >2 hexes away AND a trakt runs near
the direct path, the narrator FIRST asks: prosto przez dzicz czy traktem? The
player's answer picks a route profile:

  * "direct" — shortest terrain path, full terrain cost, full encounter chance.
  * "road"   — A* biased onto `road` hexes (ROAD_COST_MULT cheaper/faster per hex)
               with half the encounter chance while on a road (ROAD_ENCOUNTER_MULT).

The chosen mode is stashed in `travel_plan` so an interrupted trip resumes in the
same mode. Short trips (≤2 hexes) or no nearby road → travel immediately, no ask.

Map: (0,0) start. Forest arm east → Vilnograd (4,0). Parallel road arm one row
below (r=-1). Short town Bród at (0,2), dist 2.
"""
import sys
import json
import sqlite3

import pytest

sys.path.insert(0, "/app")

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER NOT NULL,
    r INTEGER NOT NULL,
    hex_type TEXT NOT NULL DEFAULT 'plains',
    label TEXT,
    atmosphere TEXT,
    encounter_chance REAL NOT NULL DEFAULT 0.0,
    encounter_pool TEXT NOT NULL DEFAULT '[]',
    location_key TEXT,
    region TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    map_level INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL,
    description TEXT DEFAULT '',
    parent_id INTEGER,
    parent_key TEXT DEFAULT NULL,
    location_type TEXT DEFAULT 'macro',
    is_active INTEGER NOT NULL DEFAULT 1,
    canonical INTEGER NOT NULL DEFAULT 0,
    safe_for_rest INTEGER NOT NULL DEFAULT 0,
    temporary INTEGER NOT NULL DEFAULT 0,
    review_status TEXT NOT NULL DEFAULT 'permanent',
    created_by TEXT DEFAULT 'seed',
    ai_generated INTEGER NOT NULL DEFAULT 0,
    usage_count INTEGER NOT NULL DEFAULT 0,
    world_hex_q INTEGER,
    world_hex_r INTEGER
);
CREATE TABLE IF NOT EXISTS hex_type_config (
    hex_type TEXT PRIMARY KEY,
    label TEXT,
    travel_hours REAL NOT NULL DEFAULT 1.0,
    encounter_chance REAL NOT NULL DEFAULT 0.0,
    is_passable INTEGER NOT NULL DEFAULT 1,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS hex_teleport_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_q INTEGER NOT NULL, from_r INTEGER NOT NULL,
    to_q INTEGER NOT NULL, to_r INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_bidirectional INTEGER NOT NULL DEFAULT 1,
    travel_hours REAL DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS game_sessions (
    id TEXT PRIMARY KEY,
    campaign_id INTEGER,
    current_location_id INTEGER,
    session_flags TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS campaign_hex_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    hex_q INTEGER NOT NULL,
    hex_r INTEGER NOT NULL,
    discovered INTEGER NOT NULL DEFAULT 0,
    known INTEGER NOT NULL DEFAULT 0,
    encounter_cleared INTEGER NOT NULL DEFAULT 0,
    UNIQUE(campaign_id, hex_q, hex_r)
);
CREATE TABLE IF NOT EXISTS world_regions (
    key TEXT PRIMARY KEY,
    label TEXT,
    status TEXT DEFAULT 'live'
);
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER,
    status TEXT NOT NULL DEFAULT 'active',
    sheet_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS campaign_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER,
    character_id INTEGER,
    user_text TEXT,
    route TEXT,
    assistant_text TEXT,
    turn_number INTEGER
);
CREATE TABLE IF NOT EXISTS game_config_meta (
    key TEXT PRIMARY KEY, value TEXT
);
"""


@pytest.fixture(autouse=True)
def _no_encounters(monkeypatch):
    # encounter_chance 0.0 → 0.15 via `or 0.15`; force random miss for determinism.
    import app.services.hex_travel_service as _h
    monkeypatch.setattr(_h.random, "random", lambda: 1.0)


def _seed_common(c):
    c.execute("INSERT INTO world_regions (key, label, status) VALUES ('kresy','Kresy','live')")

    def hx(q, r, ht="plains", label=None, key=None, enc=0.0):
        c.execute(
            "INSERT INTO world_hexes (q, r, hex_type, label, location_key, region, encounter_chance,"
            " is_active, map_level) VALUES (?,?,?,?,?, 'kresy', ?, 1, 0)",
            (q, r, ht, label, key, enc),
        )

    # tuned so the FOREST arm wins in direct mode but the ROAD arm wins in road mode:
    #   forest 1.2, road 1.0 full → 0.75 discounted, town 1.0.
    for ht, lab, th in [
        ("plains", "Równina", 1.0), ("forest", "Las", 1.2), ("road", "Droga", 1.0),
        ("town", "Miasto", 1.0), ("bridge", "Most", 1.0), ("village", "Wioska", 1.0),
    ]:
        c.execute(
            "INSERT INTO hex_type_config (hex_type, label, travel_hours, encounter_chance,"
            " is_passable, is_active) VALUES (?,?,?, 0.0, 1, 1)",
            (ht, lab, th),
        )

    c.execute("INSERT INTO characters (id, campaign_id, sheet_json) VALUES (1, 1, '{}')")
    return hx


@pytest.fixture
def conn():
    """Two-arm world: forest line vs parallel road detour to Vilnograd (4,0)."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    hx = _seed_common(c)

    hx(0, 0, "plains", "Rozstaje")
    # forest arm (direct)
    hx(1, 0, "forest", "Las I")
    hx(2, 0, "forest", "Las II")
    hx(3, 0, "forest", "Las III")
    hx(4, 0, "town", "Vilnograd", key="vilnograd")
    # road arm (trakt), one row below — encounter high (harmless with random=1.0)
    hx(1, -1, "road", "Trakt I", enc=0.9)
    hx(2, -1, "road", "Trakt II", enc=0.9)
    hx(3, -1, "road", "Trakt III", enc=0.9)
    hx(4, -1, "road", "Trakt IV", enc=0.9)
    # short-trip town Bród, dist 2 from start
    hx(0, 1, "plains", "Ścieżka")
    hx(0, 2, "town", "Bród", key="brod")

    c.execute(
        "INSERT INTO game_locations (key, label, canonical, is_active, world_hex_q, world_hex_r)"
        " VALUES ('vilnograd', 'Vilnograd', 1, 1, 4, 0), ('brod', 'Bród', 1, 1, 0, 2)"
    )
    c.execute(
        "INSERT INTO game_sessions (id, campaign_id, current_location_id, session_flags)"
        " VALUES ('s1', 1, NULL, ?)",
        (json.dumps({"current_hex": {"q": 0, "r": 0}, "known_regions": ["kresy"]}),),
    )
    # hero knows Vilnograd, Bród and both arm heads (discovered)
    for q, r in [(4, 0), (0, 2), (1, 0), (1, -1)]:
        c.execute(
            "INSERT INTO campaign_hex_data (campaign_id, hex_q, hex_r, discovered) VALUES (1, ?, ?, 1)",
            (q, r),
        )
    c.commit()
    return c


def _run(conn, text):
    from app.services.turn_pipeline import execute_directional_travel
    return execute_directional_travel(
        conn=conn, campaign_id=1, character_id=1, character_sheet={}, player_text=text,
    )


def _flags(conn):
    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    return json.loads(row["session_flags"] or "{}")


def _current_hex(conn):
    return _flags(conn).get("current_hex")


def _has_road(path):
    return any((p["q"], p["r"]) == (q, -1) for p in path for q in (1, 2, 3, 4))


# ── detect_route_choice unit ──────────────────────────────────────────────────

def test_detect_route_choice():
    from app.services.hex_travel_service import detect_route_choice
    assert detect_route_choice("idę traktem") == "road"
    assert detect_route_choice("podążam drogą") == "road"
    assert detect_route_choice("prosto przez las") == "direct"
    assert detect_route_choice("na przełaj") == "direct"
    assert detect_route_choice("nie wiem") is None
    assert detect_route_choice("") is None


# ── A* profile: road mode picks the trakt, direct picks the forest ────────────

def test_find_path_direct_avoids_road(conn):
    from app.services.hex_travel_service import (
        find_path, _load_hex_graph, _load_hex_type_config,
    )
    hexes, cfg = _load_hex_graph(conn), _load_hex_type_config(conn)
    p = find_path((0, 0), (4, 0), hexes, cfg, route_mode="direct")
    coords = [(q, r) for q, r in p]
    assert coords == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]  # forest line
    assert not any(r == -1 for _, r in coords)


def test_find_path_road_mode_uses_road(conn):
    from app.services.hex_travel_service import (
        find_path, _load_hex_graph, _load_hex_type_config,
    )
    hexes, cfg = _load_hex_graph(conn), _load_hex_type_config(conn)
    p = find_path((0, 0), (4, 0), hexes, cfg, route_mode="road")
    coords = [(q, r) for q, r in p]
    assert any(r == -1 for _, r in coords), coords  # went onto the trakt


# ── total_hours differs between modes ─────────────────────────────────────────

def test_costs_differ_between_modes(conn):
    from app.services.hex_travel_service import resolve_chain_travel
    direct = resolve_chain_travel(1, 1, (0, 0), (4, 0), {}, conn, route_mode="direct")
    # reset position for a clean second run
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({"current_hex": {"q": 0, "r": 0}, "known_regions": ["kresy"]}),),
    )
    conn.commit()
    road = resolve_chain_travel(1, 1, (0, 0), (4, 0), {}, conn, route_mode="road")
    assert direct["ok"] and road["ok"]
    assert not _has_road(direct["path"])
    assert _has_road(road["path"])
    # road hexes are faster per hex (×0.75), so this detour is quicker here
    assert road["total_hours"] != direct["total_hours"]


# ── encounter halved on road hexes in road mode ───────────────────────────────

def test_roll_encounter_chance_mult():
    from app.services.hex_travel_service import _roll_encounter
    import app.services.hex_travel_service as _h
    hexd = {"hex_type": "road", "encounter_chance": 0.4}
    cfg = {"road": {}}
    # random fixed at 0.3: full chance 0.4 fires; halved 0.2 does not.
    _orig = _h.random.random
    try:
        _h.random.random = lambda: 0.3
        assert _roll_encounter(hexd, cfg, chance_mult=1.0) is True
        assert _roll_encounter(hexd, cfg, chance_mult=0.5) is False
    finally:
        _h.random.random = _orig


def test_road_mode_halves_encounter_integration(monkeypatch):
    """On a road-only path, direct mode triggers an encounter that road mode dodges."""
    import app.services.hex_travel_service as _h
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    hx = _seed_common(c)
    hx(0, 0, "plains", "Start")
    hx(1, 0, "road", "Trakt", enc=0.4)
    hx(2, 0, "road", "Trakt", enc=0.4)
    hx(3, 0, "town", "Gród", key="grod")
    c.execute(
        "INSERT INTO game_sessions (id, campaign_id, current_location_id, session_flags)"
        " VALUES ('s1', 1, NULL, ?)",
        (json.dumps({"current_hex": {"q": 0, "r": 0}}),),
    )
    c.commit()
    monkeypatch.setattr(_h.random, "random", lambda: 0.3)  # 0.4 fires, 0.2 misses

    direct = _h.resolve_chain_travel(1, 1, (0, 0), (3, 0), {}, c, route_mode="direct")
    c.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=1",
        (json.dumps({"current_hex": {"q": 0, "r": 0}}),),
    )
    c.commit()
    road = _h.resolve_chain_travel(1, 1, (0, 0), (3, 0), {}, c, route_mode="road")

    assert direct["encounter"] is not None      # direct hit a bandit on the road
    assert road["encounter"] is None            # road mode halved it away
    assert (road["arrived_hex"]["q"], road["arrived_hex"]["r"]) == (3, 0)


# ── flow: question → choice → move ────────────────────────────────────────────

def test_long_trip_asks_before_moving(conn):
    res = _run(conn, "udaję się do Vilnogradu")
    assert res["executed"] is False, res
    assert "traktem" in (res["system_fact"] or "")
    assert _current_hex(conn) == {"q": 0, "r": 0}          # did NOT move
    assert _flags(conn).get("pending_travel_choice") is not None


def test_choice_road_travels_via_trakt(conn):
    _run(conn, "udaję się do Vilnogradu")                  # arms the question
    res = _run(conn, "idę traktem")
    assert res["executed"] is True, res
    assert _current_hex(conn) == {"q": 4, "r": 0}          # reached Vilnograd
    assert "traktem" in (res["system_fact"] or "")         # narrated as the trakt route
    assert _flags(conn).get("pending_travel_choice") is None  # cleared


def test_choice_direct_travels_via_wilds(conn):
    _run(conn, "udaję się do Vilnogradu")
    res = _run(conn, "prosto na przełaj")
    assert res["executed"] is True, res
    assert _current_hex(conn) == {"q": 4, "r": 0}
    assert _flags(conn).get("pending_travel_choice") is None


def test_unclear_answer_rehints_once_then_defaults(conn):
    _run(conn, "udaję się do Vilnogradu")
    # 1st unclear → re-hint, still standing
    r1 = _run(conn, "hmm nie wiem")
    assert r1["executed"] is False
    assert _flags(conn)["pending_travel_choice"]["hinted"] == 1
    assert _current_hex(conn) == {"q": 0, "r": 0}
    # 2nd unclear → default direct, move happens, pending cleared
    r2 = _run(conn, "eee")
    assert r2["executed"] is True, r2
    assert _current_hex(conn) == {"q": 4, "r": 0}
    assert _flags(conn).get("pending_travel_choice") is None


# ── short trips never ask ─────────────────────────────────────────────────────

def test_short_trip_no_question(conn):
    res = _run(conn, "idę do Brodu")
    assert res["executed"] is True, res
    assert _current_hex(conn) == {"q": 0, "r": 2}
    assert _flags(conn).get("pending_travel_choice") is None


# ── travel_plan persists route_mode (resume keeps the mode) ───────────────────

def test_travel_plan_stores_route_mode(conn, monkeypatch):
    import app.services.hex_travel_service as _h
    # fire an encounter on the first road hex so the trip is interrupted mid-way
    monkeypatch.setattr(_h.random, "random", lambda: 0.2)  # 0.9×0.5=0.45 > 0.2 → fires
    res = _h.resolve_chain_travel(1, 1, (0, 0), (4, 0), {}, conn, route_mode="road")
    assert res["encounter"] is not None, res
    tp = _flags(conn).get("travel_plan")
    assert tp is not None
    assert tp.get("route_mode") == "road"
    assert tp.get("interrupt_reason") == "encounter"


# ── #1256: narrative-path travel also offers the direct/road choice ───────────
# When the intent classifier tags a travel phrase ("udaję się do X") as
# explore/other, the turn goes down the LLM → R5 _run_narrative_travel path,
# which historically executed the trip immediately and skipped PM4. The fix
# re-runs _pm4_maybe_prompt there so the question fires regardless of routing.

def _narr_travel(conn, location_key, label="Vilnograd"):
    from app.api.turns import _run_narrative_travel
    clean = json.dumps(
        {"narrative": "placeholder", "location_intent": {"action": "move"}},
        ensure_ascii=False,
    )
    return _run_narrative_travel(conn, 1, location_key, label, clean)


def test_narrative_travel_prompts_route_choice(conn):
    out = _narr_travel(conn, "vilnograd")
    data = json.loads(out)
    assert "Którą drogę wybierasz" in data["narrative"], data
    assert "traktu" in data["narrative"], data
    assert data["location_intent"] is None
    assert _current_hex(conn) == {"q": 0, "r": 0}              # did NOT move
    assert _flags(conn).get("pending_travel_choice") is not None


def test_narrative_prompt_then_road_answer_travels(conn):
    _narr_travel(conn, "vilnograd")                            # arms the question
    res = _run(conn, "idę traktem")                            # pre-LLM handler answers
    assert res["executed"] is True, res
    assert _current_hex(conn) == {"q": 4, "r": 0}             # reached Vilnograd
    tp = _flags(conn).get("travel_plan")
    if tp is not None:  # plan only persists when the trip is interrupted
        assert tp.get("route_mode") == "road"
    assert "traktem" in (res["system_fact"] or "")            # narrated as the trakt
    assert _flags(conn).get("pending_travel_choice") is None   # cleared


def test_narrative_short_trip_no_prompt(conn):
    out = _narr_travel(conn, "brod", label="Bród")            # dist 2 → no ask
    data = json.loads(out)
    assert "Którą drogę wybierasz" not in data.get("narrative", "")
    assert _flags(conn).get("pending_travel_choice") is None
    assert _current_hex(conn) == {"q": 0, "r": 2}             # travelled straight away
