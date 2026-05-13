# TASK 03 — Opening Scene Generation

**Status:** ❌ Not Started
**Blocking:** None — spec complete
**Depends on:** Task 02 (character must be finalized first), Task 04 (campaign plan must exist)
**Unlocks:** Gameplay (first player turn)

---

## Overview

The opening scene is the GM's first narration — delivered automatically after the character wizard is completed. It introduces the player to the world: where they are, what's happening around them, and a hook that implies something worth doing. The player has not typed anything yet. This is a GM-initiated turn that sets the stage.

No blank chat. No "What would you like to do?" The game starts with the world already in motion.

---

## Design Context

### Why auto-generate, not let admin write?
The opening scene must reference the specific character — their name, appearance, bonds, weaknesses — to feel personal. An admin-written static opener would be generic. The GM-generated opener weaves the character's identity into the world's first impression.

### Why after finalize-sheet, not on campaign create?
The campaign is created before character creation is complete. At campaign creation time, there is no character identity to reference. The opening scene requires: character name, archetype, bonds, weaknesses, the campaign's arc 1 premise, and the starting location. These only exist after `finalize-sheet` completes.

### What makes a good opening scene?
A good opening scene does 4 things:
1. **Places the character physically** — where are they, what do they see, smell, hear
2. **Reflects the character's identity** — references something from their background or bonds
3. **Creates immediate tension or curiosity** — something is wrong, unusual, or intriguing
4. **Does NOT give the player instructions** — no "what do you do?", no menu of options, no mechanical prompts

Example (vampire mystery campaign, Warrior with bond "wants to leave the mercenary life"):
> *"The road into Graustein is quieter than it should be. You've ridden through a dozen towns like this — tired walls, church spire, smoke from a few chimneys. But the gates stand open and unguarded at this hour, and the only sound is your horse's hooves on wet cobblestones. A cat watches you from a windowsill, then retreats inside. Upstairs, someone pulls a shutter closed. You came here looking for steady work, maybe enough to finally buy out of the contract. Whatever's making these people hide, it's not good for business."*

This opening places the character (riding into town), reflects their bond (wants steady work, buy out of contract), and creates tension (the town is wrong) — without telling them what to do.

---

## Current State (Code)

- No dedicated opening scene endpoint or service exists
- `POST /api/campaigns/{id}/gm-plan/generate-initial` exists but generates the PLAN, not the opening scene
- Campaign creation currently auto-generates an initial GM plan but it's unclear if an opening scene is delivered to the player
- Turn #1 may be blank or missing — player is dropped into chat with no GM introduction

---

## Full Specification

### Trigger
Called automatically by backend when `POST /characters/{id}/finalize-sheet` completes successfully.

Execution:
1. `finalize-sheet` saves identity, bonds, weaknesses, secret predisposition
2. Backend calls campaign plan generation (if not already generated) — see Task 05
3. Backend calls opening scene generation (this task)
4. Opening scene is stored as a turn in `campaign_turns`
5. Frontend receives the opening scene via SSE stream OR as first turn in turn history

### Opening Scene Turn Properties
```
campaign_turns record:
  campaign_id: {id}
  character_id: {id}
  user_text: NULL (no player input — GM-initiated)
  assistant_text: {opening scene text}
  route: "narrative"
  turn_number: 1
  metadata: {"turn_type": "opening_scene"}
```

### GM Inputs (passed to LLM)
The LLM generating the opening scene receives:
- Character name and archetype
- Character appearance and personality (from Step 4)
- Bonds (what the character cares about)
- Weaknesses (what the character fears or struggles with)
- Campaign premise (1-2 sentence summary from campaign plan Act 1)
- Starting location (name + atmosphere description from `game_locations` table)
- Tone instruction: gritty WFRP-inspired, immersive, no meta-commentary

### GM Constraints (system prompt instructions for this call)
- Length: 100–200 words
- First person or third person narration (third person preferred: "You see...", "You arrive...")
- Must reference at least one element from the character's bonds or weaknesses
- Must create a sense of place — physical environment, atmosphere, sensory detail
- Must imply something worth investigating or reacting to — not just description
- Must NOT tell the player what to do
- Must NOT reference mechanics, stats, dice, or game systems
- Must NOT use the character's name as first word (avoid "Aldric stands at..." — less immersive)
- Polish language output (game narration is in Polish)

### Frontend Behavior
1. Character wizard finalize button clicked
2. Spinner/loading state: "GM is preparing your world..."
3. Opening scene arrives (streamed or as a completed turn)
4. Chat panel displays the opening scene as a GM bubble (left-aligned)
5. Text input becomes enabled — player can now write their first action
6. Location badge updates to show the starting location

### Starting Location
The opening scene's physical setting comes from the starting location in the campaign plan. This location must:
- Exist in `game_locations` table (either permanent or pending_review)
- Be linked to the campaign in the plan
- Have a `description` and `atmosphere` field used to flavor the scene

---

## Edge Cases

- **LLM failure during opening scene:** Retry once. If second attempt fails, insert a generic fallback: "You find yourself at the start of a new journey. The world around you waits." This is ugly but prevents a blank start.
- **Player refreshes browser before opening scene loads:** Turn is already stored in DB (if write happened before stream). On reconnect, turn history is loaded and opening scene appears correctly.
- **Opening scene generation takes too long (>10s):** Frontend should show a "GM is thinking..." skeleton state in the chat area so player doesn't think the app is broken.
- **Character has no bonds or weaknesses (edge case if they were deleted in wizard):** Opening scene falls back to archetype-generic tone — still generates, just less personalized.

---

## Test Plan

1. Complete full wizard → verify opening scene appears in chat within 15 seconds
2. Opening scene contains at least one reference to character bond or weakness
3. Opening scene is 100–200 words
4. Opening scene is in Polish
5. `campaign_turns` has exactly 1 row for the campaign after wizard, with `user_text = NULL`
6. Location badge shows the starting location name after opening scene loads
7. Text input is disabled until opening scene arrives, then enabled

---

## Related Tasks
- Task 02 (Character Wizard) — finalize-sheet triggers this
- Task 04 (Campaign Plan v2) — campaign plan arc 1 is an input
- Task 09 (Location System) — starting location displayed in badge after scene loads
