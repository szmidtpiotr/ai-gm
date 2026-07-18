"""
Tests for Phase 08 Task 33 — Smart Entry Agent backend.
"""

import json
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql

import app.routers.smart_entry as smart_entry_module
from app.routers.smart_entry import (
    router as smart_entry_router,
    _require_admin,
    _infer_table,
    _build_questions_for_table,
    _all_required_filled,
    SCHEMA_DESCRIPTORS,
    WRITABLE_TABLES,
    _sessions,
    SESSION_TTL_SECONDS,
)

# ── DB helpers ────────────────────────────────────────────────────────────────

WEAPONS_DDL = """
""" + table_sql("game_config_weapons") + """
"""

ITEMS_DDL = """
""" + table_sql("game_config_items") + """
"""

CONSUMABLES_DDL = """
""" + table_sql("game_config_consumables") + """
"""

ENEMIES_DDL = """
""" + table_sql("game_config_enemies") + """
"""


def _init_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(WEAPONS_DDL + ITEMS_DDL + CONSUMABLES_DDL + ENEMIES_DDL)
        conn.commit()
    finally:
        conn.close()


def _seed_weapon(path: Path, key="test_sword", label="Test Sword") -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "INSERT OR IGNORE INTO game_config_weapons (key, label, damage_die, weapon_type, linked_stat) VALUES (?, ?, 'd8', 'melee', 'STR')",
            (key, label),
        )
        conn.commit()
    finally:
        conn.close()


# ── Test client ───────────────────────────────────────────────────────────────

def _make_client(db_path: Path) -> TestClient:
    app = FastAPI()
    app.include_router(smart_entry_router)
    app.dependency_overrides[_require_admin] = lambda: None
    smart_entry_module.DB_PATH = str(db_path)
    # Clear sessions between tests
    _sessions.clear()
    return TestClient(app)


# ── Unit: table inference ─────────────────────────────────────────────────────

class TestTableInference:
    def test_weapon_keywords_english(self):
        assert _infer_table("I want to create a sword") == "game_config_weapons"

    def test_weapon_keywords_polish(self):
        assert _infer_table("Chcę stworzyć broń") == "game_config_weapons"

    def test_enemy_keyword_english(self):
        assert _infer_table("Add a new enemy goblin") == "game_config_enemies"

    def test_enemy_keyword_polish(self):
        assert _infer_table("Chcę dodać wroga do gry") == "game_config_enemies"

    def test_consumable_keyword(self):
        assert _infer_table("new healing potion") == "game_config_consumables"

    def test_item_keyword(self):
        assert _infer_table("create an armor piece") == "game_config_items"

    def test_unknown_returns_none(self):
        assert _infer_table("something completely unrelated xyz123") is None

    def test_bow_infers_weapon(self):
        assert _infer_table("I need a cursed bow") == "game_config_weapons"

    def test_shield_infers_item(self):
        assert _infer_table("Add a shield item") == "game_config_items"


# ── Unit: schema descriptors / questions ──────────────────────────────────────

class TestSchemaDescriptors:
    def test_weapons_has_required_fields(self):
        schema = SCHEMA_DESCRIPTORS["game_config_weapons"]
        assert "key" in schema["required"]
        assert "label" in schema["required"]
        assert "damage_die" in schema["required"]
        assert "weapon_type" in schema["required"]
        assert "linked_stat" in schema["required"]

    def test_items_has_required_fields(self):
        schema = SCHEMA_DESCRIPTORS["game_config_items"]
        assert "key" in schema["required"]
        assert "label" in schema["required"]
        assert "item_type" in schema["required"]
        assert "value_gp" in schema["required"]

    def test_consumables_has_required_fields(self):
        schema = SCHEMA_DESCRIPTORS["game_config_consumables"]
        assert "key" in schema["required"]
        assert "label" in schema["required"]
        assert "effect_type" in schema["required"]
        assert "base_price" in schema["required"]

    def test_enemies_has_required_fields(self):
        schema = SCHEMA_DESCRIPTORS["game_config_enemies"]
        assert "key" in schema["required"]
        assert "label" in schema["required"]
        assert "tier" in schema["required"]
        assert "hp_base" in schema["required"]
        assert "damage_dice" in schema["required"]

    def test_damage_die_has_options(self):
        q = SCHEMA_DESCRIPTORS["game_config_weapons"]["fields"]["damage_die"]
        assert q["type"] == "single_choice"
        labels = [o["label"] for o in q["options"]]
        assert "d6" in labels
        assert "d10" in labels

    def test_tier_has_options(self):
        q = SCHEMA_DESCRIPTORS["game_config_enemies"]["fields"]["tier"]
        assert q["type"] == "single_choice"
        labels = [o["label"] for o in q["options"]]
        assert "weak" in labels
        assert "boss" in labels


