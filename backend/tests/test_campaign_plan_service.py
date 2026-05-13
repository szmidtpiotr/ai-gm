"""
Tests for Campaign Plan Service — V2 Phase 02 Task 07
"""
import json
import sqlite3
import pytest
from unittest.mock import patch

from app.services.campaign_plan_service import (
    CampaignPlan, PlotAct, PlotEnding, PlotNPC, PlotLocation, EnginePrivate,
    _build_user_prompt, _extract_json, get_public_plan, generate_v2_campaign_plan,
)


# ── Schema validation ──────────────────────────────────────────────────────

MINIMAL_VALID_PLAN = {
    "title": "Cień nad Graustein",
    "premise": "Tajemnicze morderstwa w małym mieście.",
    "acts": [
        {"number": 1, "title": "Przylot", "summary": "Bohater przybywa.", "key_beats": ["dotarcie", "spotkanie"], "completed": False},
        {"number": 2, "title": "Eskalacja", "summary": "Sprawy się komplikują.", "key_beats": ["odkrycie"], "completed": False},
        {"number": 3, "title": "Finał", "summary": "Rozwiązanie.", "key_beats": ["konfrontacja"], "completed": False},
    ],
    "endings": [
        {"id": "ending_primary", "title": "Pyrrusowe zwycięstwo", "type": "primary",
         "description": "Wróg pokonany, ale coś utracone.", "requirements": ["antagonist_defeated"]},
        {"id": "ending_alternate", "title": "Kompromis", "type": "alternate",
         "description": "Ugoda z kosztem moralnym.", "requirements": ["negotiation_done"]},
    ],
    "key_npcs": [
        {"key": "innkeeper_boris", "name": "Boris", "role": "informant",
         "importance": "supporting", "deviation_consequence": "steer", "alive": True},
        {"key": "vampire_master", "name": "Nieznany", "role": "antagonist",
         "importance": "critical", "deviation_consequence": "branch", "alive": True},
    ],
    "key_locations": [
        {"key": "loc_graustein", "name": "Graustein", "role": "starting_point", "visited": False},
    ],
    "active_act": 1,
    "scene_log": [],
    "deviations": [],
    "branches": [],
    "engine_private": {
        "secret_predisposition_hint": "Ukryta wrażliwość na zaufanie.",
        "hidden_twist": "Wampir to były kapłan.",
        "contingency": "Jeśli wampir zginie w akcie 1: wprowadź jego mocodawcę.",
    },
}


class TestCampaignPlanSchema:
    def test_valid_plan_parses(self):
        plan = CampaignPlan.model_validate(MINIMAL_VALID_PLAN)
        assert plan.title == "Cień nad Graustein"
        assert len(plan.acts) == 3
        assert len(plan.endings) == 2
        assert plan.engine_private.hidden_twist == "Wampir to były kapłan."

    def test_defaults_populated(self):
        plan = CampaignPlan.model_validate(MINIMAL_VALID_PLAN)
        assert plan.active_act == 1
        assert plan.scene_log == []
        assert plan.deviations == []

    def test_npc_importance_validated(self):
        from pydantic import ValidationError
        bad = dict(MINIMAL_VALID_PLAN)
        bad["key_npcs"] = [{"key": "x", "name": "x", "role": "x",
                             "importance": "legendary",  # invalid
                             "deviation_consequence": "steer"}]
        with pytest.raises(ValidationError):
            CampaignPlan.model_validate(bad)

    def test_ending_type_validated(self):
        from pydantic import ValidationError
        bad = dict(MINIMAL_VALID_PLAN)
        bad["endings"] = [{"id": "e1", "title": "T", "type": "tragic",  # invalid
                           "description": "D", "requirements": []}]
        with pytest.raises(ValidationError):
            CampaignPlan.model_validate(bad)


# ── _extract_json ─────────────────────────────────────────────────────────

class TestExtractJson:
    def test_clean_json(self):
        result = _extract_json('{"title": "Test"}')
        assert result == {"title": "Test"}

    def test_json_with_markdown(self):
        result = _extract_json('```json\n{"title": "Test"}\n```')
        assert result == {"title": "Test"}

    def test_json_with_preamble(self):
        result = _extract_json('Here is the plan:\n{"title": "Test"}')
        assert result == {"title": "Test"}

    def test_empty_returns_none(self):
        assert _extract_json("") is None
        assert _extract_json("not json at all") is None

    def test_array_returns_none(self):
        assert _extract_json('[1, 2, 3]') is None


# ── _build_user_prompt ────────────────────────────────────────────────────

