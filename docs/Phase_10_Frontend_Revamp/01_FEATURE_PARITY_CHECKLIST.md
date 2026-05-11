# Feature Parity Checklist: Legacy vs Mobile-First Frontend

**Last updated:** 2026-05-09

This document tracks feature parity between the legacy frontend (`frontend/index.html`) and the new mobile-first frontend (`frontend/front/`).

---

## Legend

| Symbol | Meaning |
|--------|---------|
| [x] | Done |
| [ ] | Not started |
| [~] | Partial / In progress |
| [—] | Not applicable / Intentionally skipped |

---

## 1. Authentication

| ID | Feature | Legacy | Mobile | Notes |
|----|---------|--------|--------|-------|
| A01 | [x] | Login form (username/password) | [x] | Done |
| A02 | [x] | Logout button | [x] | Done |
| A03 | [x] | Auth token persistence (localStorage) | [x] | Done |
| A04 | [x] | Guest login | [ ] | Hidden in legacy, skip for now |

---

## 2. Campaign Management

| ID | Feature | Legacy | Mobile | Notes |
|----|---------|--------|--------|-------|
| C01 | [x] | List user campaigns | [x] | Done |
| C02 | [x] | Select/enter campaign | [x] | Done |
| C03 | [x] | Create new campaign | [x] | Done |
| C04 | [x] | Reset campaign (clear chat/combat) | [x] | Done (settings admin panel) |
| C05 | [x] | Reset character (fresh sheet) | [x] | Done (settings admin panel) |
| C06 | [x] | Delete campaign | [—] | Not exposed in legacy settings either — skip |
| C07 | [x] | Campaign title display | [x] | Done (header) |

---

## 3. Character Creation Wizard

| ID | Feature | Legacy | Mobile | Notes |
|----|---------|--------|--------|-------|
| W01 | [x] | Character name input | [x] | Done |
| W02 | [x] | Background/backstory input | [x] | Done (step 4) |
| W03 | [x] | Archetype selection (warrior/scholar) | [x] | Done — full real flow: POST /characters → stat pool → skill swaps → LLM identity |
| W04 | [x] | Multi-step wizard UI | [x] | Done (4 steps) |
| W05 | [x] | Submit to API | [x] | Done — finalize-sheet called on step 4 |

---

## 4. Chat / Messaging

| ID | Feature | Legacy | Mobile | Notes |
|----|---------|--------|--------|-------|
| M01 | [x] | Chat message display | [x] | Done |
| M02 | [x] | Send message (input + button) | [x] | Done |
| M03 | [x] | Load chat history on enter | [x] | Done |
| M04 | [x] | GM typing indicator | [x] | Done |
| M05 | [x] | Parse JSON narrative from GM | [x] | Done — `parseGmFull()` strips code fences, char-by-char fallback, extracts `location_intent` |
| M06 | [x] | Archive toggle (OOC/system msgs) | [ ] | **TODO** |
| M07 | [x] | Slash commands (/sheet, /mem, etc.) | [x] | Done — autocomplete popup + /help, /sheet, /mem, /helpme, /history, /search, /atak |
| M08 | [x] | Hide combat bubbles preference | [ ] | Low priority |

---

## 5. Character Sheet Panel

| ID | Feature | Legacy | Mobile | Notes |
|----|---------|--------|--------|-------|
| S01 | [x] | HP display + bar | [x] | Done |
| S02 | [x] | Level display | [x] | Done |
| S03 | [x] | Stats grid (STR/DEX/etc.) | [x] | Done |
| S04 | [x] | Skills list | [x] | Done |
| S05 | [x] | Inventory list | [x] | Done |
| S06 | [x] | Gold display | [x] | Done |
| S07 | [x] | Slide-up panel toggle | [x] | Done |
| S08 | [x] | Tab navigation (stats/skills/inv) | [x] | Done |
| S09 | [x] | XP spending UI (T29) | [ ] | **TODO** — new feature |

---

## 6. Combat System

| ID | Feature | Legacy | Mobile | Notes |
|----|---------|--------|--------|-------|
| B01 | [x] | Combat panel (enemy HP, status) | [x] | Done |
| B02 | [x] | Attack button | [x] | Done |
| B03 | [x] | Flee button | [x] | Done |
| B04 | [x] | Combat state sync from API | [x] | Done (polling) |
| B05 | [x] | Combat debug status display | [—] | Debug only — skipped |
| B06 | [x] | Condition icons/effects | [—] | Skipped — no conditions in current game data |

