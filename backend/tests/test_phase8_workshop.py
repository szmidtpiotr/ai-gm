"""
Tests for Phase 08 Tasks 30/31 — Ideas Workshop & Campaign Workshop backends.
"""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.routers.ideas_workshop as ideas_workshop_module
import app.routers.campaign_workshop as campaign_workshop_module
from app.routers.ideas_workshop import (
    router as ideas_router,
    _require_admin as ideas_require_admin,
    _extract_draft,
    _sessions as idea_sessions,
)
from app.routers.campaign_workshop import (
    router as campaign_router,
    _require_admin as campaign_require_admin,
    _extract_proposed_changes,
    _apply_change_to_plan,
    _sessions as campaign_sessions,
)

# ── DB helpers ────────────────────────────────────────────────────────────────

def _init_ideas_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS campaign_ideas (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                category        TEXT    NOT NULL,
                title           TEXT    NOT NULL,
                description     TEXT    NOT NULL DEFAULT '',
                structured_data TEXT    NOT NULL DEFAULT '{}',
                tags            TEXT    NOT NULL DEFAULT '[]',
                quality_rating  INTEGER NOT NULL DEFAULT 0,
                times_used      INTEGER NOT NULL DEFAULT 0,
                created_by      TEXT    NOT NULL DEFAULT 'system',
                created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
                review_status   TEXT    NOT NULL DEFAULT 'draft',
                cooldown_hours  INTEGER NOT NULL DEFAULT 0,
                is_active       INTEGER NOT NULL DEFAULT 1
            );
        """)
        conn.commit()
    finally:
        conn.close()


def _init_campaign_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                title           TEXT NOT NULL DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'active',
                owner_user_id   INTEGER,
                gm_plan_json    TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS campaign_turns (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                turn_number REAL NOT NULL DEFAULT 0,
                role        TEXT NOT NULL DEFAULT 'user',
                content     TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
    finally:
        conn.close()


def _seed_campaign(db_path: Path, title="Test Campaign", plan=None) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        plan_json = json.dumps(plan or {"acts": [{"title": "Act 1", "summary": "Beginning"}]})
        cur = conn.execute(
            "INSERT INTO campaigns (title, status, gm_plan_json) VALUES (?, 'active', ?)",
            (title, plan_json),
        )
        conn.commit()
        cid = cur.lastrowid
        # Seed a couple of turns
        for i in range(1, 4):
            conn.execute(
                "INSERT INTO campaign_turns (campaign_id, turn_number, role, content) VALUES (?, ?, ?, ?)",
                (cid, i, "user" if i % 2 else "assistant", f"Turn {i} content"),
            )
        conn.commit()
        return cid
    finally:
        conn.close()


# ── Clients ───────────────────────────────────────────────────────────────────

def _ideas_client(db_path: Path) -> TestClient:
    app = FastAPI()
    app.include_router(ideas_router)
    app.dependency_overrides[ideas_require_admin] = lambda: None
    ideas_workshop_module.DB_PATH = str(db_path)
    return TestClient(app)


def _campaign_client(db_path: Path) -> TestClient:
    app = FastAPI()
    app.include_router(campaign_router)
    app.dependency_overrides[campaign_require_admin] = lambda: None
    campaign_workshop_module.DB_PATH = str(db_path)
    return TestClient(app)


# ── Tests: draft extraction ───────────────────────────────────────────────────

class TestExtractDraft:
    def test_extracts_json_block_with_category(self):
        text = '```json\n{"category": "npc_concept", "title": "Hrothgar", "description": "A scarred mercenary"}\n```'
        draft, ready = _extract_draft(text)
        assert draft is not None
        assert draft["category"] == "npc_concept"
        assert draft["title"] == "Hrothgar"
        assert ready is False

    def test_ignores_json_block_without_category(self):
        text = '```json\n{"title": "No category here"}\n```'
        draft, ready = _extract_draft(text)
        assert draft is None
        assert ready is False

    def test_detects_ready_to_save_inline(self):
        inner = json.dumps({"category": "seed", "title": "Dark omen"})
        text = f'{{"READY_TO_SAVE": true, "draft": {inner}}}'
        draft, ready = _extract_draft(text)
        assert ready is True
        assert draft is not None
        assert draft["title"] == "Dark omen"

    def test_no_json_returns_none(self):
        draft, ready = _extract_draft("Just some plain text without JSON.")
        assert draft is None
        assert ready is False

    def test_malformed_json_returns_none(self):
        draft, ready = _extract_draft('```json\n{broken json\n```')
        assert draft is None
        assert ready is False


# ── Tests: proposed changes extraction ───────────────────────────────────────

class TestExtractProposedChanges:
    def test_extracts_list(self):
        text = (
            'Here are my suggestions:\n'
            '```json\n[{"field": "acts.0.title", "old_value": "Act 1", "new_value": "Dark Prologue", "reason": "More atmospheric"}]\n```'
        )
        changes = _extract_proposed_changes(text)
        assert changes is not None
        assert len(changes) == 1
        assert changes[0]["new_value"] == "Dark Prologue"

    def test_returns_none_if_no_block(self):
        changes = _extract_proposed_changes("No changes block here.")
        assert changes is None

    def test_returns_none_if_not_list(self):
        text = '```json\n{"not": "a list"}\n```'
        changes = _extract_proposed_changes(text)
        assert changes is None


# ── Tests: apply change to plan ───────────────────────────────────────────────

class TestApplyChangeToPlan:
    def test_simple_field(self):
        plan = {"title": "Old Title", "summary": "Summary"}
        result = _apply_change_to_plan(plan, {"field": "title", "new_value": "New Title"})
        assert result["title"] == "New Title"

    def test_nested_dot_path(self):
        plan = {"acts": [{"title": "Act 1"}]}
        result = _apply_change_to_plan(plan, {"field": "acts.0.title", "new_value": "Prologue"})
        assert result["acts"][0]["title"] == "Prologue"

    def test_invalid_path_leaves_plan_unchanged(self):
        plan = {"acts": [{"title": "Act 1"}]}
        result = _apply_change_to_plan(plan, {"field": "acts.99.title", "new_value": "Ghost"})
        # Should not crash; plan returned as-is or with partial change
        assert result["acts"][0]["title"] == "Act 1"


# ── Tests: workshop session / message endpoint ────────────────────────────────

class TestIdeasWorkshopMessage:
    def test_creates_session_and_returns_reply(self, tmp_path):
        db_path = tmp_path / "t30.db"
        _init_ideas_db(db_path)
        client = _ideas_client(db_path)

        with patch.object(
            ideas_workshop_module,
            "generate_chat",
            return_value="Opowiedz mi więcej o swoim pomyśle!",
        ):
            resp = client.post(
                "/api/admin/ideas/workshop/message",
                json={"session_id": "sess-001", "message": "Mam pomysł na mrocznego NPC."},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sess-001"
        assert "reply" in data
        assert data["draft"] is None
        assert data["ready_to_save"] is False

    def test_extracts_draft_from_llm_reply(self, tmp_path):
        db_path = tmp_path / "t30_draft.db"
        _init_ideas_db(db_path)
        client = _ideas_client(db_path)

        llm_reply = (
            'Świetny pomysł! Oto szkic:\n'
            '```json\n'
            '{"category": "npc_concept", "title": "Hrothgar Czarny", "description": "Zdegenerowany najemnik"}\n'
            '```'
        )

        with patch.object(ideas_workshop_module, "generate_chat", return_value=llm_reply):
            resp = client.post(
                "/api/admin/ideas/workshop/message",
                json={"session_id": "sess-002", "message": "Mroczny najemnik"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["draft"] is not None
        assert data["draft"]["category"] == "npc_concept"
        assert data["draft"]["title"] == "Hrothgar Czarny"
        assert data["ready_to_save"] is False

    def test_detects_ready_to_save(self, tmp_path):
        db_path = tmp_path / "t30_ready.db"
        _init_ideas_db(db_path)
        client = _ideas_client(db_path)

        draft = {"category": "seed", "title": "Dark Omen", "description": "An omen of doom"}
        llm_reply = json.dumps({"READY_TO_SAVE": True, "draft": draft})

        with patch.object(ideas_workshop_module, "generate_chat", return_value=llm_reply):
            resp = client.post(
                "/api/admin/ideas/workshop/message",
                json={"session_id": "sess-003", "message": "zapisz"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["ready_to_save"] is True
        assert data["draft"]["title"] == "Dark Omen"

    def test_history_preserved_across_messages(self, tmp_path):
        db_path = tmp_path / "t30_hist.db"
        _init_ideas_db(db_path)
        client = _ideas_client(db_path)
        sid = "sess-history"

        with patch.object(ideas_workshop_module, "generate_chat", return_value="Odpowiedź 1"):
            client.post(
                "/api/admin/ideas/workshop/message",
                json={"session_id": sid, "message": "Pierwsza wiadomość"},
            )

        with patch.object(ideas_workshop_module, "generate_chat", return_value="Odpowiedź 2") as mock_gen:
            client.post(
                "/api/admin/ideas/workshop/message",
                json={"session_id": sid, "message": "Druga wiadomość"},
            )
            # History should include both user turns + first assistant turn
            call_messages = mock_gen.call_args[1]["messages"] if mock_gen.call_args[1] else mock_gen.call_args[0][0]
            history_roles = [m["role"] for m in call_messages]
            assert "user" in history_roles
            assert "assistant" in history_roles


# ── Tests: ideas CRUD ─────────────────────────────────────────────────────────

class TestIdeasCRUD:
    def test_save_from_idea_data(self, tmp_path):
        db_path = tmp_path / "t30_save.db"
        _init_ideas_db(db_path)
        client = _ideas_client(db_path)

        idea = {"category": "location", "title": "Wieża Szaleńca", "description": "Opuszczona wieża maga"}
        resp = client.post("/api/admin/ideas/save", json={"idea_data": idea})

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert isinstance(data["id"], int)

    def test_save_from_session_draft(self, tmp_path):
        db_path = tmp_path / "t30_session_save.db"
        _init_ideas_db(db_path)
        client = _ideas_client(db_path)

        # First create a session with a draft
        llm_reply = '```json\n{"category": "encounter", "title": "Goblin Ambush"}\n```'
        with patch.object(ideas_workshop_module, "generate_chat", return_value=llm_reply):
            client.post(
                "/api/admin/ideas/workshop/message",
                json={"session_id": "sess-save", "message": "goblin encounter"},
            )

        resp = client.post("/api/admin/ideas/save", json={"session_id": "sess-save"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_save_missing_category_fails(self, tmp_path):
        db_path = tmp_path / "t30_nocat.db"
        _init_ideas_db(db_path)
        client = _ideas_client(db_path)

        resp = client.post("/api/admin/ideas/save", json={"idea_data": {"title": "Missing category"}})
        assert resp.status_code == 422

    def test_save_missing_title_fails(self, tmp_path):
        db_path = tmp_path / "t30_notitle.db"
        _init_ideas_db(db_path)
        client = _ideas_client(db_path)

        resp = client.post("/api/admin/ideas/save", json={"idea_data": {"category": "seed"}})
        assert resp.status_code == 422

    def test_list_ideas_returns_saved(self, tmp_path):
        db_path = tmp_path / "t30_list.db"
        _init_ideas_db(db_path)
        client = _ideas_client(db_path)

        client.post("/api/admin/ideas/save", json={"idea_data": {"category": "seed", "title": "Omen A"}})
        client.post("/api/admin/ideas/save", json={"idea_data": {"category": "location", "title": "Cave B"}})

        resp = client.get("/api/admin/ideas")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2

    def test_list_filter_by_category(self, tmp_path):
        db_path = tmp_path / "t30_filter.db"
        _init_ideas_db(db_path)
        client = _ideas_client(db_path)

        client.post("/api/admin/ideas/save", json={"idea_data": {"category": "seed", "title": "Seed Idea"}})
        client.post("/api/admin/ideas/save", json={"idea_data": {"category": "npc_concept", "title": "NPC"}})

        resp = client.get("/api/admin/ideas?category=seed")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["category"] == "seed" for i in items)

    def test_patch_idea_updates_fields(self, tmp_path):
        db_path = tmp_path / "t30_patch.db"
        _init_ideas_db(db_path)
        client = _ideas_client(db_path)

        save_resp = client.post(
            "/api/admin/ideas/save",
            json={"idea_data": {"category": "seed", "title": "Original Title"}},
        )
        idea_id = save_resp.json()["id"]

        patch_resp = client.patch(
            f"/api/admin/ideas/{idea_id}",
            json={"quality_rating": 4, "title": "Updated Title"},
        )
        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data["quality_rating"] == 4
        assert data["title"] == "Updated Title"

    def test_patch_nonexistent_idea_returns_404(self, tmp_path):
        db_path = tmp_path / "t30_patch404.db"
        _init_ideas_db(db_path)
        client = _ideas_client(db_path)

        resp = client.patch("/api/admin/ideas/9999", json={"quality_rating": 3})
        assert resp.status_code == 404

    def test_delete_idea_soft_deletes(self, tmp_path):
        db_path = tmp_path / "t30_del.db"
        _init_ideas_db(db_path)
        client = _ideas_client(db_path)

        save_resp = client.post(
            "/api/admin/ideas/save",
            json={"idea_data": {"category": "seed", "title": "To Delete"}},
        )
        idea_id = save_resp.json()["id"]

        del_resp = client.delete(f"/api/admin/ideas/{idea_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["ok"] is True

        # Should no longer appear in active listing
        list_resp = client.get("/api/admin/ideas?active_only=true")
        ids = [i["id"] for i in list_resp.json()["items"]]
        assert idea_id not in ids

    def test_delete_nonexistent_returns_404(self, tmp_path):
        db_path = tmp_path / "t30_del404.db"
        _init_ideas_db(db_path)
        client = _ideas_client(db_path)

        resp = client.delete("/api/admin/ideas/9999")
        assert resp.status_code == 404


# ── Tests: campaign workshop ───────────────────────────────────────────────────

class TestCampaignWorkshop:
    def test_message_returns_reply(self, tmp_path):
        db_path = tmp_path / "t31.db"
        _init_campaign_db(db_path)
        cid = _seed_campaign(db_path)
        client = _campaign_client(db_path)

        with patch.object(
            campaign_workshop_module,
            "generate_chat",
            return_value="Oto moje sugestie dotyczące kampanii.",
        ):
            resp = client.post(
                f"/api/admin/campaigns/{cid}/workshop/message",
                json={"session_id": "camp-sess-001", "message": "Jak poprawić akt pierwszy?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "camp-sess-001"
        assert "reply" in data
        assert data["proposed_changes"] is None

    def test_extracts_proposed_changes(self, tmp_path):
        db_path = tmp_path / "t31_changes.db"
        _init_campaign_db(db_path)
        cid = _seed_campaign(db_path)
        client = _campaign_client(db_path)

        llm_reply = (
            'Proponuję następujące zmiany:\n'
            '```json\n'
            '[{"field": "acts.0.title", "old_value": "Act 1", "new_value": "Mroczny Prolog", "reason": "Bardziej dramatyczny"}]\n'
            '```'
        )

        with patch.object(campaign_workshop_module, "generate_chat", return_value=llm_reply):
            resp = client.post(
                f"/api/admin/campaigns/{cid}/workshop/message",
                json={"session_id": "camp-sess-002", "message": "zaproponuj zmiany"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["proposed_changes"] is not None
        assert len(data["proposed_changes"]) == 1
        assert data["proposed_changes"][0]["new_value"] == "Mroczny Prolog"

    def test_apply_change_updates_campaign_plan(self, tmp_path):
        db_path = tmp_path / "t31_apply.db"
        _init_campaign_db(db_path)
        cid = _seed_campaign(db_path, plan={"acts": [{"title": "Act 1", "summary": "Old summary"}]})
        client = _campaign_client(db_path)

        llm_reply = (
            '```json\n'
            '[{"field": "acts.0.title", "old_value": "Act 1", "new_value": "Nowy Tytuł", "reason": "Test"}]\n'
            '```'
        )

        with patch.object(campaign_workshop_module, "generate_chat", return_value=llm_reply):
            client.post(
                f"/api/admin/campaigns/{cid}/workshop/message",
                json={"session_id": "camp-apply-sess", "message": "zaproponuj"},
            )

        apply_resp = client.post(
            f"/api/admin/campaigns/{cid}/workshop/apply",
            json={"session_id": "camp-apply-sess", "change_index": 0},
        )
        assert apply_resp.status_code == 200
        assert apply_resp.json()["ok"] is True

        # Verify the plan was actually updated in DB
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT gm_plan_json FROM campaigns WHERE id = ?", (cid,)).fetchone()
        conn.close()
        plan = json.loads(row["gm_plan_json"])
        assert plan["acts"][0]["title"] == "Nowy Tytuł"

    def test_apply_with_out_of_range_index_fails(self, tmp_path):
        db_path = tmp_path / "t31_oob.db"
        _init_campaign_db(db_path)
        cid = _seed_campaign(db_path)
        client = _campaign_client(db_path)

        llm_reply = '```json\n[{"field": "title", "new_value": "X"}]\n```'
        with patch.object(campaign_workshop_module, "generate_chat", return_value=llm_reply):
            client.post(
                f"/api/admin/campaigns/{cid}/workshop/message",
                json={"session_id": "oob-sess", "message": "go"},
            )

        resp = client.post(
            f"/api/admin/campaigns/{cid}/workshop/apply",
            json={"session_id": "oob-sess", "change_index": 99},
        )
        assert resp.status_code == 400

    def test_apply_with_unknown_session_fails(self, tmp_path):
        db_path = tmp_path / "t31_nosess.db"
        _init_campaign_db(db_path)
        cid = _seed_campaign(db_path)
        client = _campaign_client(db_path)

        resp = client.post(
            f"/api/admin/campaigns/{cid}/workshop/apply",
            json={"session_id": "ghost-session", "change_index": 0},
        )
        assert resp.status_code == 404

    def test_message_on_nonexistent_campaign_returns_404(self, tmp_path):
        db_path = tmp_path / "t31_nocampaign.db"
        _init_campaign_db(db_path)
        client = _campaign_client(db_path)

        with patch.object(campaign_workshop_module, "generate_chat", return_value="reply"):
            resp = client.post(
                "/api/admin/campaigns/9999/workshop/message",
                json={"session_id": "x", "message": "hello"},
            )
        assert resp.status_code == 404
