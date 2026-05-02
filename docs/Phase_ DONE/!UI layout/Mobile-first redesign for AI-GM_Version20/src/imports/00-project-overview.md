---
doc: 00-project-overview
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

# AI-GM Figma Mobile Handoff

AI-GM is a Polish-language, text-based fantasy RPG web app where an AI acts as the Game Master. The player logs in, selects or creates a solo campaign, creates a character, and plays through a chat-driven narrative with rolls, slash commands, character sheet inspection, combat, campaign history, and death summaries.

The redesign baseline is mobile-first: 375 px minimum design baseline, 390 px ideal frame, one-thumb interaction, no desktop-only affordances, and a full-viewport app shell. The design should be easy to replace later by treating HTML IDs, JS selectors, and generated template structures as contracts, while making colors, spacing, typography, and visual component styling swappable.

## Audience And Context

Primary users are mobile fantasy RPG players who may play in short sessions, resume ongoing campaigns, and rely on fast narrative input. The UI must keep chat, roll decisions, combat actions, and character status reachable without forcing horizontal scanning.

## Tech Stack Notes For Design

The frontend is vanilla HTML, CSS, and JavaScript. There is no component framework. Static markup lives in `frontend/index.html`; dynamic components are injected through string templates and DOM creation in JS. CSS is split between `frontend/styles.css` and `frontend/css/combat.css`.

HTML IDs and JS-targeted classes are stable API contracts. Do not rename any ID or selector referenced from JavaScript. Future redesigns should swap CSS tokens, CSS rules, and dynamic template internals while preserving selector hooks.

## Design Goals

- Dark fantasy direction: parchment, candlelight, gothic stone, restrained gold accents, readable on dim screens.
- Mobile-first shell: top connection/settings bar, scrollable chat, sticky composer, bottom-sheet character/combat panels.
- Fast touch flow: all interactive targets at least 44 x 44 px, combat buttons at least 48 px high.
- Future upgrade path: document every replaceable surface separately from non-replaceable DOM contracts.
- Polish copy stays Polish; stat abbreviations remain English: STR, DEX, CON, INT, WIS, CHA, LCK.

## Source File Roles

- `frontend/index.html` - static DOM skeleton, overlays, modals, app shell, script load order.
- `frontend/styles.css` - global theme variables, layout, chat, modals, wizard, death screen, slash popup, roll cards.
- `frontend/css/combat.css` - combat panel, combat composer buttons, victory/loot/defeat overlays.
- `frontend/js/ui.js` - DOM references, chat rendering, roll cards, thinking/streaming bubbles, archive toggle, action popup.
- `frontend/js/actions.js` - app state helpers, LLM settings, campaign/character actions, character sheet panel, history summary.
- `frontend/js/app.js` - bootstrap flow, login gate, logout, auth overlay visibility.
- `frontend/js/api.js` - API loading for health, models, campaigns, characters, turns, combat state merge.
- `frontend/js/character_wizard.js` - post-create wizard: stats, skills, identity, finalize flow.
- `frontend/js/combat_panel.js` - combat panel rendering, attack/flee behavior, combat overlays, loot and victory UI.
- `frontend/js/combat_input.js` - combat-aware composer mode and enemy turn triggering.
- `frontend/js/death_screen.js` - campaign death/tombstone overlay and death summary fetch.
- `frontend/js/slash_commands.js` - slash command catalog and autocomplete popup.
- `frontend/js/events.js` - event binding for controls, forms, modals, archetype selection, Enter handling.
- `frontend/js/main.js` - legacy bootstrap entry hook for DOMContentLoaded/login.
- `frontend/js/state.js` - global state shape and feature flags used by the UI.

## Replaceability Model

Preserve `index.html` IDs and dynamic component root classes. Redesign work should target:

- CSS custom properties in `:root`.
- CSS classes for layout and visual treatment.
- Dynamic template strings in `ui.js`, `character_wizard.js`, `combat_panel.js`, and `death_screen.js`.
- Additive wrappers inside existing containers, not renamed containers.

Do not redesign by replacing the whole app with a framework unless a future engineering migration explicitly changes the architecture.
