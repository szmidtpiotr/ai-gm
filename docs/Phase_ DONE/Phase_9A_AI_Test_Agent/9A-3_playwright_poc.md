<!-- STATUS: IN PROGRESS -->
<!-- REV: 2 | DATE: 2026-04-27 -->
<!-- last_updated: 2026-04-27 17:09 CEST | rev: 5 -->

# PROMPT 3 — Playwright PoC + OTel RUM (Phase 9A)

> **Workflow tego pliku:**
> REV 1 → Cursor odpowiada na pytania blokujące (NIE implementuje) → Ty wklejasz odpowiedzi do Perplexity → Perplexity generuje REV 2 → Cursor implementuje → Cursor uzupełnia `## Co zostało zrobione` → Perplexity dopisuje notatki i oznacza DONE.

> **Status: 🟡 IN PROGRESS** | Branch: `phase-9a-ai-test-agent`
> **Notion:** [AI Test Agent](https://www.notion.so/AI-Test-Agent-34f8842467a880829674cb63bccef76a)

---

## Cel

Działający Playwright PoC wykonujący pełny ręczny flow gracza (login → kampania → postać → wiadomość do GM) bez AI, z włączoną instrumentacją OpenTelemetry JS w frontendzie.

---

## Kontekst techniczny

**Znane fakty z 9A-1 i 9A-2:**
- Backend DEV: `http://192.168.1.61:8100`, healthcheck `GET /api/healthz` → `{"status":"ok"}`
- Frontend DEV: `http://192.168.1.61:3002` (nginx, kontener `frontend`, `3002:80`)
- `POST /api/debug/reset_test_env` — istnieje, resetuje stan testowy
- `GET /api/debug/player_state?character_id=Y` — istnieje (9A-1)
- `backend/ai_test_config.json` — zawiera `player_id`, `character_id`, `campaign_id`, `player_username`, `gm_username`
- Hasło kont testowych (seed): `demo` (lub `AI_TEST_PLAYER_PASSWORD` w Playwright)
- Baseline testów backend: **153 passed**

**Ustalenia z REV 1:**
- Brak jakichkolwiek E2E (żadnych spec.js/playwright.config)
- Frontend: vanilla JS, jeden `index.html`, SPA-like przez overlaye — brak URL/hash routing
- Stabilne selektory: `#player-username`, `#player-password`, `#player-login-btn`, `#campaign-select`, `textarea#input`, `#send-btn`
- Kreator postaci (fallback gdy brak postaci): `#character-create-name`, `#character-create-submit`
- Brak OTel, brak `/api/otel/traces`, brak `/api/debug/settings/feature_flags`
- Katalog `ai_test_agent/` nie istnieje — do stworzenia
- Root `package.json` bez workspaces — niskie ryzyko konfliktu
- CI: tylko `workflow_dispatch` na produkcję, brak jobów node/test w CI — niskie ryzyko

---

## Implementacja (REV 2 — zatwierdzona)

> **Cursor: implementuj zgodnie z poniższymi krokami. Po zakończeniu uzupełnij sekcję `## Co zostało zrobione`.**

### Krok 1 — Struktura katalogów

Utwórz następującą strukturę:

```
ai_test_agent/
  playwright/
    poc_manual_flow.spec.js
    helpers/
      auth.js
      game_state.js
    playwright.config.js
  package.json
  .gitignore             ← dodaj: node_modules/, playwright-results/, screenshots/
```

`package.json` (`ai_test_agent/`):
```json
{
  "name": "ai-test-agent",
  "private": true,
  "scripts": {
    "test:poc": "playwright test playwright/poc_manual_flow.spec.js",
    "test:all": "playwright test"
  },
  "devDependencies": {
    "@playwright/test": "^1.44.0"
  }
}
```

### Krok 2 — Konfiguracja (`playwright.config.js`)

```javascript
// ai_test_agent/playwright/playwright.config.js
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './',
  timeout: 120_000,
  use: {
    headless: process.env.HEADED !== '1',
    baseURL: process.env.BASE_URL || 'http://192.168.1.61:3002',
    video: 'on',
    screenshot: 'only-on-failure',
  },
  outputDir: '../playwright-results',
  reporter: [['html', { outputFolder: '../playwright-report' }], ['list']],
});
```

### Krok 3 — Helper: login (`helpers/auth.js`)

```javascript
// ai_test_agent/playwright/helpers/auth.js
const path = require('path');

function loadConfig() {
  const cfgPath = path.resolve(__dirname, '../../../backend/ai_test_config.json');
  return require(cfgPath);
}

async function login(page) {
  const cfg = loadConfig();
  await page.fill('#player-username', cfg.player_username);
  await page.fill('#player-password', 'ai_test_password_2026');
  await page.click('#player-login-btn');
  // Poczekaj aż overlay logowania zniknie (lub na pojawienie się #campaign-select)
  await page.waitForSelector('#campaign-select', { timeout: 10_000 });
}

module.exports = { login, loadConfig };
```

### Krok 4 — Helper: stan gry (`helpers/game_state.js`)

```javascript
// ai_test_agent/playwright/helpers/game_state.js
const BACKEND_URL = process.env.BACKEND_URL || 'http://192.168.1.61:8100';

async function resetTestEnv() {
  const res = await fetch(`${BACKEND_URL}/api/debug/reset_test_env`, { method: 'POST' });
  const data = await res.json();
  if (!data.reset) throw new Error('reset_test_env failed: ' + JSON.stringify(data));
  return data;
}

async function getPlayerState(characterId) {
  const res = await fetch(`${BACKEND_URL}/api/debug/player_state?character_id=${characterId}`);
  return res.json();
}

module.exports = { resetTestEnv, getPlayerState };
```

### Krok 5 — Główny PoC (`poc_manual_flow.spec.js`)

```javascript
// ai_test_agent/playwright/poc_manual_flow.spec.js
const { test, expect } = require('@playwright/test');
const { login, loadConfig } = require('./helpers/auth');
const { resetTestEnv, getPlayerState } = require('./helpers/game_state');
const path = require('path');
const fs = require('fs');

let cfg;

test.beforeAll(async () => {
  cfg = loadConfig();
  const result = await resetTestEnv();
  expect(result.reset).toBe(true);
});

test('poc_manual_flow: login → kampania → chat → odpowiedź GM', async ({ page }) => {
  // 1. Otwórz frontend
  await page.goto('/');

  // 2. Login
  await login(page);

  // 3. Wybierz kampanię
  // Jeśli #campaign-select to <select>:
  await page.selectOption('#campaign-select', { label: 'AI Test Campaign' });
  // Jeśli to inny element — dostosuj do rzeczywistego widoku

  // 4. Wybierz postać lub utwórz jeśli nie istnieje
  const hasCharacter = await page.$('#send-btn').then(el => !!el).catch(() => false);
  if (!hasCharacter) {
    await page.fill('#character-create-name', 'TestPlayer');
    await page.click('#character-create-submit');
    await page.waitForSelector('#send-btn', { timeout: 10_000 });
  }

  // 5. Wyślij wiadomość do GM
  await page.fill('textarea#input', 'Czy możesz mi opisać otoczenie?');
  await page.click('#send-btn');

  // 6. Poczekaj na odpowiedź GM (nowy element w #chat, max 30s)
  const chatLocator = page.locator('#chat .message').last();
  await chatLocator.waitFor({ state: 'visible', timeout: 30_000 });

  // 7. Pobierz stan z Debug API
  const state = await getPlayerState(cfg.character_id);
  expect(state.location).toBeTruthy();

  // 8. Screenshot
  const screenshotsDir = path.resolve(__dirname, '../screenshots');
  fs.mkdirSync(screenshotsDir, { recursive: true });
  await page.screenshot({ path: path.join(screenshotsDir, 'poc_step_8.png') });
});
```

⚠️ Po pierwszym uruchomieniu dostosuj selektory krok 3 (kampania) i 4 (postać) do rzeczywistego zachowania UI. Jeśli `#campaign-select` to `<select>` — użyj `selectOption`. Jeśli to lista/button — zamień na `click`.

### Krok 6 — Feature flag endpoint (`backend/app/routers/debug.py`)

Dodaj do istniejącego pliku:

```python
@router.get("/settings/feature_flags")
def feature_flags():
    """Publiczny endpoint — zwraca flagi feature dla frontendu."""
    return {"ai_test_mode": os.getenv("AI_TEST_MODE") == "1"}
```

Bez auth. Endpoint musi być dostępny jako `GET /api/debug/settings/feature_flags`.

### Krok 7 — OTel RUM w frontendzie

**Warunkowe ładowanie w `frontend/index.html`** (w sekcji `<head>`, przed innymi skryptami JS):

```html
<!-- OTel RUM — warunkowo, tylko gdy ai_test_mode=true -->
<script>
  (function() {
    fetch('/api/debug/settings/feature_flags')
      .then(function(r) { return r.json(); })
      .then(function(flags) {
        if (flags && flags.ai_test_mode) {
          var s = document.createElement('script');
          s.src = '/js/otel_init.js';
          s.defer = true;
          document.head.appendChild(s);
        }
      })
      .catch(function() { /* cicho ignoruj — nie blokuj normalnej gry */ });
  })();
</script>
```

**Nowy plik `frontend/js/otel_init.js`:**

```javascript
// OTel RUM — ładowany tylko gdy AI_TEST_MODE=1
// CDN: @opentelemetry/sdk-trace-web + exporter-trace-otlp-http
(function() {
  // Fallback: jeśli SDK nie jest dostępny, loguj do konsoli
  var TEST_RUN_ID = window.__AI_TEST_RUN_ID || 'manual-' + Date.now();

  function logSpan(name, attrs) {
    console.log('[OTel]', name, Object.assign({ test_run_id: TEST_RUN_ID }, attrs));
  }

  // Public API do użycia przez inne moduły JS gry
  window.AITestOTel = {
    logAction: function(action, attrs) {
      logSpan('AI_ACTION', Object.assign({ action: action }, attrs));
    },
    logGMResponse: function(content, tags) {
      logSpan('GM_RESPONSE', { content: content, tags: tags });
    },
    logLocationChange: function(from, to, reason, isLegal) {
      logSpan('LOCATION_CHANGE', {
        old_location: from,
        new_location: to,
        reason: reason,
        is_legal: isLegal
      });
    }
  };

  console.log('[OTel] AI Test RUM zainicjalizowany. test_run_id:', TEST_RUN_ID);
})();
```

⚠️ To jest implementacja console-based (bez pełnego SDK). Pełny OTel SDK z OTLP HTTP exporterem zostanie dodany w 9A-7 (CI + observability), gdy infrastruktura collector będzie gotowa.

### Krok 8 — Testy backendu (`backend/tests/test_phase9a_playwright_poc.py`)

```python
# test_feature_flags_endpoint_ai_test_mode_true
#   → ustaw AI_TEST_MODE=1, GET /api/debug/settings/feature_flags → {"ai_test_mode": true}

# test_feature_flags_endpoint_ai_test_mode_false
#   → ustaw AI_TEST_MODE=0, GET /api/debug/settings/feature_flags → {"ai_test_mode": false}
```

Wzorzec: `mock.patch.dict(os.environ, {"AI_TEST_MODE": "1"})` — zgodny z innymi testami.

### Krok 9 — Uruchomienie PoC

```bash
# Instalacja
cd ai_test_agent
npm install
npx playwright install chromium

# Uruchomienie PoC
BASE_URL=http://192.168.1.61:3002 \
BACKEND_URL=http://192.168.1.61:8100 \
npx playwright test playwright/poc_manual_flow.spec.js

# Opcjonalnie: z graficznym UI przeglądarki
HEADED=1 BASE_URL=http://192.168.1.61:3002 \
  npx playwright test playwright/poc_manual_flow.spec.js
```

### Krok 10 — Weryfikacja końcowa

```bash
# Backend testy
python3 -m pytest backend/tests/test_phase9a_playwright_poc.py -v
python3 -m pytest backend/tests/ -q  # baseline: ≥153 passed

# Playwright raport
cd ai_test_agent
npx playwright show-report
ls playwright-results/videos/
ls playwright/screenshots/
```

---

## Pliki do zmiany

| Plik | Zmiana |
|------|--------|
| `ai_test_agent/package.json` | **NOWY** |
| `ai_test_agent/.gitignore` | **NOWY** |
| `ai_test_agent/playwright/playwright.config.js` | **NOWY** |
| `ai_test_agent/playwright/poc_manual_flow.spec.js` | **NOWY** |
| `ai_test_agent/playwright/helpers/auth.js` | **NOWY** |
| `ai_test_agent/playwright/helpers/game_state.js` | **NOWY** |
| `frontend/index.html` | Warunkowe ładowanie OTel (w `<head>`) |
| `frontend/js/otel_init.js` | **NOWY** — console-based OTel stub |
| `backend/app/routers/debug.py` | Dodaj `GET /api/debug/settings/feature_flags` |
| `backend/tests/test_phase9a_playwright_poc.py` | **NOWY** — 2 testy |

---

## Kryteria ukończenia

- [ ] PoC przechodzi pełny flow (login → kampania → chat → odpowiedź GM) bez błędów
- [ ] `GET /api/debug/player_state` zwraca niepustą `location` po interakcji
- [ ] Nagranie wideo dostępne w `playwright-results/videos/`
- [ ] Screenshot `playwright/screenshots/poc_step_8.png` zapisany
- [x] OTel `otel_init.js` ładuje się warunkowo (tylko `ai_test_mode=true`), normalny gracz nie widzi zmian
- [x] `GET /api/debug/settings/feature_flags` zwraca `{"ai_test_mode": bool}`
- [x] Testy backend 2/2 ✅ na 192.168.1.61
- [x] Baseline backend: ≥153 passed

---

## Odpowiedzi Cursora (REV 1)

```
1) Istniejące testy E2E i struktura frontend
- Playwright/Puppeteer/E2E:
  - brak jakichkolwiek plików `*.spec.js`, `*.spec.ts`, `playwright.config.*`
  - brak śladów `playwright|puppeteer|cypress` w kodzie.
- `ai_test_agent/`:
  - katalog obecnie nie istnieje.
- Frontend:
  - główny plik to pojedynczy `frontend/index.html` (vanilla JS, wiele `<script src="./js/...">`)
  - układ SPA-like: widoki jako overlaye/modale i dynamiczny render, nie osobne strony HTML.
- Serwowanie frontendu:
  - osobny kontener `frontend` (nginx) w `docker-compose.dev.yml`,
  - port DEV: `3002` na hoście (`3002:80`), backend osobno na `8100`.

2) Routing i URL-e
- Login / kampanie / chat:
  - nie ma osobnych URL/hash dla widoków; wszystko pod tym samym adresem frontendu.
  - login to overlay `#auth-overlay` z kontrolkami `#player-username`, `#player-password`, `#player-login-btn`.
  - kampanie wybierane przez `#campaign-select`.
  - chat to kontener `#chat`, input `#input` (textarea), wysyłka `#send-btn`.
- Routing:
  - brak hash routing i brak History API.
  - nawigacja przez stan aplikacji i pokazywanie/ukrywanie sekcji.
- Port frontendu DEV: `3002`.

3) Selektory UI
- Brak `data-testid` w aktualnym frontendzie.
- Stabilne `id`:
  - login: `#player-username`, `#player-password`, `#player-login-btn`
  - kampania: `#campaign-select`
  - czat: `#chat`, input: `textarea#input`, send: `#send-btn`
  - kreator postaci: `#character-create-name`, `#character-create-submit`

