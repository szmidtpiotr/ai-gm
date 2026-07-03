"""PT-D3 (#1126) — Pory roku i pogoda opisowa.

Przejmuje projekt #1104. Czysto OPISOWE na start — zero wpływu na mechanikę
(wpływ marszu → PT15, nocna ekonomia → PT14).

Dwa niezależne elementy:

1. **Pora roku** — czysta pochodna dnia, zero nowego stanu:
       season = SEASONS[(start_offset + (day - 1) // days_per_season) % 4]
   `days_per_season` startowo 30 (strojone w adminie), `start_offset` per
   kampania (start jesienią = offset 2 = klimat Kresów).

2. **Pogoda** — maszyna stanów w `session_flags.weather = {type, intensity,
   since_hour, slot}`; typy clear/clouds/rain/storm/fog/snow/heat; łańcuch
   Markowa ważony porą roku (zimą śnieg, latem upał/burze) i biome hexa
   (góry → mgła/śnieg, bagno → mgła/deszcz); przejścia płynne (bonus trwania
   dla obecnego typu); re-roll co WEATHER_SLOT_HOURS z deterministycznym
   seedem (campaign_id, day, slot) → ta sama kampania = ta sama pogoda.

Wstrzyknięcie: linia `POGODA: późna jesień, deszcz (umiarkowany). Zmierzch.`
w bloku ŚWIAT (`context_injector._build_world_block`). LLM wplata w opisy.

Toggle `weather_enabled` (game_config_meta, domyślnie 1) wyłącza całą linię.
Ręczne nadpisanie: `session_flags.weather_override = "storm"` (monitor admina).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from app.migrations_admin import DB_PATH
from app.services.location_config_service import get_global_flag

# ─── Stałe konfiguracyjne (Numbers Policy — wartości startowe, strojone) ──────

SEASONS = ["wiosna", "lato", "jesień", "zima"]

WEATHER_TYPES = ["clear", "clouds", "rain", "storm", "fog", "snow", "heat"]

DAYS_PER_SEASON_DEFAULT = 30
START_SEASON_OFFSET_DEFAULT = 2  # jesień — start kampanii (klimat Kresów)
WEATHER_SLOT_HOURS = 8           # re-roll pogody co ~8h gry
PERSISTENCE_BONUS = 4            # płynne przejścia: obecny typ dostaje bonus wagi

# Opisowe etykiety PL + domyślne natężenie w opisie
_WEATHER_PL = {
    "clear":  "bezchmurnie",
    "clouds": "pochmurno",
    "rain":   "deszcz",
    "storm":  "burza",
    "fog":    "mgła",
    "snow":   "śnieg",
    "heat":   "upał",
}

_INTENSITY_PL = {"light": "słaby", "moderate": "umiarkowany", "heavy": "silny"}

# Bazowy rozkład wag pogody per pora roku (łańcuch Markowa — punkt startowy).
_SEASON_WEIGHTS: dict[str, dict[str, int]] = {
    "wiosna": {"clear": 3, "clouds": 3, "rain": 3, "storm": 1, "fog": 2, "snow": 0, "heat": 0},
    "lato":   {"clear": 4, "clouds": 2, "rain": 2, "storm": 2, "fog": 1, "snow": 0, "heat": 3},
    "jesień": {"clear": 2, "clouds": 4, "rain": 3, "storm": 1, "fog": 3, "snow": 0, "heat": 0},
    "zima":   {"clear": 2, "clouds": 3, "rain": 0, "storm": 0, "fog": 2, "snow": 4, "heat": 0},
}

# Modyfikatory biome hexa (hex_type) — addytywne do wag pory roku.
_BIOME_WEIGHTS: dict[str, dict[str, int]] = {
    "mountains": {"fog": 3, "snow": 2, "storm": 1},
    "góry":      {"fog": 3, "snow": 2, "storm": 1},
    "gory":      {"fog": 3, "snow": 2, "storm": 1},
    "swamp":     {"fog": 4, "rain": 2},
    "bagno":     {"fog": 4, "rain": 2},
    "forest":    {"fog": 2, "rain": 1},
    "las":       {"fog": 2, "rain": 1},
    "desert":    {"heat": 4, "clear": 2},
    "pustynia":  {"heat": 4, "clear": 2},
}


# ─── Re-eksport get_global_flag (monkeypatch-owalny w testach toggle) ─────────

get_global_flag = get_global_flag


# ─── Pory dnia (spójne z clock_service._time_of_day_label) ────────────────────

def _period_label(ingame_hours: int) -> str:
    """Etykieta pory dnia — spójna z context_injector._time_of_day."""
    h = int(ingame_hours) % 24
    if 5 <= h < 9:
        return "świt"
    if 9 <= h < 13:
        return "rano"
    if 13 <= h < 17:
        return "południe"
    if 17 <= h < 20:
        return "popołudnie"
    if 20 <= h < 23:
        return "zmierzch"
    return "noc"


# ─── Pora roku ────────────────────────────────────────────────────────────────

def get_season(
    day: int,
    days_per_season: int = DAYS_PER_SEASON_DEFAULT,
    start_offset: int = START_SEASON_OFFSET_DEFAULT,
) -> str:
    """Pora roku jako czysta pochodna dnia (1-indexed). Zero stanu."""
    dps = max(1, int(days_per_season or DAYS_PER_SEASON_DEFAULT))
    d = max(1, int(day))
    idx = (int(start_offset) + (d - 1) // dps) % 4
    return SEASONS[idx]


# ─── Slot pogody (jednostka re-rollu) ─────────────────────────────────────────

def weather_slot(ingame_hours: int) -> int:
    """Numer slotu pogody od startu kampanii (co WEATHER_SLOT_HOURS godzin)."""
    return int(ingame_hours) // max(1, WEATHER_SLOT_HOURS)


# ─── Deterministyczny RNG z seeda (campaign, day, slot) ───────────────────────

def _seeded_int(campaign_id: int, day: int, slot: int, salt: str = "") -> int:
    raw = f"{campaign_id}:{day}:{slot}:{salt}".encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:16], 16)


# ─── Losowanie pogody (łańcuch Markowa) ──────────────────────────────────────

def _weights_for(season: str, hex_type: str | None, prev_type: str | None) -> dict[str, int]:
    weights = dict(_SEASON_WEIGHTS.get(season, _SEASON_WEIGHTS["jesień"]))
    biome = _BIOME_WEIGHTS.get((hex_type or "").strip().lower(), {})
    for t, w in biome.items():
        # nie odblokowuj typów zerowanych porą roku (np. śnieg latem) — tylko wzmacniaj dozwolone
        if weights.get(t, 0) > 0:
            weights[t] += w
    if prev_type and weights.get(prev_type, 0) > 0:
        weights[prev_type] += PERSISTENCE_BONUS
    return weights


def roll_weather(
    *,
    prev_type: str | None,
    season: str,
    hex_type: str | None,
    campaign_id: int,
    day: int,
    slot: int,
) -> str:
    """Deterministyczny typ pogody dla danego slotu. Ta sama krotka → ten sam wynik."""
    weights = _weights_for(season, hex_type, prev_type)
    types = [t for t in WEATHER_TYPES if weights.get(t, 0) > 0]
    total = sum(weights[t] for t in types)
    if total <= 0:
        return "clear"
    pick = _seeded_int(campaign_id, day, slot) % total
    acc = 0
    for t in types:
        acc += weights[t]
        if pick < acc:
            return t
    return types[-1]


def roll_intensity(campaign_id: int, day: int, slot: int) -> str:
    """Deterministyczne natężenie (light/moderate/heavy)."""
    v = _seeded_int(campaign_id, day, slot, salt="intensity") % 3
    return ("light", "moderate", "heavy")[v]


# ─── Toggle ───────────────────────────────────────────────────────────────────

def is_weather_enabled() -> bool:
    """Globalny toggle pogody (game_config_meta.weather_enabled, domyślnie 1)."""
    return str(get_global_flag("weather_enabled", "1")).strip() not in ("0", "false", "off", "")


# ─── PT15 (#1128): wpływ pogody na tempo marszu ───────────────────────────────

# Mnożnik kosztu godzinowego kroku podróży wg typu pogody. Wartości STARTOWE
# (Numbers Policy) — docelowo strojone w Sandbox/adminie obok toggle pogody.
WEATHER_MARCH_MULT: dict[str, float] = {
    "clear":  1.0,
    "clouds": 1.0,
    "rain":   1.25,
    "fog":    1.25,
    "storm":  1.5,
    "snow":   1.5,
    "heat":   1.25,
}


def weather_march_multiplier(weather_type: str | None) -> float:
    """Mnożnik kosztu godzinowego kroku marszu wg typu pogody (PT15 #1128).

    Nieznany typ / None → 1.0 (neutralny). Czysta funkcja, bez stanu."""
    if not weather_type:
        return 1.0
    return WEATHER_MARCH_MULT.get(str(weather_type).strip().lower(), 1.0)


def get_march_multiplier(
    campaign_id: int,
    conn: sqlite3.Connection,
) -> tuple[float, str | None]:
    """Efektywny mnożnik marszu dla kampanii wg stanu pogody w session_flags.

    - Respektuje globalny toggle (weather_enabled=0 → 1.0).
    - `weather_override` ma priorytet nad wylosowanym `weather.type`.
    - READ-ONLY: nie persystuje ani nie przewija stanu pogody (świadomie NIE
      wywołuje get_weather_state, by nie mieć skutków ubocznych w podróży).

    Zwraca (mnożnik, typ_pogody) — typ zwracany tylko gdy mnożnik > 1.0
    (sygnał dla narratora), inaczej None.
    """
    try:
        if not is_weather_enabled():
            return 1.0, None
    except Exception:
        # brak game_config_meta / błąd odczytu → traktuj jako włączone (domyślnie)
        pass
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        flags = json.loads((row["session_flags"] if row else None) or "{}")
    except Exception:
        return 1.0, None
    wtype = flags.get("weather_override") or (flags.get("weather") or {}).get("type")
    mult = weather_march_multiplier(wtype)
    return mult, (str(wtype) if mult > 1.0 else None)


# ─── DB helpers ───────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _read_session(conn: sqlite3.Connection, campaign_id: int) -> tuple[int, dict] | None:
    row = conn.execute(
        "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not row:
        return None
    try:
        flags = json.loads(row["session_flags"] or "{}")
    except (json.JSONDecodeError, TypeError):
        flags = {}
    return row["id"], flags


# ─── Stan pogody (odczyt + re-roll + persystencja) ────────────────────────────

def get_weather_state(
    campaign_id: int,
    hex_type: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Zwraca aktualny stan pogody, re-rollując gdy zmienił się slot.

    Kształt: {type, intensity, since_hour, slot}.
    Persystuje do session_flags.weather. Nadpisanie ręczne przez
    session_flags.weather_override (typ) ma priorytet.
    """
    managed = conn is None
    if managed:
        conn = _conn()
    try:
        read = _read_session(conn, campaign_id)
        if not read:
            return {"type": "clear", "intensity": "moderate", "since_hour": 0, "slot": 0}
        sess_id, flags = read

        ingame_hours = int(flags.get("ingame_hours", 9))
        day = (ingame_hours // 24) + 1
        slot = weather_slot(ingame_hours)
        season = get_season(
            day,
            days_per_season=_days_per_season(),
            start_offset=int(flags.get("season_start_offset", START_SEASON_OFFSET_DEFAULT)),
        )

        # Ręczne nadpisanie admina — stały typ, bez re-rollu
        override = flags.get("weather_override")
        if override in WEATHER_TYPES:
            state = {"type": override, "intensity": "moderate",
                     "since_hour": ingame_hours, "slot": slot, "forced": True}
            return state

        prev = flags.get("weather") or {}
        prev_slot = prev.get("slot")
        prev_type = prev.get("type")

        if prev_slot == slot and prev_type in WEATHER_TYPES:
            return dict(prev)  # ten sam slot → stabilna pogoda

        new_type = roll_weather(prev_type=prev_type, season=season, hex_type=hex_type,
                                campaign_id=campaign_id, day=day, slot=slot)
        state = {
            "type": new_type,
            "intensity": roll_intensity(campaign_id, day, slot),
            "since_hour": ingame_hours,
            "slot": slot,
        }
        flags["weather"] = state
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), sess_id),
        )
        if managed:
            conn.commit()
        return state
    finally:
        if managed:
            conn.close()


