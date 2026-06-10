"""F20 (#480) — Time-of-day mechanical effects.

Phase derived from ingame_hours (mod 24):
  dawn:  06–11
  day:   12–17
  dusk:  18–21
  night: 22–05

Effects stored in game_config_meta.time_of_day_effects.
"""
import json

DEFAULT_TIME_OF_DAY_EFFECTS: dict = {
    "dawn": {"initiative_bonus": 1},
    "day": {},
    "dusk": {"perception_dc_bonus": 1},
    "night": {"perception_dc_bonus": 2, "stealth_bonus": 2},
}


def get_time_of_day_phase(ingame_hours: int) -> str:
    """Return phase string for the given ingame hour total."""
    h = int(ingame_hours) % 24
    if 6 <= h < 12:
        return "dawn"
    if 12 <= h < 18:
        return "day"
    if 18 <= h < 22:
        return "dusk"
    return "night"


def get_time_of_day_effects(conn) -> dict:
    """Load time-of-day effects from game_config_meta or return defaults."""
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = 'time_of_day_effects' LIMIT 1"
        ).fetchone()
    except Exception:
        return dict(DEFAULT_TIME_OF_DAY_EFFECTS)
    if not row or not row[0]:
        return dict(DEFAULT_TIME_OF_DAY_EFFECTS)
    try:
        raw = json.loads(row[0])
        if isinstance(raw, dict) and raw:
            return raw
    except (json.JSONDecodeError, TypeError):
        pass
    return dict(DEFAULT_TIME_OF_DAY_EFFECTS)


def get_active_effects_for_phase(phase: str, effects_config: dict | None) -> dict:
    """Return the effects dict for the given phase, or empty dict."""
    if not effects_config:
        return {}
    return dict(effects_config.get(phase, {}))
