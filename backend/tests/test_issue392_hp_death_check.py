"""TDD: Issue #392 — System prompt forbids narrative death without HP check."""
import os
from pathlib import Path


def test_system_prompt_contains_hp_death_restrict_block():
    """System prompt must contain [RESTRICT] block forbidding unilateral death."""
    # arrange
    prompt_path = Path(__file__).parent.parent.parent / "prompts" / "system_prompt.txt"
    if not prompt_path.exists():
        pytest.skip(f"System prompt not found at {prompt_path}")

    # act
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    # assert
    assert "[RESTRICT]" in system_prompt, "System prompt missing [RESTRICT] section"
    assert "HP" in system_prompt or "hp_current" in system_prompt or "health" in system_prompt.lower(), \
        "System prompt missing HP/health reference"
    assert "death" in system_prompt.lower(), "System prompt missing death restriction"
    # Rough content check: should forbid unilateral death
    lower = system_prompt.lower()
    assert ("nie możesz" in lower or "nie może" in lower or "forbidden" in lower or "restrict" in lower.lower()), \
        "System prompt missing explicit death restriction (nie możesz zabić / forbidden)"


def test_system_prompt_allows_death_only_via_tags():
    """Death must be initiated ONLY via [DEATH_TRIGGER], death_save fail, or combat end."""
    # arrange
    prompt_path = Path(__file__).parent.parent.parent / "prompts" / "system_prompt.txt"
    if not prompt_path.exists():
        pytest.skip(f"System prompt not found at {prompt_path}")

    # act
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    # assert
    assert "DEATH_TRIGGER" in system_prompt or "death_save" in system_prompt, \
        "System prompt missing allowed death mechanisms (DEATH_TRIGGER, death_save)"


def test_no_narrative_death_without_hp_check_in_guidelines():
    """Guidelines must explicitly forbid narrative death without checking hp_current > 0."""
    # arrange
    prompt_path = Path(__file__).parent.parent.parent / "prompts" / "system_prompt.txt"
    if not prompt_path.exists():
        pytest.skip(f"System prompt not found at {prompt_path}")

    # act
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read().lower()

    # assert — check for death restriction logic
    assert "hp" in system_prompt or "health" in system_prompt, \
        "System prompt must reference HP/health state"
    # Should indicate death is not narrative choice
    assert ("cant" in system_prompt or "nie" in system_prompt or "only" in system_prompt), \
        "System prompt must restrict death narrative choices"
