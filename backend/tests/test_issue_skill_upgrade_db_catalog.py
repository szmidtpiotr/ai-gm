"""Regression: skill upgrade must accept ANY skill in the live game_config_skills
catalog — the same source the sheet + advancement UI renders (/mechanics/skills).

Bug: _skill_known_in_catalog validated against config_service.get_runtime_config(),
which with USE_DB_CONFIG unset returns a 13-skill hardcoded default list. DB-only
skills (shield_block/dodge/endurance …) rendered in the UI but were rejected on
upgrade with "Unknown skill — must exist in game_config_skills catalog." The fix
validates against the DB table directly, restoring the display↔upgrade invariant.
"""
import sys
import os
import json
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DB_PATH = "/data/ai_gm.db"
_TEST_CHAR_BASE = 999_734


def _insert_char(char_id: int, xp: int = 5000, skills: dict | None = None):
    sheet = json.dumps({
        "archetype": "warrior", "level": 3,
        "current_hp": 20, "max_hp": 20,
        "xp_available": xp, "xp_lifetime_earned": xp + 200,
        "stats": {"STR": 12, "DEX": 10, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10},
        "skills": skills or {},
    })
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO characters
               (id, campaign_id, user_id, name, system_id, sheet_json)
               VALUES (?, NULL, 1, ?, 'v1', ?)""",
            (char_id, "[TEST_SKILLDB] warrior", sheet),
        )
        conn.commit()
    finally:
        conn.close()


def _cleanup(char_id: int):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM characters WHERE id = ?", (char_id,))
        conn.commit()
    finally:
        conn.close()


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def _db_only_skill_keys():
    """Keys present in game_config_skills but absent from the hardcoded default
    config — the exact set that used to render-but-reject."""
    from app.services import config_service
    default_keys = {s["key"] for s in config_service._default_config()["skills"]}
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("SELECT key FROM game_config_skills").fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows if r[0] not in default_keys]


# ─── Test 1: DB-only skill (shield_block) is upgradeable ──────────────────────

def test_db_only_skill_shield_block_upgradeable():
    """shield_block is in game_config_skills but not the default list → must upgrade."""
    char_id = _TEST_CHAR_BASE + 1
    _insert_char(char_id, xp=5000, skills={"shield_block": 0})
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-skill",
            json={"skill_key": "shield_block"},
        )
        assert resp.status_code == 200, (
            f"DB-only skill 'shield_block' odrzucony: {resp.status_code} {resp.text}"
        )
        assert resp.json().get("new_rank") == 1
    finally:
        _cleanup(char_id)


# ─── Test 2: every DB-only skill validates (none rejected as unknown) ─────────

def test_all_db_only_skills_pass_catalog_check():
    """No skill rendered by /mechanics/skills may be rejected as unknown_skill."""
    from app.services.xp_service import _skill_known_in_catalog
    db_only = _db_only_skill_keys()
    assert db_only, "Expected DB-only skills beyond the default list"
    rejected = [k for k in db_only if not _skill_known_in_catalog(k)]
    assert not rejected, f"Skills shown in UI but rejected on upgrade: {rejected}"


# ─── Test 3: legacy dice-test names stay rejected (#1052) ─────────────────────

def test_legacy_dice_test_names_still_rejected():
    """melee_attack/ranged_attack/spell_attack were removed from the table (#1052)
    and must NOT become upgradeable via the DB-table check."""
    from app.services.xp_service import _skill_known_in_catalog
    for legacy in ("melee_attack", "ranged_attack", "spell_attack", "sleight_of_hand"):
        assert not _skill_known_in_catalog(legacy), (
            f"Legacy skill '{legacy}' should stay rejected (#1052)"
        )


# ─── Test 4: bogus key rejected ───────────────────────────────────────────────

def test_bogus_skill_rejected():
    from app.services.xp_service import _skill_known_in_catalog
    assert not _skill_known_in_catalog("totally_not_a_skill_xyz")
