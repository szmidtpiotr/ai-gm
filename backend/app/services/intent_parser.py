"""
Intent Parser — V2 Phase 01 Task 02

Converts unstructured player text into a single machine-readable ACTION tag.
This is LLM call #1 in the V2 pipeline. It does NOT narrate or evaluate validity.
The World State Machine (TASK_03) validates the result downstream.

Button-click actions from the frontend bypass this entirely — they arrive
pre-structured and skip straight to the WSM.
"""

from __future__ import annotations

import re
import structlog
from dataclasses import dataclass, field

from app.services import llm_service

logger = structlog.get_logger()

# ── Valid action types ──────────────────────────────────────────────────────

VALID_ACTION_TYPES = {
    "ATTACK",
    "FLEE",
    "STEALTH_ATTEMPT",
    "DIALOGUE",
    "MOVEMENT",
    "SEARCH",
    "ITEM_USE",
    "ITEM_PICKUP",
    "REST",
    "EXAMINE",
    "SKILL_ATTEMPT",
    "SHOP",
}

SPECIAL_TYPES = {"CLARIFY", "BLOCKED"}

# Tags come in two forms:
#   [ACTION:TYPE:param=val:...]   — for VALID_ACTION_TYPES
#   [CLARIFY:reason=...]          — special output
#   [BLOCKED:reason=...]          — special output
_ACTION_TAG_RE = re.compile(
    r"^\[ACTION:(?P<type>[A-Z_]+)(?::(?P<params>[^\]]*))?\]$",
    re.IGNORECASE,
)
_SPECIAL_TAG_RE = re.compile(
    r"^\[(?P<type>CLARIFY|BLOCKED)(?::(?P<params>[^\]]*))?\]$",
    re.IGNORECASE,
)


# ── Return type ─────────────────────────────────────────────────────────────

@dataclass
class ParsedIntent:
    action_type: str                  # "ATTACK", "FLEE", "CLARIFY", "BLOCKED"
    params: dict[str, str]            # e.g. {"target": "goblin_1", "weapon": "sword_iron"}
    raw_tag: str                      # the full [ACTION:...] string as returned by LLM
    attempt_number: int = 1
    parsing_failed: bool = False      # True if LLM output was not a valid tag after retries


# ── Parser ──────────────────────────────────────────────────────────────────

def parse_intent(
    player_message: str,
    game_state: str,
    current_location_key: str,
    current_location_name: str,
    combat_roster: list[dict],
    npcs_present: list[dict],
    inventory_keys: list[str],
    available_destination_keys: list[str],
    loot_available_keys: list[str] | None = None,
    llm_config: dict | None = None,
) -> ParsedIntent:
    """
    Convert player free text into a structured ACTION tag.

    Args:
        player_message: Raw text from the player input box.
        game_state: Current WSM state string (e.g. "NARRATIVE", "COMBAT").
        current_location_key: DB key of the current location.
        current_location_name: Human-readable location name.
        combat_roster: List of alive enemies: [{"key": "goblin_1", "name": "...", "hp": 12}]
        npcs_present: NPCs at this location: [{"key": "innkeeper_boris", "name": "Boris"}]
        inventory_keys: Item keys in character inventory.
        available_destination_keys: Location keys reachable from current location.
        loot_available_keys: Item keys available as loot (optional).
        llm_config: Override LLM config (uses server default if None).

    Returns:
        ParsedIntent with action_type, params, raw_tag.
    """
    loot_available_keys = loot_available_keys or []

    # Attempt 1 — standard prompt
    prompt = _build_prompt(
        player_message=player_message,
        game_state=game_state,
        current_location_key=current_location_key,
        current_location_name=current_location_name,
        combat_roster=combat_roster,
        npcs_present=npcs_present,
        inventory_keys=inventory_keys,
        available_destination_keys=available_destination_keys,
        loot_available_keys=loot_available_keys,
        retry=False,
    )

    raw = _call_llm(prompt, llm_config)
    parsed = _parse_tag(raw)

    if parsed is not None:
        logger.info(
            "intent_parsed",
            action_type=parsed.action_type,
            attempt=1,
            raw=raw,
        )
        return parsed

    # Attempt 2 — stricter retry prompt
    logger.warning("intent_parse_retry", raw_output=raw, player_message=player_message)
    retry_prompt = _build_prompt(
        player_message=player_message,
        game_state=game_state,
        current_location_key=current_location_key,
        current_location_name=current_location_name,
        combat_roster=combat_roster,
        npcs_present=npcs_present,
        inventory_keys=inventory_keys,
        available_destination_keys=available_destination_keys,
        loot_available_keys=loot_available_keys,
        retry=True,
        previous_bad_output=raw,
    )

    raw2 = _call_llm(retry_prompt, llm_config)
    parsed2 = _parse_tag(raw2)

    if parsed2 is not None:
        logger.info("intent_parsed", action_type=parsed2.action_type, attempt=2, raw=raw2)
        parsed2.attempt_number = 2
        return parsed2

    # Both attempts failed — return CLARIFY
    logger.warning("intent_parse_failed", raw1=raw, raw2=raw2, player_message=player_message)
    return ParsedIntent(
        action_type="CLARIFY",
        params={"reason": "action_unclear"},
        raw_tag="[CLARIFY:reason=action_unclear]",
        attempt_number=2,
        parsing_failed=True,
    )


