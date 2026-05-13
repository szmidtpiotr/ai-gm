# TASK 07 — Campaign Plan Generation

**Status:** ✅ Done — commit `56a46d5` (2026-05-13)
**Phase:** 02 — Character
**New file:** `backend/app/services/campaign_plan_service.py`
**Test file:** `backend/tests/test_campaign_plan_service.py` — 22 tests, all passing

**Implementation Notes:**
- `CampaignPlan` uses Pydantic v2 `.model_validate()` / `.model_dump()`
- `engine_private` stored in separate `campaigns.engine_private_json` column (migration added)
- `_store_plan()` gracefully falls back to storing full plan in `gm_plan_json` if column missing
- `get_public_plan()` strips `engine_private` for player-facing endpoints
- `finalize-sheet` detects V2 characters (has bonds/weaknesses) and routes to V2 generator; falls back to legacy for V1 characters
- Ideas Bank seeds query (`campaign_ideas` table) — returns empty list gracefully if no approved seeds
- `deviation_consequence` and `importance` fields on PlotNPC are validated via Literal types

---

## Overview

After the character wizard finalizes, the system automatically generates a structured campaign plan tailored to the character's identity. The LLM produces a JSON object that the backend validates, stores, and uses throughout the campaign to guide the GM narrator.

The plan is the world's skeleton — not a script. The LLM narrator follows it loosely, steers toward it, and branches when the player deviates significantly.

---

## Trigger

Auto-called immediately after `POST /api/characters/{id}/finalize-sheet` completes successfully. The campaign plan generation runs server-side before the opening scene is triggered.

---

## Inputs to Generation

The LLM prompt receives:

**From character:**
- `name` (string)
- `archetype` (warrior / scholar)
- `background_note` (string, may be empty)
- `appearance` (string — from Step 4 visible output)
- `personality` (string — from Step 4 visible output)
- `bonds` (array of 2 Bond objects: `{description, type}`)
- `weaknesses` (array of 2 Weakness objects: `{description, type}`)

**Hidden — not in the player-visible plan:**
- `secret_predisposition` (string — from `sheet_json.gm_only`)

**From Ideas Bank:**
- Top 3 seeds queried by setting/tone similarity to the background note and archetype. Each seed: `{title, premise_snippet}`. If no Ideas Bank seeds exist, omit this section gracefully.

---

## Output Schema

Pydantic model `CampaignPlan`. All fields required unless marked optional.

```python
class Bond(BaseModel):
    description: str
    type: Literal["person", "place", "object", "ideal"]

class Weakness(BaseModel):
    description: str
    type: Literal["fear", "flaw", "addiction", "trauma"]

class PlotAct(BaseModel):
    number: int                  # 1, 2, or 3
    title: str
    summary: str                 # 2–4 sentences
    key_beats: list[str]         # 3–5 bullet points of expected events
    completed: bool = False

class PlotEnding(BaseModel):
    id: str                      # slug, e.g. "ending_redemption"
    title: str
    type: Literal["primary", "alternate"]
    description: str             # 2–3 sentences
    requirements: list[str]      # conditions that unlock this ending

class PlotNPC(BaseModel):
    key: str                     # FK to npc_definitions.key
    name: str
    role: str                    # narrative role, e.g. "informant", "antagonist"
    importance: Literal["critical", "supporting", "replaceable"]
    deviation_consequence: Literal["ignore", "steer", "branch"]
    alive: bool = True

class PlotLocation(BaseModel):
    key: str                     # FK to game_locations.key
    name: str
    role: str                    # narrative role, e.g. "opening town", "final confrontation"
    visited: bool = False

class EnginePrivate(BaseModel):
    secret_predisposition_hint: str   # rephrased from character's secret_predisposition
    hidden_twist: str                  # 1–2 sentences — a plot revelation for Act 2/3
    contingency: str                   # 1–2 sentences — what happens if player kills a critical NPC early

class CampaignPlan(BaseModel):
    title: str
    premise: str                       # 1–2 sentences
    acts: list[PlotAct]                # exactly 3
    endings: list[PlotEnding]          # 2 or more; at least one primary, at least one alternate
    key_npcs: list[PlotNPC]            # 3–6 entries
    key_locations: list[PlotLocation]  # 2–5 entries
    active_act: int = 1
    scene_log: list[str] = []          # populated during play
    deviations: list[str] = []         # populated during play
    branches: list[str] = []           # populated during play
    engine_private: EnginePrivate
```

---

## Generation Process

1. Build the LLM prompt from inputs (see Inputs section above).
2. Instruct the LLM to return **only valid JSON** matching the schema. No prose wrapper.
3. Parse response with `CampaignPlan.model_validate_json(response_text)`.
4. On validation failure: retry once with an appended correction instruction ("Your previous response failed schema validation. Return only valid JSON.").
5. On second failure: raise a structured error, log the raw LLM output, return HTTP 500 with a user-facing message ("The GM had trouble planning your campaign. Please try again.").
6. On success: store the plan as JSON in `campaigns.plan_json`. Store `engine_private` separately in `campaigns.engine_private_json` (never served to the player API).

---

## Dark Fantasy Personalization Rules

These are hard constraints the LLM prompt must state explicitly:

1. **Act 1 hook must connect to at least one Bond.** The inciting incident involves or threatens something the character cares about.
2. **The central conflict or antagonist must touch at least one Weakness.** The story should press on the character's wound.
3. **Both endings must be morally grey.** No pure triumph. No cartoonish evil defeated. One ending may be "survival at a cost"; the other may be "victory that poisons the victor." Pure good or pure evil outcomes are rejected at validation time (soft check: endings must each contain at least one word from a predefined compromise-vocabulary list).
4. **Tone register:** WFRP dark fantasy. Despair is present but not gratuitous. Hope exists as something fragile and worth fighting for, not as a guaranteed reward.

---

## Storage

| Field                 | Table column                              | Visible to player API |
|-----------------------|-------------------------------------------|-----------------------|
| Full plan (minus private) | `campaigns.plan_json`               | Yes (via `/api/campaigns/{id}/plan`) |
| engine_private        | `campaigns.engine_private_json`           | No — server-side only |
| secret_predisposition | `characters.sheet_json.gm_only.secret_predisposition` | No |

The player-facing `/api/campaigns/{id}/plan` endpoint returns the full `CampaignPlan` minus the `engine_private` field, and minus any NPC or location entries that are not yet discovered/visited (spoiler filtering, optional in MVP).

---

## Integration Points

- **Character finalize** (TASK_06): passes bonds, weaknesses, secret_predisposition into this generator.
- **Turn context injector** (ongoing): at each turn, the game engine reads `active_act`, `key_npcs`, `key_locations` to select what context to inject into the LLM narrator prompt.
- **Location system** (TASK_08): the first entry in `key_locations` becomes the starting location. If that location key does not exist in `game_locations`, it is created as `pending_review`.
- **NPC system** (TASK_09): `key_npcs` provides the initial NPC roster. Keys must resolve to `npc_definitions`. If a key is unknown, mark it `pending_review` and create a stub.
- **Deviation tracking** (ongoing): when the player takes actions that contradict `key_beats`, append a summary to `deviations[]`. Engine uses this to decide whether to steer back or branch.
