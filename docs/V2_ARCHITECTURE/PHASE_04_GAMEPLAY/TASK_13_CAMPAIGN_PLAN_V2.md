# TASK 13 — Campaign Plan V2: Runtime Behavior

**Phase:** 04 — Gameplay  
**Status:** ❌ Not Started  
**Related tasks:** TASK 07 (plan generation), TASK 11 (turn pipeline)

---

## Overview

TASK 07 covers how the campaign plan is generated at campaign creation. This document covers what happens to the plan during live play: how the system detects when the story deviates from the plan, how the narrator is informed, and how the plan mutates in response to player choices.

The plan is stored as JSON in `campaigns.gm_plan_json`. All mutations go through the plan update functions in `game_engine.py` — never direct SQL writes to that field from other modules.

---

## Pydantic Schema (Runtime Reference)

The full schema is defined in `backend/app/models/campaign_plan.py`. Key runtime fields:

```python
class KeyBeat(BaseModel):
    beat_key: str           # e.g. "act1_meet_informant"
    title: str
    description: str
    trigger_condition: str  # what action/event completes this beat
    visited: bool = False
    visited_at_turn: int | None = None
    skipped: bool = False

class KeyNPC(BaseModel):
    npc_key: str
    name: str
    alive: bool = True
    relationship: str = "neutral"  # neutral / friendly / hostile
    deviation_consequence: str = "minor"  # ignore / minor / major / catastrophic

class Act(BaseModel):
    act_number: int
    title: str
    key_beats: list[KeyBeat]
    completed: bool = False
    completed_at_turn: int | None = None

class Branch(BaseModel):
    branch_id: str
    trigger_reason: str
    generated_at_turn: int
    acts: list[Act]

class CampaignPlan(BaseModel):
    version: int = 1
    active_act_index: int = 0
    acts: list[Act]
    key_npcs: list[KeyNPC]
    endings: list[Ending]
    branches: list[Branch] = []
    deviation_level: str = "normal"  # normal / minor / major / catastrophic
    deviation_note: str = ""
```

---

## Deviation Detection

Run once per turn, immediately after the World State Updater (TASK 11 Step 6), before the Context Injector builds the narrator prompt.

### Detection Logic

**Step 1 — NPC death check:**  
For each `KeyNPC` where `alive=false`:
- If `deviation_consequence = 'ignore'`: no deviation
- If `deviation_consequence = 'minor'`: deviation score += 1
- If `deviation_consequence = 'major'`: deviation score += 3
- If `deviation_consequence = 'catastrophic'`: deviation score += 10

**Step 2 — Beat skipping check:**  
For the active act: count `key_beats` where `visited=false` and previous beats are visited. A beat is "skipped" if the act progression has moved past it. Skipped beats: deviation score += 2 each.

**Step 3 — Classify:**

| Score | Level | Meaning |
|-------|-------|---------|
| 0 | `normal` | Story on track |
| 1–2 | `minor` | Slight deviation, narrator adapts naturally |
| 3–5 | `major` | Significant departure, narrator must acknowledge and redirect |
| 6+ | `catastrophic` | Story broken, `[BRANCH_REQUIRED]` injected automatically |

**Step 4 — Update plan deviation fields:**  
`plan.deviation_level = classified_level`  
`plan.deviation_note = generated_note`  (human-readable summary of what caused deviation)

---

## Deviation Status in Narrator Context

The Context Injector (TASK 11 Step 7) always includes the deviation block:

```
[CAMPAIGN CONTEXT]
Active Act: 1 — "Cień nad Middenheim"
Beats visited: 2/5
Deviation: minor — "Doktor Voss zginął przed przekazaniem informacji"
```

For `normal` deviation: minimal context, narrator stays on rails.  
For `minor`: narrator receives note but no special instruction.  
For `major`: narrator receives instruction: *"The story has deviated significantly. Acknowledge the consequences naturally and find a path toward the remaining unvisited beats."*  
For `catastrophic`: narrator receives instruction: *"This deviation requires a new story arc. Emit [BRANCH_REQUIRED:brief_reason] in your response."*

---

## Narrator Tags — Full Specification

The narrator LLM may embed these tags anywhere in its prose response. Backend intercepts all tags post-generation using regex before delivering text to frontend. Tags are stripped from displayed prose.

### `[BEAT_COMPLETE:beat_key]`