4) OTel i telemetria
- Brak OTel SDK, brak `@opentelemetry` w zależnościach.
- Brak endpointu `/api/otel/traces`.
- Brak `/api/debug/settings/feature_flags`.

5) Ryzyko build
- Root `package.json` bez workspaces — niskie ryzyko konfliktu.
- CI: tylko `workflow_dispatch` na produkcję, brak jobów node/test — niskie ryzyko.
```

---

## Co zostało zrobione *(uzupełnia Cursor po implementacji)*

> *Cursor: uzupełnij po zakończeniu implementacji REV 2.*

```
Data: 2026-04-27

1) Implementacja Playwright PoC
- Dodano nową strukturę:
  - `ai_test_agent/package.json`
  - `ai_test_agent/.gitignore`
  - `ai_test_agent/playwright/playwright.config.js`
  - `ai_test_agent/playwright/poc_manual_flow.spec.js`
  - `ai_test_agent/playwright/helpers/auth.js`
  - `ai_test_agent/playwright/helpers/game_state.js`
- Scenariusz PoC zawiera:
  - reset test env przed testem,
  - login test userem,
  - wybór kampanii,
  - wysłanie wiadomości,
  - walidację przez Debug API,
  - screenshot do `playwright/screenshots/poc_step_8.png`.

