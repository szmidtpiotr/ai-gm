# TASK 05 — Campaign Plan Generation

**Status:** ❌ Not Started
**Blocking:** None — spec complete
**Depends on:** Task 02 (character bonds/weaknesses/predisposition as inputs), Task 04 (campaign plan schema)
**Unlocks:** Task 03 (Opening Scene uses plan), Task 06 (Deviation uses plan)

---

## Overview

When a player finalizes their character, the GM generates a complete campaign plan from scratch using the character's identity as the raw material. The player's bonds, weaknesses, and secret predisposition are the primary inputs — the GM builds a story specifically around who this character is. The plan follows the structured schema from Task 04.

---

## Design Context

### Why generate at finalize-sheet, not at campaign-create?
Campaign creation happens BEFORE character creation. There is no character data to work with. The plan must know: Who is this character? What do they care about? What are they afraid of? Only finalize-sheet has this data.

Current code generates a plan at campaign-create — this is wrong and produces a generic plan that ignores the character.

### Why use bonds and weaknesses as primary inputs?
The best TTRPG campaigns are personal. A campaign about a vampire mystery becomes compelling when the player's bond is "I'm looking for my missing brother" — now the GM can make the vampire's first victim someone who resembles the character's brother. The player's weakness ("I freeze when confronted with the undead, from a childhood trauma") becomes a built-in narrative moment during the vampire reveal.

Generic campaigns feel like modules. Personalized campaigns feel like someone wrote the story FOR you.

### What makes a good generated campaign plan?
1. The premise references the character's background or situation
2. Act 1's hooks connect to at least one bond
3. The antagonist or conflict touches at least one weakness
4. The secret predisposition is hidden in `engine_private` as a future hook
5. Both endings feel like genuine choices (not "good ending" vs "bad ending")
6. NPCs have defined importance flags — not everything is "critical"

---

## Current State (Code)

- `POST /api/campaigns/{id}/gm-plan/generate-initial` exists
- It generates a plan via LLM but the prompt does NOT take character data as input (wrong)
- The generated plan has no formal schema (fixed by Task 04)
- Bonds and weaknesses from character are NOT currently structured fields (fixed by Task 02)

---

## Full Specification

### Trigger
Called automatically from `finalize-sheet` handler:
1. Character finalization completes (bonds, weaknesses, predisposition all saved)
2. Backend calls `generate_campaign_plan(campaign_id, character_id)`
3. Plan is generated and saved to `campaigns.gm_plan_json`
4. On success: trigger opening scene generation (Task 03)

### Generation Inputs (sent to LLM)
```
Character:
  - name, archetype
  - background_note (player-written)
  - appearance + personality (GM-generated in Step 4)
  - bonds: [{description, type}, ...]
  - weaknesses: [{description, type}, ...]

Secret (injected into engine_private, not into user-facing plan):
  - secret_predisposition

Campaign:
  - title (set by player, often just "New Campaign")
  - setting: fantasy (hardcoded for now)
```

### LLM Prompt Structure (pseudocode)
```
You are a Game Master creating a complete campaign plan for a tabletop RPG.
You MUST follow the JSON schema exactly.

Character information:
  Name: {name}
  Archetype: {archetype}
  Background: {background_note}
  Personality: {personality}
  Bonds:
    - {bond_1_description}
    - {bond_2_description}
  Weaknesses:
    - {weakness_1_description}
    - {weakness_2_description}

Instructions:
- Create a campaign with a clear beginning and TWO possible endings
- Act 1 should connect to the character's bonds
- The central conflict should touch the character's weaknesses
- Include 2-4 key NPCs with their importance levels
- Include a starting location
- Write in Polish for all narrative fields (title, descriptions, summaries)
- Respond ONLY with valid JSON matching the CampaignPlan schema

[CampaignPlan schema injected here]
```

### Generated Plan Validation
After LLM returns JSON:
1. Parse with `CampaignPlan.model_validate(data)`
2. If validation fails: log error, retry once with simplified prompt
3. If second attempt fails: save raw LLM output with `validation_error` flag, alert admin
4. If success: save to `campaigns.gm_plan_json`

