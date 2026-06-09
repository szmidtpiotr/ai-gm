"""TDD: Issue #456 (SB-2) — scene_enemies/npcs/player_conditions must be populated.

Bug: get_world_state_flags() returns empty lists for scene_enemies, scene_npcs,
player_conditions even after combat starts/ends and conditions change.

Fix: sync these columns from live data (active_combat combatants + character sheet)
whenever combat starts, ends, or a snapshot is saved.
"""

import json
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.world_state_service import get_world_state_flags, set_world_state_flags

client = TestClient(app)

DB_PATH = "/data/ai_gm.db"

# ── Stable test fixtures ────────────────────────────────────────────────────
TEST_CAMPAIGN_ID = 999444
TEST_CHARACTER_ID = 999377
DEMO_USER_ID = 1

_cached_token = None


def _token():
    global _cached_token
    if not _cached_token:
        r = client.post("/api/auth/login", json={"username": "demo", "password": "demo"})
        assert r.status_code == 200
        _cached_token = r.json()["access_token"]
    return _cached_token


def _debug_cmd(text: str) -> dict:
    r = client.post(
        "/api/debug/command",
        json={"character_id": TEST_CHARACTER_ID, "user_id": DEMO_USER_ID, "text": text},
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert r.status_code == 200, f"debug cmd failed: {r.text[:200]}"
    return r.json()


def _read_game_sessions_columns(campaign_id: int) -> dict:
    """Directly read world-state columns from game_sessions table."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT scene_enemies, scene_npcs, active_quests, player_conditions
               FROM game_sessions WHERE campaign_id = ? LIMIT 1""",
            (campaign_id,),
        ).fetchone()
        if not row:
            return {}
        return {
            "scene_enemies": json.loads(row["scene_enemies"] or "[]"),
            "scene_npcs": json.loads(row["scene_npcs"] or "[]"),
            "active_quests": json.loads(row["active_quests"] or "[]"),
            "player_conditions": json.loads(row["player_conditions"] or "[]"),
        }
    finally:
        conn.close()