# ── Pre-structured action from button clicks ─────────────────────────────────

def parse_structured_action(structured_payload: str) -> ParsedIntent:
    """
    Parse a pre-structured action string sent by the frontend (button clicks).
    Accepts:
      "ACTION:FLEE"                            (no brackets)
      "ACTION:ATTACK:target=goblin_1"          (no brackets, with params)
      "[ACTION:ATTACK:target=goblin_1]"        (with brackets)
    These bypass the LLM entirely.
    """
    payload = structured_payload.strip()
    if not payload.startswith("["):
        payload = f"[{payload}]"
    parsed = _parse_tag(payload)
    if parsed:
        return parsed
    return ParsedIntent(
        action_type="BLOCKED",
        params={"reason": "invalid_structured_payload"},
        raw_tag=payload,
        parsing_failed=True,
    )


def is_structured_action(player_message: str) -> bool:
    """
    Returns True if the player_message is a pre-structured button-click payload
    rather than free text. Convention: structured payloads start with 'ACTION:'.
    """
    return player_message.startswith("ACTION:") or player_message.startswith("[ACTION:")


# ── Clarification suggestion generator ──────────────────────────────────────

def generate_clarification_suggestions(
    game_state: str,
    combat_roster: list[dict],
    npcs_present: list[dict],
    available_exits: list[str],
) -> list[str]:
    """
    Generate 2-3 contextual action suggestions for the player when intent is unclear.
    Pure Python — no LLM call.
    """
    suggestions: list[str] = []

    if game_state == "COMBAT" and combat_roster:
        for enemy in combat_roster[:2]:
            suggestions.append(f"Zaatakuj {enemy.get('name', enemy.get('key', '?'))}")
        suggestions.append("Spróbuj uciec z walki")
    elif game_state == "NARRATIVE":
        for npc in npcs_present[:1]:
            suggestions.append(f"Porozmawiaj z {npc.get('name', npc.get('key', '?'))}")
        for exit_key in available_exits[:2]:
            suggestions.append(f"Idź do {exit_key}")
        suggestions.append("Przeszukaj otoczenie")
    else:
        suggestions.append("Opisz akcję dokładniej")
        suggestions.append("Wpisz /help aby zobaczyć dostępne komendy")

    return suggestions[:3]


# ── Internal helpers ─────────────────────────────────────────────────────────

