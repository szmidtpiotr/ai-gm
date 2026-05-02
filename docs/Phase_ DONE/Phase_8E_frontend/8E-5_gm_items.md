<!-- last_updated: 2026-04-27 09:10 CEST | rev: 4 -->

# Phase 8E — Task 8E-5: Przedmioty Fabularne GM

> **Status: ✅ DONE** | Branch: `phase-8e-frontend` | Commit: `85d7598`
> **PR:** https://github.com/szmidtpiotr/ai-gm/pull/5
> **Notion:** https://www.notion.so/Phase-8E-frontend-34d8842467a8805db44ce68c3612dcb9

---

## Co zostało zrobione

### Pliki zmienione
| Plik | Zmiana |
|------|--------|
| `backend/app/api/characters.py` | `setdefault("narrative_items", [])` w `create_character`; nowy endpoint `POST /{id}/narrative-item` |
| `backend/app/api/turns.py` | `GRANT_ITEM_RE`, wykrywanie cue `Grant Item`, usuwanie z tekstu dla gracza, zapis do `sheet_json` |
| `backend/prompts/system_prompt.txt` | Sekcja `## Przedmioty fabularne (Grant Item)` |
| `backend/tests/test_phase8e_gm_items.py` | **NOWY** — 5 testów |
| `frontend/js/app.js` | Sekcja `#narrative-items-section` pod plecakiem |
| `frontend/js/inventory.js` | Renderowanie `narrative_items` z `window.state.characterSheet` |
| `frontend/styles.css` | `.narrative-item`, `.narrative-item-label`, `.narrative-item-desc` |

### Testy (22/22 ✅)
```
pytest -q -k 'phase8e or enemy_death_victory_and_loot'
22 passed, 38 deselected
```

### Zdarzenie bezpieczeństwa
- Wykryto nieoczekiwany nietracked plik `frontend/admin_panel/sections/ai_tester.js` (halucynacja Cursora)
- Decyzja: **pominięty** — nie trafił do commita

## Deploy checklist
- [ ] `git pull` na `.61` (branch `phase-8e-frontend`)
- [ ] **Restart backendu** (`system_prompt.txt` + API)
- [ ] Restart frontendu (JS/CSS)
- [ ] Sprawdź czy GM może wyemitować `Grant Item X` — item trafia do plecaka
- [ ] Stara postać bez `narrative_items` — nie crashuje
- [ ] `main` NIE był mergowany

## Następny krok: 8E-6

Prompt: `docs/Phase_8E_frontend/8E-6_*.md` (jeśli istnieje) lub nowy task.
