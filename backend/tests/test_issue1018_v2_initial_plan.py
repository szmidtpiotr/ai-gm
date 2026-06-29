"""TDD: Issue #1018 — Nowa Kampania gracza + admin „Regeneruj plan" → plan V2
(acts/key_beats/endings), nie legacy `arcs`.

Bez tego żadna nowo utworzona kampania gracza nie da się przejść do wygranej —
maszyneria #1009–#1017 śledzi `acts[].key_beats[].beat_key`, a stary tor produkował
`arcs/scene_goals` (gołe stringi).
"""
import json
import sqlite3

import pytest

from app.services import gm_plan_generation_service as gps
from app.services.gm_plan_schema import gm_plan_is_ready


# ── Valid V2 plan the (mocked) LLM returns ──────────────────────────────────
# Mix: część beatów z objective_type (auto-complete), część bez (LLM [BEAT_COMPLETE]).
VALID_V2_PLAN = {
    "title": "Cień nad Brzeziną",
    "premise": "Mroczny kult budzi coś pod miastem.",
    "acts": [
        {
            "number": 1, "title": "Przybycie", "summary": "Bohater dociera do osady.",
            "key_beats": [
                {"beat_key": "dotrzyj_do_brzeziny", "summary": "Dotrzyj do Brzeziny",
                 "objective_type": "visit_location", "objective_value": "brzezina", "optional": False},
                {"beat_key": "porozmawiaj_z_soltysem", "summary": "Wypytaj sołtysa",
                 "optional": False},
            ],
            "completed": False,
        },
        {
            "number": 2, "title": "Trop", "summary": "Sprawy się komplikują.",
            "key_beats": [
                {"beat_key": "pokonaj_kultyste", "summary": "Pokonaj kultystę",
                 "objective_type": "kill_enemy", "objective_value": "kultysta", "optional": False},
            ],
            "completed": False,
        },
        {
            "number": 3, "title": "Finał", "summary": "Konfrontacja.",
            "key_beats": [
                {"beat_key": "zamknij_rytual", "summary": "Przerwij rytuał", "optional": False},
            ],
            "completed": False,
        },
    ],
    "endings": [
        {"id": "ending_primary", "title": "Gorzkie zwycięstwo", "type": "primary",
         "description": "Kult rozbity, ale miasto naznaczone.", "requirements": ["zamknij_rytual"]},
        {"id": "ending_alternate", "title": "Ucieczka", "type": "alternate",
         "description": "Bohater ratuje siebie, nie miasto.", "requirements": []},
    ],
    "key_npcs": [
        {"key": "soltys_brzezino", "name": "Sołtys", "role": "informator",
         "importance": "supporting", "deviation_consequence": "steer", "alive": True},
        {"key": "kultysta_wodz", "name": "Mroczny Kapłan", "role": "antagonist",
         "importance": "critical", "deviation_consequence": "branch", "alive": True},
    ],
    "key_locations": [
        {"key": "brzezina", "name": "Brzezina", "role": "starting_point", "visited": False},
    ],
    "active_act": 1,
    "scene_log": [], "deviations": [], "branches": [],
    "engine_private": {
        "secret_predisposition_hint": "Wrażliwość na magię.",
        "hidden_twist": "Sołtys jest w kulcie.",
        "contingency": "Jeśli kapłan zginie wcześnie: wprowadź jego pana.",
    },
}
VALID_V2_PLAN_JSON = json.dumps(VALID_V2_PLAN, ensure_ascii=False)

GARBAGE = "To nie jest JSON <broken>"


def _dummy_llm_config():
    return {"provider": "openai", "api_key": "test", "base_url": "http://localhost:9999"}


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL DEFAULT 'Test',
            system_id TEXT NOT NULL DEFAULT 'default',
            model_id TEXT,
            language TEXT NOT NULL DEFAULT 'pl',
            owner_user_id INTEGER NOT NULL DEFAULT 1,
            gm_plan_json TEXT NOT NULL DEFAULT '{}',
            engine_private_json TEXT DEFAULT NULL,
            plan_degraded INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER DEFAULT 1,
            name TEXT DEFAULT 'Bohater', system_id TEXT DEFAULT 'default',
            sheet_json TEXT DEFAULT '{}', location TEXT DEFAULT 'Miasto'
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL, character_id INTEGER,
            user_text TEXT NOT NULL DEFAULT '', route TEXT NOT NULL DEFAULT 'narrative',
            assistant_text TEXT, turn_number INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.execute("INSERT INTO campaigns (id, title) VALUES (1, 'Kampania testowa')")
    conn.commit()
    return conn