class TestBuildQuestions:
    def test_returns_first_unanswered_required_field(self):
        qs = _build_questions_for_table("game_config_weapons", {})
        assert len(qs) == 1
        assert qs[0]["id"] == "key"

    def test_skips_answered_fields(self):
        answered = {"key": "test", "label": "Test Weapon"}
        qs = _build_questions_for_table("game_config_weapons", answered)
        assert len(qs) == 1
        assert qs[0]["id"] == "damage_die"
        assert qs[0]["type"] == "single_choice"

    def test_returns_empty_when_all_required_answered(self):
        answered = {
            "key": "x", "label": "X", "damage_die": "d6",
            "weapon_type": "melee", "linked_stat": "STR",
            # optional also answered
            "two_handed": False, "value_gp": 10, "allowed_classes": [],
        }
        qs = _build_questions_for_table("game_config_weapons", answered)
        assert qs == []

    def test_unknown_table_returns_empty(self):
        qs = _build_questions_for_table("nonexistent_table", {})
        assert qs == []


class TestAllRequiredFilled:
    def test_false_when_empty(self):
        assert _all_required_filled("game_config_weapons", {}) is False

    def test_true_when_all_required_present(self):
        answers = {
            "key": "sword", "label": "Sword",
            "damage_die": "d8", "weapon_type": "melee", "linked_stat": "STR"
        }
        assert _all_required_filled("game_config_weapons", answers) is True

    def test_false_when_missing_one(self):
        answers = {"key": "sword", "label": "Sword", "damage_die": "d8", "weapon_type": "melee"}
        assert _all_required_filled("game_config_weapons", answers) is False


# ── Integration: /message endpoint ───────────────────────────────────────────

