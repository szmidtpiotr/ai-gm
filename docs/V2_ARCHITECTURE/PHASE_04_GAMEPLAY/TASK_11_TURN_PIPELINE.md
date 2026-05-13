# TASK 11 — Turn Processing Pipeline

**Phase:** 04 — Gameplay  
**Status:** ✅ Done — commit `92e990f` (2026-05-13)  
**File to modify:** `backend/app/services/game_engine.py`

---

## Overview

The turn pipeline is the central nervous system of every session. Every player interaction — typed command, button press, or skill roll — flows through this pipeline exactly once before a response reaches the frontend. The current `game_engine.py` handles only steps 1 and 8 (raw input reception and LLM narration). Steps 2–7 must be built.

Architecture principle: the **system controls the world**, the **LLM narrates it**. The LLM never directly changes state. Only the Mechanic Resolver and World State Updater write to the database.

---

## Pipeline Steps

### Step 1 — Receive Input

Two input types arrive from the frontend:

| Type | Shape | Next Step |
|------|-------|-----------|
| Free text | `{ "user_text": "Idę do tawerny" }` | Step 2 (Intent Parser) |
| Button action | `{ "action_tag": "ATTACK:goblin_grunt_1:sword" }` | Step 3 (skip parsing) |

Button actions are pre-structured by the frontend (combat buttons, skill check buttons, REST button). They carry a fully-formed action tag and bypass the Intent Parser entirely.

---

### Step 2 — Intent Parser (LLM Call A)

A **separate, lightweight LLM call** whose sole job is to classify the player's free text into a structured action tag. This call uses a terse system prompt (not the full narrator prompt) focused only on classification.

**Input:** raw `user_text`  
**Output:** one of:

```
ACTION:MOVE:location_key
ACTION:ATTACK:target_id:weapon_key
ACTION:SKILL_ATTEMPT:skill_key:target
ACTION:INTERACT:npc_id
ACTION:TALK:npc_id:intent
ACTION:USE_ITEM:item_key
ACTION:LOOK_AROUND
ACTION:REST
CLARIFY:ambiguity_reason
```

**On ambiguity or parse failure:** return a `CLARIFY` response directly to the frontend as a system message (not a narrator turn). The player sees a prompt like: *"Nie jestem pewien — chcesz zaatakować gobliniego sierżanta czy wartownika?"*

Failure condition: if Intent Parser itself errors (LLM timeout, malformed output), fall back to `ACTION:LOOK_AROUND` and log a warning.

---

### Step 3 — World State Machine Validation

Before any dice roll or DB lookup, the system validates whether the action is **legal in the current world state**.

Validation checks (examples):

| Action | Validation rule |
|--------|----------------|
| `ATTACK` | Target must be alive and present in current location |
| `MOVE` | Destination must be connected to current location |
| `USE_ITEM` | Item must be in player inventory |
| `TALK` | NPC must be present at current location |
| `REST` | Location must have `safe_for_rest=true` |
| `SKILL_ATTEMPT` | Skill must exist and character must have rank ≥ 1 (or be untrained) |

**On validation failure:** emit a `SYSTEM_MESSAGE` response directly to the frontend. **The LLM is not called.** The message is short and mechanical: *"[System] Nie możesz tego zrobić — cel nie jest obecny."* This keeps response latency near-zero for invalid inputs.

---

### Step 4 — DB Lookup

Load all records relevant to this specific action. This is the context assembly phase before dice.

For a combat action: load character stats, target enemy record, active weapon record, location record.  
For a skill test: load character skill ranks, relevant stat score, opposing NPC record if opposed.  
For a move: load destination location record, any NPC present there, any active loot records.  
For dialogue: load NPC definition record, relationship status, campaign plan NPC entry.

All lookups are batched into a single context dict passed to the Mechanic Resolver.

---

### Step 5 — Mechanic Resolver

Pure deterministic logic. No LLM. Receives the action tag + DB context dict, performs all dice rolls server-side, and returns a structured result JSON.