# ─── Test główny — nowa kampania gracza → V2 (acts/key_beats/endings) ────────

def test_v2_initial_plan_has_acts_keybeats_endings(monkeypatch):
    """Acceptance #1+#3: gm_plan_json ma acts[].key_beats[].beat_key + endings[],
    NIE arcs/scene_goals jako kształt główny."""
    monkeypatch.setattr(gps, "generate_chat", lambda **kw: VALID_V2_PLAN_JSON)
    conn = _make_db()

    ok, err = gps.generate_initial_gm_plan_v2_with_retries(
        conn, campaign_id=1, campaign_title="Test", campaign_language="pl",
        system_id="default", char_summary="Postać: Aldo, Wojownik.",
        user_id=1, model="gpt-4o", llm_config=_dummy_llm_config(), max_attempts=2,
    )
    assert ok is True, err
    plan = json.loads(conn.execute("SELECT gm_plan_json FROM campaigns WHERE id=1").fetchone()[0])

    assert isinstance(plan.get("acts"), list) and plan["acts"], "brak acts[]"
    first_act = plan["acts"][0]
    assert isinstance(first_act.get("key_beats"), list) and first_act["key_beats"], "brak key_beats[]"
    assert all(b.get("beat_key") for b in first_act["key_beats"]), "beat bez beat_key"
    # nie legacy arcs/scene_goals
    assert not plan.get("scene_goals"), "V2 nie powinien mieć top-level scene_goals"
    conn.close()


def test_v2_mix_objective_types(monkeypatch):
    """Acceptance #2: część beatów ma objective_type (auto-complete), część nie
    (domykane przez [BEAT_COMPLETE])."""
    monkeypatch.setattr(gps, "generate_chat", lambda **kw: VALID_V2_PLAN_JSON)
    conn = _make_db()
    gps.generate_initial_gm_plan_v2_with_retries(
        conn, campaign_id=1, campaign_title="T", campaign_language="pl",
        system_id="d", char_summary="Postać: Aldo.", user_id=1, model="m",
        llm_config=_dummy_llm_config(), max_attempts=1,
    )
    plan = json.loads(conn.execute("SELECT gm_plan_json FROM campaigns WHERE id=1").fetchone()[0])
    beats = [b for act in plan["acts"] for b in act.get("key_beats", [])]
    with_obj = [b for b in beats if b.get("objective_type")]
    without_obj = [b for b in beats if not b.get("objective_type")]
    assert with_obj, "oczekiwano co najmniej jednego beatu z objective_type"
    assert without_obj, "oczekiwano co najmniej jednego beatu bez objective_type"
    conn.close()


def test_v2_endings_filled(monkeypatch):
    """Acceptance #3: endings[] wypełnione (overlay zwycięstwa)."""
    monkeypatch.setattr(gps, "generate_chat", lambda **kw: VALID_V2_PLAN_JSON)
    conn = _make_db()
    gps.generate_initial_gm_plan_v2_with_retries(
        conn, campaign_id=1, campaign_title="T", campaign_language="pl",
        system_id="d", char_summary="Postać: Aldo.", user_id=1, model="m",
        llm_config=_dummy_llm_config(), max_attempts=1,
    )
    plan = json.loads(conn.execute("SELECT gm_plan_json FROM campaigns WHERE id=1").fetchone()[0])
    assert isinstance(plan.get("endings"), list) and len(plan["endings"]) >= 1
    assert any(e.get("title") for e in plan["endings"])
    conn.close()


def test_engine_private_stored_separately(monkeypatch):
    """engine_private trzymany osobno (engine_private_json), nie wyciekać w gm_plan_json."""
    monkeypatch.setattr(gps, "generate_chat", lambda **kw: VALID_V2_PLAN_JSON)
    conn = _make_db()
    gps.generate_initial_gm_plan_v2_with_retries(
        conn, campaign_id=1, campaign_title="T", campaign_language="pl",
        system_id="d", char_summary="Postać: Aldo.", user_id=1, model="m",
        llm_config=_dummy_llm_config(), max_attempts=1,
    )
    row = conn.execute("SELECT gm_plan_json, engine_private_json FROM campaigns WHERE id=1").fetchone()
    public = json.loads(row[0])
    assert "engine_private" not in public, "engine_private musi być odcięty z planu publicznego"
    private = json.loads(row[1])
    assert "hidden_twist" in private
    conn.close()


