# TASK 02 — Intent Parser

**Status:** ✅ Done — commit `e5ab5d5` (2026-05-13)
**Phase:** 01 — Foundation  
**Depends on:** TASK_01 (DB Schema — `action_log` table must exist)  
**Blocks:** TASK_03 (World State Machine consumes ACTION tags produced here)  
**New file:** `backend/app/services/intent_parser.py`  
**Test file:** `backend/tests/test_intent_parser.py` — 32 tests, all passing

**Notes:**
- Tag format: `[ACTION:TYPE:param=val]` for actions, `[CLARIFY:reason=...]` / `[BLOCKED:reason=...]` for signals
- `ACTION:` is a literal prefix in the tag — the regex must consume it before reading the type
- Button clicks use `parse_structured_action()` which bypasses LLM entirely
- `game_engine.py` integration deferred to TASK_11 (Turn Pipeline)

---

## Overview

The Intent Parser is a focused LLM call that converts unstructured player text into a single, machine-readable ACTION tag. The game engine then routes that tag through the World State Machine — it never passes raw player text directly to the narrator.

This document covers why the parser exists, how it works, the full action vocabulary, the LLM prompt template, and all edge cases including failure handling and ambiguity resolution.

---

## Why This Exists

### The V1 Problem

In V1, the main LLM call received the player's raw message and was expected to:

1. Understand what the player intended
2. Decide whether it was mechanically valid
3. Apply mechanical outcomes
4. Write the narrative

This produced inconsistent world state because the LLM conflated narration with decision-making. Examples of real V1 failures:

- Player types "I try to sneak past the guards" → LLM narrates a successful stealth attempt without rolling dice
- Player types "I look around for a way out" → LLM invents a secret door not in the location DB
- Player types "I talk to the merchant about the guild" → LLM reveals information not in the NPC's `keyword_triggers`

### The V2 Principle

> **System controls the world. LLM only narrates and parses intent.**

The Intent Parser enforces this by being the single conversion point from natural language to structured intent. Once the text is an ACTION tag, everything downstream is deterministic code.

---

## Architecture

```
Player text input
        │
        ▼
┌─────────────────────┐
│   Intent Parser     │  ← Short LLM call (no narration, no mechanics)
│   (LLM call #1)     │
└─────────────────────┘
        │
        ▼ ACTION tag (or CLARIFY / BLOCKED)
        │
┌─────────────────────┐
│ World State Machine │  ← Pure Python — validates, routes
└─────────────────────┘
        │
        ▼ mechanic result
        │
┌─────────────────────┐
│  Context Injector   │  ← Assembles narrator prompt from DB + mechanic result
└─────────────────────┘
        │
        ▼ structured prompt
        │
┌─────────────────────┐
│  LLM Narrator       │  ← LLM call #2 — narrative only
│  (LLM call #2)      │
└─────────────────────┘
        │
        ▼
  Polish narrative text → player
```

**Button clicks bypass the Intent Parser entirely.** When a player presses a UI button (e.g., "Attack", "Flee", "Open Shop"), the frontend sends a pre-structured payload directly to the game engine with the action type already known. The Intent Parser only handles free-text input from the player message box.

---

## ACTION Tag Format

```
[ACTION:TYPE:param1=val1:param2=val2]
```

- Square brackets delimit the tag
- Fields separated by colons
- Parameters use `key=value` syntax
- Values containing spaces must be URL-encoded or quoted (use underscore-separated keys from DB)
- The tag is the sole output of the Intent Parser — no surrounding text

**Valid examples:**
```
[ACTION:ATTACK:target=goblin_1:weapon=sword_iron]
[ACTION:FLEE]
[ACTION:DIALOGUE:npc_key=innkeeper_boris:topic=guild]
[ACTION:MOVEMENT:destination_key=loc_dark_alley]
[ACTION:SEARCH:focus=clues]
[ACTION:REST:rest_type=short]
[ACTION:EXAMINE:target=old_chest]
[ACTION:SKILL_ATTEMPT:skill_key=perception:target=north_wall]
[ACTION:ITEM_USE:item_key=potion_minor_healing]
[ACTION:ITEM_PICKUP:item_key=sword_fallen_guard]
[ACTION:SHOP:npc_key=merchant_aldric]
[ACTION:STEALTH_ATTEMPT:target=guard_patrol_1]
```

