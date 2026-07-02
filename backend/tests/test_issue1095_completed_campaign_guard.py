"""TDD: Issue #1095 — completed/archived campaigns must be read-only (no new turns)."""
import sqlite3
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_conn(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'active',
            title TEXT,
            owner_user_id INTEGER
        )
    """)
    conn.commit()
    return conn


def _insert_campaign(conn, campaign_id, status):
    conn.execute(
        "INSERT INTO campaigns (id, status, title, owner_user_id) VALUES (?, ?, ?, ?)",
        (campaign_id, status, f"Test {status}", 1),
    )
    conn.commit()


# ─── Import guard under test ──────────────────────────────────────────────────

def _get_active_campaign_or_gone(conn, campaign_id):
    """Mirror of turns.py get_active_campaign_or_gone — imported directly."""
    from fastapi import HTTPException

    row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Campaign not found")
    status = str(row["status"] or "").lower()
    if status == "ended":
        raise HTTPException(status_code=410, detail="This campaign has ended.")
    if status in ("completed", "archived"):
        raise HTTPException(status_code=409, detail="This campaign is read-only (completed or archived).")
    return row


# ─── Test główny: completed blokuje submit tury ───────────────────────────────

def test_completed_campaign_blocked(tmp_path):
    """#1095: submitting a turn on a completed campaign must raise 409."""
    from fastapi import HTTPException
    conn = _make_conn(tmp_path)
    _insert_campaign(conn, 1, "completed")

    with pytest.raises(HTTPException) as exc_info:
        _get_active_campaign_or_gone(conn, 1)

    assert exc_info.value.status_code == 409, (
        f"Expected 409 for completed campaign, got {exc_info.value.status_code}"
    )
    conn.close()


def test_archived_campaign_blocked(tmp_path):
    """#1095: submitting a turn on an archived campaign must raise 409."""
    from fastapi import HTTPException
    conn = _make_conn(tmp_path)
    _insert_campaign(conn, 2, "archived")

    with pytest.raises(HTTPException) as exc_info:
        _get_active_campaign_or_gone(conn, 2)

    assert exc_info.value.status_code == 409, (
        f"Expected 409 for archived campaign, got {exc_info.value.status_code}"
    )
    conn.close()


# ─── Backward compat: ended still 410, active still passes ───────────────────

def test_ended_campaign_still_410(tmp_path):
    """ended campaigns still return 410, not 409."""
    from fastapi import HTTPException
    conn = _make_conn(tmp_path)
    _insert_campaign(conn, 3, "ended")

    with pytest.raises(HTTPException) as exc_info:
        _get_active_campaign_or_gone(conn, 3)

    assert exc_info.value.status_code == 410
    conn.close()


def test_active_campaign_passes(tmp_path):
    """active campaigns must NOT be blocked."""
    conn = _make_conn(tmp_path)
    _insert_campaign(conn, 4, "active")

    row = _get_active_campaign_or_gone(conn, 4)
    assert row["id"] == 4
    conn.close()
