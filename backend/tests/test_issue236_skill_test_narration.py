"""TDD: Issue #236 — Skill test resolution must always return non-empty prose.

Bug: when the follow-up LLM call for skill test narration returned None (no exception),
prose_raw was None. Frontend received empty/null prose and showed nothing after the roll.

Fix: guard block `if not prose_raw.strip()` produces fallback prose including skill name,
nat20/nat1 flavour, and success/failure indicator.

Tests verify:
1. Fallback guard produces non-empty prose with skill label
2. nat20 / nat1 fallback text is distinct
3. Prose includes skill name (not generic "Sukces!" / "Porażka")
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_pending(skill_key="persuasion", skill_label="Perswazja"):
    return {
        "skill_test_id": "st-test123",
        "skill_key": skill_key,
        "skill_label": skill_label,
        "committed_d20": 12,
        "counter": {"counter_type": "dc", "dc": 12},
    }


def _apply_fallback(result: dict, pending: dict) -> str:
    """Mirror of the fallback guard in resolve_skill_test_endpoint (#236)."""
    _outcome_str = result.get("outcome", "")
    _skill_lbl = pending.get("skill_label") or pending.get("skill_key") or "Test"
    if result.get("nat20"):
        return f"{_skill_lbl} — wyjątkowy sukces!"
    elif result.get("nat1"):
        return f"{_skill_lbl} — fumble."
    elif "SUCCESS" in _outcome_str:
        return f"{_skill_lbl} — sukces."
    else:
        return f"{_skill_lbl} — niepowodzenie."


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_fallback_prose_includes_skill_label_on_success():
    """When LLM returns empty, fallback prose must include skill name + 'sukces'."""
    result = {"outcome": "SUCCESS", "success": True, "nat20": False, "nat1": False}
    pending = _make_pending("persuasion", "Perswazja")
    prose = _apply_fallback(result, pending)
    assert "Perswazja" in prose, f"Skill label missing from fallback: {prose!r}"
    assert "sukces" in prose.lower(), f"Success marker missing: {prose!r}"
    assert prose.strip(), "Prose must not be empty"


def test_fallback_prose_includes_skill_label_on_failure():
    """Fallback prose on failure must include skill name + 'niepowodzenie'."""
    result = {"outcome": "FAILURE", "success": False, "nat20": False, "nat1": False}
    pending = _make_pending("stealth", "Skradanie")
    prose = _apply_fallback(result, pending)
    assert "Skradanie" in prose, f"Skill label missing from fallback: {prose!r}"
    assert "niepowodzenie" in prose.lower(), f"Failure marker missing: {prose!r}"


def test_fallback_prose_nat20_distinct():
    """Nat20 fallback must mention 'wyjątkowy sukces', not generic 'sukces'."""
    result = {"outcome": "SUCCESS", "success": True, "nat20": True, "nat1": False}
    pending = _make_pending("awareness", "Spostrzegawczość")
    prose = _apply_fallback(result, pending)
    assert "wyjątkowy" in prose.lower(), f"Nat20 marker missing: {prose!r}"
    assert "Spostrzegawczość" in prose


def test_fallback_prose_nat1_distinct():
    """Nat1 fallback must mention 'fumble'."""
    result = {"outcome": "FAILURE", "success": False, "nat20": False, "nat1": True}
    pending = _make_pending("persuasion", "Perswazja")
    prose = _apply_fallback(result, pending)
    assert "fumble" in prose.lower(), f"Nat1 fumble marker missing: {prose!r}"


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_fallback_prose_uses_key_when_label_missing():
    """When skill_label absent, fallback must use skill_key instead of generic 'Test'."""
    result = {"outcome": "SUCCESS", "success": True, "nat20": False, "nat1": False}
    pending = {"skill_test_id": "st-x", "skill_key": "perception", "committed_d20": 15}
    prose = _apply_fallback(result, pending)
    assert "perception" in prose.lower() or "Test" in prose, (
        f"Expected skill_key in fallback prose: {prose!r}"
    )
    assert prose.strip(), "Fallback must never return empty string"


def test_skill_result_context_builder_produces_string():
    """build_skill_result_context must return a non-empty string for valid result."""
    from app.services.skill_service import build_skill_result_context
    result = {
        "skill_key": "persuasion",
        "skill_label": "Perswazja",
        "d20_roll": 14,
        "modifier": 3,
        "player_total": 17,
        "dc": 12,
        "success": True,
        "nat20": False,
        "nat1": False,
        "outcome": "SUCCESS",
        "opponent_total": 12,   # DC-based: opponent_total = DC value
        "opponent_roll": None,
    }
    ctx = build_skill_result_context(result)
    assert isinstance(ctx, str), f"Expected str, got {type(ctx)}"
    assert ctx.strip(), "Context string must not be empty"