### Starting Location
The plan includes a `key_locations` list. The first entry is the starting location.

If the location key does NOT exist in `game_locations`:
- Create a new `game_locations` record with `status = "pending_review"`
- Use the plan's location description as the `description` field
- Proceed with the new location in the session

If the location key EXISTS in `game_locations`:
- Use the existing record's description (consistent world-building)

---

## Example Generated Plan (abridged)

Input character: Warrior named "Aldric", bond: "wants to leave mercenary life", weakness: "gambling addiction"

```json
{
  "title": "Cień nad Graustein",
  "premise": "Aldric przybywa do Graustein szukając spokojnej roboty — zamiast tego wpada w sieć krwawych morderstw.",
  "acts": [
    {
      "number": 1,
      "title": "Martwe miasto",
      "summary": "Aldric przybywa i odkrywa, że miasto jest w panice. Karczma oferuje pracę — ktoś płaci za informacje o morderstwach.",
      "key_beats": ["arrival", "tavern_job_offer", "first_clue_puncture_wounds"],
      "completed": false
    },
    {
      "number": 2,
      "title": "Krew i złoto",
      "summary": "Aldric śledzi tropy. Odkrywa hazard z ofiarami wampira — to idealny wabik na kogoś z nałogiem.",
      "key_beats": ["gambling_den_discovered", "vampire_thrall_encountered", "vampire_identity_hinted"],
      "completed": false
    },
    {
      "number": 3,
      "title": "Rozliczenie",
      "summary": "Konfrontacja z wampirem. Aldric musi wybrać: zniszczyć go i zgarnąć nagrodę, czy wynegocjować układ.",
      "key_beats": ["vampire_lair_found", "final_confrontation"],
      "completed": false
    }
  ],
  "endings": [
    {
      "id": "ending_a",
      "title": "Rzeźnik z Graustein",
      "type": "primary",
      "description": "Aldric zabija wampira. Mieszczanie płacą nagrodę. Może teraz odejść z życia najemnika.",
      "requirements": ["vampire_identity_known", "confrontation_occurred"]
    },
    {
      "id": "ending_b",
      "title": "Pakt",
      "type": "alternate",
      "description": "Aldric, skuszony propozycją — wampir zna lokalizację skarbu — pozwala mu odejść. Wampir odchodzi, Aldric dostaje mapę.",
      "requirements": ["vampire_defeated", "player_chose_negotiation"]
    }
  ]
}
```

Note how Act 2 exploits the gambling weakness (gambling den as vampire bait) and the alternate ending uses greed as the motivating factor.

---

## Edge Cases

- **Campaign title is generic ("New Campaign"):** Plan title should be more evocative — LLM generates a narrative title regardless of the campaign input name
- **Background note is empty:** Generate a generic but coherent origin consistent with archetype
- **LLM produces plan with no CRITICAL NPCs:** Validation warning — at minimum the antagonist should be CRITICAL
- **Plan is generated but opening scene also needs location from the plan:** Race condition — ensure plan is fully saved before opening scene generation is called

---

## Test Plan

1. Finalize a Warrior character with specific bonds and weaknesses → verify plan's Act 1 references at least one bond
2. Verify plan JSON validates against CampaignPlan schema
3. Verify plan has exactly 3 acts and 2+ endings
4. Verify at least one NPC has `importance = "critical"`
5. Verify `engine_private.secret_predisposition_hint` is populated
6. Verify starting location is created in `game_locations` if it doesn't exist
7. Finalize a Scholar character with different background → verify plan is different (not cached)

---

## Related Tasks
- Task 02 (Character Wizard) — provides bonds, weaknesses, predisposition
- Task 04 (Campaign Plan v2 Schema) — schema that generated plan must conform to
- Task 03 (Opening Scene) — triggered after this task completes
- Task 06 (Deviation Handling) — reads generated plan's NPC importance during play
