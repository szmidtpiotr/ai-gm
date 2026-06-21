"""TDD #788 — G4: shared world state snapshot saved after MP round narration."""
import importlib
import json
import sqlite3
import sys
import os

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest

# ── Minimal schema ────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    system_id TEXT NOT NULL DEFAULT 'fantasy',
    model_id TEXT NOT NULL DEFAULT 'gpt-4',
    owner_user_id INTEGER NOT NULL,
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
    UNIQUE(campaign_id, user_id)
);
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    system_id TEXT NOT NULL DEFAULT 'fantasy',
    sheet_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active'
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
    character_id INTEGER,
    character_name TEXT NOT NULL,
    action_text TEXT NOT NULL,
    submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
    initiative_roll INTEGER NOT NULL DEFAULT 0,
    UNIQUE(round_id, user_id)
);
CREATE TABLE IF NOT EXISTS game_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL UNIQUE,
    scene_enemies TEXT,
    scene_npcs TEXT,
    scene_cleared INTEGER NOT NULL DEFAULT 0,
    active_quests TEXT,
    player_conditions TEXT,
    session_flags TEXT
);
CREATE TABLE IF NOT EXISTS world_state_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    turn_number INTEGER NOT NULL DEFAULT 0,
    snapshot_json TEXT NOT NULL DEFAULT '{}',
    snapshot_source TEXT NOT NULL DEFAULT 'auto',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS campaign_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    turn_number INTEGER NOT NULL DEFAULT 0
);
"""


def _make_test_db(tmp_path):
    db_path = str(tmp_path / "test_788.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return db_path, conn


def _setup_mp_campaign(conn):
    """2 players, 1 MP campaign, game_session with a goblin on scene."""
    conn.execute("INSERT INTO users (id, username) VALUES (101, 'aldric_player')")
    conn.execute("INSERT INTO users (id, username) VALUES (102, 'mira_player')")
    conn.execute(
        "INSERT INTO campaigns (id, title, owner_user_id, host_user_id, mode) "
        "VALUES (1, 'Drużyna', 101, 101, 'multiplayer')"
    )
    conn.execute("INSERT INTO campaign_members (campaign_id, user_id, status) VALUES (1, 101, 'accepted')")
    conn.execute("INSERT INTO campaign_members (campaign_id, user_id, status) VALUES (1, 102, 'accepted')")
    conn.execute("INSERT INTO characters (id, campaign_id, user_id, name) VALUES (11, 1, 101, 'Aldric')")
    conn.execute("INSERT INTO characters (id, campaign_id, user_id, name) VALUES (12, 1, 102, 'Mira')")
    # World state: goblin on scene (pre-existing state visible to both players)
    scene_enemies = json.dumps([{"key": "goblin", "name": "Goblin Wartownik"}])
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies, scene_npcs, active_quests, player_conditions) "
        "VALUES (1, ?, '[]', '[]', '[]')",
        (scene_enemies,),
    )
    # Round already in 'narrating' state (both players submitted)
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status) "
        "VALUES (1, 1, 1, 'narrating')"
    )
    conn.execute(
        "INSERT INTO campaign_round_actions "
        "(round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1, 1, 101, 11, 'Aldric', 'Atakuję goblina!')"
    )
    conn.execute(
        "INSERT INTO campaign_round_actions "
        "(round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1, 1, 102, 12, 'Mira', 'Rzucam Zasypij na goblina!')"
    )
    conn.commit()


_MOCK_NARRATIVE = {
    "narrative": "Aldric rusza na goblina z toporem. Mira rzuca zaklęcie snu. Goblin pada.",
    "roll_cues": [],
    "player_notes": {},
}


def _load_svc(monkeypatch, db_path: str):
    """Patch both services to use the test DB, mock LLM."""
    monkeypatch.setenv("AI_TEST_MODE", "1")
    monkeypatch.setenv("AI_TEST_DB_PATH", db_path)

    import app.services.multiplayer_round_service as svc
    import app.services.world_state_service as ws_svc
    importlib.reload(ws_svc)
    importlib.reload(svc)

    # Patch world_state_service DB_PATH for its direct sqlite3.connect calls
    monkeypatch.setattr(ws_svc, "DB_PATH", db_path)

    # Also patch the import inside multiplayer_round_service after reload
    def _patched_auto_save(campaign_id, source="auto"):
        ws_svc.auto_save_snapshot(campaign_id, source=source)

    def _patched_get_latest(campaign_id):
        return ws_svc.get_latest_snapshot(campaign_id)

    # Mock LLM driver to return canned response
    class MockDriver:
        def generate_chat(self, **kwargs):
            return json.dumps(_MOCK_NARRATIVE)

    import app.services.llm_service as llm_svc
    monkeypatch.setattr(llm_svc, "get_effective_config", lambda: {
        "provider": "openai", "base_url": "http://mock", "model": "mock", "api_key": "mock"
    })
    monkeypatch.setattr(llm_svc, "OpenAIDriver", MockDriver)

    return svc, ws_svc


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_trigger_narration_saves_world_state_snapshot(tmp_path, monkeypatch):
    """After trigger_narration, a world_state_snapshot must be saved for the campaign."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_mp_campaign(conn)
    conn.close()

    svc, ws_svc = _load_svc(monkeypatch, db_path)
    svc.trigger_narration(round_id=1)

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    snap = check.execute(
        "SELECT * FROM world_state_snapshots WHERE campaign_id = 1"
    ).fetchone()
    check.close()

    assert snap is not None, "trigger_narration must save a world_state_snapshot after narration"
    assert snap["campaign_id"] == 1
    assert snap["snapshot_source"] == "mp_round"


