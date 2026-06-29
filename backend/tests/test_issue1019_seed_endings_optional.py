"""TDD: Issue #1019 — seed-template patch adds endings[] + optional beats to the 3 premade campaigns."""
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.migrations_admin import _patch_campaign_template_endings_and_optional  # noqa: E402


# ─── Fixtures: the 3 seed templates in their PRE-#1019 shape (no endings/optional) ──────

_PRE1019_PLANS = {
    "Pierwsze Kroki": {
        "arcs": [{"id": "arc_tutorial", "label": "Tutorial", "key_beats": [
            {"beat_key": "first_combat", "label": "Pierwsza walka", "objective_type": "kill_enemy"},
            {"beat_key": "first_merchant", "label": "Pierwszy handel", "objective_type": "talk_to_npc"},
            {"beat_key": "first_exploration", "label": "Pierwsza eksploracja", "objective_type": "visit_location"},
        ], "status": "active"}]
    },
    "Przeklęte Ziemie": {
        "arcs": [{"id": "arc_curse", "label": "Klątwa", "key_beats": [
            {"beat_key": "discover_curse", "label": "Odkrycie klątwy", "objective_type": "visit_location"},
            {"beat_key": "seek_origin", "label": "Poszukiwanie źródła", "objective_type": "talk_to_npc"},
            {"beat_key": "confront_evil", "label": "Konfrontacja ze złem", "objective_type": "kill_enemy"},
            {"beat_key": "lift_curse", "label": "Zdjęcie klątwy", "objective_type": "visit_location"},
        ], "status": "active"}]
    },
    "Cień Licza": {
        "arcs": [
            {"id": "arc_awakening", "label": "Przebudzenie", "key_beats": [
                {"beat_key": "lich_awakens", "label": "Przebudzenie Licza"},
                {"beat_key": "seek_allies", "label": "Poszukiwanie sojuszników", "objective_type": "talk_to_npc"},
            ], "status": "active"},
            {"id": "arc_phylactery", "label": "Filar Duszy", "key_beats": [
                {"beat_key": "locate_phylactery", "label": "Lokalizacja filaru", "objective_type": "visit_location"},
                {"beat_key": "destroy_phylactery", "label": "Zniszczenie filaru", "objective_type": "kill_enemy"},
                {"beat_key": "final_battle", "label": "Ostateczna bitwa", "objective_type": "kill_enemy"},
            ], "status": "planned"},
        ]
    },
}


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE campaign_templates "
        "(id INTEGER PRIMARY KEY, title TEXT, gm_plan_json TEXT, created_by TEXT)"
    )
    for title, plan in _PRE1019_PLANS.items():
        conn.execute(
            "INSERT INTO campaign_templates (title, gm_plan_json, created_by) VALUES (?,?,?)",
            (title, json.dumps(plan, ensure_ascii=False), "seed"),
        )
    conn.commit()
    return conn


def _load(conn, title):
    row = conn.execute(
        "SELECT gm_plan_json FROM campaign_templates WHERE title = ?", (title,)
    ).fetchone()
    return json.loads(row["gm_plan_json"])


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_patch_adds_primary_ending_to_every_seed_template():
    """Each seed template gets endings[] with ≥1 primary ending (title + summary)."""
    conn = _make_db()
    _patch_campaign_template_endings_and_optional(conn)

    for title in _PRE1019_PLANS:
        plan = _load(conn, title)
        endings = plan.get("endings")
        assert isinstance(endings, list) and endings, f"{title}: brak endings[]"
        primaries = [e for e in endings if e.get("type") == "primary"]
        assert primaries, f"{title}: brak ending type=primary"
        assert primaries[0].get("title"), f"{title}: primary ending bez tytułu"
        assert primaries[0].get("summary"), f"{title}: primary ending bez streszczenia"


def test_patch_marks_side_beats_optional_keeps_critical_per_arc():
    """Side beats → optional:true; every arc keeps ≥1 critical (non-optional) beat."""
    conn = _make_db()
    _patch_campaign_template_endings_and_optional(conn)

    # known side beats that should now be optional
    expected_optional = {"first_exploration", "seek_origin", "seek_allies"}
    seen_optional = set()

    for title in _PRE1019_PLANS:
        plan = _load(conn, title)
        for arc in plan["arcs"]:
            beats = arc["key_beats"]
            critical = [b for b in beats if b.get("optional") is not True]
            assert critical, f"{title}/{arc['id']}: akt bez krytycznego beatu"
            for b in beats:
                if b.get("optional") is True:
                    seen_optional.add(b["beat_key"])

    assert expected_optional.issubset(seen_optional), (
        f"oczekiwane optional {expected_optional}, oznaczone {seen_optional}"
    )


# ─── Backward compatibility / idempotencja ──────────────────────────────────

def test_patch_idempotent_second_run_no_change():
    """Re-running the patch must not duplicate endings nor re-flip flags."""
    conn = _make_db()
    _patch_campaign_template_endings_and_optional(conn)
    after_first = {t: _load(conn, t) for t in _PRE1019_PLANS}

    _patch_campaign_template_endings_and_optional(conn)
    after_second = {t: _load(conn, t) for t in _PRE1019_PLANS}

    assert after_first == after_second, "patch nie jest idempotentny"
    for title in _PRE1019_PLANS:
        assert len(after_second[title]["endings"]) == 1, f"{title}: zduplikowane endings"


def test_patch_does_not_touch_running_campaigns():
    """Patch only writes campaign_templates; a campaigns table must be untouched."""
    conn = _make_db()
    conn.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY, gm_plan_json TEXT)")
    conn.execute(
        "INSERT INTO campaigns (gm_plan_json) VALUES (?)",
        (json.dumps({"arcs": [], "active_act": 2}),),
    )
    conn.commit()

    _patch_campaign_template_endings_and_optional(conn)

    row = conn.execute("SELECT gm_plan_json FROM campaigns WHERE id = 1").fetchone()
    assert json.loads(row["gm_plan_json"]) == {"arcs": [], "active_act": 2}