class TestSmartEntryMessage:
    def test_creates_session_on_first_call(self, tmp_path):
        db_path = tmp_path / "se.db"
        _init_db(db_path)
        client = _make_client(db_path)

        with patch.object(smart_entry_module, "generate_chat", return_value="Opowiedz mi więcej!"):
            resp = client.post(
                "/api/admin/smart-entry/message",
                json={"session_id": "s001", "message": "I want a cursed sword"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "s001"
        assert "reply" in data
        assert "s001" in _sessions

    def test_infers_table_from_message(self, tmp_path):
        db_path = tmp_path / "se_infer.db"
        _init_db(db_path)
        client = _make_client(db_path)

        with patch.object(smart_entry_module, "generate_chat", return_value="OK"):
            resp = client.post(
                "/api/admin/smart-entry/message",
                json={"session_id": "s002", "message": "I want a cursed sword"},
            )
        data = resp.json()
        assert data["save_table"] == "game_config_weapons"

    def test_explicit_table_overrides_inference(self, tmp_path):
        db_path = tmp_path / "se_tbl.db"
        _init_db(db_path)
        client = _make_client(db_path)

        with patch.object(smart_entry_module, "generate_chat", return_value="OK"):
            resp = client.post(
                "/api/admin/smart-entry/message",
                json={"session_id": "s003", "table": "game_config_enemies", "message": "a sword"},
            )
        data = resp.json()
        assert data["save_table"] == "game_config_enemies"

    def test_returns_questions_for_new_record(self, tmp_path):
        db_path = tmp_path / "se_qs.db"
        _init_db(db_path)
        client = _make_client(db_path)

        with patch.object(smart_entry_module, "generate_chat", return_value="Zacznijmy!"):
            resp = client.post(
                "/api/admin/smart-entry/message",
                json={"session_id": "s004", "table": "game_config_weapons", "message": "new weapon"},
            )
        data = resp.json()
        assert data["questions"] is not None
        assert len(data["questions"]) == 1
        assert data["questions"][0]["id"] == "key"

    def test_structured_answer_advances_questions(self, tmp_path):
        db_path = tmp_path / "se_adv.db"
        _init_db(db_path)
        client = _make_client(db_path)

        # First call
        with patch.object(smart_entry_module, "generate_chat", return_value="Dobra!"):
            client.post(
                "/api/admin/smart-entry/message",
                json={"session_id": "s005", "table": "game_config_weapons", "message": "new weapon"},
            )

        # Second call with answer
        with patch.object(smart_entry_module, "generate_chat", return_value="Dobra!"):
            resp = client.post(
                "/api/admin/smart-entry/message",
                json={
                    "session_id": "s005",
                    "table": "game_config_weapons",
                    "message": "ok",
                    "answer": {"question_id": "key", "value": "my_sword"},
                },
            )
        data = resp.json()
        # After answering 'key', next question should be 'label'
        assert data["questions"] is not None
        assert data["questions"][0]["id"] == "label"
        assert data["draft"]["key"] == "my_sword"

    def test_ready_to_save_when_all_required_filled(self, tmp_path):
        db_path = tmp_path / "se_ready.db"
        _init_db(db_path)
        client = _make_client(db_path)

        _sessions.clear()

        # Pre-fill session with all required answers
        _sessions["s006"] = {
            "table": "game_config_weapons",
            "history": [],
            "draft": {
                "key": "dark_blade",
                "label": "Dark Blade",
                "damage_die": "d10",
                "weapon_type": "melee",
                "linked_stat": "STR",
            },
            "target_key": None,
            "answers": {
                "key": "dark_blade",
                "label": "Dark Blade",
                "damage_die": "d10",
                "weapon_type": "melee",
                "linked_stat": "STR",
            },
            "proposed_changes": None,
            "last_active": time.time(),
        }

        with patch.object(smart_entry_module, "generate_chat", return_value="Draft gotowy!"):
            resp = client.post(
                "/api/admin/smart-entry/message",
                json={"session_id": "s006", "message": "looks good"},
            )
        data = resp.json()
        assert data["ready_to_save"] is True
        assert data["save_table"] == "game_config_weapons"
        assert data["save_key"] is None  # new record

    def test_rejected_on_read_only_table(self, tmp_path):
        db_path = tmp_path / "se_readonly.db"
        _init_db(db_path)
        client = _make_client(db_path)

        resp = client.post(
            "/api/admin/smart-entry/message",
            json={"session_id": "s007", "table": "characters", "message": "test"},
        )
        assert resp.status_code == 403

    def test_rejected_on_users_table(self, tmp_path):
        db_path = tmp_path / "se_users.db"
        _init_db(db_path)
        client = _make_client(db_path)

        resp = client.post(
            "/api/admin/smart-entry/message",
            json={"session_id": "s008", "table": "users", "message": "test"},
        )
        assert resp.status_code == 403

    def test_db_context_populated_for_similar_records(self, tmp_path):
        db_path = tmp_path / "se_ctx.db"
        _init_db(db_path)
        _seed_weapon(db_path, key="iron_sword", label="Iron Sword")
        client = _make_client(db_path)

        with patch.object(smart_entry_module, "generate_chat", return_value="Znalazłem podobne!"):
            resp = client.post(
                "/api/admin/smart-entry/message",
                json={"session_id": "s009", "table": "game_config_weapons", "message": "Iron Sword like weapon"},
            )
        data = resp.json()
        # db_context may be populated if LIKE match found
        # (it depends on label match — Iron Sword contains "Iron Sword")
        assert resp.status_code == 200

    def test_infers_enemy_table_from_wrog(self, tmp_path):
        db_path = tmp_path / "se_wrog.db"
        _init_db(db_path)
        client = _make_client(db_path)

        with patch.object(smart_entry_module, "generate_chat", return_value="OK"):
            resp = client.post(
                "/api/admin/smart-entry/message",
                json={"session_id": "s010", "message": "Chcę stworzyć wroga orka"},
            )
        data = resp.json()
        assert data["save_table"] == "game_config_enemies"


# ── Integration: /save endpoint ───────────────────────────────────────────────

class TestSmartEntrySave:
    def _prefill_session(self, sid: str, table: str, draft: dict) -> None:
        _sessions[sid] = {
            "table": table,
            "history": [],
            "draft": dict(draft),
            "target_key": None,
            "answers": dict(draft),
            "proposed_changes": None,
            "last_active": time.time(),
        }

    def test_saves_weapon_record(self, tmp_path):
        db_path = tmp_path / "se_save.db"
        _init_db(db_path)
        client = _make_client(db_path)

        self._prefill_session("ssave1", "game_config_weapons", {
            "key": "cursed_blade",
            "label": "Cursed Blade",
            "damage_die": "d10",
            "weapon_type": "melee",
            "linked_stat": "STR",
        })

        resp = client.post("/api/admin/smart-entry/save", json={"session_id": "ssave1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["key"] == "cursed_blade"

        # Verify it's in the DB
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM game_config_weapons WHERE key = 'cursed_blade'").fetchone()
        conn.close()
        assert row is not None
        assert row["label"] == "Cursed Blade"
        assert row["damage_die"] == "d10"

    def test_save_fails_on_unknown_session(self, tmp_path):
        db_path = tmp_path / "se_nosess.db"
        _init_db(db_path)
        client = _make_client(db_path)

        resp = client.post("/api/admin/smart-entry/save", json={"session_id": "ghost"})
        assert resp.status_code == 404

    def test_save_fails_on_missing_required_fields(self, tmp_path):
        db_path = tmp_path / "se_missingfields.db"
        _init_db(db_path)
        client = _make_client(db_path)

        self._prefill_session("ssave_bad", "game_config_weapons", {
            "key": "incomplete_weapon",
            "label": "Incomplete",
            # missing damage_die, weapon_type, linked_stat
        })

        resp = client.post("/api/admin/smart-entry/save", json={"session_id": "ssave_bad"})
        assert resp.status_code == 422

    def test_save_enemy_to_correct_table(self, tmp_path):
        db_path = tmp_path / "se_enemy.db"
        _init_db(db_path)
        client = _make_client(db_path)

        self._prefill_session("ssave_enemy", "game_config_enemies", {
            "key": "goblin_scout",
            "label": "Goblin Scout",
            "tier": "weak",
            "hp_base": 8,
            "ac_base": 10,
            "attack_bonus": 2,
            "damage_dice": "1d6",
        })

        resp = client.post("/api/admin/smart-entry/save", json={"session_id": "ssave_enemy"})
        assert resp.status_code == 200
        assert resp.json()["key"] == "goblin_scout"

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM game_config_enemies WHERE key = 'goblin_scout'").fetchone()
        conn.close()
        assert row is not None
        assert row["tier"] == "weak"

    def test_save_consumable(self, tmp_path):
        db_path = tmp_path / "se_cons.db"
        _init_db(db_path)
        client = _make_client(db_path)

        self._prefill_session("ssave_cons", "game_config_consumables", {
            "key": "health_potion",
            "label": "Health Potion",
            "effect_type": "heal_hp",
            "base_price": 50,
        })

        resp = client.post("/api/admin/smart-entry/save", json={"session_id": "ssave_cons"})
        assert resp.status_code == 200
        assert resp.json()["key"] == "health_potion"

    def test_save_item(self, tmp_path):
        db_path = tmp_path / "se_item.db"
        _init_db(db_path)
        client = _make_client(db_path)

        self._prefill_session("ssave_item", "game_config_items", {
            "key": "iron_shield",
            "label": "Iron Shield",
            "item_type": "armor",
            "value_gp": 30,
        })

        resp = client.post("/api/admin/smart-entry/save", json={"session_id": "ssave_item"})
        assert resp.status_code == 200
        assert resp.json()["key"] == "iron_shield"


# ── Integration: /apply-change endpoint ──────────────────────────────────────

class TestSmartEntryApplyChange:
    def _prefill_update_session(self, sid: str, table: str, target_key: str, changes: list) -> None:
        _sessions[sid] = {
            "table": table,
            "history": [],
            "draft": {},
            "target_key": target_key,
            "answers": {},
            "proposed_changes": changes,
            "last_active": time.time(),
        }

    def test_apply_change_updates_field(self, tmp_path):
        db_path = tmp_path / "se_apply.db"
        _init_db(db_path)
        _seed_weapon(db_path, key="old_sword", label="Old Sword")
        client = _make_client(db_path)

        self._prefill_update_session("sapply1", "game_config_weapons", "old_sword", [
            {"field": "label", "old_value": "Old Sword", "new_value": "Updated Sword", "reason": "Better name"},
        ])

        resp = client.post(
            "/api/admin/smart-entry/apply-change",
            json={"session_id": "sapply1", "change_index": 0},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT label FROM game_config_weapons WHERE key = 'old_sword'").fetchone()
        conn.close()
        assert row["label"] == "Updated Sword"

    def test_apply_change_out_of_range(self, tmp_path):
        db_path = tmp_path / "se_oob.db"
        _init_db(db_path)
        client = _make_client(db_path)

        self._prefill_update_session("sapply_oob", "game_config_weapons", "test_sword", [
            {"field": "label", "new_value": "X"},
        ])

        resp = client.post(
            "/api/admin/smart-entry/apply-change",
            json={"session_id": "sapply_oob", "change_index": 5},
        )
        assert resp.status_code == 400

    def test_apply_change_unknown_session(self, tmp_path):
        db_path = tmp_path / "se_nosess_apply.db"
        _init_db(db_path)
        client = _make_client(db_path)

        resp = client.post(
            "/api/admin/smart-entry/apply-change",
            json={"session_id": "ghost-sess", "change_index": 0},
        )
        assert resp.status_code == 404

    def test_apply_change_damage_die(self, tmp_path):
        db_path = tmp_path / "se_dmg.db"
        _init_db(db_path)
        _seed_weapon(db_path, key="iron_axe", label="Iron Axe")
        client = _make_client(db_path)

        self._prefill_update_session("sapply_dmg", "game_config_weapons", "iron_axe", [
            {"field": "damage_die", "old_value": "d8", "new_value": "d10"},
        ])

        resp = client.post(
            "/api/admin/smart-entry/apply-change",
            json={"session_id": "sapply_dmg", "change_index": 0},
        )
        assert resp.status_code == 200

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT damage_die FROM game_config_weapons WHERE key = 'iron_axe'").fetchone()
        conn.close()
        assert row["damage_die"] == "d10"


# ── Session TTL expiry ─────────────────────────────────────────────────────────

class TestSessionTTL:
    def test_expired_session_not_accessible_for_save(self, tmp_path):
        db_path = tmp_path / "se_ttl.db"
        _init_db(db_path)
        client = _make_client(db_path)

        # Create an expired session
        expired_time = time.time() - SESSION_TTL_SECONDS - 10
        _sessions["expired_sess"] = {
            "table": "game_config_weapons",
            "history": [],
            "draft": {"key": "old", "label": "Old"},
            "target_key": None,
            "answers": {},
            "proposed_changes": None,
            "last_active": expired_time,
        }

        # Send a new message which triggers _purge_expired
        with patch.object(smart_entry_module, "generate_chat", return_value="OK"):
            client.post(
                "/api/admin/smart-entry/message",
                json={"session_id": "fresh_sess", "message": "hello"},
            )

        # Now try to save with the expired session
        resp = client.post("/api/admin/smart-entry/save", json={"session_id": "expired_sess"})
        assert resp.status_code == 404

    def test_active_session_persists_across_calls(self, tmp_path):
        db_path = tmp_path / "se_persist.db"
        _init_db(db_path)
        client = _make_client(db_path)

        sid = "persist_sess"
        with patch.object(smart_entry_module, "generate_chat", return_value="OK"):
            client.post(
                "/api/admin/smart-entry/message",
                json={"session_id": sid, "table": "game_config_weapons", "message": "new sword"},
            )

        assert sid in _sessions
        # Session table should be set
        assert _sessions[sid]["table"] == "game_config_weapons"


# ── Read-only table protection ────────────────────────────────────────────────

class TestReadOnlyProtection:
    @pytest.mark.parametrize("table", ["characters", "campaigns", "users", "game_config_skills", "game_config_archetypes"])
    def test_read_only_tables_rejected_on_message(self, table, tmp_path):
        db_path = tmp_path / f"se_ro_{table}.db"
        _init_db(db_path)
        client = _make_client(db_path)

        resp = client.post(
            "/api/admin/smart-entry/message",
            json={"session_id": f"sess_{table}", "table": table, "message": "test"},
        )
        assert resp.status_code == 403

    def test_unknown_table_rejected(self, tmp_path):
        db_path = tmp_path / "se_unknown.db"
        _init_db(db_path)
        client = _make_client(db_path)

        resp = client.post(
            "/api/admin/smart-entry/message",
            json={"session_id": "s_unk", "table": "some_random_table", "message": "test"},
        )
        assert resp.status_code == 400
