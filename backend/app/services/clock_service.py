"""Game-clock service — Stage 2A T1.

Advances `session_flags.ingame_hours` for a campaign and keeps a rolling audit
log of every advance event. This is the single source of truth for "how much
in-game time has passed" — readers must always use `get_clock_state()` (or
read `session_flags.ingame_hours` directly) rather than the legacy column
`game_sessions.ingame_hours` which is no longer maintained.

Storage rationale: `context_injector` already reads from
`session_flags.get("ingame_hours")` to inject "Pora: …" into the narrator
prompt. Adding a parallel write path on the column would create two
sources of truth. We keep JSON.

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
  combat / dialog / shopping  → 0 (handled outside this service)
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


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _format_hour(hour: int) -> str:
    """HH:MM string for a 0–23 hour value. Minutes always 00 (no sub-hour granularity)."""
    return f"{hour % 24:02d}:00"


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


# #758 — target-time-of-day jump. The LLM emits `advance_to_time_of_day` and
# the engine computes the minutes needed to reach the START of that phase.
# Phase buckets mirror `time_of_day_service.get_time_of_day_phase`.
_PHASE_START_HOUR = {"dawn": 6, "day": 12, "dusk": 18, "night": 22}
_PHASE_ALIASES = {
    # English canonical
    "dawn": "dawn", "day": "day", "dusk": "dusk", "night": "night",
    "morning": "dawn", "noon": "day", "afternoon": "day", "evening": "dusk",
    "midnight": "night",
    # Polish synonyms (accent + accent-stripped)
    "świt": "dawn", "swit": "dawn", "rano": "dawn", "ranek": "dawn", "brzask": "dawn",
    "dzień": "day", "dzien": "day", "południe": "day", "poludnie": "day",
    "popołudnie": "day", "popoludnie": "day",
    "zmrok": "dusk", "wieczór": "dusk", "wieczor": "dusk",
    "zachód": "dusk", "zachod": "dusk", "zmierzch": "dusk",
    "noc": "night", "północ": "night", "polnoc": "night",
}


def minutes_to_reach_phase(current_hour: int, target: str) -> int:
    """Minutes to fast-forward from `current_hour` (0–23) to the start of the
    target time-of-day phase. Returns 0 when the target is unknown or we are
    already inside that phase (no jump needed)."""
    from app.services.time_of_day_service import get_time_of_day_phase

    key = _PHASE_ALIASES.get(str(target or "").strip().lower())
    if not key:
        return 0
    cur = int(current_hour) % 24
    if get_time_of_day_phase(cur) == key:
        return 0
    delta_hours = (_PHASE_START_HOUR[key] - cur) % 24
    return delta_hours * 60


def init_clock_from_plan(
    campaign_id: int, conn: sqlite3.Connection | None = None
) -> int | None:
    """#1208 — set the campaign's starting clock from `gm_plan_json.start_hour`.

    Templates/plans may declare the hour the opening scene takes place (an evening
    tavern scene → 19), instead of every campaign silently starting at 09:00.
    No-op (returns None) when:
    - the plan has no valid integer start_hour in 0–23,
    - the session does not exist yet,
    - the clock is already running (ingame_hours present or clock_history non-empty)
      — never rewinds a campaign in progress.
    Returns the applied hour on success.
    """
    managed = conn is None
    if managed:
        conn = _conn()
    try:
        row = conn.execute(
            "SELECT gm_plan_json FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        try:
            plan = json.loads((row["gm_plan_json"] if row else None) or "{}")
        except Exception:
            return None
        raw_hour = plan.get("start_hour") if isinstance(plan, dict) else None
        try:
            start_hour = int(raw_hour)
        except (TypeError, ValueError):
            return None
        if not 0 <= start_hour <= 23:
            return None

        sess = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not sess:
            return None
        flags = json.loads(sess["session_flags"] or "{}")
        if "ingame_hours" in flags or flags.get("clock_history"):
            return None  # clock already running — don't rewind mid-game

        flags["ingame_hours"] = start_hour
        flags["clock_history"] = [{
            "from": start_hour, "to": start_hour, "delta": 0,
            "reason": "plan_start_hour",
        }]
        conn.execute(
            "UPDATE game_sessions SET session_flags = ?, ingame_hours = ? WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), start_hour, sess["id"]),
        )
        if managed:
            conn.commit()
        return start_hour
    finally:
        if managed:
            conn.close()


def get_clock_state(campaign_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Read the current clock state for a campaign.

    Returns: {
        ingame_hours: int   (total hours since start),
        day: int            (1-indexed),
        hour: int           (0–23),
        hour_str: str       ("HH:00"),
        period: str         ("Rano" / "Popołudnie" / "Wieczór" / "Noc"),
        display: str        ("Dzień 3, 14:00 Popołudnie")
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
        day = (h // 24) + 1
        hour = h % 24
        return {
            "ingame_hours": h,
            "day": day,
            "hour": hour,
            "hour_str": _format_hour(hour),
            "period": _time_of_day_label(hour),
            "display": f"Dzień {day}, {_format_hour(hour)} {_time_of_day_label(hour)}",
        }
    finally:
        if managed:
            conn.close()


def advance_clock(
    campaign_id: int,
    hours: float = 0.0,
    reason: str = "",
    conn: sqlite3.Connection | None = None,
    *,
    minutes: int = 0,
) -> dict[str, Any]:
    """Advance the in-game clock for a campaign.

    Args:
        campaign_id: target campaign
        hours: hours to add (integer precision; legacy positional callers)
        reason: short string identifying the cause — one of
                "travel" | "short_rest" | "long_rest" | "camp_setup" | "admin" | …
        conn: optional existing sqlite connection (for transactional callers).
        minutes: keyword-only; sub-hour minutes accumulated in
                 session_flags.pending_clock_minutes until ≥60, then promoted
                 to whole hours. Allows turn_route callers to pass minutes
                 directly (e.g. minutes=15 for a narrative tick).

    Returns: same shape as get_clock_state(), reflecting the post-advance state,
             plus `delta_hours` (whole hours actually applied this call).

    Notes:
        - hours ≤ 0 AND minutes ≤ 0 is a no-op.
        - hours > MAX_ADVANCE_HOURS is clamped to the cap.
        - Audit log entry pushed onto session_flags.clock_history (rolling 50).
    """
    total_minutes = int(round(float(hours or 0) * 60)) + max(0, int(minutes or 0))
    if total_minutes <= 0:
        return {**get_clock_state(campaign_id, conn=conn), "delta_hours": 0}

    managed = conn is None
    if managed:
        conn = _conn()
    try:
        row = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not row:
            return {**get_clock_state(campaign_id, conn=conn), "delta_hours": 0}

        flags = json.loads(row["session_flags"] or "{}")

        # Accumulate sub-hour minutes; only advance full hours
        pending = int(flags.get("pending_clock_minutes", 0)) + total_minutes
        delta = min(pending // 60, MAX_ADVANCE_HOURS)
        flags["pending_clock_minutes"] = pending % 60

        if delta > 0:
            old_hours = int(flags.get("ingame_hours", START_HOUR_DEFAULT))
            new_hours = old_hours + delta

            history = list(flags.get("clock_history") or [])
            history.append({
                "from": old_hours,
                "to": new_hours,
                "delta": delta,
                "reason": str(reason or "unspecified"),
            })
            if len(history) > CLOCK_HISTORY_MAX_ENTRIES:
                history = history[-CLOCK_HISTORY_MAX_ENTRIES:]

            flags["ingame_hours"] = new_hours
            flags["clock_history"] = history

        # #580: keep the legacy `ingame_hours` column in sync with the authoritative
        # session_flags value, so direct column readers never see a stale time-of-day.
        conn.execute(
            "UPDATE game_sessions SET session_flags = ?, ingame_hours = ? WHERE id = ?",
            (
                json.dumps(flags, ensure_ascii=False),
                int(flags.get("ingame_hours", START_HOUR_DEFAULT)),
                row["id"],
            ),
        )
        if managed:
            conn.commit()
    finally:
        if managed:
            conn.close()

    state = get_clock_state(campaign_id)
    state["delta_hours"] = delta
    return state
