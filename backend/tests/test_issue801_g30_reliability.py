"""TDD: Issue #801 — G30 FUNDAMENT: niezawodność + współbieżność rundy MP.

Pięć kryteriów akceptacji:
A) WAL + busy_timeout na połączeniach MP
B) client_action_id idempotencja żądania
C) Maszyna stanu rundy — walidowane przejścia
D) Wstrzykiwalny zegar + force_sweep
E) Retry narratora — brak lokalnego fallbacku po błędzie LLM
"""

import json
import sqlite3
import sys
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call
import pytest

sys.path.insert(0, "/app")

# ─── Fixtures ────────────────────────────────────────────────────────────────

def _fresh_db(tmp_path):
    """Create a minimal in-memory-style temp DB for MP round tests."""
    db_path = str(tmp_path / "test_g30.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, title TEXT,
            mode TEXT DEFAULT 'multiplayer', host_user_id INTEGER,
            round_timer_minutes INTEGER DEFAULT 60, round_timer_hours INTEGER DEFAULT 1,
            max_players INTEGER DEFAULT 4, lobby_status TEXT DEFAULT 'open',
            host_note TEXT, template_id INTEGER, status TEXT DEFAULT 'active',
            spectator_policy TEXT DEFAULT 'none',
            party_hex_q INTEGER, party_hex_r INTEGER,
            quiet_start TEXT, quiet_end TEXT, team_tz TEXT
        );
        CREATE TABLE campaign_members (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
            character_id INTEGER, status TEXT DEFAULT 'accepted',
            absence_warnings INTEGER DEFAULT 0, pending_intro INTEGER DEFAULT 0,
            autopilot_consent INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE campaign_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'collecting',
            deadline TEXT,
            closed_at TEXT,
            narrative_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE campaign_round_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER NOT NULL,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            character_id INTEGER,
            character_name TEXT NOT NULL,
            action_text TEXT NOT NULL,
            submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
            initiative_roll INTEGER NOT NULL DEFAULT 0,
            client_action_id TEXT,
            UNIQUE(round_id, user_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_round_action_client_id
            ON campaign_round_actions(client_action_id)
            WHERE client_action_id IS NOT NULL;
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, name TEXT, user_id INTEGER,
            campaign_id INTEGER, status TEXT DEFAULT 'active',
            sheet_json TEXT DEFAULT '{}'
        );
        INSERT INTO campaigns (id, title, round_timer_minutes) VALUES (1, 'Test', 60);
        INSERT INTO campaign_members (campaign_id, user_id, character_id, status) VALUES (1, 10, 100, 'accepted');
        INSERT INTO campaign_members (campaign_id, user_id, character_id, status) VALUES (1, 11, 101, 'accepted');
        INSERT INTO characters (id, name, user_id, campaign_id) VALUES (100, 'Aldric', 10, 1);
        INSERT INTO characters (id, name, user_id, campaign_id) VALUES (101, 'Mira', 11, 1);
    """)
    conn.commit()
    conn.close()
    return db_path


# ─── A) WAL + busy_timeout ────────────────────────────────────────────────────

def test_db_connection_uses_wal(tmp_path):
    """_db() must open connection with journal_mode=WAL and busy_timeout set."""
    db_path = _fresh_db(tmp_path)

    import app.services.multiplayer_round_service as svc
    with patch("app.services.multiplayer_round_service.resolve_db_path", return_value=db_path):
        conn = svc._db()
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        finally:
            conn.close()

    assert mode == "wal", f"Expected WAL, got {mode}"
    assert timeout >= 5000, f"busy_timeout too low: {timeout}ms"


def test_concurrent_submits_no_locked_error(tmp_path):
    """Two concurrent submit_action calls must not raise 'database is locked'."""
    db_path = _fresh_db(tmp_path)

    import app.services.multiplayer_round_service as svc
    errors = []

    def _submit(user_id, char_id, char_name):
        try:
            # submit_action does not call trigger_narration directly (that's the API endpoint)
            # so no patch needed here — avoids concurrent-patch race that corrupts the module attr
            with patch("app.services.multiplayer_round_service.resolve_db_path", return_value=db_path):
                with patch("app.services.multiplayer_round_service._roll_initiative", return_value=10):
                    svc.submit_action(1, user_id, char_id, char_name, "Atakuję!")
        except Exception as e:
            errors.append(str(e))

    t1 = threading.Thread(target=_submit, args=(10, 100, "Aldric"))
    t2 = threading.Thread(target=_submit, args=(11, 101, "Mira"))
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert not any("locked" in e.lower() for e in errors), f"Got DB lock errors: {errors}"

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM campaign_round_actions").fetchone()[0]
    conn.close()
    assert count == 2, f"Expected 2 actions, got {count}"


# ─── B) client_action_id idempotencja ────────────────────────────────────────

def test_submit_action_accepts_client_action_id(tmp_path):
    """submit_action() accepts client_action_id kwarg without error."""
    db_path = _fresh_db(tmp_path)
    uid = str(uuid.uuid4())

    import app.services.multiplayer_round_service as svc
    with patch("app.services.multiplayer_round_service.resolve_db_path", return_value=db_path):
        with patch("app.services.multiplayer_round_service._roll_initiative", return_value=10):
            result = svc.submit_action(1, 10, 100, "Aldric", "Idę na lewo", client_action_id=uid)
    assert "round_id" in result


def test_duplicate_client_action_id_is_noop(tmp_path):
    """Second submit with same client_action_id must be a no-op (no text overwrite)."""
    db_path = _fresh_db(tmp_path)
    uid = str(uuid.uuid4())

    import app.services.multiplayer_round_service as svc

    def _submit(action_text):
        with patch("app.services.multiplayer_round_service.resolve_db_path", return_value=db_path):
            with patch("app.services.multiplayer_round_service._roll_initiative", return_value=10):
                return svc.submit_action(1, 10, 100, "Aldric", action_text, client_action_id=uid)

    _submit("Pierwsza akcja")
    _submit("Druga akcja — nadpisanie")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT action_text FROM campaign_round_actions WHERE user_id=10").fetchone()
    conn.close()
    assert row["action_text"] == "Pierwsza akcja", f"Action was overwritten: {row['action_text']}"


def test_different_client_action_ids_both_recorded(tmp_path):
    """Two different client_action_ids from same user: last one wins (normal ON CONFLICT(round_id,user_id))."""
    db_path = _fresh_db(tmp_path)

    import app.services.multiplayer_round_service as svc

    def _submit(action_text):
        with patch("app.services.multiplayer_round_service.resolve_db_path", return_value=db_path):
            with patch("app.services.multiplayer_round_service._roll_initiative", return_value=10):
                uid = str(uuid.uuid4())
                return svc.submit_action(1, 10, 100, "Aldric", action_text, client_action_id=uid)

    _submit("Pierwsza akcja")
    _submit("Zmieniam zdanie")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT action_text FROM campaign_round_actions WHERE user_id=10").fetchone()
    conn.close()
    # different uuid → normal update flow, second action wins
    assert row["action_text"] == "Zmieniam zdanie"


# ─── C) Maszyna stanu rundy ────────────────────────────────────────────────────

def test_transition_round_valid_collecting_to_narrating(tmp_path):
    """_transition_round: collecting → narrating is valid."""
    db_path = _fresh_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("INSERT INTO campaign_rounds (campaign_id, round_number, status) VALUES (1, 1, 'collecting')")
    round_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()

    import app.services.multiplayer_round_service as svc
    result = svc._transition_round(conn, round_id, "collecting", "narrating")
    conn.close()
    assert result is True


def test_transition_round_valid_narrating_to_done(tmp_path):
    """_transition_round: narrating → done is valid."""
    db_path = _fresh_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("INSERT INTO campaign_rounds (campaign_id, round_number, status) VALUES (1, 1, 'narrating')")
    round_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()

    import app.services.multiplayer_round_service as svc
    result = svc._transition_round(conn, round_id, "narrating", "done")
    conn.close()
    assert result is True


def test_transition_round_invalid_collecting_to_done(tmp_path):
    """_transition_round: collecting → done skips narrating — must be rejected."""
    db_path = _fresh_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("INSERT INTO campaign_rounds (campaign_id, round_number, status) VALUES (1, 1, 'collecting')")
    round_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()

    import app.services.multiplayer_round_service as svc
    with pytest.raises(ValueError, match="Invalid round transition"):
        svc._transition_round(conn, round_id, "collecting", "done")
    conn.close()


def test_transition_round_wrong_current_state_returns_false(tmp_path):
    """_transition_round returns False when round is already past expected_from state."""
    db_path = _fresh_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("INSERT INTO campaign_rounds (campaign_id, round_number, status) VALUES (1, 1, 'narrating')")
    round_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()

    import app.services.multiplayer_round_service as svc
    # Round is already 'narrating' — transition from 'collecting' should return False (no-op, not error)
    result = svc._transition_round(conn, round_id, "collecting", "narrating")
    conn.close()
    assert result is False


# ─── D) Wstrzykiwalny zegar + force_sweep ────────────────────────────────────

def test_make_deadline_injectable_clock(tmp_path):
    """_make_deadline accepts a 'now' parameter for testability."""
    import app.services.multiplayer_round_service as svc
    fixed_now = datetime(2030, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    deadline = svc._make_deadline(60, now=fixed_now)
    expected = datetime(2030, 1, 1, 13, 0, 0, tzinfo=timezone.utc).isoformat()
    assert deadline == expected, f"Expected {expected}, got {deadline}"


def test_force_sweep_closes_round_past_injected_time(tmp_path):
    """force_sweep(now=future) closes rounds expired relative to injected time."""
    db_path = _fresh_db(tmp_path)
    conn = sqlite3.connect(db_path)
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    conn.execute(
        "INSERT INTO campaign_rounds (campaign_id, round_number, status, deadline) VALUES (1, 1, 'collecting', ?)",
        (past,)
    )
    conn.commit()
    conn.close()

    import app.services.multiplayer_round_service as svc
    future_now = datetime.now(timezone.utc) + timedelta(minutes=1)

    with patch("app.services.multiplayer_round_service.resolve_db_path", return_value=db_path):
        with patch("app.services.multiplayer_round_service.trigger_narration"):
            svc.force_sweep(now=future_now)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status FROM campaign_rounds").fetchone()
    conn.close()
    assert row[0] == "narrating", f"Expected narrating, got {row[0]}"


def test_force_sweep_does_not_close_future_round(tmp_path):
    """force_sweep(now=past) must not close a round whose deadline is still ahead."""
    db_path = _fresh_db(tmp_path)
    conn = sqlite3.connect(db_path)
    future_dl = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    conn.execute(
        "INSERT INTO campaign_rounds (campaign_id, round_number, status, deadline) VALUES (1, 1, 'collecting', ?)",
        (future_dl,)
    )
    conn.commit()
    conn.close()

    import app.services.multiplayer_round_service as svc
    past_now = datetime.now(timezone.utc) - timedelta(minutes=1)

    with patch("app.services.multiplayer_round_service.resolve_db_path", return_value=db_path):
        svc.force_sweep(now=past_now)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status FROM campaign_rounds").fetchone()
    conn.close()
    assert row[0] == "collecting", f"Round closed prematurely, got {row[0]}"


# ─── E) Retry narratora — brak fallbacku ──────────────────────────────────────

def _narrator_setup(tmp_path):
    """Insert narrating round + one action; return (db_path, round_id)."""
    db_path = _fresh_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO campaign_rounds (campaign_id, round_number, status) VALUES (1, 1, 'narrating')"
    )
    round_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO campaign_round_actions "
        "(round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (?, 1, 10, 100, 'Aldric', 'Atakuję!')", (round_id,)
    )
    conn.commit()
    conn.close()
    return db_path, round_id


def _narrator_ctx(db_path, llm_side_effect):
    """Return nested patch context for trigger_narration tests."""
    from contextlib import ExitStack
    stack = ExitStack()
    stack.enter_context(patch(
        "app.services.multiplayer_round_service.resolve_db_path", return_value=db_path))
    stack.enter_context(patch(
        "app.services.multiplayer_round_service._llm_call", side_effect=llm_side_effect))
    # patch on the actual llm_service module (where the function is defined)
    stack.enter_context(patch(
        "app.services.llm_service.get_effective_config",
        return_value={"provider": "openai", "base_url": "http://x", "model": "m", "api_key": ""}))
    stack.enter_context(patch(
        "app.services.llm_service.OpenAIDriver", return_value=MagicMock()))
    stack.enter_context(patch(
        "app.services.multiplayer_round_service._NARRATOR_RETRY_BACKOFF_S", 0))
    return stack


def test_narrator_retry_on_llm_error(tmp_path):
    """trigger_narration retries LLM on failure — _llm_call called more than once."""
    db_path, round_id = _narrator_setup(tmp_path)

    import app.services.multiplayer_round_service as svc
    from app.services.multiplayer_round_service import trigger_narration as _real_trigger

    call_count = {"n": 0}
    def _failing_llm(*args, **kwargs):
        call_count["n"] += 1
        raise RuntimeError("LLM unavailable")

    with patch("app.services.multiplayer_round_service.resolve_db_path", return_value=db_path):
        with patch("app.services.multiplayer_round_service._llm_call", side_effect=_failing_llm):
            with patch("app.services.llm_service.get_effective_config", return_value={"provider": "openai", "base_url": "x", "model": "m", "api_key": ""}):
                with patch("app.services.llm_service.OpenAIDriver", return_value=MagicMock()):
                    with patch("app.services.multiplayer_round_service._NARRATOR_RETRY_BACKOFF_S", 0):
                        _real_trigger(round_id)

    assert call_count["n"] > 1, f"Expected retry, got {call_count['n']} call(s)"


def test_narrator_no_garbage_narrative_stored(tmp_path):
    """After LLM failure + exhausted retries, round must NOT have garbage 'Coś poszło nie tak' narrative."""
    db_path, round_id = _narrator_setup(tmp_path)

    import app.services.multiplayer_round_service as svc

    with patch("app.services.multiplayer_round_service.resolve_db_path", return_value=db_path):
        with patch("app.services.multiplayer_round_service._llm_call", side_effect=RuntimeError("down")):
            with patch("app.services.llm_service.get_effective_config", return_value={"provider": "openai", "base_url": "x", "model": "m", "api_key": ""}):
                with patch("app.services.llm_service.OpenAIDriver", return_value=MagicMock()):
                    with patch("app.services.multiplayer_round_service._NARRATOR_RETRY_BACKOFF_S", 0):
                        svc.trigger_narration(round_id)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status, narrative_json FROM campaign_rounds WHERE id=?", (round_id,)).fetchone()
    conn.close()

    if row[0] == "done" and row[1]:
        data = json.loads(row[1])
        assert "Coś poszło nie tak" not in data.get("narrative", ""), \
            "Garbage fallback narrative found in DB after exhausted retries"
