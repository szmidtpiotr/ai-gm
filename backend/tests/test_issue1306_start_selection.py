"""TDD: Issue #1306 — Kuźnia keeps scale/parent/hex in the plan + picks the hub
(not the first travel target) as the flat start location.

Two regressions this covers:
1. `PlotLocation` silently dropped `scale`/`parent`/`hex_q`/`hex_r` via model_dump()
   → settlement structure (#1212) lost on every generated plan.
2. `_flat_start_location_from_plan` treated the first `visit_location` beat of act 1
   (a TRAVEL TARGET) as the START → player anchored on the first dungeon instead of
   the opening town (the "Szlak Rozbitej Gwiazdy" desync).
"""
import sys
sys.path.insert(0, "/app")

from app.services.campaign_plan_service import PlotLocation, PlotReward  # noqa: E402
from app.services.template_start_anchor import _flat_start_location_from_plan  # noqa: E402


# ── #1306.1 — schema no longer drops settlement/hex hints ────────────────────

def test_plotlocation_preserves_scale_parent_hex():
    loc = PlotLocation.model_validate({
        "key": "wilczburg", "name": "Wilczburg", "role": "hub",
        "scale": "hub", "parent": None, "hex_q": 6, "hex_r": 8,
        "description": "Miasto na skraju Kresów.",
    })
    dumped = loc.model_dump()
    assert dumped["scale"] == "hub"
    assert dumped["hex_q"] == 6 and dumped["hex_r"] == 8
    assert dumped["description"].startswith("Miasto")


def test_plotlocation_defaults_are_none():
    loc = PlotLocation.model_validate({"key": "k", "name": "N", "role": "r"})
    d = loc.model_dump()
    assert d["scale"] is None and d["parent"] is None
    assert d["hex_q"] is None and d["hex_r"] is None


def test_plotreward_preserves_is_map_and_reveals():
    rw = PlotReward.model_validate({
        "key": "mapa_popiolu", "label": "Mapa Popiołu",
        "is_map": True, "reveals": ["spalona_kaplica"],
    })
    d = rw.model_dump()
    assert d["is_map"] is True
    assert d["reveals"] == ["spalona_kaplica"]


# ── #1306.2 — flat start = hub, not the first visit_location travel target ────

def _szlak_plan():
    """Mirror of "Szlak Rozbitej Gwiazdy" act 0: social opener in Wilczburg, first
    visit_location beat targets the chapel (a destination, not the start)."""
    return {
        "key_locations": [
            {"key": "wilczburg", "name": "Wilczburg", "role": "hub"},
            {"key": "spalona_kaplica", "name": "Spalona Kaplica", "role": "dungeon"},
        ],
        "acts": [{
            "number": 1,
            "key_beats": [
                {"beat_key": "voss", "objective_type": "talk_to_npc",
                 "objective_value": "marek_voss", "optional": False},
                {"beat_key": "kaplica", "objective_type": "visit_location",
                 "objective_value": "spalona_kaplica", "optional": False},
            ],
        }],
    }


def test_flat_start_is_hub_town_not_visit_target():
    key, label = _flat_start_location_from_plan(_szlak_plan())
    assert key == "wilczburg", "start = miasto z beatem talk_to_npc, nie cel visit_location"
    assert label == "Wilczburg"


def test_flat_start_explicit_hub_wins():
    plan = _szlak_plan()
    plan["key_locations"][1]["scale"] = "hub"  # second loc flagged hub
    plan["key_locations"][0]["scale"] = None
    key, _ = _flat_start_location_from_plan(plan)
    assert key == "spalona_kaplica", "explicit scale=hub jest autorytatywny"


def test_flat_start_pure_visit_opener_keeps_target():
    """Legacy 'you start by arriving somewhere' — no social beat → visit target is start."""
    plan = {
        "key_locations": [{"key": "oboz", "name": "Obóz"}, {"key": "ruiny", "name": "Ruiny"}],
        "acts": [{"number": 1, "key_beats": [
            {"beat_key": "arrive", "objective_type": "visit_location",
             "objective_value": "ruiny", "optional": False},
        ]}],
    }
    key, _ = _flat_start_location_from_plan(plan)
    assert key == "ruiny"


def test_flat_start_no_beats_falls_back_to_first_key_location():
    plan = {"key_locations": [{"key": "oboz_x", "name": "Obóz X"}], "acts": [{"number": 1, "key_beats": []}]}
    key, _ = _flat_start_location_from_plan(plan)
    assert key == "oboz_x"


def test_flat_start_none_when_empty():
    assert _flat_start_location_from_plan({}) is None
    assert _flat_start_location_from_plan({"key_locations": [], "acts": []}) is None
