"""Clock-tick config (BUG-02).

Per-turn-type default minutes that the auto-advance hook adds to the in-game
clock. Stored in `game_config_meta` (key/value) so admin can tune without a
deploy. The hook in `turns.create_turn_log` reads these values; the LLM can
override the narrative default upward via `time_advance_minutes` in its
response JSON.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.migrations_admin import DB_PATH
from app.services.location_config_service import get_global_flag

# Defaults — also used as fallbacks when game_config_meta has no row yet.
DEFAULT_NARRATIVE_MIN = 15
DEFAULT_COMBAT_MIN = 5
DEFAULT_TRAVEL_MIN = 60

# Sanity caps. Admin-set values outside this window are rejected.
MIN_VALUE = 0
MAX_VALUE = 480  # 8h per turn — anything higher and time-skipping should be a /rest, not a turn.

_KEYS = ("time_per_narrative_min", "time_per_combat_min", "time_per_travel_min")


def _get_int(key: str, default: int) -> int:
    raw = get_global_flag(key, str(default))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def get_clock_config() -> dict[str, int]:
    """Read all 3 tick values. Falls back to defaults if missing."""
    return {
        "narrative_min": _get_int("time_per_narrative_min", DEFAULT_NARRATIVE_MIN),
        "combat_min": _get_int("time_per_combat_min", DEFAULT_COMBAT_MIN),
        "travel_min": _get_int("time_per_travel_min", DEFAULT_TRAVEL_MIN),
    }


def _validate(value: int, label: str) -> int:
    if value < MIN_VALUE or value > MAX_VALUE:
        raise ValueError(
            f"{label} musi być w zakresie {MIN_VALUE}-{MAX_VALUE} minut (otrzymano {value})"
        )
    return value


def set_clock_config(
    *,
    narrative_min: int | None = None,
    combat_min: int | None = None,
    travel_min: int | None = None,
) -> dict[str, int]:
    """Upsert any provided values. None means 'leave unchanged'."""
    updates: list[tuple[str, int]] = []
    if narrative_min is not None:
        updates.append(("time_per_narrative_min", _validate(int(narrative_min), "narrative_min")))
    if combat_min is not None:
        updates.append(("time_per_combat_min", _validate(int(combat_min), "combat_min")))
    if travel_min is not None:
        updates.append(("time_per_travel_min", _validate(int(travel_min), "travel_min")))

    if updates:
        conn = sqlite3.connect(DB_PATH)
        try:
            for key, val in updates:
                conn.execute(
                    """
                    INSERT INTO game_config_meta (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, str(val)),
                )
            conn.commit()
        finally:
            conn.close()
    return get_clock_config()
