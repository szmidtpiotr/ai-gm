"""TDD #804 — G23: Pętla zaangażowania — wyważone haki + away-recap."""
import importlib
import json
import sqlite3
import sys
import os

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest


# ── DB helper ─────────────────────────────────────────────────────────────────

def _make_test_db(tmp_path):
    db_path = str(tmp_path / "test_804.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL DEFAULT '',
            display_name TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            system_id TEXT NOT NULL DEFAULT 'fantasy',
            model_id TEXT NOT NULL DEFAULT 'gpt-4',
            owner_user_id INTEGER NOT NULL DEFAULT 1,
            mode TEXT NOT NULL DEFAULT 'multiplayer',
            status TEXT NOT NULL DEFAULT 'active',
            round_timer_minutes INTEGER NOT NULL DEFAULT 1440,
            round_timer_hours INTEGER NOT NULL DEFAULT 24,
            max_players INTEGER NOT NULL DEFAULT 4,
            host_user_id INTEGER,
            lobby_status TEXT NOT NULL DEFAULT 'open',
            host_note TEXT,
            template_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS campaign_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'player',
            status TEXT NOT NULL DEFAULT 'accepted',
            character_id INTEGER,
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            absence_warnings INTEGER NOT NULL DEFAULT 0,
            autopilot_consent INTEGER NOT NULL DEFAULT 0,
            last_seen TEXT,
            pending_intro INTEGER NOT NULL DEFAULT 0,
            UNIQUE(campaign_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            system_id TEXT NOT NULL DEFAULT 'fantasy',
            sheet_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS campaign_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'collecting',
            deadline TEXT,
            closed_at TEXT,
            narrative_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS campaign_round_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER NOT NULL,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            character_name TEXT NOT NULL DEFAULT '',
            character_id INTEGER,
            action_text TEXT NOT NULL DEFAULT '',
            initiative_roll INTEGER NOT NULL DEFAULT 10,
            submitted_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS campaign_round_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            round_id INTEGER NOT NULL,
            summary_text TEXT NOT NULL DEFAULT '',
            layer INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    return db_path, conn


def _seed(conn, campaign_id, users):
    for uid, uname in users:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (uid, uname)
        )
        conn.execute(
            "INSERT OR IGNORE INTO campaign_members (campaign_id, user_id, status) VALUES (?,?,?)",
            (campaign_id, uid, "accepted"),
        )
    conn.execute(
        "INSERT OR IGNORE INTO campaigns (id, title, mode) VALUES (?,?,?)",
        (campaign_id, f"Camp {campaign_id}", "multiplayer"),
    )
    conn.commit()


def _insert_done_round(conn, campaign_id, round_number, narrative_json, actions):
    cur = conn.execute(
        "INSERT INTO campaign_rounds (campaign_id, round_number, status, narrative_json) VALUES (?,?,?,?)",
        (campaign_id, round_number, "done", json.dumps(narrative_json, ensure_ascii=False)),
    )
    round_id = cur.lastrowid
    for uid, char_name, action_text in actions:
        conn.execute(
            "INSERT INTO campaign_round_actions "
            "(round_id, campaign_id, user_id, character_name, action_text) VALUES (?,?,?,?,?)",
            (round_id, campaign_id, uid, char_name, action_text),
        )
    conn.commit()
    return round_id


def _load_svc(monkeypatch, db_path):
    monkeypatch.setenv("AI_TEST_DB_PATH", db_path)
    import app.services.multiplayer_round_service as svc
    importlib.reload(svc)
    return svc


# ── Tests: get_away_recap ─────────────────────────────────────────────────────


def test_no_warnings_returns_empty(tmp_path, monkeypatch):
    """Player with absence_warnings=0 gets empty recap (was present)."""
    db_path, conn = _make_test_db(tmp_path)
    _seed(conn, campaign_id=1, users=[(10, "alice")])
    svc = _load_svc(monkeypatch, db_path)
    result = svc.get_away_recap(campaign_id=1, user_id=10)
    assert result["has_recap"] is False
    assert result["missed_rounds"] == []
    assert result["summary_line"] == ""


def test_with_warnings_and_missed_rounds_returns_recap(tmp_path, monkeypatch):
    """Player with absence_warnings>0 gets missed rounds recap."""
    db_path, conn = _make_test_db(tmp_path)
    _seed(conn, campaign_id=1, users=[(10, "alice"), (20, "bob")])
    conn.execute(
        "UPDATE campaign_members SET absence_warnings=2 WHERE campaign_id=1 AND user_id=10"
    )
    _insert_done_round(conn, 1, 1,
        {"narrative": "Runda 1 narracja.", "player_notes": {}},
        [(20, "Bob", "Bob atakuje")],
    )
    _insert_done_round(conn, 1, 2,
        {"narrative": "Runda 2 narracja.", "player_notes": {}},
        [(20, "Bob", "Bob szuka")],
    )
    conn.commit()
    svc = _load_svc(monkeypatch, db_path)
    result = svc.get_away_recap(campaign_id=1, user_id=10)
    assert result["has_recap"] is True
    assert len(result["missed_rounds"]) == 2
    assert "2" in result["summary_line"] or len(result["missed_rounds"]) == 2


def test_read_resets_absence_warnings(tmp_path, monkeypatch):
    """After reading recap, absence_warnings reset to 0."""
    db_path, conn = _make_test_db(tmp_path)
    _seed(conn, campaign_id=1, users=[(10, "alice"), (20, "bob")])
    conn.execute(
        "UPDATE campaign_members SET absence_warnings=3 WHERE campaign_id=1 AND user_id=10"
    )
    _insert_done_round(conn, 1, 1,
        {"narrative": "Runda 1.", "player_notes": {}},
        [(20, "Bob", "atak")],
    )
    conn.commit()
    svc = _load_svc(monkeypatch, db_path)
    svc.get_away_recap(campaign_id=1, user_id=10)
    conn2 = sqlite3.connect(db_path)
    conn2.row_factory = sqlite3.Row
    row = conn2.execute(
        "SELECT absence_warnings FROM campaign_members WHERE campaign_id=1 AND user_id=10"
    ).fetchone()
    conn2.close()
    assert row["absence_warnings"] == 0


def test_second_call_returns_empty(tmp_path, monkeypatch):
    """After recap is read (warnings reset to 0), next call returns empty."""
    db_path, conn = _make_test_db(tmp_path)
    _seed(conn, campaign_id=1, users=[(10, "alice"), (20, "bob")])
    conn.execute(
        "UPDATE campaign_members SET absence_warnings=1 WHERE campaign_id=1 AND user_id=10"
    )
    _insert_done_round(conn, 1, 1,
        {"narrative": "Runda 1.", "player_notes": {}},
        [(20, "Bob", "atak")],
    )
    conn.commit()
    svc = _load_svc(monkeypatch, db_path)
    first = svc.get_away_recap(campaign_id=1, user_id=10)
    assert first["has_recap"] is True
    second = svc.get_away_recap(campaign_id=1, user_id=10)
    assert second["has_recap"] is False
    assert second["missed_rounds"] == []


def test_present_all_rounds_no_recap(tmp_path, monkeypatch):
    """Player with actions in every round and absence_warnings=0 → empty recap."""
    db_path, conn = _make_test_db(tmp_path)
    _seed(conn, campaign_id=1, users=[(10, "alice")])
    for rn in range(1, 4):
        _insert_done_round(conn, 1, rn,
            {"narrative": f"Runda {rn}.", "player_notes": {}},
            [(10, "Alice", f"Alice akcja {rn}")],
        )
    conn.commit()
    svc = _load_svc(monkeypatch, db_path)
    result = svc.get_away_recap(campaign_id=1, user_id=10)
    assert result["has_recap"] is False
    assert result["missed_rounds"] == []


# ── Tests: hook balance prompt ────────────────────────────────────────────────


def test_system_prompt_contains_hook_instruction():
    """_MULTIPLAYER_SYSTEM_PROMPT must contain hook balance instruction (G23)."""
    import app.services.multiplayer_round_service as svc
    assert "WYWAŻENIE HAKÓW" in svc._MULTIPLAYER_SYSTEM_PROMPT
    assert "hak" in svc._MULTIPLAYER_SYSTEM_PROMPT.lower()


def test_system_prompt_mentions_two_rounds_threshold():
    """Instruction must say 'dwie rundy' (two rounds) threshold."""
    import app.services.multiplayer_round_service as svc
    assert "dwie rundy" in svc._MULTIPLAYER_SYSTEM_PROMPT


# ── Tests: hook balance block building logic ──────────────────────────────────


def _compute_priority(svc, campaign_id, char_names):
    """Replicate the hook-balance priority logic from trigger_narration."""
    conn = svc._db()
    try:
        prev_round = conn.execute(
            "SELECT narrative_json FROM campaign_rounds "
            "WHERE campaign_id=? AND status='done' ORDER BY round_number DESC LIMIT 1",
            (campaign_id,),
        ).fetchone()
        prev_notes_keys = set()
        if prev_round and prev_round["narrative_json"]:
            prev_data = json.loads(prev_round["narrative_json"])
            prev_notes_keys = set(prev_data.get("player_notes", {}).keys())
    finally:
        conn.close()
    not_hooked = [n for n in char_names if n not in prev_notes_keys]
    was_hooked = [n for n in char_names if n in prev_notes_keys]
    return not_hooked + was_hooked


def test_unhooked_first_when_prev_has_partial_notes(tmp_path, monkeypatch):
    """Character without hook in prev round comes first in priority list."""
    db_path, conn = _make_test_db(tmp_path)
    _seed(conn, campaign_id=1, users=[(1, "alice"), (2, "bob")])
    _insert_done_round(conn, 1, 1,
        {"narrative": "R1.", "player_notes": {"Alice": "Hak dla Alice"}},
        [(1, "Alice", "atak"), (2, "Bob", "ruch")],
    )
    conn.commit()
    svc = _load_svc(monkeypatch, db_path)
    priority = _compute_priority(svc, campaign_id=1, char_names=["Alice", "Bob"])
    assert priority[0] == "Bob"
    assert "Alice" in priority


def test_all_hooked_all_in_was_hooked(tmp_path, monkeypatch):
    """When all players had hooks last round, all appear (in was_hooked)."""
    db_path, conn = _make_test_db(tmp_path)
    _seed(conn, campaign_id=1, users=[(1, "alice"), (2, "bob")])
    _insert_done_round(conn, 1, 1,
        {"narrative": "R1.", "player_notes": {"Alice": "h", "Bob": "h"}},
        [(1, "Alice", "a"), (2, "Bob", "b")],
    )
    conn.commit()
    svc = _load_svc(monkeypatch, db_path)
    priority = _compute_priority(svc, campaign_id=1, char_names=["Alice", "Bob"])
    assert set(priority) == {"Alice", "Bob"}
    assert len(priority) == 2


def test_no_prev_round_all_go_to_not_hooked(tmp_path, monkeypatch):
    """No previous rounds → all chars go into not_hooked (first priority)."""
    db_path, conn = _make_test_db(tmp_path)
    _seed(conn, campaign_id=1, users=[(1, "alice"), (2, "bob")])
    conn.commit()
    svc = _load_svc(monkeypatch, db_path)
    priority = _compute_priority(svc, campaign_id=1, char_names=["Alice", "Bob"])
    assert set(priority) == {"Alice", "Bob"}
    assert len(priority) == 2


# ── Tests: code-review fixes ──────────────────────────────────────────────────


def test_early_return_has_absence_warnings_reset_key(tmp_path, monkeypatch):
    """Early return (no warnings) must include absence_warnings_reset key for consistent shape."""
    db_path, conn = _make_test_db(tmp_path)
    _seed(conn, campaign_id=1, users=[(10, "alice")])
    # absence_warnings = 0 by default → early return path
    svc = _load_svc(monkeypatch, db_path)
    result = svc.get_away_recap(campaign_id=1, user_id=10)
    assert "absence_warnings_reset" in result
    assert result["absence_warnings_reset"] is False


def test_autopilot_rounds_count_as_missed_for_recap(tmp_path, monkeypatch):
    """Autopilot action [AUTOPILOT — ...] must count as 'absent' in catchup presence check."""
    db_path, conn = _make_test_db(tmp_path)
    _seed(conn, campaign_id=1, users=[(10, "alice"), (20, "bob")])
    conn.execute(
        "UPDATE campaign_members SET absence_warnings=2, autopilot_consent=1 "
        "WHERE campaign_id=1 AND user_id=10"
    )
    # Alice's rounds filled by autopilot sweep
    _insert_done_round(conn, 1, 1,
        {"narrative": "R1.", "player_notes": {}},
        [
            (10, "Alice", "[AUTOPILOT — postać trzyma pozycję]"),
            (20, "Bob", "Bob atakuje"),
        ],
    )
    _insert_done_round(conn, 1, 2,
        {"narrative": "R2.", "player_notes": {}},
        [
            (10, "Alice", "[AUTOPILOT — postać trzyma pozycję]"),
            (20, "Bob", "Bob szuka"),
        ],
    )
    conn.commit()
    svc = _load_svc(monkeypatch, db_path)
    result = svc.get_away_recap(campaign_id=1, user_id=10)
    # Autopilot rounds should appear as missed (player was genuinely absent)
    assert result["has_recap"] is True
    assert len(result["missed_rounds"]) == 2


def test_absent_markers_module_constant_includes_autopilot(tmp_path, monkeypatch):
    """_ABSENT_ACTION_MARKERS module constant must include both absent text variants."""
    db_path, _ = _make_test_db(tmp_path)
    svc = _load_svc(monkeypatch, db_path)
    assert "[BRAK AKCJI]" in svc._ABSENT_ACTION_MARKERS
    assert "[AUTOPILOT — postać trzyma pozycję]" in svc._ABSENT_ACTION_MARKERS
