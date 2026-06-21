"""TDD: Issue #808 — G27 quiet window: sweep skips and pushes suppressed during team silence hours."""
import sys
import os
sys.path.insert(0, "/app")

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, call


# ─── Unit tests: _in_quiet_window ────────────────────────────────────────────

def _qw(now_str, quiet_start, quiet_end, tz):
    """Helper: parse ISO datetime string and call _in_quiet_window."""
    from app.services.quiet_window import _in_quiet_window  # noqa: F401
    now = datetime.fromisoformat(now_str).replace(tzinfo=timezone.utc)
    return _in_quiet_window(now, quiet_start, quiet_end, tz)


def test_no_quiet_window_returns_false():
    """NULL params → no window configured → always False."""
    from app.services.quiet_window import _in_quiet_window  # noqa: F401
    now = datetime(2024, 1, 15, 3, 0, tzinfo=timezone.utc)
    assert _in_quiet_window(now, None, None, None) is False
    assert _in_quiet_window(now, "23:00", None, None) is False
    assert _in_quiet_window(now, None, "07:00", None) is False
    assert _in_quiet_window(now, "23:00", "07:00", None) is False


def test_before_midnight_window_is_outside():
    """22:00 Warsaw (21:00 UTC in winter) is before 23:00–07:00 window."""
    # 2024-01-15 21:00 UTC = 22:00 Warsaw (UTC+1 in January)
    assert _qw("2024-01-15T21:00:00", "23:00", "07:00", "Europe/Warsaw") is False


def test_inside_midnight_crossing_window():
    """01:00 Warsaw (00:00 UTC) is inside 23:00–07:00 window."""
    # 2024-01-16 00:00 UTC = 01:00 Warsaw
    assert _qw("2024-01-16T00:00:00", "23:00", "07:00", "Europe/Warsaw") is True


def test_at_window_start_is_inside():
    """23:00 Warsaw exactly = window start → inside."""
    # 2024-01-15 22:00 UTC = 23:00 Warsaw
    assert _qw("2024-01-15T22:00:00", "23:00", "07:00", "Europe/Warsaw") is True


def test_after_window_end_is_outside():
    """08:00 Warsaw = after 07:00 end → outside."""
    # 2024-01-15 07:00 UTC = 08:00 Warsaw
    assert _qw("2024-01-15T07:00:00", "23:00", "07:00", "Europe/Warsaw") is False


def test_at_window_end_is_outside():
    """07:00 Warsaw exactly = window end → outside (exclusive end)."""
    # 2024-01-15 06:00 UTC = 07:00 Warsaw
    assert _qw("2024-01-15T06:00:00", "23:00", "07:00", "Europe/Warsaw") is False


def test_simple_window_not_crossing_midnight_inside():
    """02:00 UTC inside simple 02:00–06:00 window."""
    assert _qw("2024-01-15T02:00:00", "02:00", "06:00", "UTC") is True


def test_simple_window_not_crossing_midnight_outside():
    """01:00 UTC outside simple 02:00–06:00 window."""
    assert _qw("2024-01-15T01:00:00", "02:00", "06:00", "UTC") is False
    assert _qw("2024-01-15T07:00:00", "02:00", "06:00", "UTC") is False


def test_timezone_affects_result():
    """Same UTC moment: inside window for Warsaw, outside for UTC."""
    # 2024-01-16 01:00 UTC = 02:00 Warsaw
    # Warsaw window 23:00–07:00 → inside (02:00 is in window)
    # UTC window 23:00–07:00 → inside (01:00 is in window)
    # Let's test a moment where Warsaw is in window but NYC (EST=UTC-5) is not
    # 2024-01-16 01:00 UTC = 02:00 Warsaw (inside 23:00-07:00) = 20:00 NYC (outside 23:00-07:00)
    from app.services.quiet_window import _in_quiet_window  # noqa: F401
    now = datetime(2024, 1, 16, 1, 0, tzinfo=timezone.utc)
    assert _in_quiet_window(now, "23:00", "07:00", "Europe/Warsaw") is True
    assert _in_quiet_window(now, "23:00", "07:00", "America/New_York") is False


def test_invalid_tz_returns_false():
    """Invalid timezone string → no crash, returns False."""
    from app.services.quiet_window import _in_quiet_window  # noqa: F401
    now = datetime(2024, 1, 16, 1, 0, tzinfo=timezone.utc)
    assert _in_quiet_window(now, "23:00", "07:00", "Invalid/Timezone") is False


# ─── Integration tests: force_sweep respects quiet window ────────────────────

def test_force_sweep_skips_round_in_quiet_window():
    """force_sweep must NOT close a round when campaign is in quiet window."""
    from app.services.multiplayer_round_service import force_sweep

    # expired round at 01:00 UTC for a Warsaw campaign with 23:00–07:00 window
    fake_now = datetime(2024, 1, 16, 1, 0, tzinfo=timezone.utc)  # 02:00 Warsaw = in window

    mock_row = MagicMock()
    mock_row.__getitem__ = lambda self, k: {
        "id": 42,
        "campaign_id": 99,
        "quiet_start": "23:00",
        "quiet_end": "07:00",
        "team_tz": "Europe/Warsaw",
    }[k]

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.execute.return_value.fetchall.return_value = [mock_row]

    with patch("app.services.multiplayer_round_service._db", return_value=mock_conn), \
         patch("app.services.multiplayer_round_service._close_expired_round") as mock_close:
        force_sweep(now=fake_now)
        mock_close.assert_not_called()


def test_force_sweep_closes_round_outside_quiet_window():
    """force_sweep MUST close a round when campaign is outside quiet window."""
    from app.services.multiplayer_round_service import force_sweep

    # 14:00 UTC = 15:00 Warsaw = outside 23:00–07:00 window
    fake_now = datetime(2024, 1, 16, 13, 0, tzinfo=timezone.utc)

    mock_row = MagicMock()
    mock_row.__getitem__ = lambda self, k: {
        "id": 43,
        "campaign_id": 100,
        "quiet_start": "23:00",
        "quiet_end": "07:00",
        "team_tz": "Europe/Warsaw",
    }[k]

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.execute.return_value.fetchall.return_value = [mock_row]

    with patch("app.services.multiplayer_round_service._db", return_value=mock_conn), \
         patch("app.services.multiplayer_round_service._close_expired_round") as mock_close:
        force_sweep(now=fake_now)
        mock_close.assert_called_once_with(43, 100)


def test_force_sweep_closes_round_no_quiet_window():
    """Campaign without quiet window (NULL fields): sweep closes normally."""
    from app.services.multiplayer_round_service import force_sweep

    fake_now = datetime(2024, 1, 16, 1, 0, tzinfo=timezone.utc)

    mock_row = MagicMock()
    mock_row.__getitem__ = lambda self, k: {
        "id": 44,
        "campaign_id": 101,
        "quiet_start": None,
        "quiet_end": None,
        "team_tz": None,
    }[k]

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.execute.return_value.fetchall.return_value = [mock_row]

    with patch("app.services.multiplayer_round_service._db", return_value=mock_conn), \
         patch("app.services.multiplayer_round_service._close_expired_round") as mock_close:
        force_sweep(now=fake_now)
        mock_close.assert_called_once_with(44, 101)