**Emitted when:** narrator recognizes that a key story beat has concluded (player met the informant, secured the artifact, survived the ambush, etc.).

**Backend action:**
1. Locate `beat_key` in active act's `key_beats`
2. Set `visited=true`, `visited_at_turn=current_turn`
3. Check if all key beats in act are visited → if yes, set `act.completed=true`, `completed_at_turn=current_turn`, increment `active_act_index`
4. If last act completed and no `CAMPAIGN_END` tag: log warning (narrator should have emitted campaign end)
5. Grant milestone XP: 30 XP per beat completion (see TASK 25)

Note: The Mechanic Resolver may also emit `beat_signals` pre-narrator (TASK 11 Step 5). Both paths write through the same plan update function — idempotent on the same beat_key.

---

### `[NPC_KILLED:npc_key]`

**Emitted when:** narrator narrates the death of a named NPC.

**Backend action:**
1. Locate `npc_key` in `plan.key_npcs`
2. Set `alive=false`
3. Trigger deviation detection immediately (before next turn)
4. If `deviation_consequence = 'catastrophic'`: immediately inject `[BRANCH_REQUIRED]` into next turn's narrator context (do not wait for narrator to emit it spontaneously)

---

### `[BRANCH_REQUIRED:reason]`

**Emitted when:** narrator determines the story can no longer proceed on the current act structure.

**Backend action:**
1. Log the branch trigger with reason and current turn number
2. Make a **separate branch generation LLM call** (same provider, full system prompt):
   - Input: current plan state, deviation summary, remaining unvisited beats, character level
   - Output: new `Branch` object (2–3 acts, new key_beats, adjusted endings)
3. Append new `Branch` to `plan.branches`
4. Replace `plan.acts` with branch acts (the new story going forward)
5. Reset `active_act_index = 0` within the new branch
6. Return to normal turn flow — the current narrator response is still delivered

Branch generation uses the same Pydantic schema as initial plan generation (TASK 07). The prompt instructs the LLM to create a coherent continuation given the new reality (e.g., the informant is dead — who else knows the secret?).

---

### `[CAMPAIGN_END:ending_id]`

**Emitted when:** narrator recognizes the player has reached one of the campaign's defined endings.

**Backend action:**
1. Locate `ending_id` in `plan.endings`
2. Set `campaign.status = 'completed'`, `campaign.ended_at = now()`
3. Store `campaign.ending_id = ending_id`
4. Grant ending XP: 200 XP (see TASK 25)
5. Send victory payload to frontend:
   ```json
   {
     "campaign_ended": true,
     "ending_id": "ending_id",
     "ending_title": "Ocalony Middenheim",
     "total_turns": 47,
     "xp_granted": 200
   }
   ```
6. Frontend shows victory/ending screen, disables input

---

## Admin View

`GET /api/admin/campaigns/{campaign_id}/plan`

Returns the full `gm_plan_json` as formatted JSON. Admin panel renders it in a collapsible tree view:

- Per act: title, completion status, beats with visited/skipped indicators
- Key NPCs: alive status, relationship, deviation consequence
- Endings: list with requirements
- Branches: if any exist, shown as separate arc trees
- Deviation level: colored badge (green/yellow/orange/red)

Read-only. Admins cannot manually edit the plan through the panel (editing the raw JSON in the DB is possible but unsupported in v1).

---

## Test Cases

1. **Beat completion via narrator tag:** Narrator emits `[BEAT_COMPLETE:act1_meet_informant]`. Verify `visited=true` set in plan JSON. Verify XP granted. Verify turn number recorded.

2. **NPC killed — minor deviation:** Narrator emits `[NPC_KILLED:herbalist_greta]` where `deviation_consequence='minor'`. Verify `alive=false`. Verify `deviation_level='minor'` after next deviation check.

3. **NPC killed — catastrophic deviation:** Narrator emits `[NPC_KILLED:lead_witness]` where `deviation_consequence='catastrophic'`. Verify branch generation LLM is called. Verify new branch appended to plan.

4. **Branch required:** Catastrophic deviation auto-injects `[BRANCH_REQUIRED]` in narrator context. Narrator emits it. Verify branch generation called, plan updated.

5. **Campaign end:** Narrator emits `[CAMPAIGN_END:ending_main_victory]`. Verify `campaign.status='completed'`. Verify victory payload sent to frontend.
