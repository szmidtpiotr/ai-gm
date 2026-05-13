# TASK 09 — NPC System (V2)

**Status:** ✅ Done — commit `cd4c2d1` (2026-05-13)
**Phase:** 03 — World

---

## Overview

V2 NPCs are DB-backed personalities. The LLM narrator does not invent NPC behaviour from scratch — it plays a character defined in `npc_definitions`. Each NPC has a personality prompt and a set of keyword triggers that constrain what they reveal in conversation. The system ensures consistency across sessions: NPCs remember what they have said (via summary), react to their own secrets, and die permanently.

---

## `npc_definitions` Schema Additions

New columns on the `npc_definitions` table:

| Column               | Type    | Description                                                                                 |
|----------------------|---------|---------------------------------------------------------------------------------------------|
| `personality_prompt` | TEXT    | Short instruction for the LLM narrator. Defines voice, manner, and hidden knowledge. Max 300 chars. |
| `keyword_triggers`   | TEXT    | JSON array of trigger objects (see below).                                                  |
| `npc_type`           | TEXT    | One of: `neutral`, `merchant`, `quest_giver`, `ally`, `antagonist`. Default: `neutral`.    |

```sql
ALTER TABLE npc_definitions ADD COLUMN personality_prompt TEXT DEFAULT '';
ALTER TABLE npc_definitions ADD COLUMN keyword_triggers TEXT DEFAULT '[]';
ALTER TABLE npc_definitions ADD COLUMN npc_type TEXT DEFAULT 'neutral';
```

---

## Keyword Trigger Schema

`keyword_triggers` is a JSON array stored in the column. Each entry:

```json
{
  "keyword": "string — word or short phrase the player's topic/input must contain",
  "must_reveal_info": "string — factual content the NPC must include in their response",
  "is_secret": false
}
```

`is_secret` behaviour:
- `false`: NPC reveals the information directly. May be mixed with flavour but must not be omitted.
- `true`: NPC reveals the information reluctantly. The LLM must hedge, hint, or resist — but still surface the core content. The instruction injected reads: "The NPC knows this but does not want to say it. They hint, deflect, then reluctantly confirm if pressed."

**Example:**
```json
[
  {
    "keyword": "miller",
    "must_reveal_info": "Henryk the miller disappeared three weeks ago. His dog was found near the old bridge.",
    "is_secret": false
  },
  {
    "keyword": "body",
    "must_reveal_info": "He found a body near the mill last week. Two puncture wounds on the neck. He reported it to no one.",
    "is_secret": true
  }
]
```

Keyword matching: case-insensitive substring match against the player's turn text and the declared topic field.

---

## Per-Turn Dialogue Flow

The player initiates a DIALOGUE action by including a recognized NPC interaction pattern in their turn, or via an explicit frontend action button with `npc_key` and `topic` parameters.

### Step 1 — World State Machine Validation

Before injecting any context:

1. NPC with `npc_key` exists in `npc_definitions`.
2. NPC is present in the current location (`npc_keys` array of `current_location` contains this key).
3. NPC is alive (`npc_definitions.is_active = 1`).

If any check fails: return a system message, not an LLM response. Examples:
- Not in location: "There is no sign of {name} here."
- Dead: "{name} is dead. The dead do not answer."

### Step 2 — Context Injection

Inject into the LLM turn context (alongside the usual session context):

```
[NPC: {name}]
Type: {npc_type}
Personality: {personality_prompt}
What they know: {npc_knowledge_summary}
```

`npc_knowledge_summary`: a short summary of what this NPC has said or revealed in previous turns (maintained in `npc_session_state` or in the session summary). Empty for first encounter.

### Step 3 — Keyword Trigger Check

Scan the player's input and topic for matches against all `keyword_triggers` for this NPC.

For each matching trigger, append to the injected context:

```
[MUST INCLUDE — NPC reveals]: {must_reveal_info}
```