class TestBuildUserPrompt:
    def test_includes_character_name(self):
        p = _build_user_prompt("Aldric", "warrior", "Były żołnierz",
                               "Milczy dużo.", [], [], "")
        assert "Aldric" in p

    def test_includes_bonds(self):
        bonds = [{"description": "Zemsta za oddział", "type": "ideal"}]
        p = _build_user_prompt("Aldric", "warrior", "", "", bonds, [], "")
        assert "Zemsta za oddział" in p
        assert "ideal" in p

    def test_includes_weaknesses(self):
        weak = [{"description": "Nałóg alkoholowy", "type": "addiction"}]
        p = _build_user_prompt("Aldric", "warrior", "", "", [], weak, "")
        assert "Nałóg alkoholowy" in p

    def test_includes_secret_predisposition(self):
        p = _build_user_prompt("Aldric", "warrior", "", "", [], [],
                               "Latentna wrażliwość na magię")
        assert "Latentna" in p

    def test_includes_ideas_seeds(self):
        seeds = [{"title": "Plaga Bogów", "premise": "Zaraza w mieście"}]
        p = _build_user_prompt("Aldric", "warrior", "", "", [], [], "", seeds)
        assert "Plaga Bogów" in p

    def test_scholar_label(self):
        p = _build_user_prompt("Mira", "scholar", "", "", [], [], "")
        assert "Uczony" in p


# ── get_public_plan ───────────────────────────────────────────────────────

class TestGetPublicPlan:
    def test_strips_engine_private(self):
        plan_with_private = dict(MINIMAL_VALID_PLAN)
        result = get_public_plan(json.dumps(plan_with_private))
        assert "engine_private" not in result
        assert "title" in result

    def test_empty_json(self):
        assert get_public_plan("{}") == {}
        assert get_public_plan("") == {}
        assert get_public_plan(None) == {}

    def test_no_engine_private_ok(self):
        plan_no_private = {k: v for k, v in MINIMAL_VALID_PLAN.items() if k != "engine_private"}
        result = get_public_plan(json.dumps(plan_no_private))
        assert result["title"] == "Cień nad Graustein"


# ── generate_v2_campaign_plan (mocked LLM) ────────────────────────────────

class TestGenerateV2CampaignPlan:
    @pytest.fixture
    def db(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE campaigns (
                id INTEGER PRIMARY KEY,
                gm_plan_json TEXT DEFAULT '{}',
                engine_private_json TEXT DEFAULT NULL
            );
            CREATE TABLE campaign_ideas (
                id INTEGER PRIMARY KEY,
                category TEXT, title TEXT, description TEXT,
                review_status TEXT, quality_rating INTEGER DEFAULT 0, times_used INTEGER DEFAULT 0
            );
            INSERT INTO campaigns (id) VALUES (1);
        """)
        conn.commit()
        yield conn
        conn.close()

    def _char_data(self):
        return {
            "name": "Aldric",
            "archetype": "warrior",
            "background_note": "Były żołnierz",
            "identity": {
                "personality": "Milczy dużo.",
                "bonds": [{"description": "Zemsta za oddział", "type": "ideal"}],
                "weaknesses": [{"description": "Nałóg alkoholowy", "type": "addiction"}],
            },
            "gm_only": {"secret_predisposition": "Latentna wrażliwość na magię"},
        }

    def test_success_stores_plan(self, db):
        with patch("app.services.campaign_plan_service.generate_chat",
                   return_value=json.dumps(MINIMAL_VALID_PLAN)):
            ok, err = generate_v2_campaign_plan(
                db, campaign_id=1, character_data=self._char_data(),
                model="test", llm_config={}
            )
        assert ok is True
        assert err is None
        row = db.execute("SELECT gm_plan_json FROM campaigns WHERE id = 1").fetchone()
        stored = json.loads(row[0])
        assert stored["title"] == "Cień nad Graustein"
        assert "engine_private" not in stored  # stripped from public plan

    def test_engine_private_stored_separately(self, db):
        with patch("app.services.campaign_plan_service.generate_chat",
                   return_value=json.dumps(MINIMAL_VALID_PLAN)):
            ok, _ = generate_v2_campaign_plan(
                db, campaign_id=1, character_data=self._char_data(),
                model="test", llm_config={}
            )
        assert ok is True
        row = db.execute("SELECT engine_private_json FROM campaigns WHERE id = 1").fetchone()
        private = json.loads(row[0])
        assert "hidden_twist" in private

    def test_invalid_json_retries_and_fails(self, db):
        with patch("app.services.campaign_plan_service.generate_chat",
                   return_value="not json at all"):
            ok, err = generate_v2_campaign_plan(
                db, campaign_id=1, character_data=self._char_data(),
                model="test", llm_config={}, max_attempts=2
            )
        assert ok is False
        assert err is not None

    def test_llm_error_returns_false(self, db):
        with patch("app.services.campaign_plan_service.generate_chat",
                   side_effect=RuntimeError("LLM timeout")):
            ok, err = generate_v2_campaign_plan(
                db, campaign_id=1, character_data=self._char_data(),
                model="test", llm_config={}
            )
        assert ok is False
        assert "timeout" in (err or "").lower()
