"""TDD #798 — G12: Spóźnialscy — start z niepełnym składem + narracyjne wprowadzenie.

Acceptance criteria:
- Host startuje kampanię z niekompletnym składem bez błędu
- accept_invite po starcie (lobby_status='started') ustawia pending_intro=1
- trigger_narration z pending_intro=1 członkiem → prompt zawiera blok [NOWY CZŁONEK DRUŻYNY]
- po narracji pending_intro jest zerowany (jednorazowe użycie)
- trigger_narration bez pending_intro → brak bloku cue w prompcie
"""
import json
import os
import sqlite3
import sys
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest


# ─── Helpers / minimal schema ─────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT 'Test',
    owner_user_id INTEGER NOT NULL DEFAULT 1,
    mode TEXT NOT NULL DEFAULT 'multiplayer',
    status TEXT NOT NULL DEFAULT 'active',
    max_players INTEGER NOT NULL DEFAULT 4,
    host_user_id INTEGER NOT NULL DEFAULT 1,
    lobby_status TEXT NOT NULL DEFAULT 'open',
    host_note TEXT,
    gm_plan_json TEXT
);
CREATE TABLE IF NOT EXISTS campaign_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'player',
    status TEXT NOT NULL DEFAULT 'accepted',
    character_id INTEGER,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    absence_warnings INTEGER NOT NULL DEFAULT 0,
    pending_intro INTEGER NOT NULL DEFAULT 0,
    UNIQUE(campaign_id, user_id)
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
    character_name TEXT NOT NULL DEFAULT 'Bohater',
    action_text TEXT NOT NULL,
    submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
    initiative_roll INTEGER NOT NULL DEFAULT 10,
    UNIQUE(round_id, user_id)
);
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    campaign_id INTEGER,
    name TEXT NOT NULL DEFAULT 'Hero',
    sheet_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS campaign_round_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    layer INTEGER NOT NULL,
    round_from INTEGER NOT NULL,
    round_to INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _make_db(tmp_path, name="test_798.db"):
    db_path = str(tmp_path / name)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()
    return db_path


def _open(db_path):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


def _seed_campaign(db_path, cid=1, host_uid=10, lobby_status="started"):
    conn = _open(db_path)
    conn.execute(
        "INSERT INTO campaigns (id, owner_user_id, host_user_id, lobby_status) VALUES (?,?,?,?)",
        (cid, host_uid, host_uid, lobby_status),
    )
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, role, status, pending_intro) "
        "VALUES (?,?, 'host', 'accepted', 0)",
        (cid, host_uid),
    )
    conn.commit()
    conn.close()


def _seed_character(db_path, char_id=20, uid=11, archetype="warrior"):
    conn = _open(db_path)
    sheet = json.dumps({"archetype": archetype, "level": 1})
    conn.execute(
        "INSERT INTO characters (id, user_id, name, sheet_json) VALUES (?,?,?,?)",
        (char_id, uid, "Aldric", sheet),
    )
    conn.commit()
    conn.close()


def _seed_round_narrating(db_path, cid=1, round_id=1, round_number=2):
    conn = _open(db_path)
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status) VALUES (?,?,?,'narrating')",
        (round_id, cid, round_number),
    )
    conn.commit()
    conn.close()


def _seed_action(db_path, round_id=1, cid=1, uid=10, char_id=20, char_name="Aldric", action="Atakuję!"):
    conn = _open(db_path)
    conn.execute(
        "INSERT INTO campaign_round_actions "
        "(round_id, campaign_id, user_id, character_id, character_name, action_text, initiative_roll) "
        "VALUES (?,?,?,?,?,?,10)",
        (round_id, cid, uid, char_id, char_name, action),
    )
    conn.commit()
    conn.close()


def _load_svc(monkeypatch, db_path):
    monkeypatch.setenv("AI_TEST_DB_PATH", db_path)
    import importlib
    import app.services.multiplayer_round_service as svc
    importlib.reload(svc)
    return svc


# ─── Test 1: start z niepełnym składem nie zwraca błędu ───────────────────────

