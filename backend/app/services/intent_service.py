"""Intent Parser — B4: extract structured player_intent from raw input.

Two-stage parser:
1. Keyword scan (fast, no LLM)
2. LLM fallback (when confidence < 0.5)
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class PlayerIntent:
    """Structured intent extracted from player input."""
    action_type: str  # "attack", "talk", "move", "use_item", "flee", "skill_test", "explore", "other"
    target: str | None = None  # enemy/NPC/item name, direction
    confidence: float = 0.8  # 0.0-1.0 (keyword=0.8, LLM=0.95)
    raw_input: str = ""


# ── Keyword patterns (stage 1) ─────────────────────────────────────────────────

_KEYWORD_PATTERNS: list[tuple[re.Pattern, str]] = [
    # ATTACK — must come first to avoid false matches
    (re.compile(
        r"(atakuj[ęe]?|uderz[ae][jm]?|strzelam|rzucam zaklęcie|czar|walczę|walcz|atak)",
        re.IGNORECASE
    ), "attack"),
    # TALK
    (re.compile(
        r"(mówię|mów|pytam|rozmawiam|porozmawiać|pytaj|zagaduję|rozmawiaj|powiedz|podchodzę)",
        re.IGNORECASE
    ), "talk"),
    # MOVE
    (re.compile(
        r"(idę|biegnę|wchodzę|wychodzę|przechodzę|przemieszczam|poruszam|ruszam|idź|biegnij)",
        re.IGNORECASE
    ), "move"),
    # FLEE
    (re.compile(
        r"(uciekam|uciekaj|wycofuję|odwrót|cofam się)",
        re.IGNORECASE
    ), "flee"),
    # USE_ITEM
    (re.compile(
        # #1181: anchored drink/use verbs — bare "pię" fragment removed, so
        # "pięścią"/"pięknie" no longer false-match use_item (piję/wypiję/pij cover drinking).
        r"(używam|piję|wypiję|\bpij\b|zakładam|zakladam|zużywam|aktywuję)",
        re.IGNORECASE
    ), "use_item"),
    # SKILL_TEST
    (re.compile(
        r"(sprawdzam|rzucam test|test umiejętności|próbuję|staram się)",
        re.IGNORECASE
    ), "skill_test"),
    # EXPLORE
    (re.compile(
        r"(odkrywam|szukam|przeszukuję|badam|przetrząsam|oglą|patrzę)",
        re.IGNORECASE
    ), "explore"),
]


def parse_intent(player_input: str, campaign_id: int | None = None) -> PlayerIntent:
    """Parse player input into structured intent.

    Stage 1: Keyword scan (fast, no LLM)
    Stage 2: LLM fallback (when confidence < 0.5) — TODO in later phase

    Args:
        player_input: raw text from player
        campaign_id: optional, for LLM context later

    Returns:
        PlayerIntent with action_type, target (None for now), confidence, raw_input
    """
    text = (player_input or "").strip()
    raw_input = text

    # Stage 1: keyword match
    for pattern, action_type in _KEYWORD_PATTERNS:
        if pattern.search(text):
            return PlayerIntent(
                action_type=action_type,
                target=None,  # Target extraction from keywords TBD
                confidence=0.8,
                raw_input=raw_input,
            )

    # No keyword match → "other" with lower confidence (stage 2 LLM fallback TBD)
    return PlayerIntent(
        action_type="other",
        target=None,
        confidence=0.4,
        raw_input=raw_input,
    )