def test_no_degraded_on_success(monkeypatch):
    """Udana generacja V2 → plan_degraded=0."""
    monkeypatch.setattr(gps, "generate_chat", lambda **kw: VALID_V2_PLAN_JSON)
    conn = _make_db()
    conn.execute("UPDATE campaigns SET plan_degraded=1 WHERE id=1")
    conn.commit()
    gps.generate_initial_gm_plan_v2_with_retries(
        conn, campaign_id=1, campaign_title="T", campaign_language="pl",
        system_id="d", char_summary="Postać: Aldo.", user_id=1, model="m",
        llm_config=_dummy_llm_config(), max_attempts=1,
    )
    assert int(conn.execute("SELECT plan_degraded FROM campaigns WHERE id=1").fetchone()[0]) == 0
    conn.close()


# ─── Degrade-guard (Acceptance #6) ───────────────────────────────────────────

def test_degrade_guard_fallback_is_v2(monkeypatch):
    """Gdy LLM łamie schemat: fallback plan V2 (acts/endings) + plan_degraded=1,
    kampania nadal startuje (ok=True)."""
    monkeypatch.setattr(gps, "generate_chat", lambda **kw: GARBAGE)
    conn = _make_db()
    ok, err = gps.generate_initial_gm_plan_v2_with_retries(
        conn, campaign_id=1, campaign_title="T", campaign_language="pl",
        system_id="d", char_summary="Postać: Aldo.", user_id=1, model="m",
        llm_config=_dummy_llm_config(), max_attempts=2,
    )
    assert ok is True and err is None
    row = conn.execute("SELECT gm_plan_json, plan_degraded FROM campaigns WHERE id=1").fetchone()
    assert int(row[1]) == 1, "plan_degraded musi być 1 po fallbacku"
    plan = json.loads(row[0])
    assert isinstance(plan.get("acts"), list) and plan["acts"], "fallback też musi być V2 (acts)"
    assert isinstance(plan.get("endings"), list) and plan["endings"], "fallback musi mieć endings"
    assert gm_plan_is_ready(row[0]), "fallback V2 musi przejść gm_plan_is_ready()"
    conn.close()


# ─── Admin „Regeneruj plan" (#966) daje ten sam V2 kształt (Acceptance #4) ───

def test_admin_regenerate_produces_v2(monkeypatch):
    monkeypatch.setattr(gps, "generate_chat", lambda **kw: VALID_V2_PLAN_JSON)
    import app.services.user_llm_settings as uls
    monkeypatch.setattr(uls, "get_user_llm_settings_full",
                        lambda user_id: {"model": "gpt-4o"})
    conn = _make_db()
    conn.execute(
        "UPDATE campaigns SET system_id='sys', model_id='gpt-4o', owner_user_id=7 WHERE id=1"
    )
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name, sheet_json, location) "
        "VALUES (10, 1, 7, 'Aldo', ?, 'Port')",
        (json.dumps({"archetype": "warrior", "max_hp": 30, "stats": {"STR": 14}}),),
    )
    conn.commit()

    ok, err = gps.retry_initial_gm_plan_for_campaign(conn, campaign_id=1, owner_user_id=7)
    assert ok is True, err
    plan = json.loads(conn.execute("SELECT gm_plan_json FROM campaigns WHERE id=1").fetchone()[0])
    assert isinstance(plan.get("acts"), list) and plan["acts"], "admin regenerate musi dać V2 (acts)"
    assert isinstance(plan.get("endings"), list) and plan["endings"]
    conn.close()


# ─── Backward compat (Acceptance #5) ─────────────────────────────────────────

def test_gm_plan_is_ready_accepts_v2_acts():
    """V2 plan (acts, brak arcs) jest 'ready' — nie wywoła ponownej generacji."""
    v2 = json.dumps({"title": "X", "acts": [
        {"number": 1, "title": "A", "summary": "s",
         "key_beats": [{"beat_key": "b1", "summary": "s"}], "completed": False}
    ]}, ensure_ascii=False)
    assert gm_plan_is_ready(v2) is True


def test_gm_plan_is_ready_still_accepts_legacy_arcs():
    """Stare plany arcs nadal 'ready' (brak regresji)."""
    legacy = json.dumps({
        "schema_version": 2,
        "arcs": {"default": {"id": "default", "title": "Start", "status": "active",
                             "roadmap": "Bohater rusza w drogę.",
                             "scene_goals": ["Cel 1"], "hooks": {}}},
        "active_arc_id": "default",
    }, ensure_ascii=False)
    assert gm_plan_is_ready(legacy) is True


def test_gm_plan_is_ready_empty_is_not_ready():
    assert gm_plan_is_ready("{}") is False
    assert gm_plan_is_ready(None) is False