2) Backend: feature flags dla frontendu
- W `backend/app/routers/debug.py` dodano:
  - `GET /api/debug/settings/feature_flags`
  - odpowiedź: `{"ai_test_mode": bool}`.

3) Frontend: warunkowe OTel
- W `frontend/index.html` dodano warunkowy fetch do:
  - `/api/debug/settings/feature_flags`
- Gdy `ai_test_mode=true`, ładowany jest:
  - `frontend/js/otel_init.js`.
- Dodano `frontend/js/otel_init.js` (console-based OTel stub, public API `window.AITestOTel`).

4) Testy backendowe
- Dodano:
  - `backend/tests/test_phase9a_playwright_poc.py`
    - `test_feature_flags_endpoint_ai_test_mode_true`
    - `test_feature_flags_endpoint_ai_test_mode_false`
    - `test_llm_stub_stream_for_playwright` (stub SSE bez prawdziwego LLM)
- Wyniki na `.61`:
  - `python3 -m pytest -q backend/tests/test_phase9a_playwright_poc.py` → `3 passed`

5) Runtime DEV + spójność DB (login / kampanie / debug)
- `docker-compose.dev.yml`: `AI_TEST_DB_PATH` domyślnie `/data/ai_gm.db` (ten sam plik co `auth` i surowe SQLite w `campaigns`), opcjonalnie `AI_TEST_STUB_LLM`, `AI_TEST_CONFIG_PATH=/data/ai_test_config.json`.
- `backend/app/api/auth.py`: logowanie przez `resolve_db_path()` zamiast sztywnego `/data/ai_gm.db`.
- `backend/scripts/seed_ai_test_env.py`: właściciel kampanii = gracz testowy (UI filtruje po `owner_user_id`); poprawiona ścieżka zapisu `ai_test_config.json` (katalog `backend/` / w kontenerze `/app/`).
- Stub LLM: `backend/app/services/llm_service.py` — przy `AI_TEST_MODE=1` i `AI_TEST_STUB_LLM=1` strumień zwraca krótką odpowiedź + `[DONE]` bez Ollamy (Playwright na hostach bez LLM).