def _build_prompt(
    player_message: str,
    game_state: str,
    current_location_key: str,
    current_location_name: str,
    combat_roster: list[dict],
    npcs_present: list[dict],
    inventory_keys: list[str],
    available_destination_keys: list[str],
    loot_available_keys: list[str],
    retry: bool = False,
    previous_bad_output: str = "",
) -> list[dict]:
    """Build the messages list for the LLM intent parser call."""

    combat_list = (
        ", ".join(f"{e.get('key','?')} ({e.get('name','?')})" for e in combat_roster)
        if combat_roster else "none"
    )
    npc_list = (
        ", ".join(f"{n.get('key','?')} ({n.get('name','?')})" for n in npcs_present)
        if npcs_present else "none"
    )
    inv_list = ", ".join(inventory_keys) if inventory_keys else "empty"
    dest_list = ", ".join(available_destination_keys) if available_destination_keys else "none"
    loot_list = ", ".join(loot_available_keys) if loot_available_keys else "none"

    system_content = f"""You are an intent classifier for a tabletop RPG game engine. Your ONLY job is to convert the player's message into a single ACTION tag. You do NOT narrate, evaluate, or judge. You do NOT decide if the action succeeds or fails.

CURRENT GAME STATE:
- Location: {current_location_key} ({current_location_name})
- Game state: {game_state}
- Enemies in combat: {combat_list}
- NPCs present: {npc_list}
- Character inventory (keys): {inv_list}
- Available destinations: {dest_list}
- Available loot: {loot_list}

ACTION VOCABULARY:
ATTACK — params: target (required, use enemy key), weapon (optional, use item key)
FLEE — no params
STEALTH_ATTEMPT — params: target (optional)
DIALOGUE — params: npc_key (required), topic (optional keyword)
MOVEMENT — params: destination_key (required, must be from available destinations)
SEARCH — params: focus (optional: clues/items/exits/traps)
ITEM_USE — params: item_key (required, must be in inventory)
ITEM_PICKUP — params: item_key (required, must be in available loot)
REST — params: rest_type (required: short/long)
EXAMINE — params: target (required)
SKILL_ATTEMPT — params: skill_key (required), target (optional)
SHOP — params: npc_key (required)

DISAMBIGUATION RULES (critical — read before choosing a tag):
- Sneaking / leaving quietly / hiding / observing from the shadows
  ("skradam się", "wychodzę po cichu", "wymykam się", "chowam się",
   "kryję się", "obserwuję z cienia", "z ukrycia") → STEALTH_ATTEMPT.
  NEVER emit SKILL_ATTEMPT:skill_key=deception for sneaking or hiding.
- SKILL_ATTEMPT:skill_key=deception is ONLY for actively lying, bluffing,
  or impersonating someone IN A CONVERSATION with a present NPC. If the
  player is not speaking a lie to an NPC, deception does NOT apply.
- A player declaring they leave/travel toward a named place is MOVEMENT,
  not a social SKILL_ATTEMPT against the NPC they are leaving. If that named
  place matches an available destination, emit MOVEMENT:destination_key=<key>.
  If it is NOT in available destinations but the player is sneaking out,
  emit STEALTH_ATTEMPT; otherwise EXAMINE. Never substitute a social skill
  test (deception/persuasion) for a movement the player just declared.
- Passive observation with no specific hidden target ("rozglądam się",
  "obserwuję", "patrzę", "co widzę") → EXAMINE (no skill test).

OUTPUT RULES:
- Output EXACTLY ONE line: the ACTION tag, CLARIFY tag, or BLOCKED tag.
- Do NOT output any text before or after the tag.
- Do NOT narrate the outcome.
- Format: [ACTION:TYPE:param1=val1:param2=val2] or [ACTION:TYPE] if no params.
- If the intent maps to a known action, output the tag.
- If intent is ambiguous with multiple valid targets, output: [CLARIFY:reason=multiple_targets_ambiguous]
- If intent cannot be mapped to any action, output: [BLOCKED:reason=action_unclear]
- Map player-friendly names to the correct DB key from context (e.g. "the goblin" → goblin_1)."""

    if retry:
        system_content = (
            f"IMPORTANT: Your previous response was incorrect: '{previous_bad_output}'\n"
            "You must output ONLY the ACTION tag, nothing else.\n"
            "Correct format example: [ACTION:ATTACK:target=goblin_1]\n"
            "Wrong format: 'The player attacks the goblin.' ← DO NOT DO THIS\n\n"
            + system_content
        )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": player_message},
    ]


def _call_llm(messages: list[dict], llm_config: dict | None) -> str:
    """Call the LLM with deterministic settings for intent parsing."""
    try:
        # Use generate_chat with low max_tokens — intent tags are short
        result = llm_service.generate_chat(
            messages=messages,
            llm_config=llm_config,
        )
        return (result or "").strip()
    except Exception as exc:
        logger.error("intent_parser_llm_error", error=str(exc))
        return ""


def _parse_tag(raw: str) -> ParsedIntent | None:
    """
    Parse a raw LLM output string into a ParsedIntent.

    Handles two formats:
      [ACTION:TYPE:param=val:...]   for normal actions
      [CLARIFY:reason=...]          for ambiguity signals
      [BLOCKED:reason=...]          for impossible-action signals

    Returns None if the output is not a valid tag.
    """
    if not raw:
        return None

    cleaned = raw.strip().strip('"').strip("'")

    # Try [ACTION:TYPE:...] first
    m = _ACTION_TAG_RE.match(cleaned)
    if m:
        type_str = m.group("type").upper()
        if type_str not in VALID_ACTION_TYPES:
            logger.warning("intent_parser_unknown_type", type_str=type_str, raw=raw)
            return None
        params = _extract_params(m.group("params") or "")
        return ParsedIntent(action_type=type_str, params=params, raw_tag=cleaned)

    # Try [CLARIFY:...] or [BLOCKED:...]
    m = _SPECIAL_TAG_RE.match(cleaned)
    if m:
        type_str = m.group("type").upper()
        params = _extract_params(m.group("params") or "")
        return ParsedIntent(action_type=type_str, params=params, raw_tag=cleaned)

    return None


def _extract_params(params_str: str) -> dict[str, str]:
    """Parse 'target=goblin_1:weapon=sword_iron' → {'target': 'goblin_1', 'weapon': 'sword_iron'}"""
    params: dict[str, str] = {}
    if not params_str:
        return params
    for part in params_str.split(":"):
        part = part.strip()
        if "=" in part:
            key, _, val = part.partition("=")
            params[key.strip()] = val.strip()
    return params