def test_world_state_context_included_in_narration_prompt(tmp_path, monkeypatch):
    """LLM prompt must include explicit world state section (not just player action text)."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_mp_campaign(conn)
    conn.close()

    captured_msgs = []

    class CapturingDriver:
        def generate_chat(self, messages=None, **kwargs):
            captured_msgs.extend(messages or [])
            return json.dumps(_MOCK_NARRATIVE)

    svc, ws_svc = _load_svc(monkeypatch, db_path)

    import app.services.llm_service as llm_svc
    monkeypatch.setattr(llm_svc, "OpenAIDriver", CapturingDriver)

    svc.trigger_narration(round_id=1)

    full_prompt = " ".join(m.get("content", "") for m in captured_msgs)
    # Must contain explicit world state section header — not just goblin from player action text
    assert "[STAN ŚWIATA]" in full_prompt or "Wrogowie w scenie" in full_prompt, \
        "trigger_narration must inject [STAN ŚWIATA] section into LLM prompt"


def test_snapshot_is_campaign_scoped_not_per_player(tmp_path, monkeypatch):
    """Snapshot must be keyed by campaign_id (shared between players), not per user."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_mp_campaign(conn)
    conn.close()

    svc, ws_svc = _load_svc(monkeypatch, db_path)
    svc.trigger_narration(round_id=1)

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row

    # Both players query the same campaign → same snapshot
    snap_for_all = check.execute(
        "SELECT campaign_id, COUNT(*) as cnt FROM world_state_snapshots "
        "WHERE campaign_id = 1 GROUP BY campaign_id"
    ).fetchone()
    # Must NOT have per-user rows (no user_id column in world_state_snapshots)
    cols = [d[0] for d in check.execute("PRAGMA table_info(world_state_snapshots)").fetchall()]
    check.close()

    assert snap_for_all is not None, "Snapshot must exist for campaign 1"
    assert snap_for_all["cnt"] >= 1, "At least 1 shared snapshot for campaign"
    assert "user_id" not in cols, "world_state_snapshots must NOT have user_id column (not per-player)"


def test_round_marked_done_after_narration(tmp_path, monkeypatch):
    """Existing behavior: round status must be 'done' after trigger_narration."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_mp_campaign(conn)
    conn.close()

    svc, ws_svc = _load_svc(monkeypatch, db_path)
    svc.trigger_narration(round_id=1)

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    row = check.execute("SELECT status, narrative_json FROM campaign_rounds WHERE id=1").fetchone()
    check.close()

    assert row["status"] == "done", f"Round must be 'done' after narration, got '{row['status']}'"
    assert row["narrative_json"] is not None, "narrative_json must be set after narration"
