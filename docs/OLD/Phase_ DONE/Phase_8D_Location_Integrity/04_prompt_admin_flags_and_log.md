<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-28 -->

# PROMPT 04 — Admin Flags + Location Log (Phase 8D)

> Workflow tego pliku: REV 1 (pytania blokujące) → odpowiedzi Cursora → REV 2 (implementacja) → raport Cursora → notatki Perplexity → DONE.

---

## Cel

Zaimplementować endpointy admin do:
1. **Zarządzania flagami Location Integrity** per sesja i globalnie
2. **Przeglądania logów blokad** z tabeli `location_integrity_log`

Zadania: **8D-13, 8D-14**.

---

## Kontekst techniczny

- **Branch:** `phase-8d-location-integrity`
- **Baseline po PROMPT 03:** `196 passed`
- **Zależność:** `location_config_service.py`, tabela `location_integrity_log`, `admin_router` w `app/routers/admin.py`
- **NIE ruszać:** `docker-compose.yml` prod, `data/ai_gm.db`, istniejące endpointy w `admin.py`

---

## Odpowiedzi Cursora (REV 1)

| # | Pytanie | Odpowiedź |
|---|---------|----------|
| 1 | Stan repo | ⚠️ PROMPT 03 niezacommitowany — commit wykonany przed implementacją |
| 2 | Auth admin | ✅ `require_admin_token()` Dependency — SHA256 tokenu vs `admin_tokens.token_hash` |
| 3 | Router admina | ✅ `app/routers/admin.py` — prefix `/api/admin/` |
| 4 | `location_config_service.py` | ⚠️ Tylko odczyt — dodano `set_session_flag()` i `delete_session_flag()` |
| 5 | `location_integrity_log` | ✅ Pełna schema |
| 6 | `log_integrity_violation()` | ✅ Zapisuje do SQLite + `logger.warning()` |

---

## Co zostało zrobione *(Cursor)*

| Zadanie | Endpoint | Opis |
|---------|----------|------|
| **8D-13** | `GET /api/admin/session/{id}/flags` | effective + overrides + global defaults |
| **8D-13** | `PATCH /api/admin/session/{id}/flags` | Nadpisz wybrane flagi sesji |
| **8D-13** | `DELETE /api/admin/session/{id}/flags/{key}` | Usuń nadpisanie (powrót do global) |
| **8D-14** | `GET /api/admin/session/{id}/location-log` | Logi blokad dla sesji |
| **8D-14** | `GET /api/admin/location-log` | Globalne logi (wszystkie sesje) |

**Nowe pliki:**
1. `app/services/location_config_service.py` — dodano `set_session_flag()`, `delete_session_flag()`, `get_all_flags()`
2. `app/routers/admin_location.py` — nowy router (171 linii)
3. `app/main.py` — rejestracja routera
4. `tests/test_8d_admin_flags.py` — 17 testów

**Wynik testów:** 213 passed (196 baseline + 17 nowych)

---

## Notatki po implementacji *(Perplexity)*

- ✅ Implementacja kompletna — pełny CRUD flag + logi
- ✅ Nowy router `admin_location.py` (zamiast dopisywania do `admin.py`) — dobra decyzja architektoniczna
- ⚠️ `get_all_flags()` — nowa funkcja eksportowana przez serwis — użyteczna w PROMPT 05 (UI toggli flag w admin panelu)
- ⚠️ `test_phase8d_migrations.py` — 15 errors fixture wciąż otwarte, do naprawy w PROMPT 06
- ✅ Fundament dla PROMPT 05: endpointy `GET`/`PATCH`/`DELETE flags` + `GET location-log` są gotowe do podłączenia UI