**Special outputs (not action tags):**
```
[CLARIFY:reason=multiple_enemies_ambiguous]
[BLOCKED:reason=action_not_possible_in_current_state]
```

---

## Full Action Type Vocabulary

### ATTACK
Initiate or continue an attack on a target in combat.

| Param | Required | Description |
|---|---|---|
| `target` | yes | Enemy key from combat state (e.g. `goblin_1`, `bandit_2`) |
| `weapon` | no | Item key from character inventory; if omitted, uses equipped weapon or unarmed |

Notes:
- If the character has no equipped weapon and no `weapon` param, the resolver defaults to `unarmed` (1d3 + STR modifier)
- `target` must match a key in the active combat roster, not a free-text name — the Intent Parser maps "the goblin" or "that large one" to the correct key using the ENTITIES BLOCK context

---

### FLEE
Attempt to disengage from active combat and escape.

No parameters. The resolver rolls DEX (character) vs DEX (slowest enemy in combat). Success ends combat and moves character to a connected "safe" location if one exists, or the previous location.

---

### STEALTH_ATTEMPT
Attempt to move or hide without being detected.

| Param | Required | Description |
|---|---|---|
| `target` | no | NPC or enemy key to hide from; omit to mean "all present entities" |

Resolver uses DEX + Stealth skill vs target's passive Perception (10 + WIS modifier).

---

### DIALOGUE
Initiate or continue conversation with an NPC.

| Param | Required | Description |
|---|---|---|
| `npc_key` | yes | NPC key from DB (e.g. `innkeeper_boris`) |
| `topic` | no | Keyword from player's message matched against `keyword_triggers`; omit for general greeting |

If `topic` matches an NPC's `keyword_triggers`, the resolver checks `is_secret` and may require a skill roll before the `must_reveal_info` is passed to the narrator.

---

### MOVEMENT
Move to a different location.

| Param | Required | Description |
|---|---|---|
| `destination_key` | yes | Location key from DB (e.g. `loc_tavern_back_room`) |

The WSM validates that the destination is reachable from the current location (connected in `location_connections` table or equivalent). If not reachable, the action is blocked.

---

### SEARCH
Search the current area.

| Param | Required | Description |
|---|---|---|
| `focus` | no | What to search for: `clues`, `items`, `exits`, `traps`; omit for general search |

Resolver rolls INT + Investigation vs a location-defined DC. On success, reveals hidden objects/clues as defined in the location DB record.

---

### ITEM_USE
Use an item from the character's inventory.

| Param | Required | Description |
|---|---|---|
| `item_key` | yes | Item key from character inventory |

The resolver checks the item's `use_effect` field in `game_config_items` and applies it. Consumables are decremented. If the item has no `use_effect`, the action is blocked with a system message.

---

### ITEM_PICKUP
Pick up an item from the environment.

| Param | Required | Description |
|---|---|---|
| `item_key` | yes | Item key from the current location's available items or `combat_loot` record |

The item must be in the current location's item pool or an open `combat_loot` row. The resolver adds it to inventory and marks it claimed.

---

### REST
Attempt to rest and recover.

| Param | Required | Description |
|---|---|---|
| `rest_type` | yes | `short` (1 hour game-time, recover 1d6 HP) or `long` (8 hours, full HP + clear mild conditions) |

The WSM checks `safe_for_rest` on the current location and that no enemies are present. Blocked if conditions not met.

---

### EXAMINE
Study an object, area, or person more closely.

| Param | Required | Description |
|---|---|---|
| `target` | yes | What is being examined — matched to a DB key if possible, otherwise passed as free text to narrator context |

No dice roll required. If the target is a DB entity, the full DB record is passed to the narrator. If it's a free-text description of something not in DB, the narrator is constrained to describe it generically without inventing properties.

