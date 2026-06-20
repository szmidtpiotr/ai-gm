"""TDD: Issue #860 — short/long rest must be blocked while combat is active.

Bug: rest_service gates only on location (`safe_for_rest`). A combat fought in a
location flagged `safe_for_rest=true` can be healed mid-fight via short rest — exploit.

Fix: rest blocked if an active `active_combat` row exists for the campaign, regardless
of location. Returns {"ok": False, "error": "in_combat"} → endpoint maps to 409.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _mk_conn() -> sqlite3.Connection:
    """Minimal in-memory DB with only the active_combat table the gate reads."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        """CREATE TABLE active_combat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL UNIQUE,
            character_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        )"""
    )
    return c


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_short_rest_blocked_during_active_combat():
    """Short rest mid-combat must be refused with error 'in_combat'."""
    from app.services.rest_service import perform_short_rest

    conn = _mk_conn()
    conn.execute(
        "INSERT INTO active_combat (campaign_id, character_id, status) VALUES (?, ?, 'active')",
        (101, 5),
    )
    result = perform_short_rest(conn, character_id=5, campaign_id=101)
    assert result.get("ok") is False
    assert result.get("error") == "in_combat", result


def test_long_rest_blocked_during_active_combat():
    """Long rest mid-combat must be refused with error 'in_combat'."""
    from app.services.rest_service import perform_long_rest

    conn = _mk_conn()
    conn.execute(
        "INSERT INTO active_combat (campaign_id, character_id, status) VALUES (?, ?, 'active')",
        (102, 6),
    )
    result = perform_long_rest(conn, character_id=6, campaign_id=102)
    assert result.get("ok") is False
    assert result.get("error") == "in_combat", result


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_combat_gate_helper_false_when_no_combat():
    """No combat row → gate must NOT block (old behavior preserved)."""
    from app.services.rest_service import _has_active_combat

    conn = _mk_conn()
    assert _has_active_combat(999, conn) is False


def test_combat_gate_helper_false_when_combat_ended():
    """Ended combat must NOT block rest — only status='active' counts."""
    from app.services.rest_service import _has_active_combat

    conn = _mk_conn()
    conn.execute(
        "INSERT INTO active_combat (campaign_id, character_id, status) VALUES (?, ?, 'ended')",
        (103, 7),
    )
    assert _has_active_combat(103, conn) is False
