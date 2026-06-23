"""TDD: Issue #938 — party_messages table missing from migrations (500 on chat endpoint)."""
import sqlite3
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ─── RED: verify table + schema exist ────────────────────────────────────────

def test_party_messages_table_exists():
    """party_messages table must exist in the live DB."""
    conn = sqlite3.connect("/data/ai_gm.db")
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='party_messages'"
    ).fetchone()
    conn.close()
    assert row is not None, "party_messages table missing — migration not applied"


def test_party_messages_has_whisper_to_column():
    """party_messages must have whisper_to TEXT column (used by party_chat.py)."""
    conn = sqlite3.connect("/data/ai_gm.db")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(party_messages)").fetchall()}
    conn.close()
    assert "whisper_to" in cols, (
        f"whisper_to column missing from party_messages; found: {cols}"
    )


def test_party_messages_insert_and_select():
    """Can INSERT a message with whisper_to=NULL and SELECT it back."""
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "INSERT INTO party_messages (campaign_id, user_id, character_name, message, whisper_to, created_at) "
            "VALUES (999998, 999998, 'TestChar', 'Hello', NULL, datetime('now')) RETURNING id, created_at, whisper_to"
        ).fetchone()
        conn.commit()
        assert row["id"] is not None
        assert row["whisper_to"] is None
        # cleanup
        conn.execute("DELETE FROM party_messages WHERE campaign_id=999998")
        conn.commit()
    finally:
        conn.close()


def test_party_messages_insert_whisper():
    """Can INSERT a whisper message (whisper_to set to character name string)."""
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "INSERT INTO party_messages (campaign_id, user_id, character_name, message, whisper_to, created_at) "
            "VALUES (999997, 999997, 'TestChar', 'Whisper!', 'TargetChar', datetime('now')) RETURNING id, whisper_to"
        ).fetchone()
        conn.commit()
        assert row["whisper_to"] == "TargetChar"
        # cleanup
        conn.execute("DELETE FROM party_messages WHERE campaign_id=999997")
        conn.commit()
    finally:
        conn.close()


# ─── Backward compat: campaign_invites also intact ───────────────────────────

def test_campaign_invites_table_exists():
    """campaign_invites table (added in #937) must still be present."""
    conn = sqlite3.connect("/data/ai_gm.db")
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='campaign_invites'"
    ).fetchone()
    conn.close()
    assert row is not None, "campaign_invites table missing (regression from #937)"
