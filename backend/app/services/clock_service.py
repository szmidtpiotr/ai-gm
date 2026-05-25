"""Game-clock service — Stage 2A T1 + BUG-02 minute resolution.

Advances `session_flags.ingame_hours` (and `ingame_minutes`) for a campaign and
keeps a rolling audit log of every advance event. Single source of truth for
"how much in-game time has passed".

Storage rationale: `context_injector` already reads `session_flags.ingame_hours`
to inject "Pora: …" into the narrator prompt. Adding a parallel write path on
the column would create two sources of truth. We keep JSON.

BUG-02: minute resolution. `ingame_minutes` (0-59) is stored alongside
`ingame_hours` to support sub-hour turn advances (e.g., 15-min narrative
turn). `advance_clock` accepts both `hours` and `minutes` kwargs; on
rollover (minutes >= 60), it carries into hours.

Time-of-day buckets (mirrors `context_injector._time_of_day`):
  06–11  Rano
  12–17  Popołudnie
  18–21  Wieczór
  22–05  Noc

Per `12_TRAVEL_SYSTEM.md`:
  campaigns start at hour 9 (morning departure)
  ingame_hours is total hours since campaign start (never resets)
  day_number = (ingame_hours // 24) + 1

Per `DECISIONS_2026_05_18.md` [D16]:
  travel between hexes        → +travel_hours
  short rest                  → +1h
  long rest                   → +8h
  Rozbij obóz                 → +1h (camp setup) + the rest that follows
  narrative turn (BUG-02)     → +15 min default (configurable)
  combat turn   (BUG-02)      → +5  min default (configurable)
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path("/data/ai_gm.db")

# Cap individual advance to a sane upper bound — defensive against bugs that
# would accidentally fast-forward years. Tunable; 168h = 1 in-game week.
MAX_ADVANCE_HOURS = 168

# Cap retained audit-log entries per session. Older entries roll off.
CLOCK_HISTORY_MAX_ENTRIES = 50

START_HOUR_DEFAULT = 9  # 09:00 — matches 12_TRAVEL_SYSTEM.md
START_MIN_DEFAULT = 0


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _format_time(hour: int, minute: int) -> str:
    """HH:MM string for a 0-23 hour and 0-59 minute (BUG-02 minute resolution)."""
    return f"{hour % 24:02d}:{minute % 60:02d}"


def _time_of_day_label(hour: int) -> str:
    """Polish label matching context_injector._time_of_day buckets."""
    h = hour % 24
    if 6 <= h < 12:
        return "Rano"
    if 12 <= h < 18:
        return "Popołudnie"
    if 18 <= h < 22:
        return "Wieczór"
    return "Noc"


def get_clock_state(campaign_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Read the current clock state for a campaign.

    Returns: {
        ingame_hours:   int   (total hours since start),
        ingame_minutes: int   (0-59, BUG-02 minute resolution),
        day:            int   (1-indexed),
        hour:           int   (0-23),
        minute:         int   (0-59),
        hour_str:       str   ("HH:MM"),
        period:         str   ("Rano" / "Popołudnie" / "Wieczór" / "Noc"),
        display:        str   ("Dzień 3, 14:23 Popołudnie")
    }
    """
    managed = conn is None
    if managed:
        conn = _conn()
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        flags = json.loads((row["session_flags"] if row else None) or "{}")
        h = int(flags.get("ingame_hours", START_HOUR_DEFAULT))
        m = int(flags.get("ingame_minutes", START_MIN_DEFAULT))
        # Defensive normalization in case stored minutes overflowed.
        h += m // 60
        m = m % 60
        day = (h // 24) + 1
        hour = h % 24
        return {
            "ingame_hours": h,
            "ingame_minutes": m,
            "day": day,
            "hour": hour,
            "minute": m,
            "hour_str": _format_time(hour, m),
            "period": _time_of_day_label(hour),
            "display": f"Dzień {day}, {_format_time(hour, m)} {_time_of_day_label(hour)}",
        }
    finally:
        if managed:
            conn.close()


def advance_clock(
    campaign_id: int,
    hours: float = 0,
    reason: str = "unspecified",
    conn: sqlite3.Connection | None = None,
    *,
    minutes: int = 0,
) -> dict[str, Any]:
    """Advance the in-game clock for a campaign.

    Args:
        campaign_id: target campaign
        hours: hours to add (legacy positional arg; rounded to int)
        reason: short string identifying the cause — one of
                "travel" | "short_rest" | "long_rest" | "camp_setup" | "admin" |
                "turn_narrative" | "turn_combat" | …
        conn: optional existing sqlite connection (for transactional callers).
        minutes: minutes to add (BUG-02 minute resolution; kw-only). Combined
                with hours: total_minutes = hours*60 + minutes. Rolls over.

    Returns: same shape as get_clock_state(), reflecting the post-advance state,
             plus `delta_hours` (legacy field) and `delta_minutes` (total minutes applied).

    Notes:
        - total delta ≤ 0 is a no-op (returns current state without writing).
        - total delta > MAX_ADVANCE_HOURS*60 minutes is clamped to the cap.
        - Audit log entry pushed onto session_flags.clock_history (rolling 50).
    """
    delta_hours = int(round(max(0.0, float(hours or 0))))
    delta_minutes = int(max(0, int(minutes or 0)))
    total_min = delta_hours * 60 + delta_minutes
    if total_min == 0:
        return {**get_clock_state(campaign_id, conn=conn), "delta_hours": 0, "delta_minutes": 0}
    max_total_min = MAX_ADVANCE_HOURS * 60
    if total_min > max_total_min:
        total_min = max_total_min

    managed = conn is None
    if managed:
        conn = _conn()
    try:
        row = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not row:
            # No session row yet — nothing to advance against. Caller should
            # ensure the session exists before driving the clock.
            return {**get_clock_state(campaign_id, conn=conn), "delta_hours": 0, "delta_minutes": 0}

        flags = json.loads(row["session_flags"] or "{}")
        old_hours = int(flags.get("ingame_hours", START_HOUR_DEFAULT))
        old_mins = int(flags.get("ingame_minutes", START_MIN_DEFAULT))
        # Normalize old state into total minutes since start, add delta, split back.
        old_total = old_hours * 60 + old_mins
        new_total = old_total + total_min
        new_hours = new_total // 60
        new_mins = new_total % 60

        history = list(flags.get("clock_history") or [])
        history.append({
            "from_h": old_hours,
            "from_m": old_mins,
            "to_h": new_hours,
            "to_m": new_mins,
            "delta_min": total_min,
            "reason": str(reason or "unspecified"),
        })
        if len(history) > CLOCK_HISTORY_MAX_ENTRIES:
            history = history[-CLOCK_HISTORY_MAX_ENTRIES:]

        flags["ingame_hours"] = new_hours
        flags["ingame_minutes"] = new_mins
        flags["clock_history"] = history

        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), row["id"]),
        )
        if managed:
            conn.commit()
    finally:
        if managed:
            conn.close()

    state = get_clock_state(campaign_id)
    state["delta_hours"] = total_min // 60  # legacy field — hours-only portion
    state["delta_minutes"] = total_min
    return state
