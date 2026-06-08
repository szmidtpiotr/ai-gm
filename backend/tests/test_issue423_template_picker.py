"""TDD: Issue #423 (E8) — player ready-campaign picker: player_visible filter + launch from template."""
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


def _mk_template(title, player_visible, plan=None):
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO campaign_templates (title, status, player_visible, gm_plan_json) "
            "VALUES (?, 'published', ?, ?)",
            (title, player_visible, json.dumps(plan or {})),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _rm(table, _id, col="id"):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(f"DELETE FROM {table} WHERE {col} = ?", (_id,))
        conn.commit()
    finally:
        conn.close()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_public_list_filters_player_invisible():
    """Published-but-hidden templates (player_visible=0) must NOT appear in the player list."""
    _migrate()
    vis = _mk_template("E8 visible", 1)
    hid = _mk_template("E8 hidden", 0)
    try:
        r = client.get("/api/campaign-templates")
        assert r.status_code == 200, r.text
        ids = {t["id"] for t in r.json()["items"]}
        assert vis in ids, "player_visible=1 template must be listed"
        assert hid not in ids, "player_visible=0 template must be hidden from players"
    finally:
        _rm("campaign_templates", vis)
        _rm("campaign_templates", hid)


def test_create_campaign_from_template_copies_plan():
    """POST /campaigns with template_id must copy the template gm_plan + bump play_count."""
    _migrate()
    plan = {"schema_version": 2, "arcs": {"a1": {"id": "a1", "title": "Akt I"}}, "active_arc_id": "a1"}
    tpl = _mk_template("E8 launch", 1, plan=plan)
    campaign_id = None
    try:
        r = client.post("/api/campaigns", json={
            "title": "Gra z szablonu", "system_id": "fantasy", "model_id": "default",
            "owner_user_id": 1, "language": "pl", "mode": "pre_built", "status": "active",
            "template_id": tpl,
        })
        assert r.status_code == 200, r.text
        campaign_id = r.json()["id"]
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            camp = conn.execute("SELECT gm_plan_json FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
            tpl_row = conn.execute("SELECT play_count FROM campaign_templates WHERE id = ?", (tpl,)).fetchone()
        finally:
            conn.close()
        camp_plan = json.loads(camp["gm_plan_json"] or "{}")
        assert camp_plan.get("active_arc_id") == "a1", f"plan not copied: {camp_plan}"
        assert tpl_row["play_count"] == 1, f"play_count not bumped: {tpl_row['play_count']}"
    finally:
        if campaign_id:
            _rm("campaigns", campaign_id)
        _rm("campaign_templates", tpl)


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_create_campaign_without_template_still_works():
    """POST /campaigns with no template_id must still create a plain campaign."""
    _migrate()
    campaign_id = None
    try:
        r = client.post("/api/campaigns", json={
            "title": "Zwykła kampania", "system_id": "fantasy", "model_id": "default",
            "owner_user_id": 1, "language": "pl", "mode": "solo", "status": "active",
        })
        assert r.status_code == 200, r.text
        campaign_id = r.json()["id"]
        assert r.json()["title"] == "Zwykła kampania"
    finally:
        if campaign_id:
            _rm("campaigns", campaign_id)
