"""TDD: Issue #426 (E11) — template narrative_hooks pre-seed narrative_state on launch."""
import sys, os, json, sqlite3

sys.path.insert(0, "/app")

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")


def _migrate():
    from app.migrations_admin import run_admin_migrations
    run_admin_migrations()


def _mk_template_with_hooks(hooks):
    plan = {
        "schema_version": 2,
        "arcs": {"a1": {"id": "a1", "title": "Akt I", "status": "active"}},
        "active_arc_id": "a1",
        "narrative_hooks": hooks,
    }
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO campaign_templates (title, status, player_visible, gm_plan_json) "
            "VALUES ('E11 tpl', 'published', 1, ?)",
            (json.dumps(plan, ensure_ascii=False),),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _rm(table, _id):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (_id,))
        conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (_id,)) if table == "campaigns" else None
        conn.commit()
    finally:
        conn.close()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_launch_from_template_seeds_narrative_state():
    """Launching a campaign from a template must seed its narrative_hooks into narrative_state."""
    _migrate()
    hooks = [
        {"key": "zaginiony_artefakt", "hint": "Gdzieś w ruinach czeka artefakt."},
        {"key": "zdrajca_w_radzie", "hint": "Jeden z doradców kłamie."},
    ]
    tid = _mk_template_with_hooks(hooks)
    campaign_id = None
    try:
        r = client.post("/api/campaigns", json={
            "title": "E11 launch", "system_id": "fantasy", "model_id": "default",
            "owner_user_id": 1, "language": "pl", "mode": "pre_built", "status": "active",
            "template_id": tid,
        })
        assert r.status_code == 200, r.text
        campaign_id = r.json()["id"]

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            gs = conn.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = ?", (campaign_id,)
            ).fetchone()
        finally:
            conn.close()
        assert gs is not None, "game_sessions row must exist after template launch"
        flags = json.loads(gs["session_flags"] or "{}")
        ns = flags.get("narrative_state") or {}
        seed_keys = {s.get("key") for s in (ns.get("seeds") or [])}
        assert "zaginiony_artefakt" in seed_keys, f"template seed not pre-seeded: {ns}"
        assert "zdrajca_w_radzie" in seed_keys, f"template seed not pre-seeded: {ns}"
    finally:
        if campaign_id:
            conn = sqlite3.connect(DB_PATH)
            try:
                conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
                conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (campaign_id,))
                conn.commit()
            finally:
                conn.close()
        _rm("campaign_templates", tid)


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_launch_template_without_hooks_no_crash():
    """A template without narrative_hooks must still launch (empty narrative_state ok)."""
    _migrate()
    tid = _mk_template_with_hooks([])  # no hooks
    campaign_id = None
    try:
        r = client.post("/api/campaigns", json={
            "title": "E11 no hooks", "system_id": "fantasy", "model_id": "default",
            "owner_user_id": 1, "language": "pl", "mode": "pre_built", "status": "active",
            "template_id": tid,
        })
        assert r.status_code == 200, r.text
        campaign_id = r.json()["id"]
    finally:
        if campaign_id:
            conn = sqlite3.connect(DB_PATH)
            try:
                conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
                conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (campaign_id,))
                conn.commit()
            finally:
                conn.close()
        _rm("campaign_templates", tid)
