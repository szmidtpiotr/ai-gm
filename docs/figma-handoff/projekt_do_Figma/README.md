---
doc: README
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

# AI-GM Figma Handoff Documentation

This folder documents the current AI-GM frontend for a mobile-first Figma redesign. It separates replaceable visual surfaces from stable HTML/JS contracts so future UI upgrades can be applied safely.

## Files

- [00-project-overview.md](00-project-overview.md) - product, audience, tech stack, source file roles, replaceability model.
- [01-screen-inventory.md](01-screen-inventory.md) - every screen, overlay, panel, trigger, state flag, and mobile concern.
- [02-component-library.md](02-component-library.md) - reusable UI components, snippets, states, and Figma variant names.
- [03-navigation-flows.md](03-navigation-flows.md) - Mermaid user journeys with trigger elements and JS handlers.
- [04-mobile-layout-spec.md](04-mobile-layout-spec.md) - mobile shell, breakpoints, typography, spacing, tokens, bottom sheet direction.
- [05-id-and-class-contracts.md](05-id-and-class-contracts.md) - non-renamable selectors referenced by JavaScript.
- [06-roll-card-anatomy.md](06-roll-card-anatomy.md) - roll card markers, HTML anatomy, verdict states, mobile sizing.
- [07-combat-panel-spec.md](07-combat-panel-spec.md) - combat panel, composer combat mode, state transitions, mobile combat banner.
- [08-death-screen-spec.md](08-death-screen-spec.md) - campaign death overlay and tombstone card.
- [09-character-wizard-spec.md](09-character-wizard-spec.md) - step-by-step character creation wizard.
- [10-slash-commands-ux.md](10-slash-commands-ux.md) - slash autocomplete behavior and mobile UX.
- [11-accessibility-checklist.md](11-accessibility-checklist.md) - ARIA inventory, contrast, keyboard, motion, and known gaps.
- [12-implementation-guide.md](12-implementation-guide.md) - how to implement a Figma redesign safely.
- [13-figma-file-structure.md](13-figma-file-structure.md) - recommended Figma pages, frames, variants, and update process.
- [CURSOR_PROMPT.md](CURSOR_PROMPT.md) - original generation prompt.
- [HANDOFF.md](HANDOFF.md) - short entrypoint for adaptation package.
- [SPEC_UI_ADAPTATION.md](SPEC_UI_ADAPTATION.md) - implementation constraints and acceptance criteria.
- [SCREEN_INVENTORY.md](SCREEN_INVENTORY.md) - compact inventory of UI states and overlays.
- [DOM_CONTRACT.md](DOM_CONTRACT.md) - selectors that must remain stable.
- [API_INTEGRATION_ASSUMPTIONS.md](API_INTEGRATION_ASSUMPTIONS.md) - frontend API contract reference.
- [TOKEN_MAP.md](TOKEN_MAP.md) - Figma token to CSS variable mapping.
- [IMPLEMENTATION_DIFF_GUIDE.md](IMPLEMENTATION_DIFF_GUIDE.md) - safe rollout sequence and regression checklist.

## Update Rule

For future functionality upgrades, update the smallest matching document first, then update `05-id-and-class-contracts.md` if new JS selectors were added. Keep the mobile frame list and implementation guide aligned with the current frontend.
