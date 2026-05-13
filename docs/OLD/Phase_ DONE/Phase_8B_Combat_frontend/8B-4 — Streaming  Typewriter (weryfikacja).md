## TASK: 8B-4 — Streaming Narration / Typewriter (verify & fix if needed)
Branch: main

### CONTEXT (from 8B-1 + 8B-2 + 8B-3 — already known)
- frontend/css/combat.css: combatEnemyFadeIn/Out/Pulse keyframes, overlay classes,
  .combat-hp-fill transition + color classes, combatFlashHit/Crit/Fumble keyframes + classes
- frontend/js/combat_panel.js:
  - _showEnemyOverlay() / _hideEnemyOverlay() + _enemyOverlayHideTimer
  - _flashElement(el, cls, ms) + this._flashTimers Map
  - Flash triggers in _onAttack() (nat20/nat1/hit all flash this._card)
  - Stable panel ref: this._card (.combat-panel-card, created in ensureDom, not re-rendered)
  - Enemy row: re-created via innerHTML on every render()
- Tests: 102 passed (baseline confirmed)

### BEFORE YOU WRITE ANY CODE — answer these questions first:
1. Read frontend/js/ui.js — find the SSE event handler. Show me:
   a) Where `this._busy = true` is set — is it BEFORE the fetch/SSE call or inside it?
   b) Where `this._busy = false` is reset — is it on [DONE] token, on stream close,
      or somewhere earlier (e.g. on first chunk)?
   c) Where `_combatVictoryUiPending` is checked and `showVictoryAfterNarration()` called —
      is it inside the [DONE] handler or outside?
2. Read frontend/js/combat_panel.js — what is the exact condition that disables
   the Attack and Flee buttons? Is `_busy` checked, `current_turn`, or both?
   Show the exact line(s) from render() or wherever buttons are built.
3. After SSE [DONE] arrives — is `render(combatState)` or any panel update triggered?
   If yes — what function and where? If no — could buttons stay disabled after narration ends?
4. Based on 1–3: is the implementation CORRECT?
   - busy=true set before stream starts? ✔/✖
   - busy=false only on [DONE]? ✔/✖
   - victory UI deferred to [DONE]? ✔/✖
   List any bugs clearly. If everything is correct — state "NO CHANGES NEEDED" and stop.

Only if bugs were identified — implement MINIMAL fixes:

### Implementation (only if needed)
Files: frontend/js/ui.js, frontend/js/combat_panel.js

- `this._busy = true` must be set BEFORE the SSE/fetch call (not inside first chunk)
- `this._busy = false` + panel re-render must fire ONLY when SSE token === '[DONE]'
- `_combatVictoryUiPending` check must be INSIDE the [DONE] branch
- Make the SMALLEST possible change — do NOT refactor SSE handler structure
- Do NOT touch _flashTimers, _enemyOverlayHideTimer, or any logic added in 8B-1/8B-2/8B-3

### Constraints
- Do NOT touch backend/*
- Do NOT touch system_prompt.txt
- Do NOT touch actions.js, app.js, tests/*
- Do NOT modify keyframes/overlay/flash logic from 8B-1/8B-2/8B-3
- After change: run python3 -m pytest → must be 102 passed, 0 failed


===========AFTER REPORT===========
Przejrzałem `8B-4 — Streaming Typewriter (weryfikacja)` i aktualny kod.

### Wynik audytu (5 punktów)

1. **SSE handler + `_busy`**
   - SSE obsługiwane jest w `sendMessage` w `frontend/js/actions.js` (tokeny `[DONE]`, `[ERROR]`, pętla `reader.read()`).
   - `this._busy = true` jest ustawiane **przed** fetch/SSE w `combat_panel.js` w `_onAttack()` (`this._busy = true;` przed requestami i przed `await this._sendCombatNarrativeFollowUp(...)`).
   - `this._busy = false` resetuje się w `finally` `_onAttack()` **po zakończeniu całego await chain** (czyli po zamknięciu `sendMessage` / streamu).
   - `_combatVictoryUiPending` + `showVictoryAfterNarration()` jest sprawdzane **w gałęzi `[DONE]`** oraz dodatkowo w bezpiecznym fallbacku „stream ended without [DONE]” (to dobre zabezpieczenie).

2. **Warunek disable przycisków Atak/Ucieczka**
   - W `render()` (`combat_panel.js`):  
     `atk.disabled = this._busy || !active || !playerTurn`  
     `flee.disabled = this._busy || !active || !playerTurn`
   - Czyli sprawdzane są **oba**: `_busy` i `current_turn` (przez `playerTurn`) + status aktywności.

3. **Czy po `[DONE]` panel się odświeża**
   - Tak: po `[DONE]` jest `await window.loadTurns(...)`, a ten flow odświeża stan walki (`/combat`) i finalnie render panelu przez istniejące hooki (`afterTurnsLoaded` -> `combatPanel.fetchAndMaybeShow()` -> `render`/`show`).

4. **Ocena correctness (z checklisty)**
   - busy=true before stream: **✔**
   - busy=false only after stream completion path: **✔**
   - victory deferred to `[DONE]`: **✔** (plus poprawny fallback dla braku `[DONE]`)

5. **Konflikty / blockery**
   - **Brak blockerów.**
   - **NO CHANGES NEEDED** dla 8B-4.

---

Nie wprowadzałem zmian w plikach, bo weryfikacja nie wykazała błędu do naprawy.
