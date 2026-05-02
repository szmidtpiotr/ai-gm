## TASK: 8B-1 — Enemy Turn Overlay (animation)
Branch: main

### AUDIT RESULTS (pre-verified — no need to re-check)
The following was confirmed before implementation:

1. `current_turn` is used in combat_panel.js at:
   - `render(combatState)` — lines ~307–318 (round/turn meta), ~360–365 (buttons), ~371–374 (overlay toggle)
   - `_fleeEnemyDisplayName()` — line ~231
   - `_currentPlayerAttackTarget()` — line ~613 (`cs.current_turn !== "player"`)
   - `_onAttack()` — line ~759

2. Overlay DOM: id="combat-enemy-overlay", CSS selector `.combat-enemy-turn-overlay`
   Existing styles (lines 231–239): position:absolute, inset:0,
   background:rgba(0,0,0,0.55), display:flex, align-items, justify-content,
   border-radius, z-index:2. NO opacity, NO pointer-events.
   `.combat-enemy-turn-label` (242–248): typography + text-shadow only.

3. No @keyframes in combat.css. Other files have: stream-cursor, typing-bounce,
   bubble-in (styles.css), admin-shimmer (admin_panel/layout.css).

4. Overlay visibility is currently controlled by INLINE STYLE in JS:
   - ensureDom (~line 79): style="display:none;"
   - render (~line 373): this._enemyOverlay.style.display = showEnemy ? "flex" : "none"
   - render (~line 374): aria-hidden toggle

5. Name new classes as `combat-enemy-overlay--fade-in` / `combat-enemy-overlay--fade-out`
   and keyframes as `combatEnemyFadeIn` / `combatEnemyFadeOut` — NO CONFLICT confirmed.

### CRITICAL IMPLEMENTATION NOTE
The overlay currently uses `display:none` / `display:flex` directly.
Setting `display:none` immediately KILLS the fade-out animation (element removed from layout).
You MUST change the hide logic as follows:

  OLD: this._enemyOverlay.style.display = showEnemy ? "flex" : "none";

  NEW:
    Show: remove fade-out class, add fade-in class, set display:flex
    Hide: swap to fade-out class, wait for animationend (or setTimeout 300ms),
          THEN set display:none and remove fade-out class

Do NOT use `visibility` + `opacity` as a replacement — keep display:none as
the final hidden state to preserve existing layout behavior.

### Implementation
Files: frontend/js/combat_panel.js, frontend/css/combat.css

CSS — add to combat.css:

  @keyframes combatEnemyFadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
  }
  @keyframes combatEnemyFadeOut {
    from { opacity: 1; }
    to   { opacity: 0; }
  }
  @keyframes combatEnemyPulse {
    0%, 100% { transform: scale(1); }
    50%       { transform: scale(1.04); }
  }

  .combat-enemy-turn-overlay.combat-enemy-overlay--fade-in {
    animation: combatEnemyFadeIn 0.3s ease forwards;
  }
  .combat-enemy-turn-overlay.combat-enemy-overlay--fade-out {
    animation: combatEnemyFadeOut 0.3s ease forwards;
  }
  .combat-enemy-turn-overlay.combat-enemy-overlay--fade-in .combat-enemy-turn-label {
    animation: combatEnemyPulse 1.2s ease-in-out infinite;
  }

JS — update render() in combat_panel.js (~line 371–374):
  Replace the single `style.display` line with:

  _showEnemyOverlay() {
    const el = this._enemyOverlay;
    el.classList.remove('combat-enemy-overlay--fade-out');
    el.style.display = 'flex';
    el.setAttribute('aria-hidden', 'false');
    // force reflow so animation triggers even on re-show
    void el.offsetWidth;
    el.classList.add('combat-enemy-overlay--fade-in');
  }

  _hideEnemyOverlay() {
    const el = this._enemyOverlay;
    el.classList.remove('combat-enemy-overlay--fade-in');
    el.classList.add('combat-enemy-overlay--fade-out');
    el.setAttribute('aria-hidden', 'true');
    setTimeout(() => {
      el.classList.remove('combat-enemy-overlay--fade-out');
      el.style.display = 'none';
    }, 300);
  }

  In render(), replace lines ~371–374 with:
    if (showEnemy) { this._showEnemyOverlay(); }
    else           { this._hideEnemyOverlay(); }

- The overlay remains INFORMATIONAL ONLY.
  Buttons stay disabled via existing _busy / current_turn logic — NOT via the overlay.

### Constraints
- Do NOT touch backend/*
- Do NOT touch system_prompt.txt
- Do NOT touch actions.js, app.js, tests/*
- After change: run python3 -m pytest → must be 102 passed, 0 failed




==============AFTER REPORT ================

Zaimplementowano **8B-1** wg [`8B-1 — Enemy Turn Overlay.txt`](docs/Phase%208B%20-%20Combat%20Frontend/8B-1%20%E2%80%94%20Enemy%20Turn%20Overlay.txt).

### Zmiany

**`frontend/css/combat.css`**
- `@keyframes combatEnemyFadeIn` / `combatEnemyFadeOut` (opacity 0↔1, 0,3 s).
- `@keyframes combatEnemyPulse` (delikatna skala 1 → 1,04 na etykiecie).
- Klasy modyfikujące: `.combat-enemy-overlay--fade-in`, `.combat-enemy-overlay--fade-out` + pulse na `.combat-enemy-turn-label` w stanie fade-in.

**`frontend/js/combat_panel.js`**
- `this._enemyOverlayHideTimer` + **`_showEnemyOverlay()`** / **`_hideEnemyOverlay()`** (anulowanie timera przy ponownym pokazaniu, `setTimeout(300)` przed `display: none` i usunięciem klasy fade-out).
- W **`render()`** zamiast jednej linii `style.display` jest `showEnemy ? _showEnemyOverlay() : _hideEnemyOverlay()`.
- Przy **`combatState === null`** natychmiastowe schowanie overlay (clear timera, usunięcie klas, `display: none`), żeby nie zostawał po zniknięciu stanu walki.

Przyciski dalej tylko z istniejącej logiki `_busy` / `playerTurn` — overlay nadal tylko informacyjny.

### Testy
Na **192.168.1.61**: `python3 -m pytest -q` → **102 passed** (1 ostrzeżenie Starlette jak wcześniej).

### Docker
**Nie trzeba** restartować ani przebudowywać Dockera po samej zmianie w JS/CSS — wystarczy odświeżyć front w przeglądarce (ew. twardy refresh). Jeśli statyczne pliki serwuje kontener z volumem, wystarczy odświeżenie; przy buildzie obrazu z wbitym frontem — wtedy dopiero rebuild obrazu.