Or, for `is_secret = true`:

```
[MUST INCLUDE — NPC reveals reluctantly, hints then confirms if pressed]: {must_reveal_info}
```

Multiple triggers may fire in a single turn if the player's input matches multiple keywords.

### Step 4 — LLM Narration

The LLM narrator plays the NPC using the injected personality and constraints. The narrator:
- Writes the NPC's dialogue in first person.
- Stays within `personality_prompt` voice.
- Includes all `must_reveal_info` content, naturally woven into the NPC's speech.
- Does not invent facts about the NPC that contradict known data.

---

## NPC Creation via `[CREATE_NPC]` Tag

When the LLM emits a `[CREATE_NPC]` tag during narration (see TASK_10 for full tag spec), the system:

1. Parses the tag fields: `key`, `name`, `role`, `personality`, `location_key`.
2. Calls the LLM to generate a full `personality_prompt` from the `personality` field and contextual session data. Prompt: "Generate a concise NPC personality instruction (max 300 characters) for an NPC named {name}, role: {role}, in a dark fantasy setting. Voice, manner, secrets." Store result in `personality_prompt`.
3. Creates the `npc_definitions` record with `review_status = 'pending_review'`, `keyword_triggers = '[]'`, `npc_type` inferred from `role`.
4. NPC is immediately usable in the session.
5. Admin reviews later (TASK_10).

---

## NPC Alive Tracking

An NPC is killed when:

- **Combat death:** combat service sets `npc_definitions.is_active = 0` on death.
- **Narrative kill:** LLM emits `[NPC_KILLED: key=x]` tag. The game engine parses this tag and sets `is_active = 0`.

On NPC death:

1. `npc_definitions.is_active = 0` in DB.
2. In the campaign plan `key_npcs` array (stored in `campaigns.plan_json`), find the entry with matching key and set `alive = false`.
3. If the killed NPC has `importance = 'critical'` in the campaign plan, trigger the `contingency` from `engine_private` on the next turn.
4. If `importance = 'replaceable'`, log the death to `deviations[]` in the campaign plan and continue.

---

## Admin Panel — NPC Editor Additions

On the NPC edit form, add:

- `personality_prompt` text area (max 300 chars, character counter).
- `npc_type` select (neutral / merchant / quest_giver / ally / antagonist).
- `keyword_triggers` dynamic list:
  - Each row: keyword (text input) | must_reveal_info (text area) | is_secret (checkbox) | delete button.
  - "Add trigger" button appends a new empty row.
  - Saved as JSON to `keyword_triggers` column on form submit.

Validation: keyword must not be empty. must_reveal_info must not be empty.

---

## Review Status

New NPCs created via `[CREATE_NPC]` start with `review_status = 'pending_review'`. Admin can:
- Approve (→ `permanent`): NPC persists across all campaigns.
- Edit + Approve: fix personality/triggers before approving.
- Discard (→ `discarded`): NPC becomes a ghost record, not injected into future sessions. Sessions where it was already used are unaffected.

See TASK_10 for the full review queue UI.

---

## Implementation Notes
- `personality_prompt`, `keyword_triggers`, `npc_type` already in DB from TASK_01 migrations
- `build_v2_npc_context_block()` in `world_service.py`: reads personality_prompt + keyword_triggers, injects must_reveal_info when player text matches keyword (case-insensitive substring match)
- Secret triggers (`is_secret=true`) inject: "NPC reveals reluctantly, hints then confirms if pressed"
- `[NPC_KILLED: key=x]` tag: sets npcs.is_active=0, updates campaign plan key_npcs alive flag
- NPC location assignment: checks `location_npc_assignments` first, falls back to `npc_keys` JSON on game_locations
- NPC personality_prompt auto-generation via secondary LLM call (on [CREATE_NPC] tag) — NOT yet implemented; personality_prompt is set from the raw `personality=` tag field (truncated to 300 chars)
