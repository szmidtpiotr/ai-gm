## TASK: 8B-2 — HP Bar Animation
Branch: main

### CONTEXT (from 8B-1 implementation — already known)
- Files modified so far: frontend/css/combat.css, frontend/js/combat_panel.js
- New keyframes added in combat.css: combatEnemyFadeIn, combatEnemyFadeOut, combatEnemyPulse
- New methods added in combat_panel.js: _showEnemyOverlay(), _hideEnemyOverlay()
- Tests: 102 passed (baseline confirmed)

### BEFORE YOU WRITE ANY CODE — answer these questions first:
1. Read frontend/css/combat.css — show ALL existing rules for `.combat-hp-fill`
   and any subclasses (`--high`, `--mid`, `--low`). Do they already have
   `transition`, `background-color`, or `width` defined?
2. Read frontend/js/combat_panel.js — find where HP bar width is set
   (likely `style.width` assignment on an element with hp-fill in its class/id).
   Show the exact line(s) and function name.
3. Is the class `--high` / `--mid` / `--low` already being toggled by JS
   based on HP%? If not, which function and line would be the right place to add it?
4. After 8B-1 we added _showEnemyOverlay() / _hideEnemyOverlay() in render().
   Would adding `transition: width 0.4s ease` to `.combat-hp-fill` interfere
   with any re-render timing (e.g. HP bar resetting to 0 then animating up on
   combat init)? State: NO CONFLICT or CONFLICT (explain).

Only after answering all 4 — implement the following:

### Implementation
Files: frontend/css/combat.css (+ minimal JS in combat_panel.js only if class toggle missing)

CSS — in combat.css:
- `.combat-hp-fill` → add `transition: width 0.4s ease`
- Color classes (add colors if missing, do NOT remove existing rules):
  - `.combat-hp-fill--high` → background-color: #4caf50  (green,  > 50% HP)
  - `.combat-hp-fill--mid`  → background-color: #ffc107  (yellow, 26–50% HP)
  - `.combat-hp-fill--low`  → background-color: #f44336  (red,    ≤ 25% HP)

JS — only if audit confirms class toggle is missing:
- In the function that sets HP bar width, add class toggle AFTER setting width:
    el.classList.remove('combat-hp-fill--high', 'combat-hp-fill--mid', 'combat-hp-fill--low');
    if (pct > 50)      el.classList.add('combat-hp-fill--high');
    else if (pct > 25) el.classList.add('combat-hp-fill--mid');
    else               el.classList.add('combat-hp-fill--low');
- Apply this for BOTH player HP bar AND enemy HP bar (if they share the same
  function, one change covers both; if separate — update both).
- Do NOT restructure the function, only add the toggle block.

### Constraints
- Do NOT touch backend/*
- Do NOT touch system_prompt.txt
- Do NOT touch actions.js, app.js, tests/*
- Do NOT modify the keyframes or overlay logic added in 8B-1
- After change: run python3 -m pytest → must be 102 passed, 0 failed

===============AFTER REPORT=================

Zrobione — **8B-2 zaimplementowany, bez blockerów**.

### Audit (4 pytania z pliku)
1. `.combat-hp-fill` i klasy `--high/--mid/--low` już istniały w `combat.css`:
   - `.combat-hp-fill`: miało `transition: width 0.25s ease, background 0.2s ease`
   - `--high/--mid/--low`: miały gradientowe `background` (bez `background-color`)
2. Szerokość paska HP jest ustawiana w `render()` w `combat_panel.js` (budowanie `rowHtml`), inline:
   - `style="width:${pct.toFixed(0)}%"`
3. Klasa tier (`--high/--mid/--low`) **już jest togglowana** przez JS:
   - `const tier = hpTier(pct)` i potem `class="combat-hp-fill combat-hp-fill--${tier}"`
   - więc **nie trzeba** dopisywać bloków `classList.remove/add`
4. `transition: width 0.4s ease` dla `.combat-hp-fill`:
   - **NO CONFLICT** (render już podaje procent width bez resetu do 0 na init; animacja tylko wygładza zmianę).

### Wdrożone zmiany
Plik: `frontend/css/combat.css`
- `.combat-hp-fill`: `transition` zmienione na `width 0.4s ease, background 0.2s ease`
- Dodane fallback kolory:
  - `.combat-hp-fill--high { background-color: #4caf50; }`
  - `.combat-hp-fill--mid { background-color: #ffc107; }`
  - `.combat-hp-fill--low { background-color: #f44336; }`
- Nie ruszałem overlay/keyframes z 8B-1 i nie ruszałem JS/Python poza wymaganiem.

### Testy
Na `.61`:
- `python3 -m pytest -q --tb=no` → **102 passed, 1 warning**

### Docker
Po tej zmianie **nie trzeba** restartu/rebuilda Dockera (to tylko CSS frontend). Wystarczy odświeżenie przeglądarki (najlepiej hard refresh).