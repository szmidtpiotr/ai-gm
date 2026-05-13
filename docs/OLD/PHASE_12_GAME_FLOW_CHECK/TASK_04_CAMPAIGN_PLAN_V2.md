# TASK 04 — Campaign Plan v2 Schema

**Status:** ❌ Not Started
**Blocking:** None — spec complete
**Depends on:** Nothing (schema design, no code dependencies)
**Unlocks:** Task 05 (generation uses this schema), Task 06 (deviation handling reads it), Task 07 (admin views it)

---

## Overview

The campaign plan is the GM's "brain" — the structured document that tells the GM where the story is going, who the key players are, and what should happen if the player does something unexpected. Currently `gm_plan_json` is a free-text blob with no formal schema, meaning the GM (LLM) can write anything in it and the system has no ability to inspect or act on its contents programmatically.

This task defines a formal Pydantic model for the campaign plan and replaces the current free-text approach.

---

## Design Context

### Why a formal schema?
The system needs to READ specific fields from the campaign plan programmatically:
- Which NPCs are "critical" (their death requires branching)?
- What is the current active arc?
- Has the player visited the required plot beats?
- What are the possible endings?

If the plan is free text, these questions can only be answered by asking the LLM — which is unreliable and expensive. With a formal schema, the backend can inspect and act on the plan directly.

### Why acts + endings?
A campaign with a beginning and one or more endings is a complete story. Acts 1/2/3 map to the classic story structure:
- **Act 1 (Setup):** Player encounters the situation. Hooks are introduced. No urgency yet.
- **Act 2 (Escalation):** Stakes rise. The player discovers the depth of the problem. Complications appear.
- **Act 3 (Resolution):** The player must make a choice. Endings diverge based on what they've done.

Multiple endings are important because they let the GM design moral complexity. In the vampire example: "kill the vampire" and "negotiate with the vampire" are both valid — they require different skills and choices, but neither is "wrong." This gives the player genuine agency while keeping the story coherent.

### Why NPC importance flags?
Not all NPCs are equal. Killing the town drunk is inconsequential. Killing the vampire hunter who knows how to defeat the antagonist is catastrophic for the plot. The importance flag tells the GM: "if this NPC is gone, you need to adapt." Without it, the LLM has no guidance and might continue the story as if nothing happened.

### Why a Deviation Tracker?
The GM needs to know what deviations have already happened and what branches have been generated. If the player killed one key NPC and the GM branched, the NEW branch's NPCs are now the critical ones. The deviation tracker is the living history of how the story evolved from the original plan.

---

## Current State (Code)

- `campaigns` table has column `gm_plan_json TEXT NOT NULL DEFAULT '{}'`
- `game_engine.py` reads `gm_plan_json`, calls `format_gm_plan_block()` to inject it into the system prompt
- `format_gm_plan_block()` is in `gm_plan_schema.py` — currently handles free-text JSON of unknown structure
- `POST /api/campaigns/{id}/gm-plan` — updates the plan (owner only)
- `POST /api/campaigns/{id}/gm-plan/generate-initial` — generates initial plan via LLM
- `POST /api/campaigns/{id}/gm-plan/advance-scene` — advances current scene

---

## Full Specification — Pydantic Schema

```python
from pydantic import BaseModel
from typing import Optional
from enum import Enum

class DeviationConsequence(str, Enum):
    IGNORE = "ignore"           # NPC death has no plot impact
    STEER = "steer"             # Minor — GM steers back naturally
    BRANCH = "branch"           # Major — GM must generate a new mini-arc
    CATASTROPHIC = "catastrophic"  # Multiple branches blocked — generate new ending

class NPCImportance(str, Enum):
    CRITICAL = "critical"       # Required for main arc to function
    SUPPORTING = "supporting"   # Adds depth but has a replacement path
    REPLACEABLE = "replaceable" # Can be removed without plot impact

class EndingType(str, Enum):
    PRIMARY = "primary"         # The intended main path
    ALTERNATE = "alternate"     # A valid but unexpected resolution

class PlotNPC(BaseModel):
    key: str                    # FK to npc_definitions.key
    name: str
    role: str                   # "antagonist", "ally", "witness", "merchant", etc.
    importance: NPCImportance
    deviation_consequence: DeviationConsequence
    alive: bool = True          # Updated during play when NPC is killed

class PlotLocation(BaseModel):
    key: str                    # FK to game_locations.key
    name: str
    role: str                   # "starting_point", "key_scene", "final_confrontation", etc.
    visited: bool = False       # Updated during play

class PlotEnding(BaseModel):
    id: str                     # "ending_a", "ending_b", etc.
    title: str                  # Short label: "Kill the Vampire", "Negotiate Peace"
    type: EndingType
    description: str            # 2-3 sentences on how this ending plays out
    requirements: list[str]     # What must be true for this ending to be reachable
    # Example requirements: ["vampire_revealed", "player_has_stake_item"]

class PlotAct(BaseModel):
    number: int                 # 1, 2, or 3
    title: str                  # "The Quiet Town", "Blood on the Cobblestones", etc.
    summary: str                # 2-3 sentences describing this act's arc
    key_beats: list[str]        # Plot beats that should happen in this act
    completed: bool = False     # True when GM determines act is resolved

class Deviation(BaseModel):
    turn_number: int
    description: str            # What the player did
    severity: str               # "minor", "major", "catastrophic"
    response: str               # What the GM did in response
    branch_generated: Optional[str] = None  # ID of new branch if generated

class Branch(BaseModel):
    id: str                     # "branch_1", "branch_2", etc.
    triggered_by: str           # Description of what caused this branch
    summary: str                # What this branch adds to the story
    new_key_npcs: list[PlotNPC] = []
    reconnects_to: str          # Which main ending this branch reconnects to

class CampaignPlan(BaseModel):
    # Metadata
    title: str
    premise: str                # 1-2 sentence summary of the campaign's core conflict

    # Structure
    acts: list[PlotAct]         # Always 3 acts
    endings: list[PlotEnding]   # 2+ endings

    # World elements
    key_npcs: list[PlotNPC]
    key_locations: list[PlotLocation]

    # Opening
    opening_scene_delivered: bool = False

    # Living state (updated during play)
    active_act: int = 1
    scene_log: list[str] = []   # Brief notes on what actually happened each session
    deviations: list[Deviation] = []
    branches: list[Branch] = []

    # GM-only (never exposed to player)
    engine_private: dict = {}   # Holds: secret_predisposition reference, hidden twists, contingency notes
```

