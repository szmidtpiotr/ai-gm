"""TDD: Issue #1025 — remove legacy 'Następna scena' button and advance-scene endpoint (V1 dead code).

V2 uses active_act + beat.visited for progression. current_scene_ordinal is never read
by narrator/game_engine/context_injector — the button only bumped a dead counter.
"""
import sys
import pytest

sys.path.insert(0, '/app')


# ─── RED tests — these FAIL until the dead code is removed ───────────────────

def test_advance_scene_service_removed():
    """advance_campaign_scene_admin must not exist in admin_campaigns.py."""
    import app.services.admin_campaigns as mod
    assert not hasattr(mod, 'advance_campaign_scene_admin'), (
        "advance_campaign_scene_admin still exported from admin_campaigns — "
        "it's V1 dead code; remove it (#1025)"
    )


def test_advance_scene_admin_route_handler_removed():
    """admin_advance_campaign_scene route handler must be removed from admin router."""
    import app.routers.admin as mod
    assert not hasattr(mod, 'admin_advance_campaign_scene'), (
        "admin_advance_campaign_scene still in admin.py — "
        "remove the route handler and its request model AdminAdvanceSceneReq (#1025)"
    )


def test_advance_scene_player_api_removed():
    """advance_campaign_scene player endpoint must be removed from campaigns router."""
    import app.api.campaigns as mod
    assert not hasattr(mod, 'advance_campaign_scene'), (
        "advance_campaign_scene still in api/campaigns.py — "
        "remove the /gm-plan/advance-scene player route (#1025)"
    )


def test_advance_scene_req_model_removed():
    """AdminAdvanceSceneReq request model must be removed with its endpoint."""
    import app.routers.admin as mod
    assert not hasattr(mod, 'AdminAdvanceSceneReq'), (
        "AdminAdvanceSceneReq still in admin.py — "
        "remove it together with the endpoint (#1025)"
    )


# ─── Backward compat — must stay GREEN before and after fix ──────────────────

def test_admin_campaigns_module_still_importable():
    """admin_campaigns.py must import cleanly after removing advance_campaign_scene_admin."""
    import importlib
    import app.services.admin_campaigns as mod
    importlib.reload(mod)
    # Core functions untouched
    assert hasattr(mod, 'get_campaign_gm_plan_admin'), "get_campaign_gm_plan_admin missing"
    assert hasattr(mod, 'regenerate_campaign_gm_plan_admin'), "regenerate_campaign_gm_plan_admin missing"
    assert hasattr(mod, 'replace_campaign_gm_plan_admin'), "replace_campaign_gm_plan_admin missing"


def test_admin_router_still_importable():
    """admin.py router must import cleanly after removing advance-scene handler."""
    import importlib
    import app.routers.admin as mod
    importlib.reload(mod)
    assert hasattr(mod, 'router'), "admin router object missing after cleanup"