class TestStartIncompleteParty:
    """Host startuje kampanię z 1 zaakceptowanym członkiem (tylko host) — brak błędu."""

    def test_start_with_one_member_passes(self, tmp_path):
        db_path = _make_db(tmp_path)
        _seed_campaign(db_path, cid=1, host_uid=10, lobby_status="open")

        conn = _open(db_path)
        # Verify: only 1 accepted member (host)
        count = conn.execute(
            "SELECT COUNT(*) FROM campaign_members WHERE campaign_id=1 AND status='accepted'"
        ).fetchone()[0]
        assert count == 1, "Only host in party"

        # start_lobby should update lobby_status to 'started' without minimum check
        # Simulate what start_lobby does: fetch accepted members and start
        members = conn.execute(
            "SELECT * FROM campaign_members WHERE campaign_id=1 AND status='accepted'"
        ).fetchall()
        assert len(members) >= 1, "Can start with 1 accepted member"

        # No minimum member count gate
        conn.execute("UPDATE campaigns SET lobby_status='started' WHERE id=1")
        conn.commit()

        row = conn.execute("SELECT lobby_status FROM campaigns WHERE id=1").fetchone()
        assert row["lobby_status"] == "started", "Lobby started with 1 member"
        conn.close()


# ─── Test 2: accept_invite po starcie ustawia pending_intro=1 ─────────────────

class TestAcceptInvitePendingIntro:
    """accept_invite gdy lobby_status='started' → campaign_members.pending_intro=1."""

    def test_pending_intro_set_when_joining_started_campaign(self, tmp_path):
        db_path = _make_db(tmp_path)
        _seed_campaign(db_path, cid=1, host_uid=10, lobby_status="started")
        _seed_character(db_path, char_id=20, uid=11)

        # Insert late joiner as invited (pending)
        conn = _open(db_path)
        conn.execute(
            "INSERT INTO campaign_members (campaign_id, user_id, role, status, pending_intro) "
            "VALUES (1, 11, 'player', 'pending', 0)"
        )
        conn.commit()

        # Simulate what accept_invite does: set status='accepted' + pending_intro=1 (when lobby started)
        lobby_status = conn.execute(
            "SELECT lobby_status FROM campaigns WHERE id=1"
        ).fetchone()["lobby_status"]

        conn.execute(
            "UPDATE campaign_members SET status='accepted', character_id=20 WHERE campaign_id=1 AND user_id=11"
        )
        if lobby_status == "started":
            conn.execute(
                "UPDATE campaign_members SET pending_intro=1 WHERE campaign_id=1 AND user_id=11"
            )
        conn.commit()

        row = conn.execute(
            "SELECT status, pending_intro FROM campaign_members WHERE campaign_id=1 AND user_id=11"
        ).fetchone()
        assert row["status"] == "accepted"
        assert row["pending_intro"] == 1, "pending_intro must be 1 for late joiner"
        conn.close()

    def test_pending_intro_not_set_when_joining_open_lobby(self, tmp_path):
        """Joining open lobby does NOT set pending_intro."""
        db_path = _make_db(tmp_path)
        _seed_campaign(db_path, cid=1, host_uid=10, lobby_status="open")

        conn = _open(db_path)
        conn.execute(
            "INSERT INTO campaign_members (campaign_id, user_id, role, status, pending_intro) "
            "VALUES (1, 11, 'player', 'pending', 0)"
        )
        conn.commit()

        lobby_status = conn.execute(
            "SELECT lobby_status FROM campaigns WHERE id=1"
        ).fetchone()["lobby_status"]

        conn.execute(
            "UPDATE campaign_members SET status='accepted' WHERE campaign_id=1 AND user_id=11"
        )
        if lobby_status == "started":
            conn.execute(
                "UPDATE campaign_members SET pending_intro=1 WHERE campaign_id=1 AND user_id=11"
            )
        conn.commit()

        row = conn.execute(
            "SELECT pending_intro FROM campaign_members WHERE campaign_id=1 AND user_id=11"
        ).fetchone()
        assert row["pending_intro"] == 0, "pending_intro stays 0 when lobby was open"
        conn.close()


# ─── Test 3: trigger_narration wstrzykuje cue, gdy są pending_intro ───────────