def _days_per_season() -> int:
    raw = get_global_flag("days_per_season", str(DAYS_PER_SEASON_DEFAULT))
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return DAYS_PER_SEASON_DEFAULT


# ─── Admin config (game_config_meta) ──────────────────────────────────────────

def _start_season_offset() -> int:
    raw = get_global_flag("season_start_offset", str(START_SEASON_OFFSET_DEFAULT))
    try:
        return int(raw) % 4
    except (TypeError, ValueError):
        return START_SEASON_OFFSET_DEFAULT


def get_weather_config() -> dict[str, Any]:
    """Globalna konfiguracja pogody (dla panelu admina)."""
    return {
        "weather_enabled": is_weather_enabled(),
        "days_per_season": _days_per_season(),
        "start_season_offset": _start_season_offset(),
        "weather_types": list(WEATHER_TYPES),
        "seasons": list(SEASONS),
        # PT15 #1128: mnożniki kosztu marszu wg pogody (startowe, Sandbox-tunable)
        "march_multipliers": dict(WEATHER_MARCH_MULT),
    }


def set_weather_config(
    *,
    weather_enabled: bool | None = None,
    days_per_season: int | None = None,
    start_season_offset: int | None = None,
) -> dict[str, Any]:
    """Upsert globalnej konfiguracji pogody. None = bez zmian."""
    updates: list[tuple[str, str]] = []
    if weather_enabled is not None:
        updates.append(("weather_enabled", "1" if weather_enabled else "0"))
    if days_per_season is not None:
        dps = int(days_per_season)
        if dps < 1 or dps > 365:
            raise ValueError("days_per_season musi być w zakresie 1-365")
        updates.append(("days_per_season", str(dps)))
    if start_season_offset is not None:
        off = int(start_season_offset) % 4
        updates.append(("season_start_offset", str(off)))

    if updates:
        conn = _conn()
        try:
            for key, val in updates:
                conn.execute(
                    """INSERT INTO game_config_meta (key, value) VALUES (?, ?)
                       ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                    (key, val),
                )
            conn.commit()
        finally:
            conn.close()
    return get_weather_config()


def set_weather_override(
    campaign_id: int,
    weather_type: str | None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Ręczne nadpisanie pogody kampanii (monitor admina, „wymuś burzę").

    weather_type=None → usuwa nadpisanie (powrót do losowania).
    """
    if weather_type is not None and weather_type not in WEATHER_TYPES:
        raise ValueError(f"nieznany typ pogody: {weather_type}")
    managed = conn is None
    if managed:
        conn = _conn()
    try:
        read = _read_session(conn, campaign_id)
        if not read:
            return {"ok": False, "reason": "no_session"}
        sess_id, flags = read
        if weather_type is None:
            flags.pop("weather_override", None)
        else:
            flags["weather_override"] = weather_type
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), sess_id),
        )
        if managed:
            conn.commit()
        return {"ok": True, "weather_override": weather_type}
    finally:
        if managed:
            conn.close()


# ─── Budowa linii POGODA do promptu narratora ─────────────────────────────────

def build_weather_line(
    campaign_id: int,
    ingame_hours: int,
    hex_type: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> str:
    """Linia `POGODA: <pora roku>, <pogoda> (<natężenie>). <Pora dnia>.`

    Pusty string gdy toggle wyłączony. Nie rzuca — błędy → "".
    """
    if not is_weather_enabled():
        return ""
    try:
        state = get_weather_state(campaign_id, hex_type=hex_type, conn=conn)
        day = (int(ingame_hours) // 24) + 1
        season = get_season(day, days_per_season=_days_per_season())
        w_type = state.get("type", "clear")
        w_pl = _WEATHER_PL.get(w_type, w_type)
        intensity = _INTENSITY_PL.get(state.get("intensity", "moderate"), "")
        period = _period_label(ingame_hours)

        # "bezchmurnie" nie potrzebuje natężenia
        if w_type in ("clear",) or not intensity:
            weather_part = w_pl
        else:
            weather_part = f"{w_pl} ({intensity})"

        return f"POGODA: {season}, {weather_part}. {period.capitalize()}."
    except Exception:
        return ""
