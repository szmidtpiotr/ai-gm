# TASK 02 — Character Creation Wizard

**Status:** 🔶 Partially Built
**Blocking:** None — spec complete
**Depends on:** Task 01 (HP/Mana formulas must be implemented to calculate HP in Step 2)
**Unlocks:** Task 03 (Opening Scene), Task 05 (Campaign Plan Generation)

---

## Overview

The character creation wizard is a 4-step modal that runs immediately after a campaign is created. Steps 1–3 already exist in some form in the frontend and backend. Step 4 (GM-generated identity) is the most significant new work — the GM/LLM reads the character's mechanical choices and writes their personality, appearance, bonds, weaknesses, and a hidden secret predisposition. All of this feeds into the campaign plan generator.

---

## Design Context

### Why GM generates the identity?
The player defines the mechanical skeleton (name, archetype, stats, skills) but the GM interprets what that means narratively. A Warrior with high CHA and Persuasion skill is mechanically a "face fighter" — the GM might give them a silver-tongued background with a bond involving a debt of honor. This creates characters who feel coherent, not just stat blocks.

### Why bonds and weaknesses?
Bonds (people, places, or things the character cares about) and weaknesses (fears, flaws, addictions) are direct inputs into the campaign plot generator. A character with a bond to a lost sibling will encounter plot hooks that exploit that. A character with a weakness for gambling will find temptations woven into the story. This makes the world feel like it reacts to WHO the character is, not just what they can do.

### Why a secret predisposition?
The secret predisposition is the GM's private narrative hook — a latent trait the player doesn't know about. A Warrior who was always curious about arcane texts might have a secret magical aptitude. A Scholar raised on the streets might surprise even themselves with their capacity for violence. This creates organic "character evolution" moments later in the campaign — the GM can introduce quests or situations that awaken this hidden trait. The player experiences it as the world noticing something about them they didn't know themselves.

### Why auto-generate, not let player write?
Players often write dry, generic identity text ("he is brave and loyal"). The GM — given the stats, skills, and background note — can produce something vivid and game-relevant. But the player CAN edit the generated text before confirming, so they're not trapped.

---

## Current State (Code)

- **Steps 1–3 exist** in `frontend/js/actions.js` and `backend/app/api/characters.py`
- **`POST /characters/{id}/generate-identity`** endpoint exists but may not accept stats + background as inputs
- **`POST /characters/{id}/finalize-sheet`** endpoint exists
- **Abandoned wizard cleanup:** no cleanup currently — orphan characters remain in DB if modal is closed
- **Bonds and weaknesses:** stored as free text strings, not structured fields
- **Secret predisposition:** does not exist in schema or code

---

## Full Specification — 4-Step Wizard

### Step 1 — Basic Info
**Fields:**
- Character name (text input, required, max 50 chars)
- Background note (textarea, optional, max 500 chars) — player's narrative seed, e.g., "grew up as a soldier, lost his unit in an ambush, seeking revenge"
- Archetype selection: **Warrior** or **Scholar** (button group, required)

**On Next:**
- `POST /api/campaigns/{id}/characters` with `{name, background_note, archetype}`
- Backend creates character with default stat block for archetype, HP/Mana calculated
- Character ID returned and stored for subsequent wizard steps
- If character was already created (back-button reuse), reuse existing ID (no duplicate creation)

**Archetype defaults:**
```
Warrior: STR=12, DEX=12, CON=12, INT=10, WIS=11, CHA=10, LCK=10
Scholar: STR=10, DEX=11, CON=10, INT=12, WIS=11, CHA=10, LCK=10
```

### Step 2 — Stats Redistribution
**Display:** All 7 stats with current values and modifiers. Pool of points to redistribute.

**Rules:**
- Stat minimum: 8 per stat
- Stat maximum: 18 per stat
- Archetype bonuses already applied (Warrior: STR+2/CON+1, Scholar: INT+2/WIS+1) and cannot be removed
- Redistribution pool: 5 points to freely move between stats
- HP preview updates live as CON changes (calls formula from Task 01)
- Mana preview (Scholar only) updates live as INT changes

**On Next:**
- `PATCH /characters/{id}/sheet` with updated stat block
- Recalculate `max_hp` and `max_mana` on backend

### Step 3 — Skills Redistribution
**Display:** Archetype-suggested skills with ranks 0–5. Pool of skill points.

**Rules:**
- Skill rank minimum: 0
- Skill rank maximum: 5
- Small redistribution pool (exact value TBD — suggest 3 points)
- Archetype-default ranks pre-filled (Warrior: Combat Skills pre-loaded; Scholar: Knowledge Skills pre-loaded)