6) Playwright PoC — zielony przebieg na `.61`
- `auth.js`: `waitForFunction` na `auth-overlay`; wybór pliku konfiguracji: `AI_TEST_CONFIG_PATH` lub `data-dev/ai_test_config.json` lub `backend/ai_test_config.json`.
- `poc_manual_flow.spec.js`: oczekiwanie na widoczną odpowiedź `.message.assistant:not(.is-archived-bubble)` (błędy LLM są archiwalne i ukryte).
- Uruchomienie (przykład na serwerze DEV):  
  `AI_TEST_MODE=1 AI_TEST_STUB_LLM=1 docker compose -f docker-compose.dev.yml up -d backend`, potem seed w kontenerze z `AI_TEST_DB_PATH` i `AI_TEST_CONFIG_PATH` jak w compose, następnie:  
  `cd ai_test_agent && BASE_URL=http://127.0.0.1:3002 BACKEND_URL=http://127.0.0.1:8100 npx playwright test --config=playwright/playwright.config.js playwright/poc_manual_flow.spec.js` → **1 passed**.

7) Dodatkowe hardening resetu test-env
- W `backend/app/routers/debug.py` w `reset_test_env` dodano bezpieczne fallbacki dla brakujących tabel (`debug_validation_log`, `campaign_turns`).
```

---

## Notatki po implementacji *(uzupełnia Perplexity)*

> *Perplexity: uzupełnij po otrzymaniu raportu Cursora. Zmień STATUS na DONE.*

```
[OCZEKUJE NA RAPORT]
```

---

## Następny krok: 9A-4 AI Agent Service

Prompt: `docs/Phase_9A_AI_Test_Agent/9A-4_ai_agent_service.md`
