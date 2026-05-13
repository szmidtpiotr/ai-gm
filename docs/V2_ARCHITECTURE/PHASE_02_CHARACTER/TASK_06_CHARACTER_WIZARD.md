# TASK 06 — Character Creation Wizard

Phase: 02 — Character
Status: Spec

---

## Overview

A 4-step modal wizard guides the player through creating a new character. Each step builds on the previous. The wizard is the sole entry point for character creation in V2 — there is no raw form fallback. The wizard is opened from the new campaign flow.

---

## Step 1 — Identity

**Fields:**

| Field            | Type     | Constraints                                 |
|-----------------|----------|---------------------------------------------|
| Name             | text     | Required. 2–50 characters.                  |
| Background note  | textarea | Optional. Max 500 characters. Narrative seed only — not stats or abilities. Hint text: "Who were you before the story began? A rumour, a wound, a name you left behind." |
| Archetype        | button group | One of: Warrior / Scholar. Required. |

**Archetype buttons** are large, flavour-rich toggles, not dropdowns. Each shows:
- Name
- Short flavour line (Warrior: "Steel, scars, and stubborn survival." / Scholar: "Ink, obsession, and the wrong kind of knowledge.")
- Stat bonuses applied (Warrior: STR +2, CON +1 / Scholar: INT +2, WIS +1)

Selecting an archetype immediately loads that archetype's default stats into Step 2's state (no navigation required yet).

---

## Step 2 — Stats

**Display:** Full 7-stat grid (STR, DEX, CON, INT, WIS, CHA, LCK). Each stat shows current value and its modifier.

**Redistribution pool:** 5 points total.

Rules:
- Player can move points from any stat to any other stat.
- Minimum per stat: 8. Maximum per stat: 18.
- Pool starts at 5 unspent. Each point added to a stat costs 1 from pool; each point removed refunds 1.
- Pool display: "Points remaining: N" — shown prominently. Cannot proceed to Step 3 if pool is negative (over-budget), but does not have to spend all points.

**Live HP/Mana preview** (see TASK_05):
- Below the stat grid: `HP: [calculated]` and, for Scholar only, `Mana: [calculated]`.
- Updates on every point change.

**Navigation:** Back → Step 1. Next → Step 3.

---

## Step 3 — Skills

**Redistribution pool:** 3 skill points.

**Display:** List of all available skills, each showing current rank.

Rules:
- Ranks range: 0–5.
- Cannot spend more than 3 points total above the archetype defaults.
- Archetype suggestions are pre-loaded: the 2–3 skills most thematically relevant to the archetype start at rank 1 (consuming 2–3 of the 3 free points). Player can override by reducing suggested skills and boosting others.
- Proficiency bonus applies at rank ≥ 3 (per system prompt mechanics — display this threshold on the UI as a subtle marker).

**Navigation:** Back → Step 2. Next → Step 4.

---

## Step 4 — GM-Generated Identity

The GM (LLM) generates the character's identity from the data collected so far.

**Trigger:** Automatically on entering Step 4. Show a loading state ("The GM is writing your fate...") while waiting.

**Inputs to generation:**
- name, archetype, background_note (from Step 1)
- final stat values (from Step 2)
- final skill ranks (from Step 3)

**Output — player-visible fields (editable):**

| Field         | Format                                  | Editable |
|---------------|-----------------------------------------|----------|
| Appearance    | 2–3 sentences. Physical only.           | Yes      |
| Personality   | 2–3 sentences. Voice, habits, manner.   | Yes      |
| Bonds         | 2 structured entries                    | Yes      |
| Weaknesses    | 2 structured entries                    | Yes      |

Bond entry structure:
```json
{
  "description": "String — what or who this person is bound to.",
  "type": "person | place | object | ideal"
}
```

Weakness entry structure:
```json
{
  "description": "String — the specific weakness or vulnerability.",
  "type": "fear | flaw | addiction | trauma"
}
```

The player may edit appearance, personality, individual bond/weakness descriptions and types before finalizing. They cannot add or remove bonds/weaknesses in this step (always exactly 2 of each).

**Output — hidden field (never shown to player):**

| Field                 | Format                                   | Stored in              |
|-----------------------|------------------------------------------|------------------------|
| Secret Predisposition | 1–2 sentences. A latent trait the character does not know about themselves. Emerges under pressure. | `sheet_json.gm_only.secret_predisposition` |

This field is populated by the LLM alongside the visible fields in a single generation call. The backend must strip it from any player-facing API response. It is passed directly to the campaign plan generator (TASK_07) and stored permanently in `sheet_json.gm_only`.

**Navigation:** Back → Step 3. Finalize button → see below.

---

## Finalize

On clicking Finalize:

1. Validate: all required fields present and within constraints.
2. POST to backend: save character (all visible fields + `gm_only` data).
3. Pass to campaign plan generator: bonds, weaknesses, and secret predisposition (see TASK_07).
4. Trigger opening scene generation.
5. Close wizard, open game session.

---

## Abandoned Wizard Cleanup

If the wizard modal is closed at any point before Finalize:

1. Show confirmation dialog: "Close without finishing? Your character and campaign will be deleted."
2. If confirmed: DELETE the orphan character record and any partially-created campaign record from the database.
3. If cancelled: return to the wizard at the current step.

A character is considered an "orphan" if it has no associated completed campaign session. The cleanup also applies if the browser tab is closed mid-wizard — handle via `beforeunload` event calling a cleanup endpoint, with a server-side TTL fallback for records in `status='wizard_draft'` older than 24 hours.

---

## Tone Notes

Dark fantasy, WFRP register. The wizard should not feel like a spreadsheet. Copy guidance:

- Step headings: terse, slightly ominous ("Who Are You?" / "What Are You Made Of?" / "What Do You Know?" / "Who Will You Become?")
- Validation errors: plain English, no exclamation marks.
- Loading states: flavour text, not "Loading...". Example: "The GM is consulting older, darker books."
- Finalize button label: "Begin" — not "Create Character" or "Submit".
