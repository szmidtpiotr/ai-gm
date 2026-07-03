"""TDD: Issue #1126 (PT-D3) — Pory dnia, pory roku i pogoda opisowa w narracji.

Pora roku = czysta pochodna dnia (zero nowego stanu).
Pogoda = deterministyczna maszyna stanów (łańcuch Markowa) ważona porą roku + biome.
Determinizm: te same (campaign_id, day, slot, prev, season, biome) → ta sama pogoda.
Toggle `weather_enabled=0` → brak linii POGODA (zero wpływu, gdy wyłączone).
"""
import json
import sqlite3

import pytest

from app.services import weather_service as ws


# ─── in-memory DB helper (game_sessions) ─────────────────────────────────────

def _mem_db(session_flags: dict | None = None, campaign_id: int = 1) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            session_flags TEXT,
            ingame_hours INTEGER
        )"""
    )
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags, ingame_hours) VALUES (?, ?, ?)",
        (campaign_id, json.dumps(session_flags or {}), (session_flags or {}).get("ingame_hours", 9)),
    )
    conn.commit()
    return conn


# ─── Test główny 1 — determinizm pogody ──────────────────────────────────────

def test_roll_weather_is_deterministic():
    """Te same wejścia (campaign, day, slot, prev, season, biome) → ta sama pogoda."""
    kwargs = dict(prev_type="clouds", season="jesień", hex_type="las",
                  campaign_id=42, day=3, slot=1)
    first = ws.roll_weather(**kwargs)
    for _ in range(50):
        assert ws.roll_weather(**kwargs) == first, "roll_weather nie jest deterministyczne"
    assert first in ws.WEATHER_TYPES


def test_roll_weather_varies_across_slots():
    """Różne sloty tej samej kampanii dają zróżnicowaną pogodę (nie zawsze to samo)."""
    seen = {
        ws.roll_weather(prev_type="clear", season="jesień", hex_type="równina",
                        campaign_id=7, day=1, slot=s)
        for s in range(40)
    }
    assert len(seen) >= 2, "pogoda nigdy się nie zmienia między slotami — brak zmienności"


# ─── Test główny 2 — pora roku z dnia ────────────────────────────────────────

def test_season_derived_from_day():
    """Pora roku to czysta pochodna dnia; start jesienią (offset=2)."""
    # Dzień 1 → jesień (start_offset=2 = jesień)
    assert ws.get_season(1, days_per_season=30, start_offset=2) == "jesień"
    # Po 30 dniach → następna pora (zima)
    assert ws.get_season(31, days_per_season=30, start_offset=2) == "zima"
    # Po 4 porach (120 dni) wraca do jesieni
    assert ws.get_season(121, days_per_season=30, start_offset=2) == "jesień"


def test_season_tunable_days_per_season():
    """DAYS_PER_SEASON strojenie: krótsze pory = szybsza rotacja."""
    assert ws.get_season(1, days_per_season=10, start_offset=0) == "wiosna"
    assert ws.get_season(11, days_per_season=10, start_offset=0) == "lato"


# ─── Test główny 3 — ważenie porą roku ───────────────────────────────────────

def test_snow_only_in_winter():
    """Śnieg pojawia się zimą, nie latem (ważenie porą roku)."""
    summer = {
        ws.roll_weather(prev_type="clear", season="lato", hex_type="równina",
                        campaign_id=99, day=200, slot=s)
        for s in range(60)
    }
    winter = {
        ws.roll_weather(prev_type="clear", season="zima", hex_type="równina",
                        campaign_id=99, day=200, slot=s)
        for s in range(60)
    }
    assert "snow" not in summer, "śnieg nie powinien padać latem"
    assert "snow" in winter, "zimą śnieg powinien być możliwy"


def test_heat_only_in_summer():
    """Upał tylko latem."""
    winter = {
        ws.roll_weather(prev_type="clear", season="zima", hex_type="równina",
                        campaign_id=5, day=50, slot=s)
        for s in range(60)
    }
    assert "heat" not in winter, "upał nie powinien występować zimą"


# ─── Test główny 4 — wstrzyknięcie linii POGODA + toggle ──────────────────────

def test_weather_line_contains_season_and_period():
    """build_weather_line zwraca linię z porą roku, pogodą i porą dnia."""
    conn = _mem_db({"ingame_hours": 21, "current_hex": {"q": 0, "r": 0}}, campaign_id=1)
    line = ws.build_weather_line(1, ingame_hours=21, hex_type="las", conn=conn)
    assert line.startswith("POGODA:"), f"zła etykieta: {line!r}"
    assert "jesień" in line.lower()  # dzień 1 = jesień
    # pora dnia (21h = zmierzch, bucket 20-23) obecna
    assert "zmierzch" in line.lower()


def test_toggle_disables_weather_line(monkeypatch):
    """weather_enabled=0 → pusta linia (pogoda wyłączona globalnie)."""
    monkeypatch.setattr(ws, "get_global_flag", lambda key, default="0": "0"
                        if key == "weather_enabled" else default)
    conn = _mem_db({"ingame_hours": 12}, campaign_id=1)
    line = ws.build_weather_line(1, ingame_hours=12, hex_type="las", conn=conn)
    assert line == "", "przy weather_enabled=0 linia POGODA musi być pusta"


# ─── Backward compat — brak stanu pogody nie wywala ──────────────────────────

def test_weather_state_persists_and_survives_missing_flags():
    """Pierwsze wywołanie tworzy stan; brak wcześniejszej pogody nie rzuca wyjątku."""
    conn = _mem_db({"ingame_hours": 30}, campaign_id=3)
    st = ws.get_weather_state(3, hex_type="góry", conn=conn)
    assert st["type"] in ws.WEATHER_TYPES
    assert "since_hour" in st
    # ponowny odczyt w tym samym slocie = ta sama pogoda (stabilność)
    st2 = ws.get_weather_state(3, hex_type="góry", conn=conn)
    assert st2["type"] == st["type"]


# ─── Admin — ręczne nadpisanie pogody ─────────────────────────────────────────

def test_weather_override_forces_type():
    """set_weather_override wymusza typ; get_weather_state go respektuje."""
    conn = _mem_db({"ingame_hours": 40}, campaign_id=8)
    res = ws.set_weather_override(8, "storm", conn=conn)
    assert res["ok"] is True
    st = ws.get_weather_state(8, hex_type="równina", conn=conn)
    assert st["type"] == "storm"
    assert st.get("forced") is True
    # usunięcie nadpisania wraca do losowania
    ws.set_weather_override(8, None, conn=conn)
    st2 = ws.get_weather_state(8, hex_type="równina", conn=conn)
    assert "forced" not in st2


def test_weather_override_rejects_bad_type():
    """Nieznany typ pogody → ValueError (walidacja admina)."""
    conn = _mem_db({"ingame_hours": 10}, campaign_id=9)
    with pytest.raises(ValueError):
        ws.set_weather_override(9, "tornado", conn=conn)
