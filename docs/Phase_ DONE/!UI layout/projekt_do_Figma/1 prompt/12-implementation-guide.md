---
doc: 12-implementation-guide
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

# Implementation Guide

This handoff is designed so the visual layer can be replaced later without breaking gameplay.

## What To Replace

Safe to replace:

- CSS tokens and visual rules in `frontend/styles.css`.
- Combat visual rules in `frontend/css/combat.css`.
- Inner HTML template strings in `frontend/js/ui.js`, `frontend/js/combat_panel.js`, `frontend/js/character_wizard.js`, and `frontend/js/death_screen.js`.
- Additive wrappers inside existing static containers.

Do not replace without an engineering migration:

- Script load order in `index.html`.
- IDs listed in `05-id-and-class-contracts.md`.
- Marker strings: `__AI_GM_ROLL_V1__`, `__AI_GM_COMBAT_ROLL_V1__`, `__AI_GM_GM_ROLL_V1__`.
- API assumptions in `api.js`, `actions.js`, and `combat_panel.js`.

## Token Export

Map Figma variables to CSS custom properties in `:root`. Recommended naming:

```css
:root {
  --color-surface-app: #0f0b09;
  --color-surface-panel: #18120e;
  --color-text-primary: #f2eadc;
  --color-text-muted: #b4a58d;
  --color-accent-primary: #b77a2b;
  --radius-default: 12px;
  --space-default-gap: 12px;
}
```

During migration, keep current names as aliases until all CSS is updated:

```css
:root {
  --bg: var(--color-surface-app);
  --panel: var(--color-surface-panel);
  --text: var(--color-text-primary);
  --muted: var(--color-text-muted);
  --accent: var(--color-accent-primary);
}
```

## Mobile Bottom Sheet Pattern

Apply to `#sheet-panel` without renaming it:

```css
@media (max-width: 640px) {
  #sheet-panel {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    height: min(80dvh, 680px);
    transform: translateY(100%);
    transition: transform 180ms ease;
  }

  .play-area.sheet-open #sheet-panel {
    transform: translateY(0);
  }
}
```

Add body/backdrop locking only after testing scroll behavior.

## Keyboard Avoidance

Use `visualViewport` for composer layout when the keyboard opens:

```js
if (window.visualViewport) {
  window.visualViewport.addEventListener("resize", () => {
    document.documentElement.style.setProperty(
      "--vvh",
      `${window.visualViewport.height}px`
    );
  });
}
```

Then use CSS to keep chat and composer inside the available height.

## Combat Integration

The combat panel must mount into `#combat-panel-slot`. The composer controls must stay in `#composer-combat-send-slot`. If redesign moves combat visually to a sticky banner, the JS can still use the same host and CSS can reposition it.

## Roll Card Integration

Roll cards are rendered as HTML strings. Figma handoff should provide HTML-ready anatomy, not static screenshots. Update:

- `buildRollCardHtml()`
- `buildCombatRollCardHtml()`
- `buildGmRollBubbleHtml()`

After changing card classes, update `06-roll-card-anatomy.md` and `05-id-and-class-contracts.md`.

## Test Checklist After CSS Swap

- Login and logout.
- Create campaign.
- Create character through all wizard steps.
- Send normal chat message.
- Receive streaming message without bubble jitter.
- Trigger pending roll and choose `Rzuć kość`.
- Toggle archive.
- Open/close sheet.
- Open history summary and regenerate as owner.
- Start combat with `/atak bandit`.
- Attack from button.
- Attack with Enter during player combat turn.
- Flee from button.
- Enemy turn disables composer.
- Victory/loot overlay.
- Defeat/death screen.
- Slash popup keyboard navigation.
- 320 px no horizontal scroll.
- 390 px keyboard-open composer usability.
- Reduced motion smoke test.

## Branch Strategy

Recommended implementation branch: `phase-8b-frontend-mobile` from the current working branch, then PR to `main` after review. Do not push directly to `main`.

## Docker / Rebuild Note

Documentation-only changes do not require Docker restart or rebuild. CSS/JS/frontend HTML changes may require browser refresh and static asset cache busting; backend Python/API changes require service restart or container rebuild depending on deployment.
