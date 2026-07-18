"""Encounter tuning config — D7 (#382), BL-A7 (#1423).

Admin-tunable knobs for the random-encounter pipeline, stored in
`game_config_meta` (key/value) so they can be balanced from admin3 without a
deploy. Default interval is intentionally high (20 turns) so wilderness
encounters don't pile up and cheap-kill the hero.

BL-A7 (#1423): dołożone pokrętło TRUDNOŚCI spotkań w podróży. `difficulty_mult`
skaluje budżet zagrożenia composera (mnożnik na wynik threat_budget_for_*), a
`threat_budget_base` / `threat_budget_per_power` / `pool_min_size` /
`repeat_penalty` wystawiają dotąd zaszyte stałe BL-A2/A5 do strojenia z admina.
Wszystkie DEFAULT_* muszą pozostać spójne ze stałymi w `encounter_service.py`
(THREAT_BUDGET_BASE / THREAT_BUDGET_PER_POWER / POOL_MIN_SIZE /
REPEAT_WEIGHT_PENALTY), bo to samo `game_config_meta` czyta i tamten moduł.
"""
from __future__ import annotations

import sqlite3

from app.migrations_admin import DB_PATH

DEFAULT_N_TURNS_INTERVAL = 20      # spokojne tury między próbami encountera w dziczy
DEFAULT_DWELL_SETTLE_TURNS = 3     # po ilu turach osiedlenia w lokacji szansa maleje
MIN_INTERVAL = 3
MAX_INTERVAL = 200

# BL-A7 (#1423) — trudność + zaawansowane strojenie composera. DEFAULT-y = stałe
# z encounter_service.py (parytet, gdy klucz meta nie ustawiony).
DEFAULT_DIFFICULTY_MULT = 1.0          # mnożnik budżetu zagrożenia (1.0 = bazowa krzywa)
DEFAULT_THREAT_BUDGET_BASE = 30.0      # THREAT_BUDGET_BASE
DEFAULT_THREAT_BUDGET_PER_POWER = 25.0 # THREAT_BUDGET_PER_POWER
DEFAULT_POOL_MIN_SIZE = 6              # POOL_MIN_SIZE
DEFAULT_REPEAT_PENALTY = 0.25          # REPEAT_WEIGHT_PENALTY

# Zakresy walidacji (twarde granice, nie startowe wartości).
MIN_DIFFICULTY_MULT, MAX_DIFFICULTY_MULT = 0.25, 3.0
MIN_BUDGET_BASE, MAX_BUDGET_BASE = 5.0, 200.0
MIN_BUDGET_PER_POWER, MAX_BUDGET_PER_POWER = 0.0, 100.0
MIN_POOL_SIZE, MAX_POOL_SIZE = 1, 30

# Presety trudności pokazywane w adminie (label → mnożnik). Startowe wartości.
DIFFICULTY_PRESETS = {
    "latwy": 0.75,
    "normalny": 1.0,
    "trudny": 1.35,
    "hardcore": 1.75,
}


def _read_int(conn: sqlite3.Connection, key: str, default: int) -> int:
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = ? LIMIT 1", (key,)
        ).fetchone()
    except sqlite3.OperationalError:
        return default
    if not row:
        return default
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return default


def _read_float(conn: sqlite3.Connection, key: str, default: float) -> float:
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = ? LIMIT 1", (key,)
        ).fetchone()
    except sqlite3.OperationalError:
        return default
    if not row:
        return default
    try:
        return float(row[0])
    except (TypeError, ValueError):
        return default


def get_encounter_config(*, conn: sqlite3.Connection | None = None) -> dict:
    own = conn is None
    if own:
        conn = sqlite3.connect(DB_PATH)
    try:
        return {
            "n_turns_interval": _read_int(conn, "encounter_n_turns_interval", DEFAULT_N_TURNS_INTERVAL),
            "dwell_settle_turns": _read_int(conn, "encounter_dwell_settle_turns", DEFAULT_DWELL_SETTLE_TURNS),
            # BL-A7 (#1423) — trudność + zaawansowane
            "difficulty_mult": _read_float(conn, "encounter_difficulty_mult", DEFAULT_DIFFICULTY_MULT),
            "threat_budget_base": _read_float(conn, "encounter_threat_budget_base", DEFAULT_THREAT_BUDGET_BASE),
            "threat_budget_per_power": _read_float(conn, "encounter_threat_budget_per_power", DEFAULT_THREAT_BUDGET_PER_POWER),
            "pool_min_size": _read_int(conn, "encounter_pool_min_size", DEFAULT_POOL_MIN_SIZE),
            "repeat_penalty": _read_float(conn, "encounter_repeat_penalty", DEFAULT_REPEAT_PENALTY),
            "difficulty_presets": DIFFICULTY_PRESETS,
        }
    finally:
        if own:
            conn.close()


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def set_encounter_config(
    *,
    conn: sqlite3.Connection | None = None,
    n_turns_interval: int | None = None,
    dwell_settle_turns: int | None = None,
    difficulty_mult: float | None = None,
    threat_budget_base: float | None = None,
    threat_budget_per_power: float | None = None,
    pool_min_size: int | None = None,
    repeat_penalty: float | None = None,
) -> dict:
    updates: list[tuple[str, str]] = []
    if n_turns_interval is not None:
        v = int(n_turns_interval)
        if v < MIN_INTERVAL or v > MAX_INTERVAL:
            raise ValueError(f"n_turns_interval musi być w zakresie {MIN_INTERVAL}-{MAX_INTERVAL}")
        updates.append(("encounter_n_turns_interval", str(v)))
    if dwell_settle_turns is not None:
        updates.append(("encounter_dwell_settle_turns", str(max(1, int(dwell_settle_turns)))))
    if difficulty_mult is not None:
        v = float(difficulty_mult)
        if v < MIN_DIFFICULTY_MULT or v > MAX_DIFFICULTY_MULT:
            raise ValueError(f"difficulty_mult musi być w zakresie {MIN_DIFFICULTY_MULT}-{MAX_DIFFICULTY_MULT}")
        updates.append(("encounter_difficulty_mult", str(round(v, 3))))
    if threat_budget_base is not None:
        v = _clamp(float(threat_budget_base), MIN_BUDGET_BASE, MAX_BUDGET_BASE)
        updates.append(("encounter_threat_budget_base", str(round(v, 2))))
    if threat_budget_per_power is not None:
        v = _clamp(float(threat_budget_per_power), MIN_BUDGET_PER_POWER, MAX_BUDGET_PER_POWER)
        updates.append(("encounter_threat_budget_per_power", str(round(v, 2))))
    if pool_min_size is not None:
        v = int(_clamp(float(pool_min_size), MIN_POOL_SIZE, MAX_POOL_SIZE))
        updates.append(("encounter_pool_min_size", str(v)))
    if repeat_penalty is not None:
        v = _clamp(float(repeat_penalty), 0.0, 1.0)
        updates.append(("encounter_repeat_penalty", str(round(v, 3))))

    own = conn is None
    if own:
        conn = sqlite3.connect(DB_PATH)
    try:
        for key, val in updates:
            conn.execute(
                "INSERT INTO game_config_meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, val),
            )
        conn.commit()
        return get_encounter_config(conn=conn)
    finally:
        if own:
            conn.close()
