---
doc: 09-character-wizard-spec
version: 1.0.0
generated: 2026-04-26
source_files:
  - frontend/index.html
  - frontend/styles.css
  - frontend/css/combat.css
  - frontend/js/ui.js
  - frontend/js/actions.js
  - frontend/js/app.js
  - frontend/js/api.js
  - frontend/js/character_wizard.js
  - frontend/js/combat_panel.js
  - frontend/js/combat_input.js
  - frontend/js/death_screen.js
  - frontend/js/slash_commands.js
  - frontend/js/events.js
  - frontend/js/main.js
  - frontend/js/state.js
---

# Character Wizard Spec

The character creation flow has one static form step and three dynamic wizard steps. The wizard is blocking from step 2 onward; close is hidden and backdrop close is disabled.

## Step 1: Static Create Form

Container: `#character-create-step-1-wrap`.

Fields:

- `#character-create-name` - required name.
- `#character-create-background` - required background.
- `.archetype-card[data-archetype="warrior"]`.
- `.archetype-card[data-archetype="scholar"]`.
- `#character-create-submit` - submits `createCharacterFromForm()`.

Current archetypes:

- `Warrior` - front-line, durable, melee.
- `Scholar` - fragile, magical/knowledge focused.

Mobile: stack archetype cards, keep each card at least 110 px tall, make selected state obvious.

## Step 2: Stats

State: `window.state.charCreationWizard.step === 2`.

Container: `#character-wizard-panel`.

Stats: STR, DEX, CON, INT, WIS, CHA. LCK exists in the character sheet but is not part of this wizard adjustment set.

Rules:

- Base values can move down to 8 and up to 18.
- Moving down creates unassigned points.
- Confirmation enabled only when unassigned points equal 0 and all values are in range.
- Class bonus applies after confirmation: Warrior gets `+2 STR, +1 CON`; Scholar gets `+2 INT, +1 WIS`.

Dynamic row:

```html
<div class="wizard-stat-row" data-stat="STR">
  <div class="wizard-stat-label">STR</div>
  <div class="wizard-stat-mod muted" aria-label="Modifier">+1</div>
  <div class="wizard-stat-controls">
    <button type="button" class="wizard-stat-btn secondary" data-act="minus" data-stat="STR">−</button>
    <span class="wizard-stat-val">12</span>
    <button type="button" class="wizard-stat-btn secondary" data-act="plus" data-stat="STR">+</button>
  </div>
</div>
```

## Step 3: Skills

State: `step === 3`.

Skill pool:

- Athletics, Stealth, Sleight of Hand, Endurance, Arcana, Investigation, Lore, Awareness, Survival, Medicine, Persuasion, Intimidation.
- Extra creation skills: Melee Attack, Ranged Attack, Spell Attack, Alchemy.

Rules:

- Only pre-rolled skill slots are shown.
- Skill level can be adjusted between 0 and 2.
- Total level-change budget is 4.
- Free swap: a rolled skill slot can swap to an unrolled skill of the same current level without consuming the level-change budget.
- `↔` opens swap mode; `↩` reverts a swap.

Mobile: use one-column full-width rows. Avoid tiny inline selects; use a bottom-sheet picker if implementing a richer replacement later.

## Step 4: Identity

State: `step === 4`.

The app calls `POST /api/characters/:id/generate-identity`. The generated identity includes:

- `appearance` - editable textarea.
- `personality` - editable textarea.
- `flaw` - readonly locked field.
- `bond` - readonly locked field.
- `secret` - stored and finalized but not directly shown as an editable field.

Current UI:

```html
<label for="wiz-id-flaw">Flaw (locked)</label>
<input id="wiz-id-flaw" type="text" readonly>
<p class="muted wizard-secret-hint">🔒 Your secret will be revealed when the story demands it.</p>
```

Design must make locked/secret content visually distinct and trustworthy. Use lock iconography, subdued background, and a short explanatory line.

## Wizard Navigation

- `#character-wizard-back` calls `characterWizardGoBack()`.
- There is no global Next button; each step has inline action buttons with `data-act`.
- Step indicator text is `Step N of 4`.

## Loading And Errors

Identity loading renders `Your GM is writing your story...`. Error state includes a retry button with `data-act="identity-retry"`.

## Mobile Frame List

- `Character Wizard / Step 1 / Empty`
- `Character Wizard / Step 1 / Archetype Selected`
- `Character Wizard / Step 2 / Stats Valid`
- `Character Wizard / Step 2 / Stats Invalid`
- `Character Wizard / Step 3 / Skills`
- `Character Wizard / Step 3 / Swap Mode`
- `Character Wizard / Step 4 / Loading`
- `Character Wizard / Step 4 / Identity`
- `Character Wizard / Step 4 / Error`

## Future Upgrade Notes

The wizard is a good candidate for a more maintainable component renderer later. Until then, preserve `#character-wizard-panel`, `data-act` hooks, and input IDs used during finalize.
