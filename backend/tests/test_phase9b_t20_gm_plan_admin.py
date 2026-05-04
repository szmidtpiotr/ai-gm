import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.admin import require_admin_token
from app.services import admin_campaigns
from app.services.gm_plan_divergence import evaluate_plan_divergence


def _seed_db(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE campaigns (
                id INTEGER PRIMARY KEY,
                title TEXT,
                status TEXT,
                owner_user_id INTEGER,
                language TEXT,
                model_id TEXT,
                gm_plan_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE campaign_turns (
                id INTEGER PRIMARY KEY,
                campaign_id INTEGER NOT NULL,
                turn_number INTEGER NOT NULL,
                route TEXT,
                user_text TEXT,
                created_at TEXT
            );
            """
        )
        plan = {
            "schema_version": 2,
            "active_arc_id": "arc1",
            "arcs": {
                "arc1": {
                    "id": "arc1",
                    "title": "Port arc",
                    "status": "active",
                    "roadmap": "Find the smugglers in the harbor and talk to Captain Mira.",
                    "scene_goals": ["Meet Mira", "Inspect the harbor warehouse"],
                    "hooks": {"npcs": ["Mira"], "locations": ["Harbor"]},
                }
            },
            "engine_private": {},
        }
        conn.execute(
            """
            INSERT INTO campaigns (id, title, status, owner_user_id, language, model_id, gm_plan_json)
            VALUES (1, 'T20 Campaign', 'active', 10, 'pl', 'gpt-test', ?)
            """,
            (json.dumps(plan, ensure_ascii=False),),
        )
        conn.executemany(
            """
            INSERT INTO campaign_turns (campaign_id, turn_number, route, user_text, created_at)
            VALUES (1, ?, 'narrative', ?, datetime('now'))
            """,
            [
                (1, "I leave the city and head into the mountains."),
                (2, "I want to track dragons and ignore all local contacts for now."),
            ],
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client_and_db(tmp_path, monkeypatch):
    db = tmp_path / "t20.db"
    _seed_db(str(db))
    monkeypatch.setattr(admin_campaigns, "DB_PATH", str(db))
    app.dependency_overrides[require_admin_token] = lambda: None
    client = TestClient(app)
    try:
        yield client, db
    finally:
        client.close()
        app.dependency_overrides.pop(require_admin_token, None)


def test_divergence_heuristic_marks_offroad_player_focus():
    plan = {
        "schema_version": 2,
        "active_arc_id": "main",
        "arcs": {
            "main": {
                "id": "main",
                "roadmap": "Investigate the harbor cult and question priest Aldor.",
                "scene_goals": ["Reach the harbor", "Question Aldor"],
                "hooks": {"locations": ["Harbor"], "npcs": ["Aldor"]},
            }
        },
        "engine_private": {},
    }
    result = evaluate_plan_divergence(
        json.dumps(plan, ensure_ascii=False),
        [
            "I ride into the mountains far from the coast.",
            "I search for dragons instead of meeting anyone from the city.",
        ],
    )
    assert result["status"] == "diverged"
    assert result["matched_plan_tokens"] == []
    assert "mountains" in result["offroad_tokens"] or "dragons" in result["offroad_tokens"]


def test_admin_get_gm_plan_returns_divergence(client_and_db):
    client, _db = client_and_db
    r = client.get("/api/admin/campaigns/1/gm-plan")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["campaign_id"] == 1
    assert body["characters_count"] == 0
    assert body["gm_plan_json"]["active_arc_id"] == "arc1"
    assert body["divergence"]["status"] == "diverged"
    assert body["divergence"]["recent_player_turns"]


def test_admin_put_and_advance_scene_update_plan(client_and_db):
    client, _db = client_and_db
    new_plan = {
        "schema_version": 2,
        "active_arc_id": "act2",
        "arcs": {
            "act2": {
                "id": "act2",
                "title": "Act II",
                "status": "active",
                "roadmap": "Return to the harbor and secure Mira's help.",
                "scene_goals": ["Return to Mira"],
                "hooks": {"npcs": ["Mira"], "locations": ["Harbor"]},
            }
        },
        "engine_private": {"main_quest_key": "main_quest"},
    }
    put_resp = client.put(
        "/api/admin/campaigns/1/gm-plan",
        json={"gm_plan_json": new_plan},
    )
    assert put_resp.status_code == 200, put_resp.text
    put_body = put_resp.json()
    assert put_body["gm_plan_json"]["active_arc_id"] == "act2"
    assert put_body["gm_plan_json"]["engine_private"]["main_quest_key"] == "main_quest"

    adv_resp = client.post(
        "/api/admin/campaigns/1/gm-plan/advance-scene",
        json={"note": "checkpoint"},
    )
    assert adv_resp.status_code == 200, adv_resp.text
    adv_body = adv_resp.json()
    arc = adv_body["gm_plan_json"]["arcs"]["act2"]
    assert arc["current_scene_ordinal"] == 1
    assert arc["scene_log"][-1]["note"] == "checkpoint"
    assert arc["scene_log"][-1]["through_turn"] == 2


def test_admin_can_regenerate_initial_gm_plan(client_and_db, monkeypatch):
    client, db = client_and_db

    def _fake_retry(conn, *, campaign_id, owner_user_id):
        plan = {
            "schema_version": 2,
            "active_arc_id": "regen",
            "arcs": {
                "regen": {
                    "id": "regen",
                    "title": "Regenerated",
                    "status": "active",
                    "roadmap": "Fresh plan",
                    "scene_goals": ["Hook the player back to the harbor"],
                    "hooks": {"npcs": ["Mira"], "locations": ["Harbor"]},
                }
            },
            "engine_private": {},
        }
        conn.execute(
            "UPDATE campaigns SET gm_plan_json = ? WHERE id = ?",
            (json.dumps(plan, ensure_ascii=False), campaign_id),
        )
        conn.commit()
        return True, None

    monkeypatch.setattr(admin_campaigns, "retry_initial_gm_plan_for_campaign", _fake_retry)
    resp = client.post("/api/admin/campaigns/1/gm-plan/regenerate-initial")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["gm_plan_json"]["active_arc_id"] == "regen"

    conn = sqlite3.connect(db)
    try:
        row = conn.execute("SELECT gm_plan_json FROM campaigns WHERE id = 1").fetchone()
        assert row is not None
        saved = json.loads(row[0])
        assert saved["active_arc_id"] == "regen"
    finally:
        conn.close()
