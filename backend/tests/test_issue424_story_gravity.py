"""TDD: Issue #424 (E9) — Story Gravity escalation when a required beat stalls."""
import sys, os, json, sqlite3

sys.path.insert(0, "/app")

import pytest

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")
_CID = 999424


def _seed(turns_since_beat: int, beat_turn: int = 5):
    """Seed a campaign with a plan whose last beat fired at beat_turn, and
    enough campaign_turns so current_turn = beat_turn + turns_since_beat."""
    plan = {
        "schema_version": 2,
        "arcs": {"a1": {"id": "a1", "title": "Akt I", "status": "active",
                         "key_beats": [{"beat_key": "intro", "visited": True, "visited_at_turn": beat_turn}]}},
        "active_arc_id": "a1",
    }
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM campaign_turns WHERE campaign_id = ?", (_CID,))
        conn.execute("DELETE FROM campaigns WHERE id = ?", (_CID,))
        conn.execute(
            "INSERT INTO campaigns (id, title, system_id, owner_user_id, status, gm_plan_json) "
            "VALUES (?, 'SG', 'dnd', 1, 'active', ?)",
            (_CID, json.dumps(plan, ensure_ascii=False)),
        )
        current_turn = beat_turn + turns_since_beat
        for t in range(1, current_turn + 1):
            conn.execute(
                "INSERT INTO campaign_turns (campaign_id, character_id, user_text, route, turn_number) "
                "VALUES (?, 1, 'x', 'narrative', ?)",
                (_CID, t),
            )
        conn.commit()
    finally:
        conn.close()


def _cleanup():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM campaign_turns WHERE campaign_id = ?", (_CID,))
        conn.execute("DELETE FROM campaigns WHERE id = ?", (_CID,))
        conn.commit()
    finally:
        conn.close()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_config_defaults_l3_off():
    """Default thresholds 5/10/15 and L3 must be OFF by default."""
    from app.services.story_gravity_service import get_story_gravity_config
    cfg = get_story_gravity_config()
    assert cfg["turns_l1"] == 5
    assert cfg["turns_l2"] == 10
    assert cfg["turns_l3"] == 15
    assert cfg["l3_enabled"] is False, "L3 forced scene must be OFF by default"


def test_escalation_levels():
    """turns since beat → level: <5=0, 5-9=1, 10-14=2, 15+=2 (L3 off caps at 2)."""
    from app.services.story_gravity_service import compute_story_gravity
    for turns_since, expected in [(3, 0), (5, 1), (9, 1), (10, 2), (14, 2), (20, 2)]:
        _seed(turns_since)
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            try:
                g = compute_story_gravity(_CID, conn)
            finally:
                conn.close()
            assert g["level"] == expected, f"turns_since={turns_since}: level {g['level']} != {expected}"
            if expected >= 1:
                assert g["hint"], f"level {expected} must carry a hint"
        finally:
            _cleanup()


def test_l3_forced_scene_when_enabled():
    """With L3 enabled, 15+ turns reaches level 3 (forced scene)."""
    from app.services.story_gravity_service import compute_story_gravity, set_story_gravity_config
    set_story_gravity_config(l3_enabled=True)
    try:
        _seed(16)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            g = compute_story_gravity(_CID, conn)
        finally:
            conn.close()
        assert g["level"] == 3, f"L3 enabled + 16 turns → level 3, got {g['level']}"
    finally:
        _cleanup()
        set_story_gravity_config(l3_enabled=False)  # restore default


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_no_turns_no_escalation():
    """A campaign with no plan/turns must yield level 0 without raising."""
    from app.services.story_gravity_service import compute_story_gravity
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        g = compute_story_gravity(999999, conn)  # nonexistent campaign
    finally:
        conn.close()
    assert g["level"] == 0
    assert g["hint"] == ""
