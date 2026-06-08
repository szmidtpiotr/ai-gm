"""Encounter tuning config — D7 (#382).

Admin-tunable knobs for the random-encounter pipeline, stored in
`game_config_meta` (key/value) so they can be balanced from admin3 without a
deploy. Default interval is intentionally high (20 turns) so wilderness
encounters don't pile up and cheap-kill the hero.
"""
from __future__ import annotations

import sqlite3

from app.migrations_admin import DB_PATH

DEFAULT_N_TURNS_INTERVAL = 20      # spokojne tury między próbami encountera w dziczy
DEFAULT_DWELL_SETTLE_TURNS = 3     # po ilu turach osiedlenia w lokacji szansa maleje
MIN_INTERVAL = 3
MAX_INTERVAL = 200


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


def get_encounter_config(*, conn: sqlite3.Connection | None = None) -> dict:
    own = conn is None
    if own:
        conn = sqlite3.connect(DB_PATH)
    try:
        return {
            "n_turns_interval": _read_int(conn, "encounter_n_turns_interval", DEFAULT_N_TURNS_INTERVAL),
            "dwell_settle_turns": _read_int(conn, "encounter_dwell_settle_turns", DEFAULT_DWELL_SETTLE_TURNS),
        }
    finally:
        if own:
            conn.close()


def set_encounter_config(
    *,
    conn: sqlite3.Connection | None = None,
    n_turns_interval: int | None = None,
    dwell_settle_turns: int | None = None,
) -> dict:
    updates: list[tuple[str, str]] = []
    if n_turns_interval is not None:
        v = int(n_turns_interval)
        if v < MIN_INTERVAL or v > MAX_INTERVAL:
            raise ValueError(f"n_turns_interval musi być w zakresie {MIN_INTERVAL}-{MAX_INTERVAL}")
        updates.append(("encounter_n_turns_interval", str(v)))
    if dwell_settle_turns is not None:
        updates.append(("encounter_dwell_settle_turns", str(max(1, int(dwell_settle_turns)))))

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
