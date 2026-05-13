## TASK: 8B-5 — Mobile Responsive Combat Panel
Branch: main

### CONTEXT (from 8B-1 + 8B-2 + 8B-3 — already known)
- frontend/css/combat.css already contains (DO NOT modify):
  - @keyframes combatEnemyFadeIn/Out/Pulse + overlay classes (8B-1)
  - .combat-hp-fill transition + --high/--mid/--low color classes (8B-2)
  - @keyframes combatFlashHit/Crit/Fumble + .combat-flash-* classes (8B-3)
- frontend/js/combat_panel.js: _showEnemyOverlay(), _hideEnemyOverlay(), _flashElement()
- Tests: 102 passed (baseline confirmed)
- No JS changes in this task — CSS only.

### BEFORE YOU WRITE ANY CODE — answer these questions first:
1. Read frontend/css/combat.css — does a `@media (max-width: 480px)` block already
   exist? If yes, show its full contents.
2. What is the current width definition of `#combat-panel` (or `.combat-panel-card`)?
   Note: stable panel ref in JS is `this._card` with class `.combat-panel-card` —
   confirm which selector is used in CSS for the main panel container.
3. Do `.combat-btn` elements already have any `min-height`, `padding`, or `height` set?
4. Does `.combat-hp-fill` already have `height` or `min-height`?
   Note: after 8B-2 it has `transition: width 0.4s ease, background 0.2s ease` —
   confirm if height/min-height was also present before or not.
5. Does `#combat-engine-turns` have any existing `max-height` or `overflow` rule?
6. Would adding the media query below conflict with any existing responsive rules,
   flexbox/grid layout, or the keyframes/classes added in 8B-1/2/3?
   State: NO CONFLICT or CONFLICT (explain).

Only after answering all 6 — implement the following:

### Implementation
File: frontend/css/combat.css ONLY — NO JS changes

Add at the END of the file (after all existing keyframes and classes):

@media (max-width: 480px) {
  #combat-panel            { width: 100%; box-sizing: border-box; }
  .combat-panel-card       { width: 100%; box-sizing: border-box; }
  .combat-btn              { min-height: 48px; }
  .combat-hp-fill          { min-height: 8px; }
  #combat-engine-turns     { max-height: 150px; overflow-y: auto; }
}

Adjust selector names based on audit answers (step 2 — use whichever panel
selector actually exists in CSS). If both `#combat-panel` and `.combat-panel-card`
exist — include both. Remove the one that doesn't exist.

### Constraints
- Do NOT touch backend/*
- Do NOT touch system_prompt.txt
- Do NOT touch any JS files
- Do NOT touch tests/*
- Do NOT modify keyframes or classes added in 8B-1, 8B-2, 8B-3
- After change: run python3 -m pytest → must be 102 passed, 0 failed