---

### SKILL_ATTEMPT
Attempt a named skill action outside of combat.

| Param | Required | Description |
|---|---|---|
| `skill_key` | yes | Skill name from `game_config_skills` (e.g. `acrobatics`, `persuasion`, `lockpicking`) |
| `target` | no | What the skill is applied to |

Resolver rolls the skill's associated stat + skill rank vs a DC defined by context (location record, NPC definition, or default by skill).

---

### SHOP
Open the shopping interface with an NPC.

| Param | Required | Description |
|---|---|---|
| `npc_key` | yes | Merchant NPC key; NPC must have `is_merchant = 1` in DB |

Transitions game state to `SHOPPING`. The shopping UI is handled separately; this action just establishes the session state.

---

## Special Outputs

### CLARIFY
Emitted when the player's intent is ambiguous and cannot be resolved without more information.

```
[CLARIFY:reason=<reason_code>]
```

Reason codes:
- `multiple_targets_ambiguous` — "I attack" when 3 enemies are present
- `unknown_item` — "I use the thing" when no item is contextually clear
- `unknown_npc` — "I talk to her" when multiple NPCs are present
- `unknown_destination` — "I go north" when no north exit is defined (suggest available exits)
- `action_unclear` — parser could not identify any action type after 2 attempts

When `CLARIFY` is returned, the game engine does NOT call the narrator. Instead it sends a system-generated clarification prompt to the player:

```
System: Nie rozumiem. Co próbujesz zrobić?
Sugestie:
  1. Zaatakuj goblin_straż_1
  2. Zaatakuj goblin_szaman_2
  3. Spróbuj uciec z walki
```

The clarification options are generated from game state (active combat roster, available NPCs, exits) — not by the LLM.

### BLOCKED
Emitted when the player's intent is clear but cannot be parsed into a valid action in the current context.

```
[BLOCKED:reason=<reason_code>]
```

This is distinct from WSM validation blocking (which happens after parsing). BLOCKED from the parser means the input describes something the game has no action type for (e.g., "I want to build a house", "I cast a spell" when the character has no magic).

---

## LLM Prompt Template for Intent Parsing

The parser uses a SHORT, FOCUSED system prompt. It does not narrate. It does not evaluate whether the action is valid. It only maps text to the action vocabulary.

```
SYSTEM:
You are an intent classifier for a tabletop RPG game engine. Your ONLY job is to convert the player's message into a single ACTION tag. You do NOT narrate, evaluate, or judge. You do NOT decide if the action succeeds or fails.

CURRENT GAME STATE:
- Location: {current_location_key} ({current_location_name})
- Game state: {game_state}  (NARRATIVE | COMBAT | SHOPPING | RESTING | ...)
- Enemies in combat: {combat_roster_list}  (empty if not in combat)
- NPCs present: {npcs_present_list}
- Character inventory (keys only): {inventory_keys_list}

ACTION VOCABULARY:
ATTACK — params: target (required), weapon (optional)
FLEE — no params
STEALTH_ATTEMPT — params: target (optional)
DIALOGUE — params: npc_key (required), topic (optional)
MOVEMENT — params: destination_key (required). Available destinations: {available_destination_keys}
SEARCH — params: focus (optional: clues/items/exits/traps)
ITEM_USE — params: item_key (required). Must be in inventory.
ITEM_PICKUP — params: item_key (required). Must be available in location or loot.
REST — params: rest_type (required: short/long)
EXAMINE — params: target (required)
SKILL_ATTEMPT — params: skill_key (required), target (optional)
SHOP — params: npc_key (required)

OUTPUT RULES:
- Output EXACTLY ONE line: the ACTION tag, CLARIFY tag, or BLOCKED tag.
- Do NOT output any text before or after the tag.
- Do NOT narrate the outcome.
- If the intent maps to a known action, output the tag.
- If the intent is ambiguous due to multiple valid targets, output: [CLARIFY:reason=multiple_targets_ambiguous]
- If the intent cannot be mapped to any action in the vocabulary, output: [BLOCKED:reason=action_unclear]
- Map player-friendly names ("the goblin", "that big one") to the correct DB key from the context provided.

PLAYER MESSAGE:
{player_message}
```

