<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-27 -->
<!-- last_updated: 2026-04-27 16:49 CEST | rev: 5 -->

# PROMPT 2 — Środowisko testowe (Phase 9A)

> **Status: ✅ DONE** | Branch: `phase-9a-ai-test-agent`
> **Notion:** [AI Test Agent](https://www.notion.so/AI-Test-Agent-34f8842467a880829674cb63bccef76a)

---

## Cel

Izolowane środowisko testowe dla AI-agenta: osobna baza SQLite, dedykowane konta AI-gracza i AI-GM,
skrypt seed danych, plik konfiguracji dla Orchestratora, endpoint resetu stanu.

---

## Kontekst techniczny

**Ustalenia z REV 1:**
- Moduł DB: `backend/app/db/__init__.py` (nie `database.py`)
- Tabela `users`: `id, username, password_hash, display_name, created_at, is_active, is_admin` — brak enum `gm/player`
- Rola GM to `campaign_members.role TEXT DEFAULT 'player'`, nie atrybut konta
- Tworzenie kont: `POST /api/admin/accounts/create` → bcrypt
- Brak `conftest.py` — testy patchują DB przez `mock.patch`
- Baseline: **149 passed** | Po 9A-2: **153 passed**
- Port kontenera: `8000`, host DEV: `8100`; volume: `./data-dev:/data`

---

## Co zostało zrobione

```
Data: 2026-04-27

1) Izolacja bazy dla AI_TEST_MODE
- Dodano `backend/app/core/db_runtime.py` z resolverami:
  - `resolve_db_path()`
  - `resolve_database_url()`
- Zmieniono `backend/app/db/__init__.py`:
  - SQLModel engine bierze URL z `resolve_database_url()`
  - przy `AI_TEST_MODE=1` używa `AI_TEST_DB_PATH` (domyślnie `/data/test_ai.db`)
  - przy `AI_TEST_MODE=0` pozostaje dotychczasowy `DATABASE_URL`/fallback.

2) Seed środowiska testowego
- Dodano:
  - `backend/scripts/__init__.py`
  - `backend/scripts/seed_ai_test_env.py`
- Seed jest idempotentny i tworzy:
  - `ai_test_player`
  - `ai_test_gm`
  - kampanię `AI Test Campaign`
  - membership w `campaign_members` (`player`/`gm`)
  - postać `TestPlayer`
- Seed generuje plik konfiguracyjny:
  - `backend/ai_test_config.json` (lub ścieżkę z `AI_TEST_CONFIG_PATH`).

3) Reset runtime test-env
- Rozszerzono `backend/app/routers/debug.py` o:
  - `POST /api/debug/reset_test_env`
- Endpoint:
  - działa tylko przy `AI_TEST_MODE=1`,
  - czyści `campaign_turns` testowej kampanii,
  - czyści `debug_validation_log` po `test_run_id` z `game_sessions` (fallback `ai_test_%`),
  - resetuje postać (`current_hp=max_hp`, `location='Start'`),
  - przywraca status kampanii do `active`,
  - nie usuwa kont ani postaci.

4) Konfiguracja env
- Dodano `env.test`:
  - `AI_TEST_MODE=1`
  - `AI_TEST_DB_PATH=/data/test_ai.db`

5) Testy 9A-2
- Dodano `backend/tests/test_phase9a_test_env.py`:
  - `test_ai_test_mode_uses_separate_db`
  - `test_seed_creates_player_and_character`
  - `test_reset_endpoint_clears_messages`
  - `test_reset_does_not_delete_character`
- Wynik na `.61`: `4 passed, 1 warning`

6) Baseline regresji
- `python3 -m pytest backend/tests/ -q` → `153 passed, 1 warning`
- Docker rebuild+restart wykonany, healthcheck: `{"status":"ok"}`
```

---

## Notatki po implementacji

```
Data: 2026-04-27 | Perplexity

- 9A-2 wdrożone bez blokerów. Kluczowa decyzja: resolver DB wydzielony do osobnego
  modułu `db_runtime.py` zamiast inlajnowego patch-a w `__init__.py` — lepsze
  do testowania i rozszerzania.
- Tabela wiadomości to `campaign_turns` (nie `game_messages`) — istotne dla
  kolejnych promptów (9A-3, reset endpoint).
- Baseline wzrósł z 149 do 153 passed (+4 testy 9A-2).
- `ai_test_config.json` i `env.test` w `.gitignore` — nie wchodą do repo.
- Przy kolejnych promptach: sprawdzać `AI_TEST_CONFIG_PATH` zamiast hardcoded
  ścieżki do configa.
```

---

## Następny krok: 9A-3 Playwright PoC

Prompt: `docs/Phase_9A_AI_Test_Agent/9A-3_playwright_poc.md`