---

## 7. Shop System

| ID | Feature | Legacy | Mobile | Notes |
|----|---------|--------|--------|-------|
| H01 | [x] | Shop modal | [ ] | **TODO** |
| H02 | [x] | Buy items list | [ ] | **TODO** |
| H03 | [x] | Sell items list | [ ] | **TODO** |
| H04 | [x] | Gold balance display | [ ] | **TODO** |

---

## 8. Voice Features

| ID | Feature | Legacy | Mobile | Notes |
|----|---------|--------|--------|-------|
| V01 | [x] | TTS toggle (read GM responses) | [ ] | **TODO** |
| V02 | [x] | STT toggle (voice input) | [ ] | **TODO** |
| V03 | [x] | Voice status indicator | [ ] | **TODO** |
| V04 | [x] | Mic button in composer | [ ] | **TODO** |

---

## 9. History & Summary

| ID | Feature | Legacy | Mobile | Notes |
|----|---------|--------|--------|-------|
| Y01 | [x] | History summary modal | [x] | Done ("Dziennik podróżnika") |
| Y02 | [x] | AI regenerate summary | [x] | Done (regen button) |
| Y03 | [x] | Dual preview (player/GM) | [—] | Skipped (low priority) |

---

## 10. Dice Rolling

| ID | Feature | Legacy | Mobile | Notes |
|----|---------|--------|--------|-------|
| D01 | [x] | Contextual roll button | [—] | Removed — obsolete |
| D02 | [x] | Roll popup (dice type select) | [—] | Removed — obsolete |
| D03 | [x] | Roll result display in chat | [—] | Removed — obsolete |

---

## 11. Death Screen

| ID | Feature | Legacy | Mobile | Notes |
|----|---------|--------|--------|-------|
| X01 | [x] | Death overlay/modal | [x] | Done |
| X02 | [x] | Death message display | [x] | Done |
| X03 | [x] | Close/dismiss button | [x] | Done (resurrect + return to campaigns) |

---

## 12. Settings & Debug

| ID | Feature | Legacy | Mobile | Notes |
|----|---------|--------|--------|-------|
| G01 | [x] | Settings panel | [x] | Done (font settings) |
| G02 | [x] | Font size slider | [x] | Done |
| G03 | [x] | Font family select | [x] | Done |
| G04 | [x] | Status indicators (backend/ollama/loki) | [ ] | Low priority |
| G05 | [x] | Copy debug button | [ ] | Low priority (debug) |
| G06 | [x] | Location debug panel | [~] | Debug panel implemented — toggle in settings, shows COMBAT state + LOCATION intent below each GM bubble; location tracking across turns pending (Task #1) |

---

## Summary

| Category | Done | TODO | Total | % |
|----------|------|------|-------|---|
| Authentication | 3 | 1 | 4 | 75% |
| Campaign Management | 6 | 0 | 6 | 100% |
| Character Wizard | 5 | 0 | 5 | 100% |
| Chat / Messaging | 5 | 3 | 8 | 63% |
| Character Sheet | 8 | 1 | 9 | 89% |
| Combat System | 6 | 0 | 6 | 100% |
| Shop System | 0 | 4 | 4 | 0% |
| Voice Features | 0 | 4 | 4 | 0% |
| History & Summary | 2 | 0 | 2 | 100% |
| Dice Rolling | 3 | 0 | 3 | 100% (removed — obsolete) |
| Death Screen | 3 | 0 | 3 | 100% |
| Settings & Debug | 3 | 3 | 6 | 50% |
| **TOTAL** | **44** | **16** | **60** | **73%** |

---

## Suggested Priority Order

### P0 — Core Gameplay ✅ DONE
- ~~**B01-B04** Combat panel + attack/flee~~ ✓
- ~~**C04-C06** Campaign reset/delete actions~~ ✓
- ~~**D01-D03** Dice rolling~~ — removed (obsolete)
- ~~**X01-X03** Death screen~~ ✓
- ~~**Y01-Y02** History summary~~ ✓

### P1 — Important UX (next up)
1. **H01-H04** Shop modal
2. **M06-M07** Archive toggle + slash commands
3. **S09** XP spending UI (T29)

### P2 — Nice to Have
4. **V01-V04** Voice features (TTS/STT)

### P3 — Low Priority (debug/optional)
5. Status indicators, debug tools (G04-G06)

