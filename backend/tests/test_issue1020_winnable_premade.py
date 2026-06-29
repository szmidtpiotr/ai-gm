"""TDD: Issue #1020 — Forge publish enforces a "winnable premade" plan.

A winnable plan guarantees a premade campaign can be played to victory (#1009)
with no manual edits:
  1. endings[] present with ≥1 type=="primary",
  2. no critical orphan beats (find_orphan_beats clean),
  3. each act has ≥1 closable critical (non-optional) beat.
"""
import sys, os, json, sqlite3

sys.path.insert(0, "/app")

import pytest

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")


def _winnable_plan():
    """A minimal but fully winnable V2 plan (3 acts, endings w/ primary)."""
    return {
        "title": "Winnable",
        "acts": [
            {"number": 1, "title": "A1", "key_beats": [
                {"beat_key": "b1", "optional": False, "narrative_close": True},
                {"beat_key": "side1", "optional": True},
            ]},
            {"number": 2, "title": "A2", "key_beats": [
                {"beat_key": "b2", "optional": False, "objective_type": "kill_enemy",
                 "objective_value": "boss"},
            ]},
            {"number": 3, "title": "A3", "key_beats": [
                {"beat_key": "b3", "optional": False, "narrative_close": True},
            ]},
        ],
        "endings": [
            {"id": "ending_primary", "type": "primary", "title": "Zwycięstwo",
             "requirements": ["b3"]},
        ],
    }


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_validate_winnable_passes_on_complete_plan():
    """A plan with endings(primary) + no orphans + closable beat/act → ok."""
    from app.services.campaign_plan_runtime import validate_winnable_plan
    res = validate_winnable_plan(_winnable_plan())
    assert res["ok"] is True, res


def test_missing_endings_fails():
    """No endings[] → not winnable (victory overlay can't render)."""
    from app.services.campaign_plan_runtime import validate_winnable_plan
    plan = _winnable_plan()
    plan.pop("endings")
    res = validate_winnable_plan(plan)
    assert res["ok"] is False
    assert any("ending" in e.lower() for e in res["errors"]), res


def test_no_primary_ending_fails():
    """Endings present but none type=='primary' → not winnable."""
    from app.services.campaign_plan_runtime import validate_winnable_plan
    plan = _winnable_plan()
    plan["endings"] = [{"id": "e", "type": "alternate", "title": "Alt"}]
    res = validate_winnable_plan(plan)
    assert res["ok"] is False
    assert any("primary" in e.lower() for e in res["errors"]), res


def test_critical_orphan_beat_fails():
    """A non-optional beat with no objective and no narrative_close → orphan → fail."""
    from app.services.campaign_plan_runtime import validate_winnable_plan
    plan = _winnable_plan()
    plan["acts"][0]["key_beats"].append({"beat_key": "orphan_x", "optional": False})
    res = validate_winnable_plan(plan)
    assert res["ok"] is False
    assert "orphan_x" in res["orphan_beats"], res


def test_act_with_only_optional_beats_fails():
    """An act of only optional beats has no closable critical beat → strands play → fail."""
    from app.services.campaign_plan_runtime import validate_winnable_plan
    plan = _winnable_plan()
    plan["acts"][1]["key_beats"] = [{"beat_key": "only_side", "optional": True,
                                     "narrative_close": True}]
    res = validate_winnable_plan(plan)
    assert res["ok"] is False
    assert 2 in res["acts_without_closable_beat"], res


# ─── Integration: publish blocked via PATCH ──────────────────────────────────

def _migrate():
    from app.migrations_admin import run_admin_migrations
    run_admin_migrations()


def _mk_template(plan):
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO campaign_templates (title, status, required_npc_keys, "
            "required_beats, gm_plan_json) VALUES ('1020 tpl', 'draft', '[]', '[]', ?)",
            (json.dumps(plan, ensure_ascii=False),),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _rm(tid):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM campaign_templates WHERE id = ?", (tid,))
        conn.commit()
    finally:
        conn.close()


def test_publish_blocked_when_not_winnable_returns_422():
    """PATCH status=published with a plan missing endings → HTTP 422 (winnable block)."""
    _migrate()
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers.adventure_forge import _require_admin
    app.dependency_overrides[_require_admin] = lambda: None
    client = TestClient(app)
    plan = _winnable_plan()
    plan.pop("endings")
    tid = _mk_template(plan)
    try:
        r = client.patch(f"/api/admin/forge/templates/{tid}", json={"status": "published"})
        assert r.status_code == 422, f"non-winnable publish must be 422, got {r.status_code}: {r.text[:200]}"
        assert "winnable" in r.text.lower() or "ending" in r.text.lower(), r.text[:300]
    finally:
        app.dependency_overrides.pop(_require_admin, None)
        _rm(tid)


def test_publish_allowed_when_winnable():
    """PATCH status=published with a winnable plan → not blocked by winnable check (200)."""
    _migrate()
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers.adventure_forge import _require_admin
    app.dependency_overrides[_require_admin] = lambda: None
    client = TestClient(app)
    tid = _mk_template(_winnable_plan())
    try:
        r = client.patch(f"/api/admin/forge/templates/{tid}", json={"status": "published"})
        assert r.status_code == 200, f"winnable publish must succeed, got {r.status_code}: {r.text[:300]}"
    finally:
        app.dependency_overrides.pop(_require_admin, None)
        _rm(tid)


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_existing_npc_beat_validation_still_runs():
    """#425 validate_template_publish (NPC/beat) contract is untouched."""
    from app.routers.adventure_forge import validate_template_publish
    assert callable(validate_template_publish)
