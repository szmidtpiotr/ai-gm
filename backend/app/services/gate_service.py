"""Gate Mechanic — B3: validate player actions against World State before LLM.

Runs synchronously at the start of every turn. No LLM calls.
Returns GateResult(allowed=False) to block + send Polish feedback to player,
or GateResult(allowed=True) to continue to the normal LLM pipeline.

Integration point: `POST /api/campaigns/{id}/turns` calls validate_action()
before run_narrative_turn().
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.world_state_service import get_world_state_flags

# ── Result type ────────────────────────────────────────────────────────────────


@dataclass
class GateResult:
    allowed: bool
    reason: str | None = None
    feedback: str | None = None  # Polish player-facing message


# ── Non-combat action types that must be blocked when enemies are alive ────────

_COMBAT_BLOCKED_ACTIONS = {
    "DIALOGUE",
    "MOVEMENT",
    "MOVE",
    "SEARCH",
    "ITEM_PICKUP",
    "REST",
    "EXAMINE",
    "SHOP",
}

# ── Gate checks ───────────────────────────────────────────────────────────────


def validate_action(
    campaign_id: int,
    player_input: str,
    intent: dict | None = None,
) -> GateResult:
    """Main gate function. Validates intent against live World State.

    Args:
        campaign_id: active campaign
        player_input: raw player text (used for logging; intent takes precedence)
        intent: dict with at minimum {"action_type": "ATTACK"|"DIALOGUE"|...}
                and optional "target" key. If None, classify_intent_stub is called.

    Returns:
        GateResult — allowed=True to pass through, allowed=False to block.
    """
    if intent is None:
        intent = classify_intent_stub(player_input)

    action_type = (intent.get("action_type") or "UNKNOWN").upper()
    target_key = intent.get("target")

    ws = get_world_state_flags(campaign_id)
    enemies: list[dict] = ws["scene_enemies"]
    scene_cleared: bool = ws["scene_cleared"]

    # ── Check 1: non-combat action during active combat ────────────────────
    alive_enemies = [e for e in enemies if int(e.get("hp", 0)) > 0]
    if alive_enemies and action_type in _COMBAT_BLOCKED_ACTIONS:
        return GateResult(
            allowed=False,
            reason="combat_active",
            feedback="Jesteś w walce! Musisz najpierw pokonać wrogów lub uciec.",
        )

    # ── Check 2a: attack when no enemies ever in scene (C3) ───────────────
    if action_type == "ATTACK" and not enemies and not scene_cleared:
        return GateResult(
            allowed=False,
            reason="no_enemies",
            feedback="Nie ma tu wrogów do ataku.",
        )

    # ── Check 2b: attack when scene already cleared ────────────────────────
    if scene_cleared and action_type == "ATTACK":
        return GateResult(
            allowed=False,
            reason="scene_cleared",
            feedback="Wszyscy wrogowie zostali pokonani. Możesz teraz eksplorować.",
        )

    # ── Check 3: attack when all enemies in scene are dead ────────────────
    if action_type == "ATTACK" and enemies and not alive_enemies:
        return GateResult(
            allowed=False,
            reason="all_targets_dead",
            feedback="Wszyscy wrogowie zostali pokonani.",
        )

    # ── Check 4: attack targeting a specific dead enemy (when target_key known) ─
    if action_type == "ATTACK" and target_key:
        enemy = next((e for e in enemies if e.get("key") == target_key), None)
        if enemy is not None and int(enemy.get("hp", 1)) <= 0:
            name = enemy.get("name") or target_key
            return GateResult(
                allowed=False,
                reason="target_dead",
                feedback=f"{name} jest już martwy/a.",
            )

    return GateResult(allowed=True)


# ── Keyword stub classifier ───────────────────────────────────────────────────

# (Polish keyword → action_type). F0-4 replaces this with a full LLM parser.
_KEYWORD_MAP: list[tuple[re.Pattern, str]] = [
    # ATTACK — must come before FLEE to catch "walka"
    # Note: Polish inflections end in "ę"/"ę"/"am" — avoid \b after stems with Unicode tails
    (re.compile(
        r"(atakuj[ęe]?|uderz[ae][jm]?|strzelam|rzucam zaklęcie|spell|cast|\batak\b|walczę|walcz)",
        re.IGNORECASE
    ), "ATTACK"),
    # FLEE
    (re.compile(r"\b(uciekam|uciekaj|odwrót|cofam się)\b", re.IGNORECASE), "FLEE"),
    # DIALOGUE
    (re.compile(
        r"\b(rozmawiam|porozmawiać|mówię|pytam|zagaduję|rozmawiaj|mów|powiedz|zapytaj)\b",
        re.IGNORECASE
    ), "DIALOGUE"),
    # MOVEMENT
    (re.compile(
        r"\b(idę|biegnę|przechodzę|wchodzę|wychodzę|przemieszczam|poruszam|ruszam|idź|biegnij)\b",
        re.IGNORECASE
    ), "MOVEMENT"),
    # REST
    (re.compile(r"\b(odpoczywam|odpoczywa|śpię|śpij|obozujemy|obóz)\b", re.IGNORECASE), "REST"),
    # SEARCH
    (re.compile(r"\b(szukam|przeszukuję|sprawdzam|badam|przetrząsam|szukaj)\b", re.IGNORECASE), "SEARCH"),
    # ITEM_USE
    (re.compile(r"\b(używam|wypiję|pij|zużywam|aktywuję)\b", re.IGNORECASE), "ITEM_USE"),
    # EXAMINE
    (re.compile(r"\b(oglądam|patrzę na|przyglą|observe|rozglądam)\b", re.IGNORECASE), "EXAMINE"),
    # SHOP
    (re.compile(r"\b(kupuję|sprzedam|handel|sklep|kupię|sprzedaj)\b", re.IGNORECASE), "SHOP"),
    # SKILL_ATTEMPT
    (re.compile(r"\b(próbuję|staram się|testuję|sprawdzam umiejęt)\b", re.IGNORECASE), "SKILL_ATTEMPT"),
]


def classify_intent_stub(player_input: str) -> dict:
    """Fast keyword-based intent classification. No LLM.

    Returns dict with at minimum {"action_type": "<TYPE>"}.
    F0-4 (full LLM intent parser) will replace this in a later phase.
    """
    text = (player_input or "").strip()
    for pattern, action_type in _KEYWORD_MAP:
        if pattern.search(text):
            return {"action_type": action_type}
    return {"action_type": "UNKNOWN"}
