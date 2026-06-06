"""TDD: Issue #357 — C3 Gate walki: ATTACK blokowany gdy scene_enemies puste."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch


def _gate(scene_enemies, scene_cleared=False, action_type="ATTACK", target_key=None):
    """Helper: call validate_action with mocked world state."""
    from app.services.gate_service import validate_action
    ws = {
        "scene_enemies": scene_enemies,
        "scene_cleared": scene_cleared,
        "active_quests": [],
        "player_conditions": [],
        "scene_npcs": [],
    }
    intent = {"action_type": action_type}
    if target_key:
        intent["target"] = target_key
    with patch("app.services.gate_service.get_world_state_flags", return_value=ws):
        return validate_action(campaign_id=1, player_input="atak", intent=intent)


# ─── Test 1: ATTACK gdy scene_enemies puste → blokada ───────────────────────

def test_attack_blocked_when_no_enemies_in_scene():
    """ATTACK z pustą scene_enemies musi być zablokowany."""
    result = _gate(scene_enemies=[])
    assert result.allowed is False
    assert result.reason == "no_enemies"
    assert result.feedback  # jakaś wiadomość


# ─── Test 2: ATTACK gdy wrogowie żywi → przepuszczony ───────────────────────

def test_attack_allowed_when_enemies_alive():
    """ATTACK z żywymi wrogami w scenie musi przechodzić."""
    enemies = [{"key": "goblin_1", "name": "Goblin", "hp": 10}]
    result = _gate(scene_enemies=enemies)
    assert result.allowed is True


# ─── Test 3: Trwająca walka (żywi wrogowie) nie jest przerywana ─────────────

def test_attack_allowed_during_active_combat():
    """Podczas aktywnej walki (wrogowie w scene_enemies z HP > 0) ATTACK musi przechodzić."""
    enemies = [
        {"key": "orc_1", "name": "Ork", "hp": 20},
        {"key": "goblin_1", "name": "Goblin", "hp": 0},  # jeden martwy
    ]
    result = _gate(scene_enemies=enemies)
    assert result.allowed is True


# ─── Test 4: Wszyscy martwi (istnieli) → blokada (stare zachowanie) ─────────

def test_attack_blocked_when_all_enemies_dead():
    """Gdy wrogowie istnieli ale wszyscy HP=0 → blokada (stare zachowanie zachowane)."""
    enemies = [{"key": "goblin_1", "name": "Goblin", "hp": 0}]
    result = _gate(scene_enemies=enemies)
    assert result.allowed is False


# ─── Test 5: scene_cleared=True → blokada (stare zachowanie) ────────────────

def test_attack_blocked_when_scene_cleared():
    """scene_cleared=True → blokada (stare zachowanie zachowane)."""
    result = _gate(scene_enemies=[], scene_cleared=True)
    assert result.allowed is False


# ─── Test 6: Inne akcje z pustą sceną → NIE blokowane przez no_enemies ──────

def test_dialogue_allowed_when_no_enemies():
    """DIALOGUE z pustą scene_enemies → przepuszczony (nie-combat akcja)."""
    result = _gate(scene_enemies=[], action_type="DIALOGUE")
    assert result.allowed is True


# ─── Test 7: Konkretny target martwy → blokada (stare zachowanie) ───────────

def test_attack_blocked_targeting_dead_enemy():
    """Atak na konkretnego martwego wroga → blokada (stare zachowanie zachowane)."""
    enemies = [{"key": "goblin_1", "name": "Goblin", "hp": 0}]
    result = _gate(scene_enemies=enemies, target_key="goblin_1")
    assert result.allowed is False