**Key constraints in this prompt:**
- The template explicitly lists available destinations and combat roster so the parser does not hallucinate keys
- The output rules section forbids narration
- The parser receives NO campaign history, NO location descriptions — only the minimal state needed to map intent to action

---

## Parser Call Parameters

The Intent Parser uses a smaller, faster model if available (e.g., a 7B model via Ollama). If only one model is configured, it uses the same model as the narrator but with `max_tokens=100` and `temperature=0.0` (deterministic).

```python
# intent_parser.py signature
async def parse_intent(
    player_message: str,
    game_state: str,
    current_location_key: str,
    current_location_name: str,
    combat_roster: list[dict],   # [{"key": "goblin_1", "name": "Goblin Strażnik", "hp": 12}]
    npcs_present: list[dict],    # [{"key": "innkeeper_boris", "name": "Boris"}]
    inventory_keys: list[str],
    available_destination_keys: list[str],
    loot_available_keys: list[str],
    attempt_number: int = 1
) -> ParsedIntent:
```

**Return type:**
```python
@dataclass
class ParsedIntent:
    action_type: str          # "ATTACK", "FLEE", "CLARIFY", "BLOCKED", etc.
    params: dict[str, str]    # parsed params
    raw_tag: str              # the full [ACTION:...] string
    attempt_number: int
    parsing_failed: bool      # True if LLM output was not a valid tag format
```

---

## Failure and Retry Logic

### Invalid Output Format

If the LLM does not return a properly formatted tag (e.g., returns prose), the parser retries once with a stricter prompt that includes:

```
IMPORTANT: Your previous response was incorrect. You must output ONLY the ACTION tag, nothing else.
Correct format example: [ACTION:ATTACK:target=goblin_1]
Wrong format: "The player attacks the goblin." ← DO NOT DO THIS

Player message: {player_message}
```

### Second Failure

If both attempts fail to produce a valid tag, `parse_intent()` returns:
```python
ParsedIntent(
    action_type="CLARIFY",
    params={"reason": "action_unclear"},
    raw_tag="[CLARIFY:reason=action_unclear]",
    attempt_number=2,
    parsing_failed=True
)
```

The game engine then sends the player a system message asking them to clarify, with 2-3 contextual suggestions generated from game state (not LLM).

### Clarification Suggestion Generation

When `CLARIFY` is returned, the game engine generates suggestions using this logic (pure Python, no LLM):

```python
def generate_clarification_suggestions(game_state: str, combat_roster: list, npcs_present: list, exits: list) -> list[str]:
    suggestions = []
    if game_state == "COMBAT" and combat_roster:
        for enemy in combat_roster[:2]:  # max 2 attack suggestions
            suggestions.append(f"Zaatakuj {enemy['name']}")
        suggestions.append("Spróbuj uciec z walki")
    elif game_state == "NARRATIVE":
        for npc in npcs_present[:1]:
            suggestions.append(f"Porozmawiaj z {npc['name']}")
        for exit_key in exits[:2]:
            suggestions.append(f"Idź do {exit_key}")
        suggestions.append("Przeszukaj otoczenie")
    return suggestions[:3]
```

---

## Ambiguity Handling

### Multiple Enemies — "I attack"

The parser returns `[CLARIFY:reason=multiple_targets_ambiguous]` when:
- `action_type` is clearly ATTACK
- `combat_roster` contains more than 1 alive enemy
- The player message contains no name, pronoun, or descriptor that maps to a unique enemy

The game engine sends a system prompt listing enemies. The player's next message ("the big one", "the shaman", "goblin 2") is then parsed in a second parser call with the previous clarification context included.

**The system (not the LLM) asks the follow-up question.** The question is templated:

```
System: Który cel masz na myśli?
  1. Goblin Strażnik (HP: 12/20) — goblin_1
  2. Goblin Szaman (HP: 18/18) — goblin_2
```

