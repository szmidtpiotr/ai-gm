---
doc: 04-mobile-layout-spec
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

# Mobile Layout Spec

The redesign must prioritize mobile play. Desktop can stretch the same model later; mobile must not be a compressed desktop layout.

## Breakpoints

| Name | Width | Notes |
|---|---:|---|
| Mobile S | 320 px | Minimum supported, stress-test labels and composer actions |
| Mobile M | 375 px | Baseline |
| Mobile L | 390-430 px | Ideal target for iPhone-size frames |
| Tablet | 768 px | Optional stretch layout |
| Desktop | 900 px+ | Current code opens sheet beside chat |

## Mobile App Shell

```text
100dvh app shell
┌─────────────────────────┐
│ Top bar: Settings, Logout, status dots
│ Optional LLM panel, collapsed by default
├─────────────────────────┤
│ Combat sticky banner when active
├─────────────────────────┤
│ Chat feed, overflow-y auto, bottom anchored
├─────────────────────────┤
│ Composer: textarea + action buttons
│ safe-area bottom padding
└─────────────────────────┘
```

Implementation target:

- `#game-app` should become a mobile shell, not a centered max-width page.
- `.chat` should be the primary scroll container.
- `.composer` should be sticky/fixed at bottom with `padding-bottom: max(12px, env(safe-area-inset-bottom))`.
- Keyboard avoidance should use `visualViewport` when implemented.

## Panels On Mobile

### Sheet Panel

Use `#sheet-panel` as an 80% height bottom sheet:

- Closed: `transform: translateY(100%)`, `aria-hidden=true`.
- Open: `transform: translateY(0)`, `aria-hidden=false`.
- Add visual drag handle inside CSS, not by renaming `#sheet-panel`.
- Keep `#sheet-panel-body` as content root.

### Combat Panel

Use `#combat-panel-slot` as the integration point, but present active combat as:

- Sticky top banner for enemy name, enemy HP, current turn.
- Expandable section for turn log.
- Composer bottom actions for `Atak` and `Ucieczka`.

### Modals

All `.character-modal-overlay` screens should become full-screen mobile pages with internal scroll and a persistent 44 px close target, except blocking character wizard steps where close is intentionally hidden.

## Touch Targets

- All buttons, selectable rows, archetype cards, slash items: minimum 44 x 44 px.
- Composer combat buttons: minimum 48 px height.
- Wizard +/- controls: 44 x 44 px.
- Close buttons: 44 x 44 px even if icon appears smaller.
- Slash popup rows: 44 px minimum height, max 4 visible on mobile.

## Typography

| Token | Size | Weight | Usage |
|---|---:|---:|---|
| `--text-xs` | 11 px | 400 | Debug, metadata, compact labels |
| `--text-sm` | 13 px | 400 | Sheet labels, status labels |
| `--text-base` | 15 px | 400 | Chat narrative, modal body |
| `--text-md` | 16 px | 500 | Composer input, primary buttons |
| `--text-lg` | 18 px | 600 | Wizard and modal headings |
| `--text-xl` | 22 px | 700 | Death screen title |

Keep narrative text readable before decorative styling. Do not use gothic display fonts for body text.

## Spacing

Use an 8 px grid with allowed increments: `4`, `8`, `12`, `16`, `24`, `32`, `48`, `64`.

Mobile defaults:

- App padding: 12 px.
- Chat gap: 12 px.
- Bubble padding: 12-16 px.
- Modal padding: 16 px.
- Sheet inner padding: 12-16 px.

## Current CSS Variables

| Current variable | Current value | Suggested semantic alias |
|---|---|---|
| `--bg` | `#f5f0e8` | `color/surface/app` |
| `--panel` | `#fffdf8` | `color/surface/panel` |
| `--panel-2` | `#f0ebe0` | `color/surface/panel-muted` |
| `--text` | `#1a1410` | `color/text/primary` |
| `--muted` | `#6b6050` | `color/text/muted` |
| `--accent` | `#7c4f1e` | `color/accent/primary` |
| `--accent-light` | `#c8944a` | `color/accent/highlight` |
| `--danger` | `#b91c1c` | `color/status/danger` |
| `--warning` | `#b45309` | `color/status/warning` |
| `--ok` | `#15803d` | `color/status/success` |
| `--border` | `#d6cfc0` | `color/border/default` |
| `--user` | `#1e3a5f` | `color/chat/player` |
| `--assistant` | `#2d4a2d` | `color/chat/gm` |
| `--system` | `#5a5040` | `color/chat/system` |
| `--radius` | `12px` | `radius/default` |
| `--gap` | `12px` | `space/default-gap` |
| `--shadow` | `0 4px 16px rgba(80, 50, 20, 0.10)` | `shadow/panel` |
| `--bubble-max` | `min(78%, 860px)` | `size/chat/bubble-max` |

## Variables Referenced As Fallbacks

Some CSS uses fallback variable names that are not declared in `:root`: `--primary`, `--accent-dark`, `--surface`, `--color-surface-2`, `--color-border`, `--color-surface-offset`, `--color-surface`. Future token cleanup can either define these aliases or replace them with the canonical variables above.

## Mobile Acceptance Criteria

- No horizontal scrolling at 320 px.
- Primary gameplay path fits one hand: chat read, type, send, sheet, roll, attack/flee.
- Settings are collapsed by default and do not dominate the first viewport.
- Combat state remains visible while the player types.
- Sheet and modals use internal scrolling, not body scroll leaks.
