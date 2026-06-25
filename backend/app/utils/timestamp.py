"""Timestamp normalization helpers.

SQLite returns two different created_at formats depending on the table:
  campaign_turns: "2026-06-25 12:58:01"  (space separator, no zone)
  combat_turns:   "2026-06-25T10:27:08Z" (ISO 8601, T separator, Z suffix)

String comparison between these formats is unreliable because 0x20 (space) < 0x54 (T),
causing campaign_turns to always sort before combat_turns regardless of actual time.
"""

from typing import Any


def normalize_ts_for_sort(ts: Any) -> str:
    """Normalize a created_at timestamp to a sortable ISO-8601 string.

    Handles both space-format ("2026-06-25 12:58:01") and ISO T+Z format
    ("2026-06-25T10:27:08Z"). Returns "" for falsy input.
    """
    if not ts:
        return ""
    s = str(ts).strip()
    # Replace space separator with T (space-format → ISO)
    s = s.replace(" ", "T")
    # Strip trailing Z so both formats compare as plain datetime strings
    if s.endswith("Z"):
        s = s[:-1]
    return s
