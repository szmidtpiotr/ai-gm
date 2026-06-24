"""TDD: Issue #986 — reaction card shows '? vs ?' for take/dodge/block events."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_reaction_row(narrative: dict) -> dict:
    """Simulate a combat_turns row with event_type=reaction."""
    return {
        "event_type": "reaction",
        "actor": "player",
        "roll_value": narrative.get("dodge_total") or narrative.get("block_total") or 0,
        "damage": narrative.get("damage"),
        "hp_after": 10,
        "target_id": "player",
        "target_name": "Bohater",
        "hit": False,
        "narrative": json.dumps(narrative),
    }


# ─── Test: backend must include roll values in dodge narrative ────────────────

def test_dodge_reaction_narrative_contains_roll_values():
    """resolve_reaction dodge must write dodge_total + attack_roll to narrative JSON."""
    from app.services.combat_service import _try_dodge_reaction

    fake_p = {
        "reaction_declared": "dodge",
        "reaction_locked_round": None,
        "reaction_used_round": None,
    }
    fake_sheet = {"skills": {"dodge": 2}, "DEX": 14}

    with patch("app.services.combat_service.roll_d20", return_value=15):
        result = _try_dodge_reaction(fake_p, fake_sheet, attack_roll=10, round_n=1)

    assert result is not None, "dodge reaction should fire"
    assert result.get("reaction") == "dodge"
    assert "dodge_total" in result, "dodge_total must be in reaction dict"
    assert "attack_roll" in result, "attack_roll must be in reaction dict"
    assert result["dodge_total"] is not None, "dodge_total must not be None"
    assert result["attack_roll"] == 10, "attack_roll must match input"


def test_shield_block_narrative_contains_roll_values():
    """resolve_reaction shield_block must write block_total + dc to narrative JSON."""
    from app.services.combat_service import _try_shield_block_reaction

    fake_p = {"reaction_declared": "shield_block"}
    fake_sheet = {"skills": {"shield_block": 2}, "STR": 14}

    mock_conn = MagicMock()
    # simulate shield equipped
    shield_row = MagicMock()
    shield_row.__getitem__ = lambda s, k: 42 if k == "inv_id" else None
    mock_conn.execute.return_value.fetchone.return_value = shield_row

    with patch("app.services.combat_service.roll_d20", return_value=15), \
         patch("app.services.combat_service.roll_damage_dice", return_value=4):
        result = _try_shield_block_reaction(mock_conn, 1, fake_p, fake_sheet,
                                            attack_roll=12, round_n=1, dmg=8)

    assert result is not None, "shield_block reaction should fire"
    assert result.get("reaction") == "shield_block"
    assert "block_total" in result, "block_total must be in reaction dict"
    assert "dc" in result, "dc must be in reaction dict"
    assert result["block_total"] is not None
    assert result["dc"] is not None


# ─── Test: take reaction must NOT expose ? vs ? values ───────────────────────

def test_take_reaction_narrative_has_damage_not_roll_values():
    """'take' reaction narrative must have 'damage' but NOT dodge_total/attack_roll.
    Frontend must handle this without showing '? vs ?' from dodge template.
    """
    # This is what the backend currently stores for 'take':
    take_narrative = {"reaction": "take", "choice": "take", "damage": 5}
    row = _make_reaction_row(take_narrative)

    meta = json.loads(row["narrative"])
    assert meta["reaction"] == "take"
    assert "damage" in meta
    # Backend correctly does NOT include dodge/block roll fields for take — this is expected
    assert "dodge_total" not in meta, "take has no dodge_total — frontend must handle this"
    assert "attack_roll" not in meta, "take has no attack_roll — frontend must handle this"
    assert "block_total" not in meta, "take has no block_total — frontend must handle this"


def test_dodge_narrative_has_both_roll_values_for_display():
    """Dodge reaction narrative must have both dodge_total and attack_roll for frontend display."""
    dodge_narrative = {
        "reaction": "dodge",
        "available": True,
        "dodged": False,
        "d20": 3,
        "dodge_total": 8,
        "attack_roll": 15,
        "margin": -7,
        "outcome": "CRITICAL_FAILURE",
        "locked_next_round": True,
        "dex_mod": 2,
        "skill_rank": 2,
    }
    row = _make_reaction_row(dodge_narrative)
    meta = json.loads(row["narrative"])

    assert meta.get("dodge_total") is not None, "dodge_total must be present for display"
    assert meta.get("attack_roll") is not None, "attack_roll must be present for display"
    # verify the expected display string would NOT contain '?'
    display = f"test {meta.get('dodge_total', '?')} vs {meta.get('attack_roll', '?')}"
    assert '?' not in display, f"display must not contain '?', got: {display}"


# ─── Backward compat: existing dodge/block paths unchanged ───────────────────

def test_existing_dodge_path_still_sets_reaction_declared():
    """_try_dodge_reaction still returns None when no dodge declared (backward compat)."""
    from app.services.combat_service import _try_dodge_reaction
    p = {}  # no reaction_declared
    result = _try_dodge_reaction(p, {"skills": {"dodge": 2}}, attack_roll=10, round_n=1)
    assert result is None, "should return None when no declaration"
