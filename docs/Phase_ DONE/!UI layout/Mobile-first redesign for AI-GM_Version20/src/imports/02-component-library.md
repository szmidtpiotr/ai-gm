---
doc: 02-component-library
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

# Component Library

Design these as Figma components with mobile variants first. Visual styling can change, but selectors and injected root classes must stay stable.

## Buttons

### PrimaryButton

Examples: `#send-btn`, `#character-create-submit`, `#campaign-create-submit`.

```html
<button type="button" id="send-btn">Wyślij</button>
```

Behavior: `#send-btn` calls `window.sendMessage`; campaign and character submit buttons submit their forms. States are default, hover, active, disabled, loading where JS swaps text.

Mobile spec: minimum 48 px height in composer, 44 px elsewhere. Variant names: `Button/Primary/Default`, `Button/Primary/Disabled`, `Button/Primary/Loading`.

### SecondaryButton

Examples: `.secondary`, `#dice-btn`, `#llm-settings-toggle-btn`, close buttons.

```html
<button type="button" class="secondary sheet-inline-btn" id="dice-btn">👤 Karta postaci</button>
```

Behavior: used for sheet toggle, settings, modal close, reset, reconnect. Variant names: `Button/Secondary/Default`, `Button/Secondary/IconLabel`, `Button/Secondary/Compact`.

### DangerButton

Example: `#delete-campaign-btn`.

```html
<button type="button" class="danger" id="delete-campaign-btn">Usuń</button>
```

Behavior: destructive confirm flow in `deleteCampaign()`. Variant names: `Button/Danger/Default`, `Button/Danger/Disabled`.

### CombatButton

Examples: `.combat-input-btn--attack`, `.combat-input-btn--flee`, `.combat-btn--attack`, `.combat-btn--flee`.

```html
<button type="button" id="composer-combat-attack" class="combat-input-btn combat-input-btn--attack">Atak</button>
<button type="button" id="composer-combat-flee" class="combat-input-btn combat-input-btn--flee">Ucieczka</button>
```

Behavior: `combat_input.js` calls `combatPanel._onAttack()` and `combatPanel._onFlee()`. Mobile spec: bottom composer row, 48 px minimum height, clear color contrast.

## Chat Components

### ChatMessage

Rendered by `addMessage()` and `renderTurnsToChat()`.

```html
<div class="message assistant">
  <div class="meta"><div><strong>GM</strong></div><div><span class="route-badge">narrative</span></div></div>
  <div class="message-body"><pre>...</pre></div>
</div>
```

Variants: `ChatMessage/Narrator`, `ChatMessage/Player`, `ChatMessage/System`, `ChatMessage/Error`, `ChatMessage/Memory`, `ChatMessage/OOC`, `ChatMessage/EnemyRoll`.

Mobile spec: max width 100%, font floor 15 px for narrative, metadata can be 11-12 px. The bubble tail radius difference should remain perceptible but not reduce text width.

### ThinkingBubble

Rendered by `showThinkingBubble()`.

```html
<div class="message assistant thinking" id="thinking-bubble">
  <div class="meta">...</div>
  <div class="thinking-wrap">
    <span class="thinking-text">GM myśli</span>
    <span class="typing-dots" aria-hidden="true"><span></span><span></span><span></span></span>
  </div>
</div>
```

Design states: normal, memory, helpme. Add reduced-motion static dots in implementation.

### RollCard

Rendered by `buildRollCardHtml()`, `buildCombatRollCardHtml()`, and `buildGmRollBubbleHtml()`.

Root classes: `.roll-card`, `.roll-card--light`, `.roll-card--success`, `.roll-card--fail`, `.roll-card--neutral`, `.combat-roll-card`, `.roll-card--gm`.

Variant names: `RollCard/Skill/Success`, `RollCard/Skill/Fail`, `RollCard/Attack/Crit`, `RollCard/Attack/Fumble`, `RollCard/Combat/PlayerHit`, `RollCard/Combat/EnemyHit`, `RollCard/Flee`.

## Status And Toolbar

### StatusDot

