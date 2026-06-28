"""TDD: Issue #1017 — Forge plan generator: key_beats jako struktura (PlotBeat), nie stringi.

Cała maszyneria wygranej (#1009–#1014) wymaga, by acts[].key_beats[] były obiektami
z `beat_key`. Generator dotąd produkował gołe stringi. Te testy wymuszają model PlotBeat
z koercją string→obiekt (wsteczna zgodność) i unikalnymi beat_key w obrębie planu.
"""
import sys
sys.path.insert(0, "/app")

import pytest

from app.services.campaign_plan_service import PlotAct, PlotBeat, CampaignPlan


# ─── helpers ─────────────────────────────────────────────────────────────────

def _minimal_plan(acts: list[dict]) -> dict:
    """Build a minimal-but-valid CampaignPlan dict with the given acts."""
    return {
        "title": "Mroczna Kampania",
        "premise": "Konflikt.",
        "acts": acts,
        "endings": [
            {"id": "ending_primary", "title": "A", "type": "primary",
             "description": "x", "requirements": ["r"]},
            {"id": "ending_alternate", "title": "B", "type": "alternate",
             "description": "y", "requirements": ["r"]},
        ],
        "key_npcs": [
            {"key": "npc_a", "name": "A", "role": "r",
             "importance": "critical", "deviation_consequence": "branch", "alive": True},
        ],
        "key_locations": [
            {"key": "loc_a", "name": "A", "role": "starting_point", "visited": False},
        ],
        "active_act": 1,
        "engine_private": {
            "secret_predisposition_hint": "h", "hidden_twist": "t", "contingency": "c"
        },
    }


# ─── Test główny: model PlotBeat ─────────────────────────────────────────────

def test_plotbeat_model_exists_with_fields():
    """PlotBeat ma beat_key, summary, objective_type, objective_value, optional."""
    b = PlotBeat(beat_key="zabij_smoka", summary="Zabij smoka",
                 objective_type="kill_enemy", objective_value="dragon", optional=False)
    assert b.beat_key == "zabij_smoka"
    assert b.objective_type == "kill_enemy"
    assert b.optional is False


def test_plotact_keeps_structured_beats():
    """Akt z beatami-obiektami zachowuje beat_key/objective/optional."""
    act = PlotAct.model_validate({
        "number": 1, "title": "Akt 1", "summary": "s",
        "key_beats": [
            {"beat_key": "spotkanie", "summary": "Spotkanie z wiedźmą",
             "objective_type": "talk_to_npc", "objective_value": "witch", "optional": True},
        ],
    })
    assert isinstance(act.key_beats[0], PlotBeat)
    assert act.key_beats[0].beat_key == "spotkanie"
    assert act.key_beats[0].optional is True
    assert act.key_beats[0].objective_type == "talk_to_npc"


def test_plotact_coerces_string_beats_to_objects():
    """KLUCZOWE: gołe stringi (stary generator) podnoszone do PlotBeat z beat_key+summary."""
    act = PlotAct.model_validate({
        "number": 1, "title": "Akt 1", "summary": "s",
        "key_beats": ["Zabij smoka", "Znajdź zaginiony miecz"],
    })
    assert all(isinstance(b, PlotBeat) for b in act.key_beats)
    assert act.key_beats[0].summary == "Zabij smoka"
    assert act.key_beats[0].beat_key  # niepusty slug
    assert " " not in act.key_beats[0].beat_key
    assert act.key_beats[0].beat_key == act.key_beats[0].beat_key.lower()


def test_dict_beat_without_beat_key_gets_generated_slug():
    """Beat-obiekt bez beat_key dostaje deterministyczny slug z summary."""
    act = PlotAct.model_validate({
        "number": 1, "title": "Akt 1", "summary": "s",
        "key_beats": [{"summary": "Spotkanie z wiedźmą"}],
    })
    assert act.key_beats[0].beat_key
    assert " " not in act.key_beats[0].beat_key


def test_beat_keys_unique_within_plan():
    """Te same summary w różnych aktach → różne beat_key (unikalność w obrębie planu)."""
    plan = CampaignPlan.model_validate(_minimal_plan([
        {"number": 1, "title": "A1", "summary": "s", "key_beats": ["Spotkanie"]},
        {"number": 2, "title": "A2", "summary": "s", "key_beats": ["Spotkanie"]},
    ]))
    all_keys = [b.beat_key for act in plan.acts for b in act.key_beats]
    assert len(all_keys) == len(set(all_keys)), f"duplikaty beat_key: {all_keys}"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_full_plan_with_string_beats_still_validates():
    """Stary plan z key_beats=list[str] nadal się ładuje (podniesiony do obiektów)."""
    plan = CampaignPlan.model_validate(_minimal_plan([
        {"number": 1, "title": "A1", "summary": "s",
         "key_beats": ["Beat jeden", "Beat dwa", "Beat trzy"]},
    ]))
    assert len(plan.acts[0].key_beats) == 3
    assert all(isinstance(b, PlotBeat) for b in plan.acts[0].key_beats)


def test_empty_beats_list_ok():
    """Akt bez beatów nadal waliduje (pusta lista)."""
    act = PlotAct.model_validate({
        "number": 1, "title": "A", "summary": "s", "key_beats": [],
    })
    assert act.key_beats == []


# ─── Integracja z walidatorem #1010 (acceptance) ─────────────────────────────

def test_find_orphan_beats_runs_on_generated_plan_keys_not_missing():
    """#1010 walidator działa na planie #1017 — sieroty mają beat_key, nie '<no-key>'.

    Beat z objective_type → nie sierota; optional → nie sierota; plain → flagowany,
    ale z prawdziwym beat_key (dowód że struktura ma klucze)."""
    from app.services.campaign_plan_runtime import find_orphan_beats

    plan = CampaignPlan.model_validate(_minimal_plan([
        {"number": 1, "title": "A1", "summary": "s", "key_beats": [
            {"beat_key": "boss", "summary": "Pokonaj bossa",
             "objective_type": "kill_enemy", "objective_value": "boss"},
            {"beat_key": "poboczny", "summary": "Scena poboczna", "optional": True},
            {"summary": "Negocjacje z radą"},  # plain → narrative-close beat
        ]},
    ])).model_dump()

    orphans = find_orphan_beats(plan)
    assert "boss" not in orphans            # ma objective_type
    assert "poboczny" not in orphans        # optional
    assert "<no-key>" not in orphans        # każdy beat ma klucz
    assert all(o and o != "<no-key>" for o in orphans)
