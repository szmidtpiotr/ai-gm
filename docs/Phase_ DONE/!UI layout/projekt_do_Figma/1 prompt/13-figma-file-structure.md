---
doc: 13-figma-file-structure
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

# Figma File Structure

Recommended file: `AI-GM Mobile Redesign`.

```text
AI-GM Mobile Redesign
├── 00 Handoff README
├── 01 Foundations
│   ├── Colors
│   ├── Typography
│   ├── Spacing
│   ├── Radius + Shadows
│   └── Motion
├── 02 Components
│   ├── Buttons
│   ├── Status Dots
│   ├── Chat Messages
│   ├── Roll Cards
│   ├── Composer
│   ├── Action Popup
│   ├── Character Sheet
│   ├── Combat Panel
│   ├── Character Wizard
│   ├── Modals
│   ├── Death Screen
│   └── Slash Commands
├── 03 Screens - Mobile 390
│   ├── 00 Auth Login
│   ├── 01 Game Chat Idle
│   ├── 02 Game Settings Expanded
│   ├── 03 Game Sheet Bottom Sheet
│   ├── 04 Game Pending Roll
│   ├── 05 Combat Player Turn
│   ├── 06 Combat Enemy Turn
│   ├── 07 Combat Victory Loot
│   ├── 08 Character Create Step 1
│   ├── 09 Character Wizard Stats
│   ├── 10 Character Wizard Skills
│   ├── 11 Character Wizard Identity
│   ├── 12 Campaign Create
│   ├── 13 History Summary
│   └── 14 Death Screen
├── 04 Screens - Mobile 320 Stress
├── 05 Prototype Flows
│   ├── First Visit
│   ├── Return Visit
│   ├── Combat Loop
│   ├── Character Sheet
│   ├── History Summary
│   └── Death Flow
└── 06 Developer Handoff
    ├── Selector Contracts
    ├── Token Mapping
    ├── Component States
    └── Export Notes
```

## Frame Annotation Rules

Each screen frame should include:

- Screen name matching `01-screen-inventory.md`.
- Mobile width in the frame name, e.g. `Game Chat Idle / 390`.
- Interaction hotspots with target frame names.
- Component instance names matching `02-component-library.md`.
- Notes for selector contracts from `05-id-and-class-contracts.md`.
- Redlines on 8 px spacing.
- Typography tokens from `04-mobile-layout-spec.md`.

## Component Variant Naming

Use slash-separated names that map to code:

- `Button/Primary/Default`
- `Button/Combat/Attack`
- `ChatMessage/Assistant/Narrative`
- `ChatMessage/User/Input`
- `RollCard/Skill/Success`
- `RollCard/Combat/PlayerHit`
- `SheetPanel/Mobile/Open`
- `CombatPanel/Mobile/PlayerTurn`
- `Wizard/Stats/Valid`
- `DeathScreen/Loaded`

## Handoff Notes Page

Create a final Figma page named `Developer Handoff` that links back to this folder and contains:

- List of non-renamable IDs.
- Token map from Figma variables to CSS variables.
- Screens that need dynamic HTML templates.
- Mobile acceptance checklist.
- Any intentionally future-looking designs not yet implemented.

## Future Updates

When functionality changes later:

1. Add or update only the affected Figma page/component.
2. Update the matching markdown spec file in `/docs/figma-handoff/`.
3. Update `05-id-and-class-contracts.md` if any selectors were added.
4. Update this file only if the Figma organization changes.
