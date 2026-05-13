---
doc: 11-accessibility-checklist
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

# Accessibility Checklist

Accessibility is part of the design contract. Do not trade it away for fantasy styling.

## Current Attributes To Preserve Or Improve

| Element | Current attributes | Preserve? | Notes |
|---|---|---|---|
| `<html>` | `lang="pl"` | Yes | UI language is Polish |
| `#campaign-death-screen` | `hidden`, `aria-hidden`, `role="dialog"`, `aria-modal="true"`, `aria-labelledby="death-title-heading"` | Yes | Add focus management in future implementation |
| `#campaign-death-backdrop` | `aria-hidden="true"` | Yes | Backdrop should not be focused |
| `#campaign-death-close-btn` | `aria-label="Zamknij"` | Yes | 44 px target |
| `#archive-toggle-btn` | `aria-pressed="false"` | Yes | Update pressed state remains required |
| `.archive-toggle-icon` | `aria-hidden="true"` | Yes | Icon has text label next to it |
| `#composer-combat-send-slot` | `aria-hidden="true"` | Yes | Toggled by combat input |
| `#combat-panel-slot` | `aria-hidden="true"` | Yes | Toggled during active combat |
| `#combat-debug-status` | `aria-live="polite"` | Debug only | Hide in production design |
| `#auth-overlay` | `aria-hidden="false"` | Yes | Should be `role="dialog"` in future |
| `#character-create-panel` | `role="dialog"`, `aria-modal="true"`, `aria-labelledby` | Yes | Needs focus trap |
| `#character-create-close` | `aria-label="Zamknij"` | Yes | Disabled/hidden during blocking steps |
| `#character-create-step-indicator` | `aria-live="polite"` | Yes | Announces step changes |
| `#history-summary-overlay` | `aria-hidden="true"` | Yes | Toggle correctly |
| History modal section | `role="dialog"`, `aria-modal="true"`, `aria-labelledby` | Yes | Needs focus trap |
| `#campaign-create-overlay` | `aria-hidden="true"` | Yes | Toggle correctly |
| Campaign modal section | `role="dialog"`, `aria-modal="true"`, `aria-labelledby` | Yes | Needs focus trap |
| `#slash-popup` | `role="listbox"`, `aria-hidden` | Yes | Options use `role="option"` |

## Required Design Checks

- Text contrast on dark backgrounds: WCAG AA 4.5:1 for body text.
- Large display text: at least 3:1.
- Do not encode status only by color; keep labels for Backend, Ollama, Loki, verdicts, and combat state.
- All interactive targets: minimum 44 x 44 px.
- Composer input font: at least 16 px on mobile to avoid unwanted iOS zoom.
- Keyboard tab order follows visual reading order.
- Focus states are visible and not color-only.
- Modal focus should enter the dialog and return to triggering control on close in future implementation.
- Motion must respect `prefers-reduced-motion`.
- Roll verdict text must remain visible; icon-only verdicts are not acceptable.

## Known Gaps To Address During Implementation

- Focus trapping is not implemented for modals.
- `#auth-overlay` lacks explicit `role="dialog"` and `aria-modal`.
- Some buttons use emoji as leading icons; keep adjacent text labels.
- Combat enemy overlay uses English `ENEMY TURN`; consider Polish visible text or add hidden localized label.
- Inline style and hidden display toggles are used heavily; ensure redesigned states keep `aria-hidden` in sync.

## Mobile Screen Reader Notes

- Bottom sheets should announce as dialogs or complementary panels.
- Sticky composer should not trap focus.
- Slash popup should work with keyboard and screen reader selection.
- Loading states like `GM myśli`, `Ładowanie…`, and wizard generation should be announced politely.

## Acceptance Checklist

- Login can be completed by keyboard.
- Campaign and character modal can be opened, completed, and dismissed by keyboard.
- Chat send works with Enter and button.
- Sheet open state is discoverable and closable.
- Combat Attack/Flee are reachable and disabled state is understandable.
- Death screen close and start-new actions are reachable.
