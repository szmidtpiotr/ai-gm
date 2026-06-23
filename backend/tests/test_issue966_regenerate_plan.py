"""TDD: Issue #966 — admin regenerate-plan must report plan_degraded status.

The admin "♻ Regeneruj plan MG" button needs to know whether the freshly
regenerated plan came out full (plan_degraded=0 → "Plan wygenerowany") or
still fell back (plan_degraded=1 → "Nadal uproszczony — sprawdź LLM").
So the service response MUST carry the post-regeneration `plan_degraded` flag.
"""
import json
import sqlite3

import pytest

from app.services import admin_campaigns


def _seed_db(path: str, *, plan_degraded: int) -> None:
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
                gm_plan_json TEXT NOT NULL DEFAULT '{}',
                plan_degraded INTEGER NOT NULL DEFAULT 0
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
        fallback_plan = {
            "schema_version": 2,
            "active_arc_id": "default",
            "arcs": {
                "default": {
                    "id": "default",
                    "title": "Start przygody",
                    "status": "active",
                    "roadmap": "Bohater wyrusza w nieznane.",
                    "scene_goals": ["Zapoznaj się z okolicą"],
                    "hooks": {"npcs": ["Nieznajomy"], "locations": ["Karczma"]},
                }
            },
            "engine_private": {},
        }
        conn.execute(
            """
            INSERT INTO campaigns (id, title, status, owner_user_id, language, model_id,
                                   gm_plan_json, plan_degraded)
            VALUES (1, 'Camp 966', 'active', 10, 'pl', 'gpt-test', ?, ?)
            """,
            (json.dumps(fallback_plan, ensure_ascii=False), plan_degraded),
        )
        conn.commit()
    finally:
        conn.close()


def _full_plan() -> dict:
    return {
        "schema_version": 2,
        "active_arc_id": "regen",
        "arcs": {
            "regen": {
                "id": "regen",
                "title": "Regenerated",
                "status": "active",
                "roadmap": "Fresh plan with hooks and goals.",
                "scene_goals": ["Spotkaj kapitana", "Zbadaj port"],
                "hooks": {"npcs": ["Mira"], "locations": ["Port"]},
            }
        },
        "engine_private": {},
    }


# ─── Test główny — sukces: plan_degraded=0 raportowany ───────────────────────

def test_regenerate_reports_plan_degraded_false_on_success(tmp_path, monkeypatch):
    db = tmp_path / "ok.db"
    _seed_db(str(db), plan_degraded=1)
    monkeypatch.setattr(admin_campaigns, "DB_PATH", str(db))

    def _fake_retry(conn, *, campaign_id, owner_user_id):
        # Strong LLM → full plan, plan_degraded cleared.
        conn.execute(
            "UPDATE campaigns SET gm_plan_json = ?, plan_degraded = 0 WHERE id = ?",
            (json.dumps(_full_plan(), ensure_ascii=False), campaign_id),
        )
        conn.commit()
        return True, None

    monkeypatch.setattr(admin_campaigns, "retry_initial_gm_plan_for_campaign", _fake_retry)

    result = admin_campaigns.regenerate_campaign_gm_plan_admin(1)
    assert result["plan_degraded"] is False
    assert result["ok"] is True
    assert result["gm_plan_json"]["active_arc_id"] == "regen"


# ─── Test główny — wciąż degraded: plan_degraded=1 raportowany ───────────────

def test_regenerate_reports_plan_degraded_true_when_still_weak(tmp_path, monkeypatch):
    db = tmp_path / "weak.db"
    _seed_db(str(db), plan_degraded=1)
    monkeypatch.setattr(admin_campaigns, "DB_PATH", str(db))

    def _fake_retry(conn, *, campaign_id, owner_user_id):
        # Weak LLM → fallback again, plan_degraded stays 1.
        conn.execute(
            "UPDATE campaigns SET plan_degraded = 1 WHERE id = ?",
            (campaign_id,),
        )
        conn.commit()
        return True, None

    monkeypatch.setattr(admin_campaigns, "retry_initial_gm_plan_for_campaign", _fake_retry)

    result = admin_campaigns.regenerate_campaign_gm_plan_admin(1)
    assert result["plan_degraded"] is True
    assert result["ok"] is True


# ─── Backward compat — get_campaign_gm_plan_admin nadal zwraca swoje pola ─────

def test_get_gm_plan_still_returns_core_keys_plus_degraded(tmp_path, monkeypatch):
    db = tmp_path / "get.db"
    _seed_db(str(db), plan_degraded=1)
    monkeypatch.setattr(admin_campaigns, "DB_PATH", str(db))

    body = admin_campaigns.get_campaign_gm_plan_admin(1)
    # Existing contract preserved
    assert body["campaign_id"] == 1
    assert "gm_plan_json" in body
    assert "divergence" in body
    assert "formatted_plan" in body
    # New: plan_degraded surfaced for the admin Plan GM tab badge/button
    assert body["plan_degraded"] is True