```json
{
  "action_type": "ATTACK",
  "roll": 14,
  "modifiers": { "stat": 2, "skill": 1, "proficiency": 0 },
  "total": 17,
  "dc_or_opponent": 15,
  "outcome": "SUCCESS",
  "damage": 8,
  "nat20": false,
  "nat1": false,
  "beat_signals": [],
  "tags_emitted": []
}
```

Key fields:
- `outcome`: one of `SUCCESS`, `FAILURE`, `CRITICAL_SUCCESS`, `CRITICAL_FAILURE`
- `beat_signals`: list of `BEAT_COMPLETE:beat_key` if the action logically completes a key beat (e.g., killing the final boss in the final beat)
- `tags_emitted`: pre-computed tags for the narrator context

**BEAT_COMPLETE detection:** The Mechanic Resolver checks the campaign plan's `active_act.key_beats` list. If the current action (e.g., killing a specific enemy, claiming a specific item) matches a beat's `trigger_condition` field, the resolver adds `BEAT_COMPLETE:beat_key` to `beat_signals`. The World State Updater (step 6) acts on this — the narrator receives it only as context.

---

### Step 6 — World State Update

Writes the outcome to the database. Called only after the Mechanic Resolver returns a valid result. Nothing writes to DB before this point.

Updates performed (depending on action type):

| Outcome | DB writes |
|---------|-----------|
| Attack hits | `characters.current_hp -= damage` for target; if target=enemy: `enemies.status='dead'` |
| Attack misses | No HP change. Log turn. |
| Move succeeds | `characters.current_location_id = new_location_id` |
| Skill success | May update NPC relationship, unlock location, add item |
| Rest | `characters.current_hp`, `current_mana` adjusted |
| BEAT_COMPLETE | `campaign_plan.key_beats[beat_key].visited = true`; check act completion |
| NPC_KILLED (from beat_signals) | `campaign_plan.key_npcs[npc_key].alive = false` |

Every turn is stored in `action_log`:

```sql
INSERT INTO action_log (
  campaign_id, character_id, turn_number, user_text, 
  action_tag, mechanic_result_json, narrator_response, 
  hp_before, hp_after, location_id, created_at
)
```

The `action_log` table is created in Phase 01 DB schema.

---

### Step 7 — Context Injector

Assembles the narrator prompt from the mechanical result and current world state. The narrator receives no raw game data — only this assembled context block.

Context block structure:

```
[WORLD STATE]
Location: {location.name} — {location.description_short}
Character: {character.name}, HP {current_hp}/{max_hp} [{wound_label}], Mana {mana}
Turn: {turn_number}

[MECHANICAL RESULT]
Action: {action_tag}
Outcome: {outcome} (roll {total} vs {dc_or_opponent})
Damage dealt: {damage}
Nat20: {nat20} | Nat1: {nat1}

[CAMPAIGN CONTEXT]
Act: {act_number} — {act_title}
Recent beats: {last_3_visited_beats}
Deviation status: {deviation_level} — {deviation_note}

[NARRATOR INSTRUCTION]
Narrate the outcome in Polish. 80-150 words. Dark fantasy tone. 
Do not mention dice numbers or DC values.
If outcome is CRITICAL_SUCCESS: show exceptional fortune or skill.
If outcome is CRITICAL_FAILURE: introduce a complication.
```

The system prompt (from `system_prompt.txt`) is prepended before this context block.

---

### Step 8 — LLM Narrator Call

Single LLM call to the configured provider. Receives system prompt + context block.

Returns Polish prose (80–150 words). The narrator may embed action tags (see TASK 13 for full tag list):

- `[SKILL_TEST:perception:DC:14]`
- `[BEAT_COMPLETE:beat_key]`
- `[NPC_KILLED:npc_key]`
- `[BRANCH_REQUIRED:reason]`

Backend intercepts these tags **before** delivering prose to the frontend. Tags are stripped from the displayed text and processed separately (plan updates, branch generation, etc.).

---

### Step 9 — Frontend Delivery

Response payload sent to frontend:

```json
{
  "prose": "Twój cios trafia gobliniego sierżanta...",
  "state": {
    "character_hp": 18,
    "character_max_hp": 24,
    "wound_label": "Ranny",
    "current_location": "Karczma Czarnego Kruka",
    "location_badge": "dark_tavern",
    "xp_delta": 25,
    "xp_total": 75,
    "level": 2
  },
  "turn_number": 7,
  "system_messages": []
}
```

