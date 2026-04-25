<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# To prompt podsumowujacy:

# AI GM — Phase 8B: Combat Frontend Polish

## Kontekst projektu

Repo: github.com/szmidtpiotr/ai-gm
Stack: FastAPI + SQLite + Vanilla JS + HTML + Docker
Frontend: port 3001 | Backend: port 8000
Branch roboczy: phase-8-combat-system
Język gry: polski (pl)

## Co jest już gotowe (nie ruszaj)

- Backend walki (endpoints): /combat, /combat/resolve-attack, /combat/flee, /combat/turns
- combat_panel.js — panel HP, przyciski Atak/Ucieczka, overlay victory/fled/player_dead
- Karty rzutów __AI_GM_COMBAT_ROLL_V1__ w ui.js
- Tury w \#combat-engine-turns
- Status COMBAT w app.js
- 102 testy przechodzą (pytest)


## Cel Phase 8B

Poprawić odczucia i wizualną jakość systemu walki po stronie frontendu.
NIE zmieniamy backendu ani system_prompt.txt.

## Zadania do wykonania

### 8B-1 — Enemy turn overlay (animacja)

Plik: frontend/js/combat_panel.js + frontend/css/combat.css

- \#combat-enemy-overlay pojawia się gdy current_turn != "player"
- Dodaj CSS keyframe: fade-in + lekki pulse na tekście "ENEMY TURN"
- Po zakończeniu tury wroga (backend update) overlay znika płynnie (fade-out)
- NIE blokuj UI — overlay jest tylko informacyjny, przyciski pozostają disabled
przez logikę JS (nie przez overlay)


### 8B-2 — HP bar animacja

Plik: frontend/css/combat.css

- Zmiana HP (atak gracza / atak wroga) → animacja transition na szerokości
.combat-hp-fill (np. transition: width 0.4s ease)
- Kolor paska: zielony > 50% HP, żółty 26–50%, czerwony ≤ 25%
(klasy combat-hp-fill--high/mid/low już istnieją — dodaj tylko kolory i transition)


### 8B-3 — Feedback po ataku (flash)

Plik: frontend/js/combat_panel.js + frontend/css/combat.css