```html
<span class="status-dot-wrap" title="Backend">
  <span class="status-dot unknown" id="status-backend-dot"></span>
  <span class="status-dot-label">Backend</span>
</span>
```

Behavior: `loadHealth()` toggles `.unknown`, `.ok`, `.warn`, `.error`. Text label must stay visible for accessibility.

### ArchiveToggleBar

```html
<button type="button" id="archive-toggle-btn" class="archive-toggle-btn" aria-pressed="false">
  <span class="archive-toggle-icon" aria-hidden="true">📦</span>
  <span class="archive-toggle-label">Pokaż archiwum</span>
  <span class="archive-toggle-count" id="archive-toggle-count">0</span>
</button>
```

Behavior: toggles `window.state.showArchiveBubbles` and `#chat.archive-hidden`.

## Sheet Components

### StatBlock

Rendered in `renderCharacterSheetPanel()`.

```html
<div class="sheet-stat">
  <span class="sheet-stat-key">STR</span>
  <span class="sheet-stat-val">12</span>
  <span class="sheet-stat-mod">+1</span>
</div>
```

Use compact cards in a 3-column grid on mobile.

### SkillRow

```html
<div class="sheet-skill">
  <span>Athletics</span>
  <strong>2/5</strong>
</div>
```

Future upgrade: replace `2/5` with pips without changing `.sheet-skill`.

## Creation Components

### ArchetypeCard

```html
<button type="button" class="archetype-card" data-archetype="warrior">
  <span class="archetype-title">Warrior</span>
  <span class="archetype-desc">Frontowy wojownik...</span>
</button>
```

Behavior: `events.js` toggles `.selected` and writes `data-archetype` to the form.

### WizardStatRow

Dynamic root: `.wizard-stat-row`; controls use `.wizard-stat-btn` with `data-act="minus"` and `data-act="plus"`.

Mobile spec: single-column list, 44 px +/- targets, running total visible near top.

### WizardSkillRow

Dynamic roots: `.wizard-skill-row`, `.wizard-skill-row--budget`, `.wizard-skill-row--swapped`, `.wizard-skill-row--swapping`.

Behavior: skill level changes and free skill swaps. Design must show level changes separately from swap state.

## Overlays And Panels

### ModalOverlay

Static overlays use `.character-modal-overlay`; inner cards use `.character-modal`.

Examples: `#character-create-overlay`, `#campaign-create-overlay`, `#history-summary-overlay`.

Mobile spec: full-screen modal page, internal scroll, close target at top-right with 44 px tap area.

### ActionPopup

```html
<div id="action-popup" class="action-popup hidden">
  <button type="button" id="popup-roll-btn" class="action-popup__btn">🎲 Rzuć kość</button>
  <div id="action-popup-roll-hint" class="muted"></div>
  <button type="button" id="popup-action-btn" class="action-popup__btn">✍️ Akcja</button>
</div>
```

Future mobile variant should be `ActionSheet/PendingRoll` but keep IDs.

### LLMSettingsPanel

Root: `#llm-controls`. Collapsed state: `.llm-controls--collapsed`. It should behave as an advanced settings accordion, not as primary gameplay UI.

### CombatPanel

Dynamic root: `#combat-panel-host`; card: `.combat-panel-card`.

Subcomponents: `.combat-panel-header`, `.combat-engine-turns`, `.combat-combatant`, `.combat-hp-bar`, `.combat-hp-fill`, `.combat-enemy-turn-overlay`.

Mobile spec: convert into a sticky combat banner or bottom-sheet section without changing `#combat-panel-slot`.

### DeathCard

Dynamic root inside `#campaign-death-inner`.

Subcomponents: `.death-title`, `.death-name`, `.death-reason`, `.death-epitaph`, `.death-secret-block`, `.death-bonds-list`, `.death-new-campaign-btn`.

Design tone: cinematic, dark, emotional, with secret reveal clearly differentiated.

## Future Upgrade Pattern

When adding future features, create a new component section and preserve this structure:

- Contract selectors.
- Source-rendered snippet.
- Behavior owner JS file.
- Mobile spec.
- Figma variant names.
