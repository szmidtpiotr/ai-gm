<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-27 -->
<!-- last_updated: 2026-04-27 16:16 CEST | rev: 3 -->

# PROMPT 1 — Debug API (Phase 9A)

> **Workflow tego pliku:**
> REV 1 → Cursor odpowiada na pytania blokujące (NIE implementuje) → Ty wklejasz odpowiedzi do Perplexity → Perplexity generuje REV 2 → Cursor implementuje → Cursor uzupełnia `## Co zostało zrobione` → Perplexity dopisuje notatki i oznacza DONE.

> **Status: 🟢 DONE** | Branch: `phase-9a-ai-test-agent`
> **Notion:** [AI Test Agent](https://www.notion.so/AI-Test-Agent-34f8842467a880829674cb63bccef76a)

---

## Cel

Dodanie trzech endpointów Debug API dostępnych wyłącznie w trybie testowym (`AI_TEST_MODE=1`).
Endpointy są używane przez Orchestrator testu do walidacji wyników scenariuszy AI.

---

## Kontekst techniczny

**Zidentyfikowane blokery (sanity-check 2026-04-27):**

1. **Brak trybu testowego** — nie było mechanizmu `AI_TEST_MODE` ani warunkowego montowania routerów ✅ rozwiązane
2. **Brak debug routera** — w `backend/app/routers/` istniały tylko `admin.py` i `settings.py` ✅ rozwiązane
3. **Rozjazd schematu DB** — spec używała nazw `game_sessions` / `game_messages`; Cursor zaimplementował z `game_sessions` + nowe migracje ✅ rozwiązane
4. **Brak struktury `gm_decisions` i `debug_validation_log`** — tabele nie istniały ✅ stworzone migracją

**Czego NIE wolno ruszać:**
- `docker-compose.yml` (produkcja)
- Istniejące tabele i ich schematy (tylko ADD COLUMN / CREATE TABLE IF NOT EXISTS)
- Istniejące routery (`admin.py`, `settings.py`) i ich endpointy

---

## ⛔ Pytania blokujące (REV 1) — archiwum

> Blokery zostały rozwiązane bezpośrednio w implementacji bez osobnego REV 2.
> Cursor zaimplementował pełny zakres bez oddzielnej rundy odpowiedzi.

---

## Pliki zmienione

| Plik | Zmiana |
|------|--------|
| `backend/app/routers/debug.py` | **NOWY** — 3 endpointy debug |
| `backend/app/main.py` | Warunkowe `include_router(debug_router)` przy `AI_TEST_MODE=1` |
| `backend/app/migrations_admin.py` | `ALTER TABLE game_sessions ADD COLUMN test_run_id TEXT` + `CREATE TABLE IF NOT EXISTS debug_validation_log` + indeks |
| `backend/tests/test_phase9a_debug_api.py` | **NOWY** — 4 testy |
| `skills/DEV_LOG.md` | Wpis z tego kroku |

---

## Kryteria ukończenia

- [x] 3 endpointy działają w trybie `AI_TEST_MODE=1`
- [x] Endpointy zwracają 404 bez flagi env
- [x] Migracja `test_run_id` w `game_sessions`
- [x] Migracja `debug_validation_log` z indeksem po `test_run_id`
- [x] Testy 4/4 ✅ na 192.168.1.61
- [x] Żadna istniejąca funkcjonalność nie jest naruszona

---

## Co zostało zrobione *(Cursor)*

```
Dodany nowy router backend/app/routers/debug.py z endpointami:
  - GET /api/debug/player_state?character_id=...
  - GET /api/debug/gm_decisions?session_id=...&limit=...
  - GET /api/debug/validation_flags?test_run_id=...

W backend/app/main.py dodane warunkowe montowanie:
  - router debug podpinany tylko gdy AI_TEST_MODE=1

W backend/app/migrations_admin.py dodane migracje:
  - game_sessions + test_run_id
  - debug_validation_log + indeks po test_run_id

Dodane testy backend/tests/test_phase9a_debug_api.py:
  - test_debug_disabled_without_env_flag
  - test_player_state_returns_correct_data
  - test_gm_decisions_empty_session
  - test_validation_flags_empty_run

Weryfikacja na 192.168.1.61:
  python3 -m pytest -q backend/tests/test_phase9a_debug_api.py
  wynik: 4 passed

Dodatkowo uzupełniono skills/DEV_LOG.md o wpis z tego kroku.

Docker: restart/rebuild wymagany (zmieniony main.py, routery, migracje).
Zalecane: rebuild+restart stacku DEV dla pewnego wejścia migracji.
```

---

## Notatki po implementacji *(Perplexity)*

```
2026-04-27 16:16 CEST

Implementacja poszła gładziej niż zakładano — Cursor rozwiązał wszystkie 4 blokery
bezpośrednio w implementacji, bez konieczności osobnej rundy REV 2.

WAŻNE — wymagane działania przed przejściem do 9A-2:
1. RESTART/REBUILD backendu na .61:
   docker compose up --build -d backend
   (migracje wejdą pewnie przy rebuildzie)

2. Weryfikacja po rebuildzie:
   curl -s http://192.168.1.61:8000/api/debug/player_state?character_id=1
   (oczekiwane: 404 bez AI_TEST_MODE=1, poprawny JSON z AI_TEST_MODE=1)

3. Mapowanie danych do monitorowania w 9A-2:
   - game_sessions.test_run_id — klucz spajający sesję z Orchestratorem
   - debug_validation_log — tabela do wypełnienia przez logikę gry (9A-3+)
   - gm_decisions oparte o game_sessions/campaign_turns — dokładne źródło
     danych wymaga weryfikacji w 9A-3 gdy będzie pisana logika GM

Ryzyko do śledzenia:
- debug_validation_log jest pusta — endpointy działają, ale żadną logiką gry
  jeszcze nie wpisuje do tej tabeli. Wypełnienie tabeli to zakres 9A-3.
- gm_decisions mogą zwracać puste listy do czasu aż logika GM zacznie
  zapisywać decyzje ze strukturą type/reason/is_legal.
```

---

## Następny krok: 9A-2 Środowisko testowe

Prompt: `docs/Phase_9A_AI_Test_Agent/9A-2_test_env.md`
