"""TDD: Issue #349 — B3 Gate Mechanic: validate actions against World State before LLM."""
import json
import sqlite3

import pytest

from app.services.gate_service import GateResult, validate_action, classify_intent_stub
from app.services.world_state_service import set_world_state_flags

DB_PATH = "/data/ai_gm.db"
TEST_CAMPAIGN_ID = 99349
TEST_SESSION_ID = "test-session-99349"

_ALIVE_GOBLIN = {"key": "goblin_01", "name": "Goblin", "hp": 10, "zone": "engaged"}
_DEAD_GOBLIN = {"key": "goblin_01", "name": "Goblin", "hp": 0, "zone": "engaged"}
_ALIVE_ORC = {"key": "orc_01", "name": "Ork", "hp": 25, "zone": "engaged"}


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_session():
    """Fresh game_session with no enemies before each test."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (TEST_CAMPAIGN_ID,))
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (?, ?, '{}')",
        (TEST_SESSION_ID, TEST_CAMPAIGN_ID),
    )
    conn.commit()
    conn.close()
    yield
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (TEST_CAMPAIGN_ID,))
    conn.commit()
    conn.close()


# ─── GateResult dataclass ─────────────────────────────────────────────────────

def test_gate_result_allowed_has_no_feedback():
    """GateResult(allowed=True) should work with no reason/feedback."""
    gr = GateResult(allowed=True)
    assert gr.allowed is True
    assert gr.reason is None
    assert gr.feedback is None


def test_gate_result_blocked_has_polish_feedback():
    """GateResult(allowed=False) must carry a Polish player-facing message."""
    gr = GateResult(allowed=False, reason="combat_active", feedback="Jesteś w walce!")
    assert gr.allowed is False
    assert gr.feedback is not None
    assert len(gr.feedback) > 0


# ─── Combat gating: non-combat action blocked when enemies alive ──────────────

def test_gate_blocks_dialogue_when_enemies_alive():
    """DIALOGUE intent → blocked when scene has alive enemies."""
    set_world_state_flags(TEST_CAMPAIGN_ID, scene_enemies=[_ALIVE_GOBLIN])
    result = validate_action(TEST_CAMPAIGN_ID, "Chcę porozmawiać z tobą", {"action_type": "DIALOGUE"})
    assert result.allowed is False
    assert result.feedback is not None
    # Must contain Polish combat cue
    assert any(w in (result.feedback or "").lower() for w in ("walce", "walka", "wróg", "przeciwnik"))


def test_gate_blocks_movement_when_enemies_alive():
    """MOVEMENT intent → blocked when scene has alive enemies."""
    set_world_state_flags(TEST_CAMPAIGN_ID, scene_enemies=[_ALIVE_GOBLIN])
    result = validate_action(TEST_CAMPAIGN_ID, "Idę do karczmy", {"action_type": "MOVEMENT"})
    assert result.allowed is False


def test_gate_blocks_rest_when_enemies_alive():
    """REST intent → blocked when scene has alive enemies."""
    set_world_state_flags(TEST_CAMPAIGN_ID, scene_enemies=[_ALIVE_GOBLIN])
    result = validate_action(TEST_CAMPAIGN_ID, "Odpoczywam", {"action_type": "REST"})
    assert result.allowed is False


def test_gate_allows_attack_when_enemies_alive():
    """ATTACK intent → allowed when scene has alive enemies (combat is valid)."""
    set_world_state_flags(TEST_CAMPAIGN_ID, scene_enemies=[_ALIVE_GOBLIN])
    result = validate_action(
        TEST_CAMPAIGN_ID,
        "Atakuję goblina mieczem",
        {"action_type": "ATTACK", "target": "goblin_01"},
    )
    assert result.allowed is True


def test_gate_allows_flee_when_enemies_alive():
    """FLEE intent → allowed even with alive enemies."""
    set_world_state_flags(TEST_CAMPAIGN_ID, scene_enemies=[_ALIVE_GOBLIN])
    result = validate_action(TEST_CAMPAIGN_ID, "Uciekam!", {"action_type": "FLEE"})
    assert result.allowed is True


# ─── No enemies: all actions allowed ─────────────────────────────────────────

def test_gate_allows_all_when_no_enemies():
    """No enemies in scene → any action is allowed."""
    # scene_enemies defaults to [] via fixture
    for action_type in ("DIALOGUE", "MOVEMENT", "SEARCH", "REST", "ATTACK"):
        result = validate_action(TEST_CAMPAIGN_ID, "Akcja", {"action_type": action_type})
        assert result.allowed is True, f"Expected allowed=True for {action_type} with no enemies"


# ─── Dead target gating ───────────────────────────────────────────────────────

def test_gate_blocks_attack_on_dead_target():
    """ATTACK targeting a dead enemy (hp=0) → blocked."""
    set_world_state_flags(TEST_CAMPAIGN_ID, scene_enemies=[_DEAD_GOBLIN])
    result = validate_action(
        TEST_CAMPAIGN_ID,
        "Atakuję goblina",
        {"action_type": "ATTACK", "target": "goblin_01"},
    )
    assert result.allowed is False
    assert result.feedback is not None


def test_gate_allows_attack_when_target_alive():
    """ATTACK targeting an alive enemy → allowed."""
    set_world_state_flags(TEST_CAMPAIGN_ID, scene_enemies=[_ALIVE_GOBLIN])
    result = validate_action(
        TEST_CAMPAIGN_ID,
        "Atakuję goblina",
        {"action_type": "ATTACK", "target": "goblin_01"},
    )
    assert result.allowed is True


def test_gate_allows_attack_no_target_specified():
    """ATTACK with no target key → allowed (target resolution happens later)."""
    set_world_state_flags(TEST_CAMPAIGN_ID, scene_enemies=[_ALIVE_GOBLIN])
    result = validate_action(TEST_CAMPAIGN_ID, "Atakuję!", {"action_type": "ATTACK"})
    assert result.allowed is True


# ─── Scene cleared gating ─────────────────────────────────────────────────────

def test_gate_blocks_attack_when_scene_cleared():
    """scene_cleared=True + ATTACK intent → blocked (no enemies left)."""
    set_world_state_flags(TEST_CAMPAIGN_ID, scene_cleared=True, scene_enemies=[_DEAD_GOBLIN])
    result = validate_action(
        TEST_CAMPAIGN_ID,
        "Atakuję jeszcze raz!",
        {"action_type": "ATTACK", "target": "goblin_01"},
    )
    assert result.allowed is False


def test_gate_allows_dialogue_when_scene_cleared():
    """scene_cleared=True + non-combat action → allowed (exploration mode)."""
    set_world_state_flags(TEST_CAMPAIGN_ID, scene_cleared=True, scene_enemies=[_DEAD_GOBLIN])
    result = validate_action(
        TEST_CAMPAIGN_ID,
        "Rozglądam się",
        {"action_type": "SEARCH"},
    )
    assert result.allowed is True


# ─── Keyword stub classifier ──────────────────────────────────────────────────

def test_stub_classifies_attack_polish():
    """'Atakuję' → action_type ATTACK."""
    intent = classify_intent_stub("Atakuję goblina mieczem!")
    assert intent["action_type"] == "ATTACK"


def test_stub_classifies_dialogue():
    """'Mówię' / 'porozmawiać' → DIALOGUE."""
    intent = classify_intent_stub("Chcę porozmawiać z elfem")
    assert intent["action_type"] == "DIALOGUE"


def test_stub_classifies_movement():
    """'Idę' / 'biegnę' → MOVEMENT."""
    intent = classify_intent_stub("Idę do lasu na północy")
    assert intent["action_type"] == "MOVEMENT"


def test_stub_classifies_rest():
    """'Odpoczywam' → REST."""
    intent = classify_intent_stub("Odpoczywam przy ognisku")
    assert intent["action_type"] == "REST"


def test_stub_returns_default_for_unknown():
    """Unknown input → default action type, never raises."""
    intent = classify_intent_stub("xyzzy frobozz")
    assert "action_type" in intent  # any valid key — no crash


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_world_state_service_still_imports():
    """B1/B2 functions remain importable alongside gate_service."""
    from app.services.world_state_service import (
        get_latest_snapshot,
        save_snapshot,
        get_world_state_flags,
        set_world_state_flags,
    )
    assert all(callable(f) for f in (get_latest_snapshot, save_snapshot,
                                      get_world_state_flags, set_world_state_flags))
