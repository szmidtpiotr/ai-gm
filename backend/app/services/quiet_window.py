"""G27 (#808) — Quiet window helper: is current time inside the campaign's silence period?

Extracted to its own module to avoid circular import between
multiplayer_round_service (which imports push_notification_service) and
push_notification_service (which needs to check the quiet window).
"""
from datetime import datetime, time as dt_time
from typing import Optional


def _in_quiet_window(
    now: datetime,
    quiet_start: Optional[str],
    quiet_end: Optional[str],
    tz: Optional[str],
) -> bool:
    """Return True if `now` falls inside the campaign's quiet window.

    Handles windows that cross midnight (e.g. 23:00–07:00).
    Returns False if any param is None/empty (no quiet window configured).
    """
    if not quiet_start or not quiet_end or not tz:
        return False
    try:
        import zoneinfo
        zone = zoneinfo.ZoneInfo(tz)
        local = now.astimezone(zone)
        sh, sm = map(int, quiet_start.split(":"))
        eh, em = map(int, quiet_end.split(":"))
        start = dt_time(sh, sm)
        end = dt_time(eh, em)
        t = local.time().replace(second=0, microsecond=0)
        if start <= end:
            return start <= t < end
        else:
            # Crosses midnight (e.g. 23:00–07:00)
            return t >= start or t < end
    except Exception:
        return False
