"""TDD: #1254 (TS1 defect) — resolver prefers the hub's own sub-location.

"kuźnia Brunna" inside a settlement must resolve to the hub's sub-location
``kuznia_na_skraju_wsi`` (placed on the settlement hex), NOT a global floating
macro "Kuźnia Brunna" that sits outside the settlement with no world_hex — which
used to win by full-string fuzzy score and desync pin ↔ location.
"""
import sys

sys.path.insert(0, "/app")


HUB = {"id": 1, "key": "blotstein", "label": "Błotstein",
       "location_type": "macro", "parent_id": None, "world_hex_q": 0, "ai_generated": 0}
SUB_FORGE = {"id": 2, "key": "kuznia_na_skraju_wsi", "label": "Kuźnia na skraju wsi",
             "location_type": "sub", "parent_id": 1, "world_hex_q": 0, "ai_generated": 0}
FLOATING_FORGE = {"id": 9, "key": "kuznia", "label": "Kuźnia Brunna",
                  "location_type": "macro", "parent_id": None, "world_hex_q": None, "ai_generated": 0}
PLACED_MACRO = {"id": 5, "key": "vilnograd", "label": "Vilnograd",
                "location_type": "macro", "parent_id": None, "world_hex_q": 4, "ai_generated": 0}


def _match(target, locations, current_loc):
    from app.services.location_validator import _fuzzy_match_location_hub_aware
    return _fuzzy_match_location_hub_aware(target, locations, current_loc)


def test_hub_sub_wins_over_floating_macro():
    """The classic #1254 case: forge sub-location of the current hub beats the
    identically-named global floating macro without a hex."""
    m = _match("kuźnia Brunna", [FLOATING_FORGE, SUB_FORGE], HUB)
    assert m is not None
    assert m["key"] == "kuznia_na_skraju_wsi", m["key"]


def test_floating_no_hex_excluded_inside_settlement():
    """When a hub sub matches, the placeless floating macro is not even returned."""
    m = _match("idę do kuźni Brunna", [FLOATING_FORGE, SUB_FORGE], HUB)
    assert m["key"] != "kuznia"


def test_placed_wins_over_floating_without_hub_context():
    """Even with no current location, a placed location beats a floating one."""
    m = _match("kuźnia Brunna", [FLOATING_FORGE, SUB_FORGE], None)
    assert m["key"] == "kuznia_na_skraju_wsi"


def test_strong_named_macro_still_matches():
    """A plain strong name match (Vilnograd) still resolves normally."""
    m = _match("Vilnograd", [PLACED_MACRO, FLOATING_FORGE, SUB_FORGE], HUB)
    assert m["key"] == "vilnograd"


def test_only_floating_matches_returns_floating():
    """If nothing hub-local matches, a genuine floating match is still returned."""
    m = _match("Kuźnia Brunna", [FLOATING_FORGE], None)
    assert m is not None and m["key"] == "kuznia"


def test_unrelated_target_returns_none():
    m = _match("smocza jaskinia", [FLOATING_FORGE, SUB_FORGE], HUB)
    assert m is None