### Ambiguous Destinations

"I go north" when the location has no defined north exit triggers `[CLARIFY:reason=unknown_destination]`. The game engine lists available exits:

```
System: Nie można tam pójść. Dostępne wyjścia:
  - Tawerna (loc_tavern)
  - Ulica Targowa (loc_market_street)
```

### Partial NPC Name

"I talk to Boris" when the DB has `innkeeper_boris` — the parser resolves this via substring match on the NPC name in context. If no match, CLARIFY is returned.

---

## Integration into `game_engine.py`

The Intent Parser is called in the turn pipeline inside `game_engine.py`. The relevant section of the pipeline (pseudocode):

```python
async def process_player_turn(session: GameSession, player_message: str) -> TurnResult:
    
    # Step 0: Check if this is a button-click action (already structured)
    if is_structured_action(player_message):
        parsed = parse_structured_action(player_message)
    else:
        # Step 1: Intent Parser (LLM call #1)
        parsed = await intent_parser.parse_intent(
            player_message=player_message,
            game_state=session.current_state,
            current_location_key=session.location_key,
            ...
        )
    
    # Step 2: Handle CLARIFY / BLOCKED from parser
    if parsed.action_type == "CLARIFY":
        suggestions = generate_clarification_suggestions(...)
        return TurnResult(
            system_message=format_clarification(suggestions),
            requires_player_response=True
        )
    
    if parsed.action_type == "BLOCKED":
        return TurnResult(
            system_message="Nie możesz teraz tego zrobić.",
            requires_player_response=True
        )
    
    # Step 3: World State Machine (pure Python)
    wsm_result = world_state_machine.validate_and_route(session, parsed)
    
    if wsm_result.blocked:
        return TurnResult(system_message=wsm_result.block_reason, ...)
    
    # Step 4: Mechanic resolver (pure Python)
    mechanic_result = wsm_result.resolver.resolve(session, parsed)
    
    # Step 5: Log to action_log
    await action_log_service.log(session, parsed, mechanic_result)
    
    # Step 6: Context Injector
    narrator_prompt = context_injector.build(session, mechanic_result)
    
    # Step 7: LLM Narrator (LLM call #2)
    narrative = await llm_service.narrate(narrator_prompt)
    
    return TurnResult(narrative=narrative, mechanic_result=mechanic_result)
```

---

## Edge Cases

1. **Player types in English instead of Polish:** The parser must still classify the intent correctly. The LLM is capable of this. The narrator always responds in Polish regardless.

2. **Player types a multi-action message:** "I attack the goblin and then drink a potion." The parser outputs only the FIRST action. A subsequent message will handle the second. The system message should note: "Wykonaj jedną akcję na raz." This rule is documented in the player-facing help.

3. **Player types OOC (out of character) text:** "Can you make this more exciting?" or "What are my options here?" The parser returns `[BLOCKED:reason=action_unclear]`. The game engine detects the `action_unclear` reason code and responds with a templated help message listing available actions in the current state — not a free LLM response.

4. **`available_destination_keys` is empty:** If a location has no exits defined in DB, MOVEMENT is always BLOCKED. This is a data integrity issue — all locations must have at least one connection. The parser should not be the one to catch this; the WSM validates it. But the parser context should still receive the empty list.

5. **Intent parser called during `SHOPPING` state:** The action vocabulary changes — only `ITEM_BUY`, `ITEM_SELL`, `SHOP_LEAVE` are valid. The parser prompt must inject the shopping-specific vocabulary when `game_state == "SHOPPING"`. Future task handles shopping state fully; for now, the parser can return `[BLOCKED:reason=in_shop_use_ui]` for all free-text during shopping.

6. **LLM returns tag with invented action type:** e.g., `[ACTION:CAST_SPELL:spell=fireball]`. The parser validation layer checks the action type against the vocabulary enum. If not valid, it's treated as a parse failure and retried.