**On Next:**
- `PATCH /characters/{id}/sheet` with updated skill block

### Step 4 — GM-Generated Identity
**Trigger:** On entering Step 4, frontend calls `POST /characters/{id}/generate-identity`

**GM inputs (sent to LLM):**
- Character name
- Background note (player-written)
- Archetype
- Final stat block (STR, DEX, CON, INT, WIS, CHA, LCK with modifiers)
- Final skill ranks (which skills are highest)

**GM outputs — SHOWN TO PLAYER (editable):**
- **Appearance** (2-3 sentences) — physical description, notable features, how they carry themselves
- **Personality** (2-3 sentences) — temperament, speech patterns, how they react under pressure
- **Bonds** (2 entries) — structured: `{description: "...", type: "person|place|object|ideal"}`
  - Example: `{description: "Owes his life to a tavern keeper in Sorgenwald", type: "person"}`
- **Weaknesses** (2 entries) — structured: `{description: "...", type: "fear|flaw|addiction|trauma"}`
  - Example: `{description: "Cannot refuse a gamble, no matter the stakes", type: "addiction"}`

**GM outputs — HIDDEN FROM PLAYER (stored in sheet_json under `gm_only` key):**
- **Secret Predisposition** — 1-2 sentences describing a latent trait the player doesn't know about
  - Example: "Despite his warrior training, Aldric's hands tremble with latent magical sensitivity — he mistakes it for battle-nerves."
  - Stored in `sheet_json.gm_only.secret_predisposition`
  - Never returned by any player-facing API endpoint
  - Used by Campaign Plan generator as a private hook for future story arcs

**Player action:** Can freely edit Appearance, Personality, Bonds, Weaknesses. Cannot see Secret Predisposition.

**On Confirm:**
- `POST /characters/{id}/finalize-sheet` with final identity data
- Bonds and weaknesses saved as structured JSON arrays (not free text)
- Secret predisposition saved in `sheet_json.gm_only`
- Triggers Opening Scene generation (Task 03) — asynchronous, UI shows loading state

### Abandoned Wizard Cleanup
**Problem:** If the player closes the modal at any step, an orphan character (and potentially orphan campaign) remains in the DB.

**Solution:**
- When modal is opened, store `{campaign_id, character_id}` in modal state
- When modal is closed WITHOUT finalize: `DELETE /api/campaigns/{id}` (cascade deletes character)
- Exception: if campaign already has completed turns (player was returning to a completed character), do NOT delete
- Frontend confirmation dialog: "Are you sure? Your character will be lost."

---

## Schema Changes Required

### `sheet_json` structure additions
```json
{
  "bonds": [
    {"description": "...", "type": "person|place|object|ideal"}
  ],
  "weaknesses": [
    {"description": "...", "type": "fear|flaw|addiction|trauma"}
  ],
  "gm_only": {
    "secret_predisposition": "..."
  }
}
```

### API changes
- `POST /characters/{id}/generate-identity` — must accept: name, archetype, stats, skills, background_note
- Response must include all editable fields (appearance, personality, bonds, weaknesses) but NOT gm_only
- `POST /characters/{id}/finalize-sheet` — must save structured bonds/weaknesses
- `GET /characters/{id}/sheet` — must EXCLUDE `sheet_json.gm_only` from response

---

## Edge Cases

- **Player edits all GM-generated text:** Valid — player has final say on appearance/personality/bonds/weaknesses
- **Player clears a bond/weakness:** Should require at least 1 bond and 1 weakness (min enforcement in frontend)
- **Back button from Step 4 to Step 3:** Character already exists, stat/skill changes should re-trigger identity generation on re-entering Step 4 OR player can keep existing generated identity
- **LLM fails to generate identity:** Show generic placeholder, allow player to write manually, continue
- **Secret predisposition accidentally returned in API:** Add unit test: GET /characters/{id}/sheet must not contain `gm_only` key at top level

---

## Test Plan

1. Complete full 4-step wizard → verify character has name, stats, skills, identity, bonds, weaknesses, secret predisposition
2. Close modal at Step 2 → verify campaign and character are deleted from DB
3. Edit all GM-generated text fields → verify edits saved in finalize
4. GET /characters/{id}/sheet → verify `gm_only` key is absent from response
5. Check `gm_plan_json` after campaign creation → verify bonds and weaknesses are referenced as inputs
6. Stat redistribution in Step 2 → verify HP updates live when CON changes

---

## Related Tasks
- Task 01 (HP/Mana) — HP formula must be applied in Step 2 preview
- Task 03 (Opening Scene) — triggered at end of this wizard
- Task 05 (Campaign Plan Generation) — bonds, weaknesses, secret predisposition are inputs
