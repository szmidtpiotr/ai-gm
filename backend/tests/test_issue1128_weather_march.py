"""TDD: Issue #1128 — PT15 Pogoda wpływa na tempo marszu (mnożnik kosztu godzin z stanu pogody).

Zła pogoda (deszcz/mgła ×1.25, burza/śnieg ×1.5, upał ×1.25) podnosi koszt
godzinowy kroku marszu w podróży świata (resolve_chain_travel). Trasa jest ta
sama (A* bez zmian) — rośnie tylko czas, przez co budżet dzienny (PT7) wyczerpuje
się szybciej. Ruch lokalny (15 min) bez zmian.
"""
import sys
import json
import sqlite3
import pytest

sys.path.insert(0, "/app")

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER NOT NULL, r INTEGER NOT NULL,
    hex_type TEXT NOT NULL DEFAULT 'plains',
    label TEXT, atmosphere TEXT,
    encounter_chance REAL NOT NULL DEFAULT 0.0,
    encounter_pool TEXT NOT NULL DEFAULT '[]',
    location_key TEXT, region TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    map_level INTEGER NOT NULL DEFAULT 0,
    created_by_gm INTEGER NOT NULL DEFAULT 0,
    parent_hex_id INTEGER
);
CREATE TABLE IF NOT EXISTS hex_type_config (
    hex_type TEXT PRIMARY KEY,
    travel_hours REAL NOT NULL DEFAULT 1.0,
    encounter_base_chance REAL NOT NULL DEFAULT 0.0,
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
CREATE TABLE IF NOT EXISTS game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL, label TEXT NOT NULL,
    canonical INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    ai_generated INTEGER NOT NULL DEFAULT 0,
    world_hex_q INTEGER, world_hex_r INTEGER,
    location_type TEXT DEFAULT 'macro',
    map_icon TEXT, review_status TEXT DEFAULT 'permanent',
    safe_for_rest INTEGER NOT NULL DEFAULT 0,
    temporary INTEGER NOT NULL DEFAULT 0,
    description TEXT DEFAULT '',
    parent_key TEXT DEFAULT NULL,
    created_by TEXT DEFAULT 'seed'
);
CREATE TABLE IF NOT EXISTS game_sessions (
    id TEXT PRIMARY KEY, campaign_id INTEGER,
    current_location_id INTEGER,
    session_flags TEXT NOT NULL DEFAULT '{}',
    ingame_hours INTEGER DEFAULT 9
);
CREATE TABLE IF NOT EXISTS campaign_hex_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    hex_q INTEGER NOT NULL, hex_r INTEGER NOT NULL,
    discovered INTEGER NOT NULL DEFAULT 0,
    encounter_cleared INTEGER NOT NULL DEFAULT 0,
    UNIQUE(campaign_id, hex_q, hex_r)
);
CREATE TABLE IF NOT EXISTS world_regions (
    key TEXT PRIMARY KEY, label TEXT, status TEXT DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS active_combat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER UNIQUE, status TEXT DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER, sheet_json TEXT NOT NULL DEFAULT '{}'
);
"""


def _mk_conn(weather_flags: dict | None = None):
    """10 plains hexes (0,0)→(9,0). Plains = 1h each. No encounters.
    weather_flags merged into session_flags."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    c.execute("INSERT INTO hex_type_config (hex_type, travel_hours, encounter_base_chance) VALUES ('plains', 1.0, 0.0)")
    for q in range(10):
        c.execute(
            "INSERT INTO world_hexes (q, r, hex_type, label, encounter_chance, encounter_pool, is_active, map_level)"
            " VALUES (?, 0, 'plains', ?, 0.0, '[]', 1, 0)",
            (q, f"Równina-{q}"),
        )
    flags = {"current_hex": {"q": 0, "r": 0}, "ingame_hours": 9}
    if weather_flags:
        flags.update(weather_flags)
    c.execute(
        "INSERT INTO game_sessions (id, campaign_id, session_flags, ingame_hours) VALUES ('s1', 1, ?, 9)",
        (json.dumps(flags),),
    )
    c.commit()
    return c


def _travel(conn, to=(4, 0)):
    from app.services import hex_travel_service as hts
    # Determinism: fixture sets encounter_chance=0.0, but _roll_encounter treats
    # explicit 0.0 as unset (`or 0.15`) and #1146 fallback pools supply a default
    # enemy even for empty pools — random bandit encounters were interrupting the
    # march mid-route and flaking these time-based assertions. Weather tests care
    # only about hour costs, so disable encounter rolls entirely.
    hts._roll_encounter = lambda *a, **k: False
    return hts.resolve_chain_travel(
        campaign_id=1, character_id=None,
        from_hex=(0, 0), to_hex=to,
        character_sheet={}, conn=conn,
    )


# ── Test 1 (main): storm slows 4-plains march 4h → 6h ─────────────────────────