7. **Very short player messages:** "yes", "ok", "attack" — the parser must use game context heavily. "attack" in COMBAT state with one enemy maps to `[ACTION:ATTACK:target=<only_enemy_key>]` without needing CLARIFY. "yes" in a dialogue context might map to DIALOGUE if there's an active conversation, but the parser should prefer CLARIFY rather than guessing wrong.

---

## Test Checklist

Note: Tests 1–10 (combat state) and 11–15 (narrative state) covered by mocked LLM tests in `test_intent_parser.py`. Full live LLM tests deferred to integration testing.

Test against a COMBAT state with enemies `goblin_1` (Goblin Strażnik) and `goblin_2` (Goblin Szaman), location `loc_forest_clearing`, NPCs: none, inventory: `sword_iron`, `potion_minor_healing`, exits: `loc_forest_path`, `loc_cave_entrance`.

| # | Player Input | Expected ACTION Tag | Status |
|---|---|---|---|
| 1 | "Atakuję szamana mieczem!" | `[ACTION:ATTACK:target=goblin_2:weapon=sword_iron]` | [x] mocked |
| 2 | "Próbuję uciec!" | `[ACTION:FLEE]` | [x] mocked |
| 3 | "Piję miksturę" | `[ACTION:ITEM_USE:item_key=potion_minor_healing]` | [x] mocked |
| 4 | "Atakuję" (ambiguous — 2 enemies) | `[CLARIFY:reason=multiple_targets_ambiguous]` | [x] mocked |
| 5 | "Uderzam tego mniejszego" (goblin_1 is described as smaller in context) | `[ACTION:ATTACK:target=goblin_1]` | [x] mocked |
| 6 | "Chcę się schować za drzewem" | `[ACTION:STEALTH_ATTEMPT]` | [x] mocked |
| 7 | "Chcę iść do jaskini" | `[ACTION:MOVEMENT:destination_key=loc_cave_entrance]` | [x] mocked |
| 8 | "Szukam wyjścia" | `[ACTION:SEARCH:focus=exits]` | [x] mocked |
| 9 | "What are my options?" (OOC English) | `[BLOCKED:reason=action_unclear]` | [x] mocked |
| 10 | "Rzucam zaklęcie ognia" (no magic in class) | `[BLOCKED:reason=action_unclear]` | [x] mocked |

Additional tests in NARRATIVE state (no combat, NPC `innkeeper_boris` present, exits: `loc_market`):

| # | Player Input | Expected ACTION Tag | Status |
|---|---|---|---|
| 11 | "Rozmawiam z Borisem o gildii" | `[ACTION:DIALOGUE:npc_key=innkeeper_boris:topic=guild]` | [x] mocked |
| 12 | "Oglądam stary kufer w rogu" | `[ACTION:EXAMINE:target=old_chest]` | [x] mocked |
| 13 | "Chcę odpocząć" | `[ACTION:REST:rest_type=short]` | [x] mocked |
| 14 | "Przeszukuję pokój w poszukiwaniu wskazówek" | `[ACTION:SEARCH:focus=clues]` | [x] mocked |
| 15 | "Próbuję otworzyć zamek wytrychem" | `[ACTION:SKILL_ATTEMPT:skill_key=lockpicking]` | [x] mocked |

[~] Live LLM tests for all 15 cases — deferred to integration testing phase.

---

## Implementation Notes

- File: `backend/app/services/intent_parser.py`
- Tests: `backend/tests/test_intent_parser.py` — 32 tests, all passing
- Critical design decision: tag format is `[ACTION:TYPE:params]` — `"ACTION:"` is a LITERAL PREFIX, not the type. Required two separate regexes: `_ACTION_TAG_RE` for actions, `_SPECIAL_TAG_RE` for CLARIFY/BLOCKED
- `parse_structured_action()` handles button-click payloads (no brackets): `"ACTION:FLEE"` → brackets added before parsing
- `is_structured_action()` detects button vs free text: checks for `"ACTION:"` prefix
- Retry logic: 2 attempts max. Both fail → return CLARIFY with `parsing_failed=True`
- `generate_clarification_suggestions()` is pure Python (no LLM) — uses `combat_roster` and `npcs_present` from game state
