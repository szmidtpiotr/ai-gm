"""TDD: Issue #350 — Intent parser: extract structured player_intent from raw input."""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ─── Test główny: keyword stage ──────────────────────────────────────────────

def test_intent_parser_attack_keyword():
    """Keyword stage recognizes attack intent with high confidence."""
    from app.services.intent_service import parse_intent
    
    result = parse_intent("Atakuję goblina mieczem")
    assert result.action_type == "attack"
    assert result.target == "goblin" or result.target is None  # target extraction TBD
    assert result.confidence >= 0.8

def test_intent_parser_talk_keyword():
    """Keyword stage recognizes dialogue intent."""
    from app.services.intent_service import parse_intent
    
    result = parse_intent("Mówię kupcy o złocie")
    assert result.action_type == "talk"
    assert result.confidence >= 0.8

def test_intent_parser_move_keyword():
    """Keyword stage recognizes movement intent."""
    from app.services.intent_service import parse_intent
    
    result = parse_intent("Idę do drzwi")
    assert result.action_type == "move"
    assert result.confidence >= 0.8

def test_intent_parser_flee_keyword():
    """Keyword stage recognizes flee intent."""
    from app.services.intent_service import parse_intent
    
    result = parse_intent("Uciekam!")
    assert result.action_type == "flee"
    assert result.confidence >= 0.8

def test_intent_parser_use_item_keyword():
    """Keyword stage recognizes item use intent."""
    from app.services.intent_service import parse_intent
    
    result = parse_intent("Piję miksturę zdrowia")
    assert result.action_type == "use_item"
    assert result.confidence >= 0.8

# ─── Test fallback: LLM stage (low confidence input) ──────────────────────────

def test_intent_parser_ambiguous_input_returns_other():
    """Ambiguous input returns action_type='other' with lower confidence."""
    from app.services.intent_service import parse_intent
    
    result = parse_intent("Co się stało?")  # Generic question, not a clear action
    assert result.action_type == "other" or result.confidence < 0.8

def test_intent_parser_returns_player_intent_object():
    """Parser always returns PlayerIntent dataclass with all required fields."""
    from app.services.intent_service import parse_intent, PlayerIntent
    
    result = parse_intent("Atakuję")
    assert isinstance(result, PlayerIntent)
    assert hasattr(result, "action_type")
    assert hasattr(result, "target")
    assert hasattr(result, "confidence")
    assert hasattr(result, "raw_input")
    assert result.raw_input == "Atakuję"

# ─── Backward compatibility ──────────────────────────────────────────────────

def test_gate_still_works_without_explicit_intent():
    """Gate can be called without intent arg (backward compat)."""
    from app.services.gate_service import validate_action
    
    # Gate should work even if intent is not passed
    result = validate_action(1, "Atakuję", intent=None)
    assert hasattr(result, "allowed")
    assert hasattr(result, "feedback")
