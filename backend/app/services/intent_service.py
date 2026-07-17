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

# #1420 — dopasowanie odporne na brak polskich znaków: wzorce ODdiakrytyzowane,
# wejście też normalizowane (patrz parse_intent).
from app.core.text_utils import strip_pl_diacritics as _sd


def _c(pattern: str) -> re.Pattern:
    return re.compile(_sd(pattern), re.IGNORECASE)


_KEYWORD_PATTERNS: list[tuple[re.Pattern, str]] = [
    (_c(r"(atakuj[ęe]?|uderz[ae][jm]?|strzelam|rzucam zaklęcie|czar|walczę|walcz|atak)"), "attack"),
    (_c(r"(mówię|mów|pytam|rozmawiam|porozmawiać|pytaj|zagaduję|rozmawiaj|powiedz|podchodzę)"), "talk"),
    (_c(r"(idę|biegnę|wchodzę|wychodzę|przechodzę|przemieszczam|poruszam|ruszam|idź|biegnij)"), "move"),
    (_c(r"(uciekam|uciekaj|wycofuję|odwrót|cofam się)"), "flee"),
    # #1181: anchored drink/use verbs — bare "pię" fragment removed, so
    # "pięścią"/"pięknie" no longer false-match use_item.
    (_c(r"(używam|piję|wypiję|\bpij\b|zakładam|zużywam|aktywuję)"), "use_item"),
    (_c(r"(sprawdzam|rzucam test|test umiejętności|próbuję|staram się)"), "skill_test"),
    (_c(r"(odkrywam|szukam|przeszukuję|badam|przetrząsam|oglą|patrzę)"), "explore"),
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
    norm = _sd(text)  # #1420 — dopasowanie bez polskich znaków

    # Stage 1: keyword match
    for pattern, action_type in _KEYWORD_PATTERNS:
        if pattern.search(norm):
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
