"""TDD: Issue #474 — Dead code generate_combat_loot / claim_loot removed from economy_service."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ─── RED: these dead functions should NOT exist in economy_service ───────────

def test_generate_combat_loot_not_exported():
    """generate_combat_loot should not exist in economy_service after F14."""
    import app.services.economy_service as es
    assert not hasattr(es, "generate_combat_loot"), (
        "generate_combat_loot is dead code — must be removed from economy_service"
    )


def test_claim_loot_not_exported():
    """claim_loot should not exist in economy_service after F14."""
    import app.services.economy_service as es
    assert not hasattr(es, "claim_loot"), (
        "claim_loot is dead code — must be removed from economy_service"
    )


def test_expire_loot_on_location_change_not_exported():
    """expire_loot_on_location_change is also dead — remove alongside claim_loot."""
    import app.services.economy_service as es
    assert not hasattr(es, "expire_loot_on_location_change"), (
        "expire_loot_on_location_change is dead code — must be removed from economy_service"
    )


# ─── Backward compatibility: live functions still work ─────────────────────

def test_journal_gold_delta_still_present():
    """journal_gold_delta is actively used — must NOT be removed."""
    from app.services.economy_service import journal_gold_delta
    assert callable(journal_gold_delta)


def test_grant_xp_still_present():
    """grant_xp is actively used — must NOT be removed."""
    from app.services.economy_service import grant_xp
    assert callable(grant_xp)


def test_wound_labels_still_present():
    """get_wound_label is used by the frontend — must NOT be removed."""
    from app.services.economy_service import get_wound_label
    assert callable(get_wound_label)