def test_storm_multiplies_march_hours(conn=None):
    """PT15 RED: 4 plains hexes (1h each) w burzy (×1.5) = 6h zamiast 4h."""
    conn = _mk_conn({"weather": {"type": "storm"}})
    result = _travel(conn, to=(4, 0))

    assert result.get("ok") is True, f"Travel must succeed: {result}"
    assert result.get("arrived_hex") == {"q": 4, "r": 0}, (
        f"6h < 8h soft cap → full arrival at (4,0), got: {result.get('arrived_hex')}"
    )
    assert float(result.get("total_hours")) == pytest.approx(6.0), (
        f"4×1h×1.5(storm) must be 6.0h, got: {result.get('total_hours')}"
    )
    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0])
    assert float(flags.get("hours_marched_today", 0)) == pytest.approx(6.0), (
        f"budget must also reflect ×1.5, got: {flags.get('hours_marched_today')}"
    )


# ── Test 2: bad weather brings dusk sooner (fewer hexes before 8h cap) ─────────

def test_storm_dusk_comes_sooner(conn=None):
    """PT15 RED: burza ×1.5 na równinach → zmierzch po 6 hexach (9h≥8), nie 8."""
    conn = _mk_conn({"weather": {"type": "storm"}})
    result = _travel(conn, to=(9, 0))

    assert result.get("ok") is True
    # plains ×1.5: hex6 → 9.0h ≥ 8.0 soft cap → dusk stop at (6,0)
    assert result.get("arrived_hex") == {"q": 6, "r": 0}, (
        f"storm dusk must stop at (6,0), got: {result.get('arrived_hex')}"
    )
    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0])
    assert flags.get("travel_plan", {}).get("interrupt_reason") == "dusk", (
        f"must dusk-interrupt, got: {flags.get('travel_plan')}"
    )


# ── Test 3: narrator gets a weather-slowdown fact when multiplier active ───────

def test_weather_slowdown_signalled_in_result(conn=None):
    """PT15 RED: gdy mnożnik aktywny, wynik niesie sygnał dla narratora."""
    conn = _mk_conn({"weather": {"type": "rain"}})
    result = _travel(conn, to=(3, 0))
    assert result.get("weather_slowdown"), (
        f"result must flag weather_slowdown when mult>1, got: {result.get('weather_slowdown')}"
    )
    assert float(result.get("weather_multiplier")) == pytest.approx(1.25), (
        f"rain multiplier must be 1.25, got: {result.get('weather_multiplier')}"
    )


# ── Test 4: pure multiplier function per weather type ─────────────────────────

def test_weather_march_multiplier_values():
    """PT15 RED: mnożniki startowe wg typu pogody."""
    from app.services.weather_service import weather_march_multiplier
    assert weather_march_multiplier("clear") == 1.0
    assert weather_march_multiplier("clouds") == 1.0
    assert weather_march_multiplier("rain") == 1.25
    assert weather_march_multiplier("fog") == 1.25
    assert weather_march_multiplier("storm") == 1.5
    assert weather_march_multiplier("snow") == 1.5
    assert weather_march_multiplier("heat") == 1.25
    # unknown / None → neutral
    assert weather_march_multiplier(None) == 1.0
    assert weather_march_multiplier("nonsense") == 1.0


# ── Test 5 (backward compat): no weather → ×1.0, unchanged 4h ──────────────────

def test_no_weather_unchanged(conn=None):
    """PT15 COMPAT: brak stanu pogody → mnożnik 1.0, 4 równiny = 4h jak wcześniej."""
    conn = _mk_conn(None)
    result = _travel(conn, to=(4, 0))
    assert result.get("ok") is True
    assert result.get("arrived_hex") == {"q": 4, "r": 0}
    assert float(result.get("total_hours")) == pytest.approx(4.0), (
        f"no weather must keep 4×1h=4.0h, got: {result.get('total_hours')}"
    )
    assert not result.get("weather_slowdown"), (
        f"no slowdown flag when weather absent, got: {result.get('weather_slowdown')}"
    )


# ── Test 6: clear weather present but neutral (×1.0) ───────────────────────────

def test_clear_weather_neutral(conn=None):
    """PT15 COMPAT: pogoda clear obecna → mnożnik 1.0, brak spowolnienia."""
    conn = _mk_conn({"weather": {"type": "clear"}})
    result = _travel(conn, to=(4, 0))
    assert float(result.get("total_hours")) == pytest.approx(4.0)
    assert not result.get("weather_slowdown")


# ── Test 7: weather_override takes priority over rolled state ──────────────────

def test_weather_override_priority(conn=None):
    """PT15 RED: session_flags.weather_override wygrywa nad weather.type."""
    conn = _mk_conn({"weather": {"type": "clear"}, "weather_override": "storm"})
    result = _travel(conn, to=(4, 0))
    assert float(result.get("total_hours")) == pytest.approx(6.0), (
        f"override storm ×1.5 must win over clear, got: {result.get('total_hours')}"
    )
