"""TDD: Issue #953 — turns tab must show full text with expand/collapse, no hardcoded slice."""
from pathlib import Path

# Runs in container: JS file copied alongside test as campaigns_953_source.js
# Runs on host (if pytest installed): finds file via relative path
_candidates = [
    Path("/app/tests/campaigns_953_source.js"),
    Path(__file__).parent.parent.parent / "frontend/admin/sections/campaigns.js",
]
CAMPAIGNS_JS = next((p for p in _candidates if p.exists()), _candidates[0])


def test_no_hardcoded_slice_in_turns_render():
    """campaigns.js must not contain hardcoded text slicing in turns render."""
    js = CAMPAIGNS_JS.read_text()
    assert "narrative.slice(0,300)" not in js, "narrative still hardcoded slice(0,300)"
    assert "narrative.slice(0,400)" not in js, "debug narrative still hardcoded slice(0,400)"
    assert "(t.user_text||'').slice(0,200)" not in js, "turns user_text still hardcoded slice(0,200)"
    assert "(t.user_text||'').slice(0,300)" not in js, "turns user_text debug still hardcoded slice(0,300)"


def test_expand_collapse_button_in_turns_render():
    """campaigns.js must contain expand/collapse UI for turn text."""
    js = CAMPAIGNS_JS.read_text()
    assert "Rozwiń" in js, "expand button 'Rozwiń' missing from turns render"
    assert "Zwiń" in js, "collapse button 'Zwiń' missing from turns render"
