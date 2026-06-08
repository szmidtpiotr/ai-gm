"""TDD: Issue #425 (E10) — Forge publish validation: required NPCs/beats must exist."""
import sys, os, json, sqlite3

sys.path.insert(0, "/app")

import pytest

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")


def _migrate():
    from app.migrations_admin import run_admin_migrations
    run_admin_migrations()


def _mk_template(required_npcs, required_beats, plan=None):
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO campaign_templates (title, status, required_npc_keys, required_beats, gm_plan_json) "
            "VALUES ('E10 tpl', 'draft', ?, ?, ?)",
            (json.dumps(required_npcs), json.dumps(required_beats), json.dumps(plan or {})),
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


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_validate_reports_missing_npc():
    """A required NPC key absent from npcs table must be reported missing."""
    _migrate()
    from app.routers.adventure_forge import validate_template_publish
    tid = _mk_template(["__definitely_missing_npc__"], [])
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            result = validate_template_publish(tid, conn)
        finally:
            conn.close()
        assert result["ok"] is False, "validation should fail with missing NPC"
        assert "__definitely_missing_npc__" in result["missing_npcs"], result
    finally:
        _rm(tid)


def test_validate_reports_missing_beat():
    """A required beat absent from the plan must be reported missing."""
    _migrate()
    from app.routers.adventure_forge import validate_template_publish
    plan = {"arcs": {"a1": {"id": "a1", "key_beats": [{"beat_key": "intro"}]}}, "active_arc_id": "a1"}
    tid = _mk_template([], ["finale_not_in_plan"], plan=plan)
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            result = validate_template_publish(tid, conn)
        finally:
            conn.close()
        assert result["ok"] is False
        assert "finale_not_in_plan" in result["missing_beats"], result
    finally:
        _rm(tid)


def test_validate_passes_when_complete():
    """No required items (or all present) → validation ok."""
    _migrate()
    from app.routers.adventure_forge import validate_template_publish
    tid = _mk_template([], [])
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            result = validate_template_publish(tid, conn)
        finally:
            conn.close()
        assert result["ok"] is True, result
    finally:
        _rm(tid)


def test_publish_blocked_via_patch_returns_422():
    """PATCH status=published with missing requirements must return HTTP 422."""
    _migrate()
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers.adventure_forge import _require_admin
    app.dependency_overrides[_require_admin] = lambda: None  # bypass auth for the test
    client = TestClient(app)
    tid = _mk_template(["__missing_for_patch__"], [])
    try:
        r = client.patch(f"/api/admin/forge/templates/{tid}", json={"status": "published"})
        assert r.status_code == 422, f"publish with missing NPC must be 422, got {r.status_code}: {r.text[:200]}"
        body = r.json()
        assert "__missing_for_patch__" in json.dumps(body), f"missing NPC not in 422 detail: {body}"
    finally:
        app.dependency_overrides.pop(_require_admin, None)
        _rm(tid)


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_validate_function_importable():
    """validate_template_publish must be importable (contract)."""
    _migrate()
    from app.routers.adventure_forge import validate_template_publish
    assert callable(validate_template_publish)