- Po trafieniu: combatant wroga dostaje krótki CSS flash czerwony (0.3s)
- Po pudłe: brak flash (tylko msg w \#combat-panel-msg)
- Po nat 20: złoty flash (0.4s) na całym panelu walki
- Po nat 1: fioletowy flash (0.4s) na całym panelu walki
- Implementacja: dodaj/usuń klasę CSS via JS, setTimeout na usunięcie


### 8B-4 — Streaming narracji walki (typewriter)

Plik: frontend/js/ui.js + frontend/js/combat_panel.js

- Narracja GM po ataku/ucieczce przychodzi przez SSE (już działa)
- Upewnij się, że podczas streamingu przycisk "Atak" pozostaje disabled
(this._busy = true do momentu [DONE] w SSE)
- Po [DONE]: this._busy = false → re-render panelu → przyciski wracają
- Jeśli _combatVictoryUiPending: showVictoryAfterNarration() wywoływane
dopiero na [DONE] (już naprawione w 8.3 fix 2 — zweryfikuj tylko)


### 8B-5 — Mobile / responsive panel walki

Plik: frontend/css/combat.css

- Na ekranach < 480px: panel walki zajmuje pełną szerokość
- Przyciski Atak/Ucieczka: min-height 48px (touch target)
- HP bar: min-height 8px
- \#combat-engine-turns: max-height 150px + overflow-y: auto


## Pliki do modyfikacji

frontend/css/combat.css
frontend/js/combat_panel.js
frontend/js/ui.js (tylko 8B-4 jeśli potrzebne)

## Pliki których NIE ruszamy

backend/* (wszystko)
backend/prompts/system_prompt.txt
frontend/js/actions.js
frontend/js/app.js (chyba że drobna poprawka statusu)
tests/*

## Weryfikacja po zmianach

1. python3 -m pytest → musi być 102 passed, 0 failed
2. Odśwież przeglądarkę (twarde odświeżenie Ctrl+Shift+R)
3. Zrób walkę E2E wg docs/combat_system_2/e2e_checklist.md
— min. Scenariusz 1 (victory) i Scenariusz 2 (ucieczka)
4. Docker restart NIE jest potrzebny (statyczne pliki CSS/JS)

## Priorytety (jeśli mało czasu)

Najpierw: 8B-1 (overlay) + 8B-2 (HP bar)
Potem: 8B-3 (flash) + 8B-5 (mobile)
Na końcu: 8B-4 (streaming — już częściowo działa)

Przygotuj plan dzialania

Oto plan działania dla **Phase 8B — Combat Frontend Polish**, ułożony według priorytetów z promptu:

***

## 🗂️ Plan działania — Phase 8B

### Zasady pracy (niezmienne)

- Backend (`backend/*`) i `system_prompt.txt` są **zamrożone** — żadnych modyfikacji
- Testy: po każdym zadaniu `python3 -m pytest` → musi być **102 passed, 0 failed**
- Restart Dockera **nie jest wymagany** — CSS/JS to pliki statyczne, wystarczy `Ctrl+Shift+R`
- Każde ukończone zadanie → commit do brancha `phase-8-combat-system`

***

## 🥇 Priorytet 1 — 8B-1: Enemy Turn Overlay

**Pliki:** `frontend/js/combat_panel.js` + `frontend/css/combat.css`

1. Pokaż mi aktualną zawartość `combat_panel.js` (sekcję obsługi `current_turn`) i `combat.css` (istniejące style `#combat-enemy-overlay`)
2. Dodam CSS keyframe: `fade-in` (0 → 1 opacity) + `pulse` na tekście "ENEMY TURN"
3. Po zmianie tury na `player` — dodaję klasę `.fade-out` (opacity 1 → 0, `transition: opacity 0.3s ease`)
4. Overlay jest **wyłącznie informacyjny** — blokada przycisków pozostaje po stronie logiki JS (`_busy`, `current_turn !== 'player'`), nie przez `pointer-events` na overlayzie

***

## 🥇 Priorytet 2 — 8B-2: HP Bar Animacja

**Plik:** `frontend/css/combat.css`

1. Pokaż mi aktualny CSS `.combat-hp-fill` i istniejące klasy `--high/--mid/--low`
2. Dodam:
    - `transition: width 0.4s ease` na `.combat-hp-fill`
    - Kolory: `--high` → `#4caf50` (zielony), `--mid` → `#ffc107` (żółty), `--low` → `#f44336` (czerwony)
3. Zweryfikuję, że JS przypisuje właściwą klasę w oparciu o procent HP wroga i gracza po każdym update

***

## 🥈 Priorytet 3 — 8B-3: Flash po ataku

**Pliki:** `frontend/js/combat_panel.js` + `frontend/css/combat.css`

1. Pokaż mi funkcję obsługującą wynik ataku (gdzie czytany jest `hit`, `nat`, wynik rzutu)
2. Implementacja przez **add/remove klasy CSS + `setTimeout`**:
    - Trafienie → `.flash-hit` (czerwony, 0.3s) na elemencie wroga
    - Pudło → brak flash, tylko wiadomość w `#combat-panel-msg`
    - Nat 20 → `.flash-crit` (złoty, 0.4s) na całym `#combat-panel`
    - Nat 1 → `.flash-fumble` (fioletowy, 0.4s) na całym `#combat-panel`
3. Keyframe animacja `@keyframes flash` w CSS (opacity ping-pong lub background-color pulse)

***

## 🥈 Priorytet 4 — 8B-5: Mobile / Responsive

**Plik:** `frontend/css/combat.css`

Dodaję media query `@media (max-width: 480px)`:

```css
#combat-panel { width: 100%; }
.combat-btn { min-height: 48px; }
.combat-hp-fill { min-height: 8px; }
#combat-engine-turns { max-height: 150px; overflow-y: auto; }
```

Bez zmian w JS — tylko CSS.

***

## 🥉 Priorytet 5 — 8B-4: Streaming / Typewriter (weryfikacja)

**Pliki:** `frontend/js/ui.js` + `frontend/js/combat_panel.js`

1. Pokaż mi sekcję SSE `[DONE]` w `ui.js` i miejsce gdzie `this._busy` jest resetowane
2. Weryfikuję że:
    - `this._busy = true` ustawiane przed wysłaniem akcji ataku/ucieczki
    - `this._busy = false` + re-render panelu następuje **dopiero na `[DONE]`** — nie wcześniej
    - `_combatVictoryUiPending` → `showVictoryAfterNarration()` wywołane na `[DONE]` (naprawione w 8.3 fix 2 — tylko potwierdzam)
3. Jeśli coś nie gra — minimalna poprawka w `ui.js` (dopisanie warunku, nie refactor)

***

## ✅ Weryfikacja końcowa

| Krok | Co sprawdzamy |
| :-- | :-- |
| `pytest` | 102 passed, 0 failed |
| `Ctrl+Shift+R` | Nowe CSS/JS załadowane |
| E2E Scenariusz 1 | Victory — overlay, flash, HP bar, animacje |
| E2E Scenariusz 2 | Ucieczka — overlay znika, panel reset |
| Mobile 480px | Panel walki full-width, przyciski touchable |


***

**Gotowy do startu.** Zacznijmy od **8B-1 + 8B-2** — prześlij mi aktualne pliki `combat_panel.js` i `combat.css` (lub ich kluczowe fragmenty), a dodam kod bez zbędnych przepisywań całości.