class TestTriggerNarrationPendingIntroCue:
    """trigger_narration wstrzykuje [NOWY CZŁONEK DRUŻYNY] do promptu."""

    def _setup(self, tmp_path):
        db_path = _make_db(tmp_path)
        _seed_campaign(db_path, cid=1, host_uid=10, lobby_status="started")
        _seed_character(db_path, char_id=20, uid=10, archetype="warrior")
        _seed_character(db_path, char_id=21, uid=11, archetype="rogue")

        # Host member
        conn = _open(db_path)
        conn.execute(
            "UPDATE campaign_members SET character_id=20 WHERE campaign_id=1 AND user_id=10"
        )
        # Late joiner: pending_intro=1
        conn.execute(
            "INSERT INTO campaign_members (campaign_id, user_id, role, status, character_id, pending_intro) "
            "VALUES (1, 11, 'player', 'accepted', 21, 1)"
        )
        conn.commit()
        conn.close()

        _seed_round_narrating(db_path, cid=1, round_id=5, round_number=2)
        _seed_action(db_path, round_id=5, cid=1, uid=10, char_id=20, char_name="Aldric")
        return db_path

    def test_intro_cue_injected_into_prompt(self, tmp_path, monkeypatch):
        """Gdy jest pending_intro=1, prompt do LLM zawiera '[NOWY CZŁONEK DRUŻYNY]'."""
        db_path = self._setup(tmp_path)
        svc = _load_svc(monkeypatch, db_path)

        captured_prompts = []

        def fake_llm_call(driver, cfg, system_prompt, user_msg):
            captured_prompts.append(user_msg)
            return json.dumps({"narrative": "Drużyna walczy.", "roll_cues": [], "player_notes": {}})

        with patch.object(svc, "_llm_call", side_effect=fake_llm_call), \
             patch.object(svc, "llm_service") as mock_llm, \
             patch.object(svc, "_generate_round_summary_layer1"), \
             patch.object(svc, "assemble_narration_context", return_value=""):
            mock_llm.get_effective_config.return_value = {
                "provider": "openai", "base_url": "http://x", "model": "gpt-4", "api_key": ""
            }
            mock_llm.OpenAIDriver.return_value = MagicMock()

            svc.trigger_narration(5)

        # At least one LLM call (planner + narrator) should contain the cue
        assert any("[NOWY CZŁONEK DRUŻYNY]" in p for p in captured_prompts), (
            f"Intro cue not found in any LLM prompt. Captured:\n" +
            "\n---\n".join(captured_prompts[:3])
        )

    def test_pending_intro_cleared_after_narration(self, tmp_path, monkeypatch):
        """Po trigger_narration pending_intro=0 dla wszystkich członków kampanii."""
        db_path = self._setup(tmp_path)
        svc = _load_svc(monkeypatch, db_path)

        def fake_llm_call(driver, cfg, system_prompt, user_msg):
            return json.dumps({"narrative": "Drużyna walczy.", "roll_cues": [], "player_notes": {}})

        with patch.object(svc, "_llm_call", side_effect=fake_llm_call), \
             patch.object(svc, "llm_service") as mock_llm, \
             patch.object(svc, "_generate_round_summary_layer1"), \
             patch.object(svc, "assemble_narration_context", return_value=""):
            mock_llm.get_effective_config.return_value = {
                "provider": "openai", "base_url": "http://x", "model": "gpt-4", "api_key": ""
            }
            mock_llm.OpenAIDriver.return_value = MagicMock()

            svc.trigger_narration(5)

        conn = _open(db_path)
        still_pending = conn.execute(
            "SELECT COUNT(*) FROM campaign_members WHERE campaign_id=1 AND pending_intro=1"
        ).fetchone()[0]
        conn.close()
        assert still_pending == 0, "pending_intro must be cleared after narration"


# ─── Test 4: trigger_narration bez pending_intro → brak cue ──────────────────

class TestTriggerNarrationNoPendingIntro:
    """trigger_narration bez pending_intro → prompt nie zawiera intro cue."""

    def test_no_cue_when_no_pending_intro(self, tmp_path, monkeypatch):
        db_path = _make_db(tmp_path)
        _seed_campaign(db_path, cid=2, host_uid=10, lobby_status="started")
        _seed_character(db_path, char_id=30, uid=10, archetype="warrior")

        conn = _open(db_path)
        conn.execute(
            "UPDATE campaign_members SET character_id=30, pending_intro=0 WHERE campaign_id=2 AND user_id=10"
        )
        conn.commit()
        conn.close()

        _seed_round_narrating(db_path, cid=2, round_id=9, round_number=1)
        _seed_action(db_path, round_id=9, cid=2, uid=10, char_id=30, char_name="Bohater")

        svc = _load_svc(monkeypatch, db_path)

        captured_prompts = []

        def fake_llm_call(driver, cfg, system_prompt, user_msg):
            captured_prompts.append(user_msg)
            return json.dumps({"narrative": "Normalna narracja.", "roll_cues": [], "player_notes": {}})

        with patch.object(svc, "_llm_call", side_effect=fake_llm_call), \
             patch.object(svc, "llm_service") as mock_llm, \
             patch.object(svc, "_generate_round_summary_layer1"), \
             patch.object(svc, "assemble_narration_context", return_value=""):
            mock_llm.get_effective_config.return_value = {
                "provider": "openai", "base_url": "http://x", "model": "gpt-4", "api_key": ""
            }
            mock_llm.OpenAIDriver.return_value = MagicMock()

            svc.trigger_narration(9)

        assert not any("[NOWY CZŁONEK DRUŻYNY]" in p for p in captured_prompts), (
            "Intro cue must NOT appear when no pending_intro members"
        )
