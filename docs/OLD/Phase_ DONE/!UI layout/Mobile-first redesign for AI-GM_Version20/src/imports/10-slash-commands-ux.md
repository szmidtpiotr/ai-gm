---
doc: 10-slash-commands-ux
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

# Slash Commands UX

Slash command autocomplete is frontend-only and attached to `#input`. It appears when the user types `/` at the start of a line/word.

## Trigger And Position

- Trigger: typing `/` in `#input`.
- Context: slash must be at line/word start and the token before cursor must not contain whitespace.
- Popup: `#slash-popup.slash-popup`.
- Position: fixed, same width as input, above the input using `bottom = window.innerHeight - input.top + 8`.

## Current Commands

| Command | Description |
|---|---|
| `/help` | Show available commands list |
| `/sheet` | Display your current character sheet |
| `/mem [pytanie]` | Pytanie o przeszłość z podsumowań — bez wpływu na narrację (żółte dymki) |
| `/helpme [pytanie]` | Doradca OOC — wskazówki bez zmiany fabuły (czerwone dymki); nie wpływa na kontekst narracji |
| `/roll` | Roll d20 + modifier for the last GM-requested roll |
| `/name <new name>` | Rename your character |
| `/history` | Show the last 10 turns of the session |
| `/export` | Export the full session to a text file on the server |
| `/atak` | Silnik walki: sync or start combat with enemy keys |
| `/search` | Przeszukaj zabitą postać lub lokację |

The list can be overridden by `GET /api/mechanics/slash-commands`, so designs should support admin-edited descriptions.

## Keyboard Behavior

- Arrow Down/Up changes highlighted item.
- Enter inserts highlighted command when popup is open.
- Tab inserts highlighted command.
- Escape closes popup.
- Click/tap inserts command.

## Component Anatomy

```html
<div id="slash-popup" class="slash-popup" role="listbox" aria-hidden="true">
  <ul class="slash-popup-list">
    <li class="slash-popup-item slash-popup-item--active" role="option" aria-selected="true">
      <span class="slash-popup-cmd">/mem [pytanie]</span>
      <span class="slash-popup-desc">Pytanie o przeszłość...</span>
    </li>
  </ul>
</div>
```

## Mobile Spec

- Popup appears above keyboard/composer.
- Max visible items: 4 on mobile.
- Each item minimum 44 px height.
- Command label should remain readable even if description wraps.
- Active item must be visible without relying on hover.
- If future composer becomes fixed/sticky, reposition on `visualViewport` resize.

## Special Command UX

- `/helpme` should display an OOC indicator near the composer or on the message bubble. Current chat bubble uses `[POMOC — poza fabułą]`.
- `/mem` uses yellow memory bubbles and should be visually distinct from narrative.
- `/sheet` opens or returns a character sheet response; pair it with the visible `Karta postaci` button.
- `/atak` connects to combat; in mobile UI, prefer explicit combat affordances once combat is active.
- `/search` is disabled in active combat and should show a clear error.

## Replaceability Notes

Preserve `#slash-popup` and child classes. The visual popup can be redesigned as a mobile command sheet later, but it must still support keyboard navigation and `role="listbox"` semantics.
