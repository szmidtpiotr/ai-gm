<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-27 -->
<!-- last_updated: 2026-04-27 19:47 CEST | rev: 5 -->

# PROMPT 4 — AI Agent Service (observe → decide → act)

> **Workflow tego pliku:**
> REV 1 → Cursor odpowiada na pytania blokujące (NIE implementuje) → Ty wklejasz odpowiedzi do Perplexity → Perplexity generuje REV 2 → Cursor implementuje → Cursor uzupełnia `## Co zostało zrobione` → Perplexity dopisuje notatki i oznacza DONE.

> **Status: ✅ DONE** | Branch: `develop` | Commit: `fa16d19`
> **Notion:** [AI Test Agent](https://www.notion.so/AI-Test-Agent-34f8842467a880829674cb63bccef76a)

---

## Cel

Serwis AI-agenta realizujący pętlę `observe → decide → act`: odczytuje snapshot stanu gry (UI + Debug API), wysyła do LLM, odbiera decyzję o następnej akcji, waliduje ją i wykonuje przez Playwright.

**Scenariusz docelowy PoC:** „Sprawdz czy uda się przekonać GM do zmiany lokacji postaci bez ukończenia questa.”

---

## Kontekst (stan po 9A-1 → 9A-3)

- Backend DEV: `http://192.168.1.61:8100` | Frontend DEV: `http://192.168.1.61:3002`
- `AI_TEST_MODE=1` + `AI_TEST_STUB_LLM=1` aktywne na DEV od 9A-3
- `POST /api/debug/reset_test_env` — działa
- `GET /api/debug/player_state?character_id=Y` — działa
- `GET /api/debug/settings/feature_flags` — działa
- `GET /api/debug/gm_decisions?session_id=<campaign_id>&limit=N` — działa (uwaga: param nazywa się `session_id`, ale to **campaign_id**)
- Konta testowe: hasło `demo` (lub `AI_TEST_PLAYER_PASSWORD`)
- `ai_test_agent/` — Node.js v18.19.1 + Playwright PoC działa (9A-3)
- `window.AITestOTel` — console stub w frontendzie (9A-3)
- Tabela wiadomości: `campaign_turns`
- Baseline backend: **156 passed**
- Kluczowe lekcje z 9A-3:
  - seed, auth, kampanie — ta sama baza (`AI_TEST_DB_PATH=/data/ai_gm.db`)
  - właściciel kampanii = `ai_test_player` (nie GM)
  - `AI_TEST_CONFIG_PATH=/data/ai_test_config.json`
  - po zmianach backendu: rebuild + restart kontenera backendu

**Ustalenia z REV 1:**
- Stub GM: `generate_chat_stream()` w `backend/app/services/llm_service.py`, wywoływany przez `POST /api/campaigns/{campaign_id}/turns/stream` (normalny endpoint gry) — brak osobnego stub-endpointu
- Format GM response: SSE stream (`data: token\n\n` … `data: [DONE]\n\n`), błędy jako `data: [ERROR] ...`
- Backend LLM: własny `httpx`, Ollama lub OpenAI (brak openai/anthropic/langchain paczkowych SDK)
- `httpx` w `backend/requirements.txt` (zduplikowany — warto później posprzatać, nie teraz)
- Nie ma `GET /api/debug/campaign_turns` — surowe tury są w `gm_decisions` (j.w.)
- `player_state` JSON: `character_id`, `location`, `hp`, `max_hp`, `gold_gp`, `inventory: [{item_key, slot}]`, `quests_completed`, `quests_active`
- Node.js na `.61`: **v18.19.1** (LTS, OK dla Playwright)
- Klucze LLM: poza repo, opcjonalne; Ollama wymaga osobnej usługi dostępnej z Dockera
- **`AI_AGENT_STUB=1` jako start: zaakceptowane**
- **HTTP + SSE serwis (Opcja B): zaakceptowane** jako docelowy kształt; CLI wrapper opcjonalnie

---

## Implementacja (REV 2 — zatwierdzona i zrealizowana)

### Zrealizowana struktura

```
ai_test_agent/
  agent/
    run.js              ← CLI entry point
    orchestrator.js     ← główna pętla observe→decide→act
    snapshot.js         ← Debug API + DOM
    llm_client.js       ← AI_AGENT_STUB=1 | OpenAI-compatible
    action_executor.js  ← Playwright executor + oczekiwanie na GM
    action_validator.js ← guard + detekcja pętli
    models.js           ← stałe: ACTION_TYPES, timeouty
    server.js           ← Express: POST /agent/run (SSE) + GET /agent/scenarios
  scenarios/
    cheat_location.json ← PoC + `campaign_label`
  tests/
    test_validator.js   ← 6 testów (node:test)
    test_snapshot.js    ← 3 testy (node:test)
  playwright/helpers/
    game_state.js       ← backendUrl() per-request, re-export loadConfig
```

Npm scripts: `test:agent`, `agent:run`, `agent:server`. Zależność dodana: `express`.

---

## Kryteria ukończenia

- [x] Pętla `observe→decide→act` kończy scenariusz `cheat_location.json` w stub mode bez crashu
- [x] Action Validator odrzuca: puste wiadomości, nieznane screeny/selektory, JS injection, pętle (3 powtórzenia)
- [x] Fallback na `wait_for_gm_response` gdy LLM zwraca invalid JSON
- [x] Każdy krok emituje log przez `window.AITestOTel.logAction()` (page.evaluate)
- [x] `POST /agent/run` zwraca SSE stream z krokami na żywo, kończy się `{done: true}`
- [x] `GET /agent/scenarios` zwraca listę dostępnych scenariuszy
- [x] Testy jednostkowe 9/9 ✅
- [x] Backend: ≥156 passed (brak regresji)
- [x] Nagranie wideo z sesji dostępne w `playwright-results/videos/`

---

## Odpowiedzi Cursora (REV 1)

```
### 1. LLM — istniejąca integracja

- AI_TEST_STUB_LLM=1 (wymaga też AI_TEST_MODE=1): stub jest w `backend/app/services/llm_service.py`,
  funkcja `generate_chat_stream()`. Generator od razu zwraca strumień SSE identyczny jak prawdziwy LLM:
  `data: <tekst>\n\n`, potem `data: [DONE]\n\n`. Wywoływany przez `POST /api/campaigns/{campaign_id}/turns/stream`.

- Normalny tryb gry: Ollama lub OpenAI przez własny httpx — brak paczek openai/anthropic/langchain w requirements.

- Format GM response: SSE stream, chunki `data: ...\n\n`, zakończenie `data: [DONE]\n\n`,
  błędy jako `data: [ERROR] ...`.

- httpx: tak, w backend/requirements.txt (zduplikowany). aiohttp: nie.

### 2. Debug endpointy

- GET /api/debug/player_state?character_id=  — ✅
  JSON: character_id, location, hp, max_hp, gold_gp, inventory:[{item_key,slot}],
        quests_completed:[str], quests_active:[str]

- GET /api/debug/gm_decisions?session_id=<campaign_id>&limit=  — ✅
  UWAGA: session_id to campaign_id (mysląca nazwa parametru).
  JSON: { session_id, decisions:[{timestamp, type, reason, is_legal,
          details:{turn_number, route, user_text, assistant_text}}] }
  Heurystyki type/reason w kodzie, nie pełna prawda reguł gry.

- GET /api/debug/validation_flags?test_run_id=  — ✅

- GET /api/debug/settings/feature_flags  — ✅ { "ai_test_mode": bool }

- Brak dedykowanego GET /api/debug/campaign_turns.

### 3. Architektura agenta

- Node.js w ai_test_agent/ — zaakceptowane.
- Python venv dla agenta: nie potrzebny.
- Node.js na .61: v18.19.1

### 4. Klucze LLM

- Klucze poza repo. Ollama wymaga osobnej usługi z Dockera.
- AI_AGENT_STUB=1 na start: zaakceptowane.

### 5. HTTP vs CLI

- Opcja B (HTTP + SSE): zaakceptowane. CLI jako opcjonalny wrapper.
```

---

## Co zostało zrobione *(Cursor, 2026-04-27)*

```
Data: 2026-04-27 | Commit: fa16d19 | Branch: develop

- Struktura `ai_test_agent/agent/`: models.js, action_validator.js, snapshot.js
  (Debug API + gm_decisions + DOM), llm_client.js (AI_AGENT_STUB=1 +
  OpenAI-compatible opcjonalnie), action_executor.js (send + wait na odpowiedź
  GM + open_screen/click), orchestrator.js, server.js (Express, POST /agent/run
  → SSE, GET /agent/scenarios), run.js (CLI).

- scenarios/cheat_location.json + pole campaign_label ("AI Test Campaign").

- playwright/helpers/game_state.js: backendUrl() per-request, re-export loadConfig.

- action_executor: po `send` oczekiwanie na odpowiedź HTTP /turns/stream;
  wait_for_gm_response szuka .message.assistant lub .message.error w #chat
  (odporność na błąd/sukces).

- orchestrator: reset env, login, wybór kampanii, kreator postaci, czekanie na
  #send-btn enabled, AITestOTel.logAction co krok, wideo w playwright-results/videos/.

- Testy: node --test — 9/9 (6 validator + 3 snapshot). npm: test:agent, agent:run,
  agent:server; zależność express.

- Weryfikacja na .61: node agent/run.js ze stubem kończy (stub_completed, exit 1
  bo success: false — zgodnie ze stub). pytest backend 156 passed.

- Docker: brak zmian w obrazie backendu, nie potrzeba rebuildu.
```

---

## Notatki po implementacji *(Perplexity, 2026-04-27)*

```
[ZAMKNIĖCIE 9A-4]

Wynik: PASS — wszystkie 9 kryteriów spełnione.

Rzeczywista implementacja vs. REV 2 — rozbieżności i dobre decyzje:

1. action_executor — wait_for_gm_response szuka `.message.assistant`
   lub `.message.error` (nie tylko .assistant jak w REV 2). Lepsza
   wersja — obsługuje scenariusz gdzie GM zwraca błąd (np. stub_llm
   w trybie error). Zachować w 9A-5.

2. `campaign_label` w cheat_location.json — dobre rozszerzenie względem
   REV 2 (hardcoded string 'AI Test Campaign' w orchestratorze zastąpiony
   polem ze scenariusza). Wzorzec do powielenia w kolejnych scenariuszach.

3. backendUrl() w game_state.js jako funkcja (nie stała) — prawidłowe,
   pozwala na nadpisanie przez env w czasie runtime bez restartu.

4. exit code 1 przy success: false — poprawne zachowanie CLI. CI pipeline
   może od razu użyć exit code do określenia czy test wykrył exploit
   (exit 0 = exploit found, exit 1 = nie znalazł).

Otwarte ryzyko na 9A-5:
- selector 'textarea#input' i '#send-btn' mogą nie być prawidłowe
  w aktualnym frontendzie — do weryfikacji podczas integracji z Admin Panel.
- wait_for_gm_response: timeout 30s może być za długi dla scenariuszy
  z AI_TEST_STUB_LLM=1 (stub odpowiada błyskawicznie). Rozważyć
  skrócenie do 8s w stub mode w 9A-5.
- Jeden test scenariusz (cheat_location) nie wystarczy do smoke suite
  w CI. 9A-5 powinno dodać co najmniej 1 scenariusz pozytywny (legal path)
  jako baseline — agent wykonuje legalną akcję, success: true.

Następny krok: 9A-5 Admin Panel UI — chat do planowania testów +
podgląd screenshot stream + step log.
```

---

## Następny krok: 9A-5 Admin Panel Test Runner UI

Prompt: `docs/Phase_9A_AI_Test_Agent/9A-5_admin_panel_ui.md`