def _end_any_active_combat(campaign_id: int):
    """Ensure no active combat before test starts."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE active_combat SET status='ended', ended_reason='test_cleanup' "
            "WHERE campaign_id=? AND status='active'",
            (campaign_id,),
        )
        conn.commit()
    finally:
        conn.close()


def _clear_world_state(campaign_id: int):
    """Reset world-state columns to empty."""
    set_world_state_flags(
        campaign_id,
        scene_enemies=[],
        scene_npcs=[],
        active_quests=[],
        player_conditions=[],
        scene_cleared=False,
    )


# ── Tests ──────────────────────────────────────────────────────────────────


class TestSceneEnemiesSync:
    """scene_enemies must reflect active combat combatants."""

    @pytest.fixture(autouse=True)
    def reset(self):
        _end_any_active_combat(TEST_CAMPAIGN_ID)
        _clear_world_state(TEST_CAMPAIGN_ID)
        _debug_cmd("/debug set-state NARRATIVE")
        yield
        _end_any_active_combat(TEST_CAMPAIGN_ID)
        _clear_world_state(TEST_CAMPAIGN_ID)
        _debug_cmd("/debug set-state NARRATIVE")

    def test_scene_enemies_populated_after_combat_start(self):
        """
        RED: after initiate_combat, scene_enemies column must contain enemy entries.

        Before fix: scene_enemies == [] even after combat started.
        After fix: scene_enemies contains at least 1 entry with hp > 0.
        """
        from app.services.combat_service import initiate_combat

        # Start combat with a known test enemy
        combat = initiate_combat(TEST_CAMPAIGN_ID, TEST_CHARACTER_ID, ["goblin"])

        # Read world state columns directly
        ws = _read_game_sessions_columns(TEST_CAMPAIGN_ID)
        enemies = ws["scene_enemies"]

        assert len(enemies) > 0, (
            f"scene_enemies is still empty after combat start!\n"
            f"  Expected: at least 1 enemy entry\n"
            f"  Got: {enemies}\n"
            f"  Combat state: {json.dumps(combat, indent=2)[:400]}"
        )
        alive = [e for e in enemies if int(e.get("hp", 0)) > 0]
        assert len(alive) > 0, (
            f"scene_enemies has entries but all have hp=0!\n"
            f"  enemies: {enemies}"
        )

    def test_scene_enemies_cleared_after_combat_end(self):
        """
        RED: after end_combat, scene_enemies must be empty.

        Before fix: scene_enemies never gets set, so it's always empty.
        After fix: scene_enemies is populated during combat, cleared after.
        This test verifies the end→clear path specifically.
        """
        from app.services.combat_service import initiate_combat, end_combat

        initiate_combat(TEST_CAMPAIGN_ID, TEST_CHARACTER_ID, ["goblin"])

        # Verify it was set (pre-condition for meaningful end test)
        ws_during = _read_game_sessions_columns(TEST_CAMPAIGN_ID)
        assert len(ws_during["scene_enemies"]) > 0, (
            "Pre-condition failed: scene_enemies not set during combat "
            "(test_scene_enemies_populated_after_combat_start must pass first)"
        )

        end_combat(TEST_CAMPAIGN_ID, "victory")

        ws_after = _read_game_sessions_columns(TEST_CAMPAIGN_ID)
        assert ws_after["scene_enemies"] == [], (
            f"scene_enemies not cleared after combat ended!\n"
            f"  Got: {ws_after['scene_enemies']}"
        )


class TestPlayerConditionsSync:
    """player_conditions must reflect character sheet conditions."""

    @pytest.fixture(autouse=True)
    def reset(self):
        _clear_world_state(TEST_CAMPAIGN_ID)
        yield
        _clear_world_state(TEST_CAMPAIGN_ID)

    def _set_character_condition(self, condition_key: str):
        """Directly inject a condition into the character's sheet_json."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT sheet_json FROM characters WHERE id = ?", (TEST_CHARACTER_ID,)
            ).fetchone()
            sheet = json.loads(row["sheet_json"] or "{}")
            conds = sheet.get("conditions") or []
            if condition_key not in conds:
                conds.append(condition_key)
            sheet["conditions"] = conds
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), TEST_CHARACTER_ID),
            )
            conn.commit()
        finally:
            conn.close()

    def _clear_character_conditions(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT sheet_json FROM characters WHERE id = ?", (TEST_CHARACTER_ID,)
            ).fetchone()
            sheet = json.loads(row["sheet_json"] or "{}")
            sheet["conditions"] = []
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), TEST_CHARACTER_ID),
            )
            conn.commit()
        finally:
            conn.close()

    def test_player_conditions_synced_on_auto_save_snapshot(self):
        """
        RED: after auto_save_snapshot, player_conditions must contain active conditions.

        Before fix: player_conditions == [] even when character has conditions.
        After fix: player_conditions reflects character sheet conditions.
        """
        self._set_character_condition("stun")

        from app.services.world_state_service import auto_save_snapshot
        auto_save_snapshot(TEST_CAMPAIGN_ID)

        ws = _read_game_sessions_columns(TEST_CAMPAIGN_ID)
        assert "stun" in ws["player_conditions"], (
            f"player_conditions does not contain 'stun' after auto_save_snapshot!\n"
            f"  Got: {ws['player_conditions']}\n"
            f"  Expected 'stun' to be present"
        )

        self._clear_character_conditions()

    def test_player_conditions_cleared_when_character_has_none(self):
        """
        Backward compat: if character has no conditions, player_conditions must be [].
        """
        self._clear_character_conditions()

        from app.services.world_state_service import auto_save_snapshot
        auto_save_snapshot(TEST_CAMPAIGN_ID)

        ws = _read_game_sessions_columns(TEST_CAMPAIGN_ID)
        assert ws["player_conditions"] == [], (
            f"player_conditions should be [] when character has no conditions!\n"
            f"  Got: {ws['player_conditions']}"
        )