Frontend updates: HP bar, wound label below bar, location badge in header, XP bar in character panel. The prose is appended to the narrative scroll.

---

## Campaign Plan Integration

Campaign plan update flow in the pipeline:

1. Mechanic Resolver emits `beat_signals` in result JSON (step 5)
2. World State Updater marks beats visited and checks act completion (step 6)
3. Context Injector includes deviation status in narrator block (step 7)
4. Narrator may emit `[BEAT_COMPLETE]`, `[NPC_KILLED]`, `[BRANCH_REQUIRED]` tags (step 8)
5. Backend intercepts tags post-LLM, runs plan update functions before delivering response (between step 8 and 9)

---

## Implementation Notes

Current state of `game_engine.py`:
- Has a `process_turn(user_text, campaign_id, character_id)` function
- Calls LLM with raw user_text concatenated into prompt
- Returns LLM response directly

Required additions:
- `parse_intent(user_text)` — calls Intent Parser LLM
- `validate_action(action_tag, world_state)` — state machine checks
- `load_action_context(action_tag, character_id, campaign_id)` — DB lookup
- `resolve_mechanics(action_tag, context)` — dice + outcome
- `update_world_state(mechanic_result, context)` — DB writes
- `build_narrator_context(mechanic_result, world_state)` — context assembly
- Refactor existing LLM call to use narrator context block
- Tag interception loop post-LLM

---

## Test Walkthroughs

### Walkthrough 1 — Narrative Exploration

Player types: *"Rozglądam się po tawernie"*  
Expected flow:
1. Free text → Intent Parser → `ACTION:LOOK_AROUND`
2. State machine: always valid
3. DB: load location record (Karczma Czarnego Kruka), present NPCs
4. Mechanic Resolver: no roll needed, outcome = `DESCRIPTION`
5. World state: no changes, log turn
6. Context: location description + NPC list injected
7. Narrator: 100-word atmospheric description in Polish
8. Frontend receives prose + unchanged state

### Walkthrough 2 — Skill Test

Player types: *"Próbuję przekraść się za strażnikiem"*  
Expected flow:
1. Intent Parser → `ACTION:SKILL_ATTEMPT:stealth:guard_1`
2. State machine: guard_1 present in location, character has stealth rank
3. DB: load stealth rank (2), DEX modifier (+1), guard perception modifier (+2)
4. Mechanic Resolver: d20=11, total=14 vs opposed d20+2=9. Outcome=`SUCCESS`
5. World state: update `location_guards_alerted=false`, log turn
6. Context: stealth success, guard positions, dark corridor description
7. Narrator: *"Poruszasz się jak cień..."* — 90 words Polish
8. Frontend: no HP change, location badge unchanged

### Walkthrough 3 — Combat Start

Player clicks `[Atakuj: Goblin Wartownik]` button  
Expected flow:
1. Button → `ATTACK:goblin_guard_1:shortsword` — skip Intent Parser
2. State machine: goblin_guard_1 alive=true, present=true, character has shortsword equipped
3. DB: load character STR+2, shortsword ATK+1, goblin AC=13, goblin HP=12
4. Mechanic Resolver: d20=16, total=19 vs AC 13. Hit. Damage d6+2=7.
5. World state: goblin HP → 5. Log turn. (Not dead yet.)
6. Context: attack hit, 7 damage, goblin HP low, combat ongoing
7. Narrator: *"Twój miecz wbija się w ramię goblina..."* — combat prose 80 words
8. Frontend: enemy HP bar updates in combat panel, player HP unchanged

---

## Open Questions

- Intent Parser model: use same provider as narrator or a smaller/faster model? Recommend: same provider, lower temperature (0.1), 150 token limit.
- Should `ACTION:LOOK_AROUND` always succeed without a roll, or can perception DC be optionally injected by the narrator? Recommend: no roll for passive look, narrator may inject `[SKILL_TEST:perception:DC:N]` for hidden details.
