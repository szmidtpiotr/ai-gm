# TASK 14 — Opening Scene

**Phase:** 04 — Gameplay  
**Status:** ✅ Done — commit `92e990f` (2026-05-13)  
**Related tasks:** TASK 07 (campaign plan generation), TASK 09 (character finalization), TASK 11 (turn pipeline)

---

## Overview

The opening scene is the narrator's first words. It fires exactly once per campaign, after both character finalization and campaign plan generation are confirmed complete. It is stored as turn #1 in `action_log` and is treated as a special narration-only turn — no player action, no mechanic resolution.

---

## Trigger Sequence

```
Player submits final character sheet
  → POST /api/characters/{id}/finalize
    → character.finalized = true
    → if campaign.gm_plan_json is complete:
        → generate_opening_scene()
    → else:
        → wait (plan generation async, may still be running)

Plan generation completes
  → if character.finalized = true:
      → generate_opening_scene()
```

Both pathways converge on `generate_opening_scene()`. The function is idempotent — it checks `campaign.opening_scene_generated` flag before calling the LLM, preventing double generation.

This means opening scene generation is inherently sequential: it cannot fire until both character finalization AND plan generation are done.

---

## Inputs to Narrator

The narrator receives a specialized opening scene prompt, not the standard turn context block.

**Character identity block:**

```
[CHARACTER]
Name: {character.name}
Appearance: {character.appearance_description}
Archetype: {character.archetype}
Personality: {character.personality_trait}
Bond: {character.bond}          ← must be referenced in scene
Flaw or Weakness: {character.flaw}
Background: {character.background_summary}
```

**Campaign opening block:**

```
[CAMPAIGN OPENING]
Act 1 Title: {plan.acts[0].title}
Act 1 Summary: {plan.acts[0].description}
Opening Hook: {plan.opening_hook}
Starting Location: {location.name}
Location Atmosphere: {location.description_long}
Location Sensory Details: {location.sensory_notes}  ← smell, sound, light
```

**Narrator instruction:**

```
[OPENING SCENE INSTRUCTION]
Write the opening scene for this campaign in Polish. 100-200 words.
Dark fantasy tone (WFRP-inspired: grim, grounded, morally complex world).

MANDATORY:
- Reference the character's bond or flaw directly (not by mechanic name — weave it into scene)
- Place the character physically in the starting location
- Create immediate tension or curiosity — something is wrong, unknown, or threatening
- End on a moment that demands player response

FORBIDDEN:
- Do not begin with the character's name as the first word
- Do not mention dice, stats, HP, skills, or any mechanical term
- Do not tell the player what to do or what their options are
- Do not use second person to describe what they "should" do
- Do not use fantasy clichés as openers ("W pewnym odległym królestwie...", "Legenda głosi...")
```

---

## Output Requirements

| Requirement | Spec |
|-------------|------|
| Language | Polish |
| Word count | 100–200 words |
| POV | Second person ("Stoisz przy...") or third limited ("Marian wchodzi do...") |
| Bond/flaw reference | Woven into scene naturally, not named as a mechanic |
| Physical placement | Character's position in starting location must be clear |
| Tension element | Something specific that creates unease or urgency |
| Ending moment | Scene ends at a beat requiring player choice (not a rhetorical question) |
| First word | Must NOT be the character's name |

---

## Storage

Stored as `action_log` entry with `turn_number=1` and `metadata.opening_scene=true`:

```sql
INSERT INTO action_log (
  campaign_id, character_id, turn_number,
  user_text, action_tag, mechanic_result_json,
  narrator_response, hp_before, hp_after,
  location_id, metadata_json, created_at
)
VALUES (
  {campaign_id}, {character_id}, 1,
  NULL,           -- no player input
  'OPENING_SCENE', NULL,
  {prose},
  {character.max_hp}, {character.max_hp},
  {starting_location_id},
  '{"opening_scene": true}',
  NOW()
)
```

Additionally: set `campaign.opening_scene_generated = true` and `campaign.status = 'active'`.

---

## Frontend Behavior

**Loading state** (while opening scene is generating):

Display centered in the narrative area:
```
GM przygotowuje twój świat...
[animated quill/parchment icon]
```

Input field is disabled. Send button is disabled.

**On delivery:**

1. Opening scene prose fades in (CSS opacity transition, 0.8s)
2. After fade completes (or 1s timeout): input field enables
3. Character panel populates with starting HP, starting location badge, character name
4. No system message, no "Turn 1" label — the scene appears as if the world simply begins

**No "press any key to start" screen.** The scene is the start.

---

## Test Cases

1. **No blank start:** With a complete character and plan, the opening scene is generated and returned. `narrator_response` is non-null and non-empty in `action_log`.

2. **Bond referenced:** Parse the opening scene prose for a substring matching any keyword from `character.bond`. If bond is "twoja siostra" — the prose must contain a reference to sibling/family. (Fuzzy match acceptable in test; semantic check in manual QA.)

3. **Polish language:** Run a language detection check on the prose. Must return `pl` confidence > 0.95.

4. **Word count:** Split on whitespace, count tokens. Must be between 80 and 250 (generous range to allow for Polish compound words and punctuation edge cases; target is 100–200).

5. **Not character name as first word:** `prose.split()[0].lower() != character.name.lower()`

6. **Idempotent:** Call `generate_opening_scene()` twice for the same campaign. Verify LLM is called only once (second call returns early on `opening_scene_generated=true` flag). Verify `action_log` has exactly one `opening_scene` entry.

---

## Implementation Notes
**Status:** ✅ Done — commit `92e990f` (2026-05-13)  
**File:** `backend/app/services/turn_pipeline.py` → `generate_opening_scene()`

- Idempotency check: queries `campaign_turns` for an existing row with `user_text IS NULL`; if found, skips generation and returns `None`
- Prompt uses V2 character identity: bonds + weaknesses from `sheet_json.identity`, NOT the legacy `char_summary` string
- Campaign plan inputs: Act 1 title + summary + starting location name (first key_location with "start" in role, or first entry)
- Prose stored in `campaign_turns` with `user_text=NULL`, `route='narrative'`, `turn_number=1`
- The existing V1 opening scene (using `char_summary`) remains as fallback in `characters.py` for characters without V2 identity (bonds/weaknesses)
- V2 path not yet wired into `characters.py` finalize-sheet flow — the `generate_v2_opening_scene` import was added but the conditional call had indentation issues; reverted. The `generate_opening_scene()` function is ready to be called directly from `turns.py` or a post-finalize hook in Phase 09/10.
- Length target: 100-200 words. No instruction to player. References one bond or weakness. Dark fantasy tone.
