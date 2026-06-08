"""TDD: Issue #421 (E6) — ARC_ADVANCE tag advances the active GM-plan arc."""
import sys, os, json, sqlite3

sys.path.insert(0, "/app")

import pytest

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")
_CID = 999421   # synthetic campaign id

_PLAN = {
    "schema_version": 2,
    "arcs": {
        "arc1": {"id": "arc1", "title": "Akt I", "status": "active", "scene_goals": [], "hooks": {}},
        "arc2": {"id": "arc2", "title": "Akt II", "status": "draft", "scene_goals": [], "hooks": {}},
    },
    "active_arc_id": "arc1",
    "engine_private": {},
}


def _seed_plan():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM campaigns WHERE id = ?", (_CID,))
        conn.execute(
            "INSERT INTO campaigns (id, title, system_id, owner_user_id, status, gm_plan_json) "
            "VALUES (?, 'ArcTest', 'dnd', 1, 'active', ?)",
            (_CID, json.dumps(_PLAN, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


def _cleanup():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM campaigns WHERE id = ?", (_CID,))
        conn.commit()
    finally:
        conn.close()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_advance_arc_to_named_arc():
    """advance_arc(arc2) → arc2 active, arc1 closed, active_arc_id=arc2."""
    from app.services.campaign_plan_runtime import advance_arc
    _seed_plan()
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            changed = advance_arc(_CID, "arc2", conn)
        finally:
            conn.close()
        assert changed is True, "advance_arc should report a change"
        conn = sqlite3.connect(DB_PATH)
        try:
            raw = conn.execute("SELECT gm_plan_json FROM campaigns WHERE id = ?", (_CID,)).fetchone()[0]
        finally:
            conn.close()
        plan = json.loads(raw)
        assert plan["active_arc_id"] == "arc2", f"active_arc_id: {plan['active_arc_id']}"
        assert plan["arcs"]["arc2"]["status"] == "active", f"arc2: {plan['arcs']['arc2']}"
        assert plan["arcs"]["arc1"]["status"] == "closed", f"arc1: {plan['arcs']['arc1']}"
    finally:
        _cleanup()


def test_advance_arc_unknown_arc_noop():
    """advance_arc to a non-existent arc must not change the active arc."""
    from app.services.campaign_plan_runtime import advance_arc
    _seed_plan()
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            changed = advance_arc(_CID, "nope", conn)
        finally:
            conn.close()
        assert changed is False, "unknown arc should be a no-op"
        conn = sqlite3.connect(DB_PATH)
        try:
            raw = conn.execute("SELECT gm_plan_json FROM campaigns WHERE id = ?", (_CID,)).fetchone()[0]
        finally:
            conn.close()
        plan = json.loads(raw)
        assert plan["active_arc_id"] == "arc1", "active arc must stay arc1"
    finally:
        _cleanup()


def test_arc_advance_tag_regex():
    """The [ARC_ADVANCE: key] tag must be parseable by the shared regex helper."""
    from app.services.campaign_plan_runtime import parse_arc_advance_tags
    keys = parse_arc_advance_tags("Bohater wkracza w nowy rozdział. [ARC_ADVANCE: arc2] Dalej...")
    assert keys == ["arc2"], f"parsed keys: {keys}"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_beat_complete_still_works():
    """mark_beat_visited must still be importable + callable (no regression)."""
    from app.services.campaign_plan_runtime import mark_beat_visited
    assert callable(mark_beat_visited)
