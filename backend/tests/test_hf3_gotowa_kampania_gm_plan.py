"""TDD: Issue #525 — HF-3: Gotowa Kampania GM Plan 0 scen (szablon nie zasiewa beats)."""
import json
import sys
import os
import sqlite3
import tempfile

sys.path.insert(0, "/app")

from app.services.gm_plan_schema import normalize_gm_plan, gm_plan_is_ready


# ─── Template plan fixture ───────────────────────────────────────────────────

TEMPLATE_PLAN = json.dumps({
    "arcs": [
        {
            "id": "arc_curse",
            "label": "Klątwa",
            "key_beats": [
                {"beat_key": "discover_curse", "label": "Odkrycie klątwy"},
                {"beat_key": "seek_origin", "label": "Poszukiwanie źródła"},
                {"beat_key": "lift_curse", "label": "Zdjęcie klątwy"},
            ],
            "status": "active"
        },
        {
            "id": "arc_finale",
            "label": "Finał",
            "key_beats": [
                {"beat_key": "final_battle", "label": "Ostateczna bitwa"},
            ],
            "status": "planned"
        }
    ]
})

W1_PLAN = json.dumps({
    "schema_version": 2,
    "arcs": {
        "arc_main": {
            "id": "arc_main",
            "title": "Klątwa",
            "status": "active",
            "scene_goals": ["Odkryj klątwę", "Znajdź źródło"],
            "hooks": {}
        }
    },
    "active_arc_id": "arc_main",
    "engine_private": {}
})


# ─── FIX 1: normalize_gm_plan handles list arcs ──────────────────────────────

def test_normalize_gm_plan_handles_list_arcs():
    """normalize_gm_plan musi konwertować arcs jako listę → dict, nie dropować."""
    plan = normalize_gm_plan(TEMPLATE_PLAN)
    arcs = plan.get("arcs")
    assert isinstance(arcs, dict), f"arcs powinno być dict, got: {type(arcs)}"
    assert "arc_curse" in arcs, "arc_curse powinno być kluczem w arcs dict"
    assert "arc_finale" in arcs, "arc_finale powinno być kluczem w arcs dict"


def test_normalize_gm_plan_list_arcs_produces_scene_goals():
    """key_beats z szablonu muszą trafiać do scene_goals po normalizacji."""
    plan = normalize_gm_plan(TEMPLATE_PLAN)
    arc = plan["arcs"].get("arc_curse", {})
    goals = arc.get("scene_goals", [])
    assert len(goals) >= 3, f"oczekiwano min 3 scene_goals, got: {goals}"
    assert "Odkrycie klątwy" in goals, f"label beatu powinien być w scene_goals: {goals}"
    assert "Poszukiwanie źródła" in goals
    assert "Zdjęcie klątwy" in goals


def test_normalize_gm_plan_active_arc_from_status():
    """Arc z status='active' powinien stać się active_arc_id po normalizacji."""
    plan = normalize_gm_plan(TEMPLATE_PLAN)
    assert plan.get("active_arc_id") == "arc_curse", (
        f"active_arc_id powinno być 'arc_curse', got: {plan.get('active_arc_id')}"
    )


def test_normalize_gm_plan_dict_arcs_unchanged():
    """Jeśli arcs już dict (W1 format) — normalize_gm_plan nie zmienia struktury."""
    plan = normalize_gm_plan(W1_PLAN)
    arcs = plan.get("arcs")
    assert isinstance(arcs, dict)
    assert "arc_main" in arcs
    assert plan.get("active_arc_id") == "arc_main"


# ─── FIX 1: gm_plan_is_ready ─────────────────────────────────────────────────

def test_gm_plan_is_ready_template_format_returns_true():
    """gm_plan_is_ready() musi zwrócić True dla formatu szablonu (list arcs z key_beats)."""
    result = gm_plan_is_ready(TEMPLATE_PLAN)
    assert result is True, "gm_plan_is_ready() powinno być True dla planu szablonowego"


def test_gm_plan_is_ready_empty_plan_returns_false():
    """gm_plan_is_ready() zwraca False dla pustego planu — backward compat."""
    assert gm_plan_is_ready(None) is False
    assert gm_plan_is_ready("{}") is False
    assert gm_plan_is_ready("") is False


# ─── FIX 2: campaign_plan_runtime.get_plan arcs→acts ─────────────────────────

def test_get_plan_arcs_as_acts():
    """get_plan() musi zwracać acts gdy plan ma tylko arcs (format szablonu)."""
    from app.services.campaign_plan_runtime import get_plan

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            gm_plan_json TEXT
        )
    """)
    conn.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (1, ?)", (TEMPLATE_PLAN,))
    conn.commit()

    plan = get_plan(1, conn)
    acts = plan.get("acts", [])
    assert len(acts) >= 2, f"acts powinny mieć min 2 elementy, got: {acts}"
    act_ids = [a.get("id") for a in acts if isinstance(a, dict)]
    assert "arc_curse" in act_ids, f"arc_curse powinno być w acts: {act_ids}"


def test_get_plan_dict_arcs_not_affected():
    """get_plan() nie zmienia planów już w W1 format (acts osobno)."""
    from app.services.campaign_plan_runtime import get_plan

    plan_with_acts = json.dumps({
        "acts": [{"id": "act1", "title": "Akt 1", "key_beats": []}],
        "arcs": {}
    })
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY, gm_plan_json TEXT)")
    conn.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (1, ?)", (plan_with_acts,))
    conn.commit()

    plan = get_plan(1, conn)
    assert len(plan.get("acts", [])) == 1


# ─── FIX 3: _migrate_template_plan_to_w1 ─────────────────────────────────────

def test_migrate_template_plan_to_w1_basic():
    """Migracja: arcs lista → W1 dict + acts lista dla V2 runtime."""
    from app.api.campaigns import _migrate_template_plan_to_w1

    result_raw = _migrate_template_plan_to_w1(TEMPLATE_PLAN)
    result = json.loads(result_raw)

    # arcs powinno być dict
    assert isinstance(result.get("arcs"), dict), "arcs powinno być dict po migracji"
    assert "arc_curse" in result["arcs"]

    # acts powinno być populowane
    acts = result.get("acts", [])
    assert len(acts) >= 2, f"acts powinno mieć min 2 elementy: {acts}"

    # scene_goals z key_beats
    arc = result["arcs"]["arc_curse"]
    assert "Odkrycie klątwy" in arc.get("scene_goals", [])


def test_migrate_template_plan_to_w1_idempotent():
    """Jeśli plan już W1 format — migracja nic nie zmienia."""
    from app.api.campaigns import _migrate_template_plan_to_w1

    result_raw = _migrate_template_plan_to_w1(W1_PLAN)
    result = json.loads(result_raw)
    original = json.loads(W1_PLAN)

    # arcs dict pozostaje niezmieniony
    assert isinstance(result.get("arcs"), dict)
    assert "arc_main" in result["arcs"]


def test_migrate_template_plan_to_w1_empty():
    """Pusta/null wejście → bezpieczny wynik."""
    from app.api.campaigns import _migrate_template_plan_to_w1

    assert _migrate_template_plan_to_w1("{}") == "{}"
    assert _migrate_template_plan_to_w1("") == "{}"
    assert _migrate_template_plan_to_w1(None) == "{}"
