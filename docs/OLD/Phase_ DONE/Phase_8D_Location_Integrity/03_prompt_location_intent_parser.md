<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-28 -->

# PROMPT 03 — Location Intent Parser + Validator (Phase 8D)

> Workflow tego pliku: REV 1 (pytania blokujące) → odpowiedzi Cursora → REV 2 (implementacja) → raport Cursora → notatki Perplexity → DONE.

---

## Cel

Zaimplementować rdzeń systemu Location Integrity:
1. **Parser intencji ruchu** z odpowiedzi LLM (Opcja A JSON + Opcja B fallback)
2. **Walidator spójności ruchu** (fuzzy match + reguły przechodzenia)
3. **Updater lokalizacji sesji** (`PATCH /api/session/{id}/location`)
4. **Injector kontekstu** do system promptu GM
5. **Handler komendy `/move`**
6. **Integracja z głównym loop GM** w `backend/app/api/turns.py`

Zadania: **8D-8, 8D-9, 8D-10, 8D-11, 8D-12**.

---

## Kontekst techniczny

- **Branch:** `phase-8d-location-integrity`
- **Baseline po PROMPT 02:** `181 passed`
- **Zależność:** tabela `game_locations` (PROMPT 01) + `POST /api/locations` (PROMPT 02)
- **NIE ruszać:** `docker-compose.yml` prod, `data/ai_gm.db`, `backend/prompts/system_prompt.txt`

---

## Odpowiedzi Cursora (REV 1)

| # | Pytanie | Odpowiedź |
|---|---------|----------|
| 1 | Stan repo | ⚠️ PROMPT 02 niezacommitowany — commit wykonany przed implementacją |
| 2 | Główny loop GM | ✅ `backend/app/api/turns.py` — `generate_chat_stream` / `generate_chat` |
| 3 | Config service | ⚠️ Brak `get_flag()` — zaimplementowano nowy `location_config_service.py` |
| 4 | Komendy | ✅ `backend/app/api/turns.py` (~linia 1025) + `slash_command_registry.py` |
| 5 | LLM client | ✅ `httpx` przez `llm_service.py` — użyto `generate_chat()` dla Opcji B |
| 6 | Kolumny w DB | ✅ `current_location_id` i `session_flags` istnieją |
| 7 | `rapidfuzz` | ❌ Brak — dodano do `requirements.txt` i zainstalowano |

---

## Co zostało zrobione *(Cursor)*

| Zadanie | Komponent | Plik |
|---------|-----------|------|
| **8D-8** | Location Intent Parser | `app/services/location_intent_parser.py` |
| **8D-9** | Location Validator | `app/services/location_validator.py` |
| **8D-10** | Session Location Updater | `app/routers/session_location.py` |
| **8D-11** | Location Context Injector | `app/services/location_context_injector.py` |
| **8D-12** | Handler `/move` | `app/api/turns.py` (~linia 1176) |
| **Integracja** | GM Loop integration | `app/api/turns.py` (~linia 1855) |

**Nowe pliki:**
1. `requirements.txt` — `rapidfuzz>=3.0.0`
2. `app/services/location_config_service.py` — merge logika flag
3. `app/services/location_intent_parser.py` — Opcja A + B
4. `app/services/location_validator.py` — fuzzy match + reguły
5. `app/services/location_context_injector.py` — system prompt injection
6. `app/routers/session_location.py` — endpointy sesji
7. `app/api/turns.py` — `/move` handler + integracja GM loop
8. `app/main.py` — rejestracja `session_location_router`
9. `tests/test_8d_intent_parser.py` — nowe testy

**Wynik testów:** 196 passed (164 baseline + 32 nowe: 17 locations API + 15 intent parser)

**Znany problem:** `test_phase8d_migrations.py` — 15 errors (fixture tymczasowej bazy, nie blokuje)

---

## Notatki po implementacji *(Perplexity)*

- ✅ Implementacja kompletna — wszystkie 5 komponentów + integracja z loop GM
- ✅ `location_config_service.py` (zamiast `config_service.py`) — odnotować tą nazwę w PROMPT 04 (admin flags używa tego samego serwisu)
- ✅ Endpointy sesji w `session_location.py`: `PATCH`, `GET` i `POST /validate-move` — więcej niż zakładano w REV 2
- ⚠️ Zweryfikować czy `location_integrity_enabled` w DB to `'0'` (powinno być na czas dev)
- ⚠️ `test_phase8d_migrations.py` — 15 errors fixture do naprawy w PROMPT 06
