"""TDD: Issue #325 — Player must receive orientation context after resurrection.

Bug: apply_resurrection() revives the hero mechanically but sets no session flag.
Next narrative turn has no hint for the LLM to orient the player (where are they,
what happened, what is next). Player is confused after resurrection.

Fix:
1. apply_resurrection() writes session_flags.pending_resurrection_briefing = True
2. _inject_resurrection_briefing() in game_engine reads the flag, injects a
   mandatory LLM instruction, then clears the flag so it only fires once.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db_runtime import resolve_db_path


@pytest.fixture
def conn():
    c = sqlite3.connect(resolve_db_path())
    c.row_factory = sqlite3.Row
    yield c
    c.close()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_apply_resurrection_sets_pending_briefing_flag(conn):
    """apply_resurrection must write pending_resurrection_briefing=True to session_flags.

    Before fix: session_flags unchanged after resurrection.
    After fix: session_flags.pending_resurrection_briefing = True.
    """
    from app.services.resurrection_service import apply_resurrection

    # Find a campaign with an active game_session to test with
    row = conn.execute(
        """SELECT c.id AS campaign_id, c.owner_user_id, ch.id AS character_id
           FROM campaigns c
           JOIN characters ch ON ch.campaign_id = c.id AND ch.is_active = 1
           JOIN game_sessions gs ON gs.campaign_id = c.id
           WHERE c.status IN ('active', 'ended')
           LIMIT 1"""
    ).fetchone()
    if not row:
        pytest.skip("No campaign with active character and game session found")

    campaign_id = row["campaign_id"]
    character_id = row["character_id"]
    user_id = row["owner_user_id"]

    # Clear flag first (may be leftover from a prior test run)
    gs_row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if gs_row:
        flags_clean = json.loads(gs_row["session_flags"] or "{}")
        flags_clean.pop("pending_resurrection_briefing", None)
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (json.dumps(flags_clean, ensure_ascii=False), campaign_id),
        )
        conn.commit()

    gs_before = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    flags_before = json.loads(gs_before["session_flags"] or "{}") if gs_before else {}

    # The flag must NOT be present before resurrection
    assert "pending_resurrection_briefing" not in flags_before, (
        "Flag should not exist before resurrection (cleanup failed)"
    )

    # Apply resurrection (force=True to bypass config/uses checks)
    apply_resurrection(character_id, user_id, conn, force=True)

    gs_after = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    flags_after = json.loads(gs_after["session_flags"] or "{}") if gs_after else {}

    assert flags_after.get("pending_resurrection_briefing") is True, (
        f"Expected pending_resurrection_briefing=True in session_flags after resurrection, "
        f"got: {flags_after}"
    )

    # Cleanup: remove the flag
    flags_after.pop("pending_resurrection_briefing", None)
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(flags_after, ensure_ascii=False), campaign_id),
    )
    conn.commit()


def test_inject_resurrection_briefing_exists():
    """_inject_resurrection_briefing must be importable from game_engine."""
    from app.services.game_engine import _inject_resurrection_briefing  # noqa: F401


def test_inject_resurrection_briefing_injects_context_when_flag_set(conn):
    """_inject_resurrection_briefing must add a system message when flag is True."""
    from app.services.game_engine import _inject_resurrection_briefing

    # Find a campaign with a game session
    row = conn.execute(
        "SELECT campaign_id, session_flags FROM game_sessions LIMIT 1"
    ).fetchone()
    if not row:
        pytest.skip("No game session found")

    campaign_id = row["campaign_id"]
    flags = json.loads(row["session_flags"] or "{}")

    # Set the flag
    flags["pending_resurrection_briefing"] = True
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(flags, ensure_ascii=False), campaign_id),
    )
    conn.commit()

    messages = [{"role": "system", "content": "System prompt."}]
    _inject_resurrection_briefing(conn, campaign_id, messages)

    # Must have injected a message
    all_content = " ".join(m.get("content", "") for m in messages)
    assert "wskrzesz" in all_content.lower() or "resurrect" in all_content.lower() or "orientuj" in all_content.lower() or "ożyw" in all_content.lower(), (
        f"Expected resurrection briefing context in messages, got: {all_content[:200]}"
    )

    # Flag must be cleared after injection
    gs_after = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    flags_after = json.loads(gs_after["session_flags"] or "{}")
    assert "pending_resurrection_briefing" not in flags_after, (
        "Flag must be cleared after injection so briefing only fires once"
    )


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_inject_resurrection_briefing_no_op_when_flag_absent(conn):
    """_inject_resurrection_briefing must not inject anything when flag not set."""
    from app.services.game_engine import _inject_resurrection_briefing

    row = conn.execute(
        "SELECT campaign_id, session_flags FROM game_sessions LIMIT 1"
    ).fetchone()
    if not row:
        pytest.skip("No game session found")

    campaign_id = row["campaign_id"]
    flags = json.loads(row["session_flags"] or "{}")

    # Ensure flag is absent
    flags.pop("pending_resurrection_briefing", None)
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(flags, ensure_ascii=False), campaign_id),
    )
    conn.commit()

    messages = [{"role": "system", "content": "System prompt."}]
    original_len = len(messages)
    _inject_resurrection_briefing(conn, campaign_id, messages)

    assert len(messages) == original_len, (
        "No messages should be added when pending_resurrection_briefing flag absent"
    )