### JSON Example (stored in `gm_plan_json`)
```json
{
  "title": "Cień nad Graustein",
  "premise": "Mieszkańcy małego miasteczka giną w tajemniczych okolicznościach. Gracz musi odkryć prawdę i dokonać wyboru.",
  "acts": [
    {
      "number": 1,
      "title": "Cisza przed burzą",
      "summary": "Gracz przybywa do Graustein i odkrywa, że coś jest nie tak. Ludzie zamknęli się w domach. W karczmie krążą plotki o trupach z nakłuciami na szyi.",
      "key_beats": ["arrival_in_town", "tavern_rumors", "first_body_discovered"],
      "completed": false
    }
  ],
  "endings": [
    {
      "id": "ending_a",
      "title": "Pokonaj wampira",
      "type": "primary",
      "description": "Gracz konfrontuje i zabija wampira. Miasteczko jest bezpieczne. Nagroda od mieszczan.",
      "requirements": ["vampire_identity_known", "player_has_stake_or_silver"]
    },
    {
      "id": "ending_b",
      "title": "Pakt z wampirem",
      "type": "alternate",
      "description": "Po pokonaniu wampira w walce gracz może wynegocjować układ: wampir opuszcza miasteczko w zamian za przysługę.",
      "requirements": ["vampire_defeated_not_killed", "player_chose_negotiation"]
    }
  ],
  "key_npcs": [
    {
      "key": "vampire_master",
      "name": "Nieznany",
      "role": "antagonist",
      "importance": "critical",
      "deviation_consequence": "branch",
      "alive": true
    }
  ],
  "key_locations": [],
  "opening_scene_delivered": false,
  "active_act": 1,
  "scene_log": [],
  "deviations": [],
  "branches": [],
  "engine_private": {
    "secret_predisposition_hint": "Character has latent magical sensitivity",
    "hidden_twist": "The vampire was once a local healer, cursed against their will",
    "contingency": "If vampire killed in Act 1 before reveal: introduce vampire's thrall as new antagonist"
  }
}
```

---

## Code Changes Required

### 1. New file: `backend/app/schemas/campaign_plan.py`
Define the full Pydantic model as above.

### 2. `backend/app/services/gm_plan_schema.py`
- Add `validate_campaign_plan(raw_json: str) -> CampaignPlan` — parses and validates
- Update `format_gm_plan_block(plan: CampaignPlan) -> str` — formats for LLM injection
- The formatted block should highlight: active act, next unvisited key beats, alive NPCs + importance

### 3. `backend/app/api/campaigns.py`
- On `GET /campaigns/{id}` or plan endpoints: validate `gm_plan_json` against schema
- Validate on WRITE operations: reject malformed plans with 422

### 4. Migration
No new DB columns needed — `gm_plan_json` remains TEXT. But existing rows have unstructured data and must be migrated or accepted as-is (graceful fallback).

---

## Injection Format (what the LLM sees per turn)

```
=== CAMPAIGN PLAN ===
Title: Cień nad Graustein
Current Act: 1 — Cisza przed burzą
Next required beats: arrival_in_town, tavern_rumors

Key NPCs:
  - Nieznany (antagonist) [CRITICAL — do not kill before reveal]

Deviations this campaign: none yet
=====================
```

The injection must be SHORT — the full JSON is not dumped into the prompt. Only actionable fields.

---

## Edge Cases

- **LLM generates plan that doesn't validate:** Accept with warnings, log validation errors, fall back to unstructured mode
- **Key NPC killed before they appeared:** `alive = false` flag triggers deviation handling (Task 06)
- **Player completes Act 3 without visiting Act 2 beats:** Backend detects active_act should be 3 but key Act 2 beats are unvisited — GM steers to visit them or allows skip and generates adapted ending

---

## Related Tasks
- Task 05 (Campaign Plan Generation) — generates the plan that fills this schema
- Task 06 (Deviation Handling) — reads key_npcs.deviation_consequence and key_npcs.alive
- Task 07 (Admin Workshop) — admin views and edits this schema
