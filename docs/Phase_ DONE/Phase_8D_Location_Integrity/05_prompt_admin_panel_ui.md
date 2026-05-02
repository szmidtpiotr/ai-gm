<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-28 -->

# PROMPT 05 — Admin Panel UI (Phase 8D)

> Workflow tego pliku: REV 1 (pytania blokujące) → odpowiedzi Cursora → REV 2 (implementacja) → raport Cursora → notatki Perplexity → DONE.

---

## Cel

Zaimplementować interfejs admina dla systemu Location Integrity:
1. **Zakładka „Locations”** w Game Design — drzewo makro/sub + CRUD
2. **Przypisywanie `enemy_keys`** do lokalizacji
3. **Edytor `rules`** z walidacją JSON
4. **Toggle flagów** Location Integrity w nowej zakładce Sessions
5. **Log viewer** prób blokad

Zadania: **8D-15, 8D-16, 8D-17, 8D-18, 8D-19**.

---

## Kontekst techniczny

- **Branch:** `phase-8d-location-integrity`
- **Baseline po PROMPT 04:** `213 passed`
- **Stack frontend:** Vanilla JS + HTML, inline CSS, `data-tab`/`data-panel` zakładki
- **API wrapper:** `api(path, options)` w `admin.js` z `Authorization: Bearer state.token`
- **NIE ruszać:** istniejące zakładki, `docker-compose.yml` prod

---

## Odpowiedzi Cursora (REV 1)

| # | Pytanie | Odpowiedź |
|---|---------|----------|
| 1 | Stan repo | ⚠️ PROMPT 04 niezacommitowany |
| 2 | Zakładki | ✅ `data-tab`/`data-panel`, 11 istniejących zakładek |
| 3 | CSS/Styl | ✅ Inline `<style>`, `.secondary/.primary/.field/.table-wrap`, brak modali |
| 4 | Sekcja sesji | ⚠️ Brak — dodano nową zakładkę `Sessions` |
| 5 | Enemies format | ✅ `{ items: [{ key, label }] }` |
| 6 | API wrapper | ✅ `api(path, options)` z Bearer token |

---

## Co zostało zrobione *(Cursor)*

**Frontend** (`admin.html`, `admin.css`, `js/admin.js`):
- ✅ Zakładka "Locations" — drzewo lokalizacji makro/sub
- ✅ Formularz CRUD inline z auto-generacją klucza (slugify)
- ✅ Przypisywanie wrogów: select + tagi z usuwaniem (×)
- ✅ Edytor `rules` z walidacją JSON na żywo (czerwona/zielona ramka)
- ✅ Zakładka "Sessions" z toggle flagami Location Integrity (3 checkboxy + global info)
- ✅ Log viewer blokad z filtrami daty (since/until)

**Backend** (`locations.py`, `admin_location.py`):
- ✅ `PUT /api/locations/{key}` — aktualizacja
- ✅ `DELETE /api/locations/{key}` — soft-delete (blokowany jeśli ma dzieci)
- ✅ `GET/PUT /api/admin/config/location-flags` — globalne flagi

**Git:**
- Branch: `phase-8d-location-integrity`
- Commit: `bfc1dba`
- 18 plików zmienionych, 3964+ linii
- PR: [https://github.com/szmidtpiotr/ai-gm/pull/new/phase-8d-location-integrity](https://github.com/szmidtpiotr/ai-gm/pull/new/phase-8d-location-integrity)

---

## Notatki po implementacji *(Perplexity)*

- ✅ Implementacja kompletna — wszystkie 5 zadań UI gotowe
- ✅ `PUT` zamiast `PATCH` dla edycji lokalizacji — odnotować w PROMPT 06 (testy muszą używać `PUT`)
- ✅ Soft-delete z blokadą dla lokalizacji z dziećmi — dobra decyzja dla integralności danych
- ⚠️ `test_phase8d_migrations.py` — 15 errors fixture wciąż otwarte → **PROMPT 06 musi naprawić fixture jako krok 0**
- ⚠️ `location_integrity_enabled` — zweryfikować czy w DB to `'0'` (dev) czy `'1'` (wdrożone przypadkowo w PROMPT 01)
- 🎯 Po PROMPT 06: wszystkie testy passed → można tworzyć PR i merge do `develop`
