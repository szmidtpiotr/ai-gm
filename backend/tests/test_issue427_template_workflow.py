"""TDD: Issue #427 (E12) — template status workflow draft → review → published + revert."""
import sys, os, json, sqlite3

sys.path.insert(0, "/app")

import pytest
from fastapi.testclient import TestClient
from app.main import app

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")


def _migrate():
    from app.migrations_admin import run_admin_migrations
    run_admin_migrations()


def _client():
    from app.routers.adventure_forge import _require_admin
    app.dependency_overrides[_require_admin] = lambda: None
    return TestClient(app)


def _unauth():
    from app.routers.adventure_forge import _require_admin
    app.dependency_overrides.pop(_require_admin, None)


def _mk_template(status="draft"):
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO campaign_templates (title, status, gm_plan_json) VALUES ('E12 wf', ?, '{}')",
            (status,),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _status(tid):
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute("SELECT status FROM campaign_templates WHERE id = ?", (tid,)).fetchone()[0]
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

def test_draft_to_review_allowed():
    """draft → review must be accepted (review is the middle workflow state)."""
    _migrate()
    client = _client()
    tid = _mk_template("draft")
    try:
        r = client.patch(f"/api/admin/forge/templates/{tid}", json={"status": "review"})
        assert r.status_code == 200, r.text
        assert _status(tid) == "review"
    finally:
        _unauth(); _rm(tid)


def test_review_hidden_from_players():
    """A template in review must NOT be in the player-facing published list."""
    _migrate()
    tid = _mk_template("review")
    try:
        # player endpoint (no auth)
        client = TestClient(app)
        r = client.get("/api/campaign-templates")
        assert r.status_code == 200
        ids = {t["id"] for t in r.json()["items"]}
        assert tid not in ids, "review template must be hidden from players"
    finally:
        _rm(tid)


def test_published_revert_to_draft():
    """published → draft (revert) must be allowed."""
    _migrate()
    client = _client()
    tid = _mk_template("published")
    try:
        r = client.patch(f"/api/admin/forge/templates/{tid}", json={"status": "draft"})
        assert r.status_code == 200, r.text
        assert _status(tid) == "draft"
    finally:
        _unauth(); _rm(tid)


def test_invalid_status_rejected():
    """An unknown status value must be rejected with 422 (workflow guard)."""
    _migrate()
    client = _client()
    tid = _mk_template("draft")
    try:
        r = client.patch(f"/api/admin/forge/templates/{tid}", json={"status": "garbage_state"})
        assert r.status_code == 422, f"invalid status must be 422, got {r.status_code}"
        assert _status(tid) == "draft", "status must be unchanged after rejection"
    finally:
        _unauth(); _rm(tid)


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_publish_still_validated():
    """draft → published still runs the required-NPC validation (no regression)."""
    _migrate()
    client = _client()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO campaign_templates (title, status, required_npc_keys, gm_plan_json) "
            "VALUES ('E12 pub', 'draft', ?, '{}')",
            (json.dumps(["__missing_npc_e12__"]),),
        )
        conn.commit()
        tid = cur.lastrowid
    finally:
        conn.close()
    try:
        r = client.patch(f"/api/admin/forge/templates/{tid}", json={"status": "published"})
        assert r.status_code == 422, f"publish with missing NPC must be 422, got {r.status_code}"
    finally:
        _unauth(); _rm(tid)
