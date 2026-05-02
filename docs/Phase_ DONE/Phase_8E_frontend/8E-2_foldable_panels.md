<!-- last_updated: 2026-04-27 07:44 CEST | rev: 3 -->

# Phase 8E — Task 8E-2: Zwijane sekcje UI gracza

> **Status: ✅ DONE** | Branch: `phase-8e-frontend` | Commit: `982bea5`
> **PR:** https://github.com/szmidtpiotr/ai-gm/pull/5
> **Notion:** https://www.notion.so/Phase-8E-frontend-34d8842467a8805db44ce68c3612dcb9

---

## Co zostało zrobione

### Pliki zmienione
| Plik | Zmiana |
|------|--------|
| `frontend/js/app.js` | `loadUiPanelDefaults()`, `applyFoldState()`, delegacja kliku, wrappery w `renderCharacterSheetPanel`, `applyFoldState()` na końcu renderu |
| `frontend/styles.css` | Bloki 8E-2: `.sheet-section-header`, `.fold-icon`, `.sheet-section-body`, `.fold-collapsed` |
| `frontend/admin_panel/index.html` | Sidebar: przycisk „Ustawienia UI”, panel `data-section="ui-settings"`, `maybeInitUiSettings`, `wireSidebarNav`, `layout.css?v=25` |
| `frontend/admin_panel/layout.css` | Style `.ui-settings-form` / `.ui-settings-row` |
| `backend/app/routers/ui_panel_settings.py` | **Już istniał** — GET/PATCH `/api/settings/ui` |
| `frontend/admin_panel/sections/ui_settings.js` | **Już istniał** — panel UI admina |
| `backend/tests/test_phase8e_foldable.py` | **Już istniał** — 4 testy |

### Kluczowe decyzje (zachowane)
- `.sheet-fluff` na wewnętrznym `div.sheet-identity-block` — `combat_input.js` bez zmian ✔
- Wrapper sekcji Postać renderowany tylko gdy istnieje identity ✔
- `applyFoldState()` kolejność: localStorage → API defaults → fallback (mobile <768px) ✔
- `GET /api/settings/ui` publiczny (bez auth) ✔

### Testy (4/4 ✅)
```
test_ui_settings_get_returns_defaults
test_ui_settings_patch_merges_correctly
test_ui_settings_patch_unknown_panel_ignored
test_ui_settings_get_after_patch_reflects_change
```
Uruchomione na `192.168.1.61`.

## Deploy checklist
- [ ] `git pull` na serwerze `.61` (branch `phase-8e-frontend`)
- [ ] Reload nginx / redeploy frontend (statyczne pliki — backend restart niekonieczny)
- [ ] Hard refresh przeglądarki (Ctrl+Shift+R)
- [ ] Sprawdź czy sekcje Statystyki/Umiejętności są zwijalne w UI gracza
- [ ] Sprawdź Admin Panel → Ustawienia UI — toggles działają
- [ ] `main` NIE był mergowany — zgodnie z regułą

## Następny krok: 8E-3 Panel Ekwipunku

Prompt: `docs/Phase_8E_frontend/8E-3_inventory_panel.md`


==============================AFTER REPORT=================================
## Status 8E-2

**Blokerów nie było** — backend (`GET/PATCH /api/settings/ui`, `ui_panel_settings.py`, testy `test_phase8e_foldable.py`) i `admin_panel/sections/ui_settings.js` były już w repozytorium. **Dokończyłem warstwę gracza + integrację admina**, zgodnie z `8E-2_foldable_panels.md` (rev 2).

### Co doszło w tej iteracji

1. **`frontend/js/app.js`**
- `loadUiPanelDefaults()` — `fetch` na `/api/settings/ui`, zapis do `window._uiPanelDefaults`
- `applyFoldState()` — kolejność: `localStorage` (`ui_fold_{stats|skills|identity}`) → defaults z API → fallback (mobile &lt; 768: tylko `stats` expanded)
- Jednorazowa delegacja kliku na `[data-fold-toggle]`
- W `renderCharacterSheetPanel`: wrappery `sheet-foldable-section` + nagłówek + `sheet-section-body` dla **Statystyki**, **Umiejętności**; dla **Postać** wrapper tylko gdy jest identity — **`.sheet-fluff` zostaje na wewnętrznym** `div.sheet-identity-block` (jak w dokumencie, `combat_input.js` bez zmian)
- Na końcu renderu: `window.applyFoldState()`

2. **`frontend/styles.css`** — bloki 8E-2 (nagłówek, ikona, `max-height` + `.fold-collapsed`)

3. **`frontend/admin_panel/index.html`** — przycisk sidebar **„Ustawienia UI”**, panel `data-section="ui-settings"`, `maybeInitUiSettings`, podpięcie w `wireSidebarNav`, `layout.css?v=25`

4. **`frontend/admin_panel/layout.css`** — style `.ui-settings-form` / `.ui-settings-row` itd.

`main.js` już wołał `loadUiPanelDefaults` i `applyFoldState` w `bootstrap` — po dodaniu funkcji to działa spójnie.

### Testy

Na **192.168.1.61**: `pytest tests/test_phase8e_foldable.py` → **4 passed** (kod na serwerze mógł być starszy niż lokalny commit; lokalnie pytest nie był zainstalowany).

### Git

- Branch: **`phase-8e-frontend`**
- Commit: **`982bea5`**
- **Push:** `origin/phase-8e-frontend` (aktualizacja istniejącego PR, np. #5)

### Docker

Ta zmiana to **głównie statyczne pliki** (`app.js`, `styles.css`, admin). Zwykle wystarczy **odświeżenie / redeploy frontendu** (lub volume z kodem + reload nginx). **Backendu nie trzeba restartować** wyłącznie przez ten commit — o ile nie wdrażasz pierwszy raz endpointów `settings/ui` (wtedy i tak migracje przy starcie backendu).