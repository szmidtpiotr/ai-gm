---
doc: 07-combat-panel-spec
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

# Combat Panel Spec

Combat UI is partially embedded in the sheet panel and partially in the composer. The redesign should make combat more visible on mobile while preserving current injection points.

## Mount Points

- `#combat-panel-slot` is static in `index.html` inside `#sheet-panel`.
- `#combat-panel-host` is dynamically injected by `CombatPanel.ensureDom()`.
- `#composer-combat-send-slot` is static in the composer and replaces `#send-btn` during player combat turns.

## Dynamic Anatomy

```html
<div id="combat-panel-host" class="combat-panel-host">
  <div class="combat-panel-card">
    <div class="combat-panel-header">
      <h2 class="combat-panel-title">Walka</h2>
      <span class="combat-panel-meta" id="combat-panel-meta">Runda 1 · Tura: Gracz</span>
    </div>
    <div class="combat-engine-turns" id="combat-engine-turns"></div>
    <div class="combat-panel-body" id="combat-panel-body"></div>
    <div class="combat-msg" id="combat-panel-msg"></div>
    <div class="combat-actions" id="combat-panel-actions">...</div>
    <div class="combat-enemy-turn-overlay" id="combat-enemy-overlay" aria-hidden="true">
      <span class="combat-enemy-turn-label">ENEMY TURN</span>
    </div>
  </div>
</div>
```

## Combatant Row

Rendered for player and living enemies:

- Name and initiative.
- HP row with `HP current / max · DEF value`.
- HP bar using `.combat-hp-fill--high`, `.combat-hp-fill--mid`, `.combat-hp-fill--low`.
- Condition badges if present.

## Composer Combat Mode

```html
<div id="composer-combat-send-slot" class="composer-combat-send-slot" aria-hidden="true">
  <button type="button" id="composer-combat-attack" class="combat-input-btn combat-input-btn--attack">Atak</button>
  <button type="button" id="composer-combat-flee" class="combat-input-btn combat-input-btn--flee">Ucieczka</button>
</div>
```

Behavior:

- Player turn: textarea enabled, placeholder `Opisz akcję lub użyj przycisków poniżej...`, Attack/Flee visible.
- Enemy turn: textarea disabled, placeholder `Tura wroga — czekaj...`, combat buttons hidden, enemy turn API triggered.
- Combat ended/null: normal composer restored.

## State Transitions

| Backend state | Panel | Composer | Notes |
|---|---|---|---|
| No active combat | hidden | normal send | `combatInput.syncWithCombat(null)` |
| Active, player turn | visible | Attack/Flee | Enter maps to attack |
| Active, enemy turn | visible with overlay | input disabled | Enemy turn request auto-runs |
| Ended victory | victory overlay | normal | Loot may show before victory overlay |
| Ended fled | fled overlay | normal | Continue hides panel |
| Ended player_dead | defeat overlay/death save | roll prompt possible | Death flow can follow |

## Mobile Design Direction

Current desktop placement under sheet is easy to miss. For mobile:

- Show a sticky combat banner immediately below top bar when combat is active.
- Include enemy name, enemy HP, player HP, and current turn in the collapsed banner.
- Tap/expand to show full initiative log and all combatants.
- Keep `Atak` and `Ucieczka` in the bottom composer area, not hidden in the sheet.
- Hide `#combat-debug-status` in production design; it is debug-only.

## Figma Frames

- `Combat / Player Turn`
- `Combat / Enemy Turn`
- `Combat / Attack Hit`
- `Combat / Attack Miss`
- `Combat / Victory With Loot`
- `Combat / Fled`
- `Combat / Defeat`
- `Combat / Bottom Composer Actions`

## Replaceability Notes

The card internals can be redesigned, but keep:

- `#combat-panel-slot`
- `#combat-panel-host`
- `#combat-panel-body`
- `#combat-engine-turns`
- `#composer-combat-send-slot`
- `#composer-combat-attack`
- `#composer-combat-flee`

Future combat features such as inventory use should add a new button variant rather than overloading Attack/Flee.
