## TASK: 8B-3 — Attack Result Flash
Branch: main

### CONTEXT (from 8B-1 + 8B-2 — already known)
- frontend/css/combat.css has: combatEnemyFadeIn/Out/Pulse keyframes, overlay classes,
  .combat-hp-fill transition + --high/--mid/--low color classes
- frontend/js/combat_panel.js has: _showEnemyOverlay(), _hideEnemyOverlay(),
  this._enemyOverlayHideTimer, updated render() overlay logic
- HP bar width set inline via rowHtml in render(), tier class toggled via hpTier(pct)
- Tests: 102 passed (baseline confirmed)

### BEFORE YOU WRITE ANY CODE — answer these questions first:
1. Read frontend/js/combat_panel.js — find the function that handles attack result
   (reads `hit`, `nat_roll`, or similar fields from backend response).
   Show the exact function name, line numbers, and what fields it reads.
2. Is there already any `.flash-*` class, `@keyframes flash`, or `setTimeout` cleanup
   logic in combat_panel.js or combat.css? List everything found.
   (Note: _enemyOverlayHideTimer setTimeout from 8B-1 is already there — that is fine,
   just confirm no flash-specific logic exists yet.)
3. What is the exact DOM element representing the enemy combatant? What is its
   id or class? Is it stable across re-renders or re-created each turn via innerHTML?
   If re-created — the flash class will be lost immediately; flag this as CONFLICT.
4. What is the DOM id/class of the main combat panel? Confirm it exists and is stable
   (not re-created by render()).
5. Would adding temporary CSS classes via setTimeout conflict with:
   a) the overlay fade logic added in 8B-1 (setTimeout 300ms)?
   b) victory/dead/fled overlay class toggling?
   State: NO CONFLICT or CONFLICT (explain each).

Only after answering all 5 — implement the following:

### Implementation
Files: frontend/js/combat_panel.js, frontend/css/combat.css

CSS — add to combat.css (after existing keyframes from 8B-1):

  @keyframes combatFlashHit {
    0%   { background-color: rgba(244, 67,  54,  0.45); }
    100% { background-color: transparent; }
  }
  @keyframes combatFlashCrit {
    0%   { background-color: rgba(255, 193,  7,  0.40); }
    100% { background-color: transparent; }
  }
  @keyframes combatFlashFumble {
    0%   { background-color: rgba(156,  39, 176, 0.40); }
    100% { background-color: transparent; }
  }

  .combat-flash-hit    { animation: combatFlashHit    0.3s ease forwards; }
  .combat-flash-crit   { animation: combatFlashCrit   0.4s ease forwards; }
  .combat-flash-fumble { animation: combatFlashFumble 0.4s ease forwards; }

Keyframe naming: use `combatFlash*` prefix (not generic `flash`) to avoid
conflict with any global utility classes in styles.css.

JS — in the function that handles attack result:

  Trigger conditions (read from attack result fields):
  - nat_roll === 20             → combatFlashPanel('combat-flash-crit',   400)
  - nat_roll === 1              → combatFlashPanel('combat-flash-fumble', 400)
  - hit === true, nat_roll 2–19 → combatFlashEnemy('combat-flash-hit',    300)
  - hit === false               → NO flash (only update message)

  Helper pattern (add as private methods or inline — your choice):

  _flashElement(el, cls, ms) {
    if (!el) return;
    el.classList.remove(cls);       // reset if already running
    void el.offsetWidth;            // force reflow
    el.classList.add(cls);
    setTimeout(() => el.classList.remove(cls), ms);
  }

  Usage:
    // crit/fumble — flash the whole panel
    this._flashElement(this._panel, 'combat-flash-crit', 400);

    // hit — flash enemy row element (use whatever stable ref exists)
    this._flashElement(enemyEl, 'combat-flash-hit', 300);

### CRITICAL — if enemy element is re-created by innerHTML in render():
  Do NOT flash a stale DOM reference. Instead, flash the panel element
  for hits as well (same as crit/fumble), using a different color.
  Only use the enemy element directly if it is a stable, persistent node.
  Flag your decision in a one-line comment in the code.

### Constraints
- Do NOT touch backend/*
- Do NOT touch system_prompt.txt
- Do NOT touch actions.js, app.js, tests/*
- Do NOT modify keyframes/overlay logic from 8B-1 or HP bar from 8B-2
- After change: run python3 -m pytest → must be 102 passed, 0 failed



==============AFTER REPORT====================
Zaimportowałem i wdrożyłem `8B-3 - Flash po ataku` — **brak blockerów**.

### Krótki audit (5 punktów z pliku)
1. Obsługa wyniku ataku jest w `CombatPanel._onAttack()` w `frontend/js/combat_panel.js`; czyta m.in. `data.hit`, `data.player_nat1`, `data.dodged`, `data.damage`, plus lokalny `d20` (`raw_d20`).
2. Flash-specific logiki wcześniej nie było (`.flash-*`, `combatFlash*`, cleanup timerów dla flash). Był tylko timer overlay z 8B-1 (`_enemyOverlayHideTimer`).
3. Enemy combatant row to `.combat-combatant` budowany przez `rowHtml` i wstrzykiwany przez `this._bodyEl.innerHTML = ...` — **re-created na każdym renderze**.
4. Stabilny panel główny to `this._card` (`.combat-panel-card`) tworzony w `ensureDom()` i nieodtwarzany przy każdym `render()`.
5. Konflikty:  
   - z 8B-1 overlay timerem: **NO CONFLICT** (oddzielne klasy/timery),  
   - z victory/dead/fled overlayami: **NO CONFLICT** (flash dotyczy `this._card`, a end/loot to osobne warstwy `_endLayer/_lootLayer`).

### Implementacja

#### `frontend/css/combat.css`
Dodałem:
- `@keyframes combatFlashHit`
- `@keyframes combatFlashCrit`
- `@keyframes combatFlashFumble`
- klasy:
  - `.combat-flash-hit`
  - `.combat-flash-crit`
  - `.combat-flash-fumble`

#### `frontend/js/combat_panel.js`
Dodałem:
- `this._flashTimers = new Map()`
- helper `_flashElement(el, cls, ms)` z resetem klasy + cleanup `setTimeout`
- w `_onAttack()`:
  - `natRoll === 20` -> `combat-flash-crit` (400ms, panel)
  - `natRoll === 1` -> `combat-flash-fumble` (400ms, panel)
  - `data.hit` dla 2–19 -> `combat-flash-hit` (300ms, panel)
  - miss -> brak flash

oraz komentarz (zgodnie z CRITICAL): enemy row jest przebudowywany przez `innerHTML`, więc flash idzie w stabilny `this._card`.

### Testy
Na `.61`:
- `python3 -m pytest -q --tb=no` -> **102 passed, 1 warning**

### Docker
Po tej zmianie **nie trzeba** restartu/rebuilda Dockera (frontend JS/CSS). Wystarczy odświeżenie przeglądarki (najlepiej hard refresh).