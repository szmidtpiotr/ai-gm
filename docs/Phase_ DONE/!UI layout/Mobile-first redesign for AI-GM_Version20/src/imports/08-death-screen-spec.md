---
doc: 08-death-screen-spec
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

# Death Screen Spec

The death screen is a full-screen cinematic overlay shown when campaign turns return HTTP 410 or death summary is requested after a terminal state.

## Static Container

```html
<div id="campaign-death-screen" class="campaign-death-screen" hidden aria-hidden="true" role="dialog" aria-modal="true" aria-labelledby="death-title-heading">
  <div class="campaign-death-backdrop" id="campaign-death-backdrop" aria-hidden="true"></div>
  <div class="campaign-death-dialog">
    <button type="button" class="campaign-death-close" id="campaign-death-close-btn" aria-label="Zamknij">×</button>
    <div id="campaign-death-inner" class="campaign-death-card"></div>
  </div>
</div>
```

Visibility:

- `body.campaign-death-active` controls display.
- `hidden` and `aria-hidden` are toggled by `showCampaignDeathScreen()` and `dismissCampaignDeathScreen()`.

## Dynamic Card Anatomy

Rendered by `buildTombstoneHtml(d)` in `death_screen.js`.

```html
<div class="death-tomb-inner">
  <div class="death-cross" aria-hidden="true">✝</div>
  <h1 class="death-title" id="death-title-heading">In Memoriam</h1>
  <p class="death-name">Character Name</p>
  <p class="death-meta">Class — <span class="muted">died at</span> date</p>
  <p class="death-reason">Cause of death</p>
  <blockquote class="death-epitaph">"Epitaph"</blockquote>
  <div class="death-secret-block">
    <div class="death-secret-label">🔒 Secret revealed:</div>
    <p class="death-secret-text">...</p>
  </div>
  <div class="death-bonds-block">
    <div class="death-bonds-label">Bonds at death:</div>
    <ul class="death-bonds-list">...</ul>
  </div>
  <button type="button" class="death-new-campaign-btn" id="death-start-new-btn">Start New Campaign</button>
</div>
```

## Interactions

- `#campaign-death-close-btn`: dismiss overlay.
- `#campaign-death-backdrop`: dismiss overlay.
- `Escape`: dismiss overlay.
- `#death-start-new-btn`: dismiss, open `#campaign-create-overlay`, reload campaigns.

## Design Tone

Use a dark, cinematic treatment: blackened parchment, candlelight gold, stone border, deep red accents. The card should feel like a tombstone or memorial, not an error page.

The secret reveal is the emotional centerpiece. Give `.death-secret-block` a locked/revealed treatment, but keep the text readable and copyable.

## Mobile Spec

- Full-bleed overlay.
- Dialog width: `calc(100% - 32px)` with internal scroll.
- Close button fixed in top-right of card, 44 x 44 px target.
- Main CTA at least 48 px height.
- Optional future gesture: swipe down to dismiss, but keep button and Escape.

## Figma Variants

- `DeathScreen/Loading`
- `DeathScreen/Loaded`
- `DeathScreen/Error`
- `DeathCard/WithBonds`
- `DeathCard/NoBonds`

## Replaceability Notes

Preserve `#campaign-death-screen`, `#campaign-death-inner`, `#campaign-death-close-btn`, `#campaign-death-backdrop`, and `#death-start-new-btn`. The internal layout can be replaced by editing `buildTombstoneHtml()`.
