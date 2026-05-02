<!-- STATUS: IMPLEMENTED -->
<!-- REV: 2 | DATE: 2026-04-27 -->
<!-- last_updated: 2026-04-27 20:25 CEST | rev: 2 -->

# PROMPT 5 — Admin Panel: Test Runner UI

> **Workflow tego pliku:**
> REV 1 → Cursor odpowiada na pytania blokujące (NIE implementuje) → Ty wklejasz odpowiedzi do Perplexity → Perplexity generuje REV 2 → Cursor implementuje → Cursor uzupełnia `## Co zostało zrobione` → Perplexity dopisuje notatki i oznacza DONE.

> **Status: Zaimplementowano (2026-04-27)** | Branch: `phase-9a-ai-test-agent`
> **Notion:** [AI Test Agent](https://www.notion.so/AI-Test-Agent-34f8842467a880829674cb63bccef76a)

---

## Cel

Nowa sekcja **Test Runner** w Admin Panelu z:
1. **Czatem do planowania** — opisujesz AI jaki test chcesz, AI generuje YAML scenariusza
2. **Podglądem + edytorem YAML** — możesz poprawiać przed uruchomieniem i zapisać
3. **Live view** — screenshot stream + step log podczas trwania testu
4. **Wynikiem** — status PASS/FAIL + link do raportu po zakończeniu

---

## Kontekst (stan po 9A-1 → 9A-4)

- Backend DEV: `http://192.168.1.61:8100` | Frontend DEV: `http://192.168.1.61:3002`
- Agent serwis: `http://192.168.1.61:4000` (`ai_test_agent/agent/server.js`, Express)
  - `POST /agent/run` → SSE stream kroków (`{step, action, snapshot, timestamp}`), kończy `{done: true, ...}`
  - `GET /agent/scenarios` → lista plików JSON ze scenariuszami
- Scenariusze: `ai_test_agent/scenarios/*.json`
- `AI_TEST_MODE=1` wymagane dla endpointów debug
- `AI_TEST_STUB_LLM=1` — backend stub GM (nie stub agenta)
- `AI_AGENT_STUB=1` — agent stub (deterministyczna sekwencja bez LLM)
- Selektory potwierdzone w action_executor.js: `textarea#input`, `#send-btn`, `#inventory-btn`, `#character-btn`, `#map-btn`
- Otwarte ryzyka z 9A-4:
  - Selektory mogą nie odpowiadać aktualnemu frontendowi gry — do weryfikacji
  - `wait_for_gm_response` timeout 30s — rozważyć skrócenie do 8s w stub mode
  - Brak scenariusza „legalna ścieżka” jako baseline CI — do dodania w 9A-6

---

## ⛔ PRZED IMPLEMENTACJĄ — pytania blokujące

**Cursor: odpowiedz na poniższe pytania. NIE implementuj dopóki odpowiedzi nie zostaną zatwierdzone przez Perplexity.**

### 1. Struktura Admin Panelu

```bash
head -100 frontend/admin_panel/index.html
grep -n 'data-section\|wireSidebarNav\|maybeInit\|sidebar-btn\|section-panel' \
  frontend/admin_panel/index.html | head -30
ls frontend/admin_panel/sections/
```

**Odpowiedz:**
- Jak dodawane są nowe sekcje? Pattern sidebar + panel (np. `data-section`, `wireSidebarNav`, inne)?
- Ile sekcji istnieje, jakie nazwy?
- Czy istnieje plik CSS dedykowany dla Admin Panelu (`layout.css` lub inny)?
- Czy dodanie nowej sekcji może złamać istniejące (np. przez działanie `querySelectorAll`/`forEach`)?

### 2. Połączenie Admin Panel → zewnętrzne serwisy

```bash
grep -rn 'EventSource\|WebSocket\|fetch\|SSE' \
  frontend/admin_panel/ --include="*.js" --include="*.html" | head -20
grep -n 'AGENT_URL\|BACKEND_URL\|4000\|test_runner' \
  frontend/admin_panel/ -r | head -20
```

**Odpowiedz:**
- Czy Admin Panel ma już połączenia SSE / WebSocket?
- Czy Admin Panel może wołać `http://192.168.1.61:4000` (agent) bezpośrednio z przeglądarki (CORS?), czy musi przez proxy backendu (`:8100`)?
- Czy istnieją już jakiekolwiek endpointy `/api/test_runner/...` w backendzie?

### 3. LLM dla generatora scenariuszy

```bash
grep -rn 'generate_chat_stream\|llm_service\|AI_TEST_STUB_LLM' \
  backend/app/ --include="*.py" | head -20
```

**Odpowiedz:**
- Czy `llm_service.generate_chat_stream()` może być użyta bezpośrednio do generowania YAML scenariuszy (inny system prompt), czy potrzebna jest osobna funkcja?
- Czy przy `AI_TEST_STUB_LLM=1` możemy go użyć do stub odpowiedzi czatu planistycznego, czy będzie konflikt?
- Czy backend ma dostęp do Ollamy / OpenAI bez `AI_TEST_STUB_LLM=1`?

### 4. Screenshot z Playwright

```bash
grep -rn 'screenshot\|recordVideo\|page.screenshot' \
  ai_test_agent/ --include="*.js" | head -20
ls playwright-results/ 2>/dev/null || echo 'brak'
```

**Odpowiedz:**
- Jak aktualnie robione są screenshoty podczas testu? Czy `orchestrator.js` zapisuje je do pliku co krok, czy tylko wideo na końcu?
- Czy agent serwis (`:4000`) może zwracać `GET /agent/screenshot` z aktualnym zrzutem jako JPEG base64?
- Czy jest ryzyko kolizji podczas screenshotu (page.screenshot() blokuje Playwright na chwilę)?

### 5. Uruchomienie agenta z backendu vs. z frontu

**Odpowiedz:**
- Architektura: Admin Panel (przeglądarka) woła agenta przez:
  - **Opcja A** — bezpośrednio `POST http://192.168.1.61:4000/agent/run` (prosto, wymaga CORS na agencie)
  - **Opcja B** — przez proxy w backendzie: `POST /api/test_runner/start` → backend woła `localhost:4000` (brak CORS issue, dodatkowa warstwa)
  - Perplexity rekomenduje **Opcję B** (proxy przez backend) — spójne z resztą Admin Panelu, CORS kontrolowany, łatwe logowanie po stronie backendu
  - Jeśli nie masz preferencji — napisz to wprost

---

## Implementacja (REV 1 — szkic, do zatwierdzenia po odpowiedziach Cursora)

> ⚠️ Ten plan zostanie uścisłony w REV 2. Cursor NIE implementuje na podstawie tej sekcji.

### Zakładany layout sekcji Test Runner

```
+----------------------------+-----------------------------+
|   LEWY PANEL (40%)         |   PRAWY PANEL (60%)         |
|                            |                             |
|  💬 CHAT z AI              |  📄 YAML Preview (edytowalny)  |
|  +----------------------+  |  +-------------------------+|
|  | Historia rozmowy     |  |  | name: "..."             ||
|  | (scrollowalna)       |  |  | goal: "..."             ||
|  +----------------------+  |  | ...                     ||
|  [ Opisz test... ] [Wyślij]|  +--[ Uruchom ▶ ][ Zapisz]+|
|                            |                             |
|                            |  🖥️ Screenshot stream       |
|                            |  +-------------------------+|
|                            |  | [live img 1500ms]       ||
|                            |  +-------------------------+|
|                            |                             |
|                            |  📋 Step Log (SSE)          |
|                            |  ✅ Krok 1: login            |
|                            |  ✅ Krok 2: kampania         |
|                            |  🔄 Krok 3: wysyłam...      |
|                            |  Status: RUNNING | 3/30    |
+----------------------------+-----------------------------+
```

### Backend — `backend/app/routers/test_runner.py`

Nowy router (aktywny tylko przy `AI_TEST_MODE=1`):

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/api/test_runner/generate_scenario` | POST | Chat z LLM → YAML scenariusza |
| `/api/test_runner/start` | POST | Uruchom agenta (proxy do `:4000/agent/run`), zwraca `run_id` |
| `/api/test_runner/status/{run_id}` | GET | Aktualny status testu (`IDLE/RUNNING/DONE/ERROR`) |
| `/api/test_runner/stream/{run_id}` | GET | SSE proxy kroków z agenta |
| `/api/test_runner/screenshot/{run_id}` | GET | Aktualny screenshot z agenta (JPEG base64) |
| `/api/test_runner/save_scenario` | POST | Zapisz YAML do `ai_test_agent/scenarios/` |
| `/api/test_runner/scenarios` | GET | Lista plików JSON w katalogu scenariuszy |

**System prompt dla generate_scenario:**
```
Jesteś asystentem do pisania testów AI dla gry RPG.
Kiedy użytkownik opisze test, generujesz YAML w formacie:
  name, goal, persona, constraints[], success_criteria{}, max_steps, timeouts.
Najpierw zadaj pytania precyzujące (persona, agresywność, oczekiwany wynik).
Gdy masz kompletne dane, zwróć YAML w bloku ```yaml ... ``` i ustaw ready: true w JSON response.
Format odpowiedzi JSON: {"reply": str, "yaml": str|null, "ready": bool}
```

### Frontend — `frontend/admin_panel/sections/test_runner.js`

Kluczowe żyłki:

```javascript
// 1. Chat planistyczny
async function sendPlanningMessage(text, history) {
  const res = await fetch('/api/test_runner/generate_scenario', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: text, history })
  });
  const data = await res.json();
  appendChatMessage('ai', data.reply);
  if (data.yaml) setYamlPreview(data.yaml);
  if (data.ready) enableRunButton();
}

// 2. Uruchomienie testu
async function startTest(yamlContent) {
  const res = await fetch('/api/test_runner/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ yaml: yamlContent })
  });
  const { run_id } = await res.json();
  startScreenshotPolling(run_id);  // co 1500ms
  startStepLogSSE(run_id);         // EventSource
}

// 3. Screenshot polling (aktywny tylko przy RUNNING)
function startScreenshotPolling(runId) {
  const img = document.getElementById('live-screenshot');
  const interval = setInterval(async () => {
    const res = await fetch(`/api/test_runner/screenshot/${runId}`);
    if (!res.ok) return;
    const { base64 } = await res.json();
    img.src = `data:image/jpeg;base64,${base64}`;
    if (currentStatus !== 'RUNNING') clearInterval(interval);
  }, 1500);
}

// 4. Step Log przez SSE
function startStepLogSSE(runId) {
  const es = new EventSource(`/api/test_runner/stream/${runId}`);
  es.onmessage = (e) => {
    const step = JSON.parse(e.data);
    if (step.done) {
      es.close();
      showFinalResult(step);
      return;
    }
    appendStepLog(step);
  };
}
```

### Agent serwis — dopiski do `server.js`

Dodaj endpoint screenshotu (jeśli page jest aktywna):
```javascript
// GET /agent/screenshot
// Zwraca { base64: string } lub 404 gdy brak aktywnej sesji
app.get('/agent/screenshot', async (_req, res) => {
  if (!activePage) return res.status(404).json({ error: 'no active session' });
  const buf = await activePage.screenshot({ type: 'jpeg', quality: 70 });
  res.json({ base64: buf.toString('base64') });
});
```

Wymaga przechowania `activePage` w module-level zmiennej podczas trwania testu.

### Testy — `backend/tests/test_phase9a_admin_ui.py`

```python
# test_generate_scenario_returns_yaml  — mock LLM, sprawdz czy zwraca {reply, yaml, ready}
# test_start_run_returns_run_id        — mock agent serwisu, sprawdz UUID w response
# test_status_endpoint_returns_running — po starcie status = RUNNING
# test_scenarios_list_returns_saved    — po save_scenario, GET /scenarios zawiera nowy
```

---

## Pliki do zmiany (oczekiwane)

| Plik | Zmiana |
|------|--------|
| `frontend/admin_panel/index.html` | Przycisk sidebar + panel `data-section="test-runner"` |
| `frontend/admin_panel/sections/test_runner.js` | **NOWY** — chat, YAML preview, screenshot, step log |
| `frontend/admin_panel/layout.css` | Style split layout, chat, YAML preview, step log |
| `backend/app/routers/test_runner.py` | **NOWY** — 7 endpointów |
| `backend/app/main.py` | `include_router(test_runner_router)` przy `AI_TEST_MODE=1` |
| `backend/tests/test_phase9a_admin_ui.py` | **NOWY** — 4 testy |
| `ai_test_agent/agent/server.js` | Dodaj `GET /agent/screenshot` (activePage) |

---

## Kryteria ukończenia

- [x] Sekcja "Test Runner" widoczna w Admin Panelu sidebar, nie psuje innych sekcji
- [x] Chat z AI generuje YAML scenariusza (stub `AI_TEST_STUB_SCENARIO=1` + runda doprecyzowania; pełny LLM przez `generate_scenario` + `LLM_*`)
- [x] YAML/JSON edytowalny przed uruchomieniem
- [x] Przycisk [Uruchom] startuje test i zwraca `run_id` (proxy do agenta)
- [x] Screenshot polling co ~1500ms podczas RUNNING
- [x] Step Log przez EventSource (SSE) na `/api/test_runner/stream/{run_id}?token=…`
- [x] [Zapisz] + lista + wczytanie pliku (backend: `save_scenario`, `scenarios`, `scenario/{filename}` → katalog `AI_TEST_SCENARIOS_DIR` / repo `ai_test_agent/scenarios/`)
- [x] Istniejące sekcje Admin Panelu — ten sam wzorzec `maybeInit*`, bez zmiany logiki innych paneli
- [x] Backend: 4 testy w `test_phase9a_admin_ui.py`; pełny suite: **160 passed** na `.61` (2026-04-27)

---

## Odpowiedzi Cursora (REV 1)

> *Cursor: wklej tutaj odpowiedzi na pytania 1–5. NIE modyfikuj pozostałych sekcji.*

```
### 1. Struktura Admin Panelu

- **Wzorzec:** sidebar `#sidebar-nav` — przyciski `<button data-section="…">` + w `<section class="sections">` pusty panel `<div class="section-panel" data-section="…" aria-busy="true">`. `wireSidebarNav()` (`index.html`) nasłuchuje klików, przełącza `.active` na przyciskach i panelach (`panels.forEach` + `panel.dataset.section === selected`). Inicjacja sekcji jest **leniwa:** osobne funkcje `maybeInitGameDesign`, `maybeInitAccounts`, `maybeInitTechnical`, `maybeInitConfig`, `maybeInitUiSettings` — każda dynamicznie `import()` modułu z `admin_panel/sections/<nazwa>.js` i woła `init(container)` na właściwym `.section-panel`.
- **Ile sekcji (obecnie 5):** `game-design`, `accounts`, `technical`, `config`, `ui-settings` (etykiety w nav: Game Design, Accounts, Technical, Config, Ustawienia UI).
- **CSS:** jeden główny plik — `frontend/admin_panel/layout.css` (import w `index.html` jako `/admin_panel/layout.css?v=…`).
- **Ryzyko regresji:** niskie przy poprawnym dodaniu pary **przycisk + panel** o tym samym `data-section`. `querySelectorAll(".section-panel")` tylko przełącza widoczność — dodanie kolejnego panelu **nie** psuje logiki, o ile doda się też `maybeInit…` w handlerze kliku (wzorzec z istniejących sekcji). Trzeba dodać flagę typu `testRunnerReady` i wywołanie `maybeInitTestRunner(selected)` obok pozostałych `maybeInit*`.

---

### 2. Połączenie Admin Panel → zewnętrzne serwisy

- **SSE / WebSocket w Admin Panelu:** w `frontend/admin_panel/**` **brak** użycia `EventSource`, `WebSocket` ani `text/event-stream` (przeszukane). Komunikacja to głównie `adminFetch` → JSON do `/api/...` (`shared/api.js`).
- **CORS a agent `:4000`:** panel ładowany z tej samej origini co reszta (np. `http://192.168.1.61:3002`) woła zwykle **`/api/*`** na tym hoście. Bezpośredni `fetch` / `EventSource` do **innego originu** (`:4000`) wymagałby **CORS** na Express agencie. **Rekomendacja: proxy w backendzie** (`POST /api/…` → serwer woła `http://127.0.0.1:4000` lub sieć docker), żeby przeglądarka widziała tylko ten sam host/port co API — spójnie z resztą panelu i bez otwierania CORS na agencie.
- **Endpointy `/api/test_runner/...`:** w repozytorium **nie ma** jeszcze takiego routera — to praca na 9A-5 (dok. REV 1 to przewiduje).

---

### 3. LLM dla generatora scenariuszy

- **`generate_chat_stream()`** jest powiązane ze **strumieniem narracji GM** w grze (SSE, ścieżka tur) — **nie** jest to gotowiec pod „wygeneruj YAML w jednej odpowiedzi JSON”. Do generowania scenariusza sensowniej jest dodać **osobną** funkcję/endpoint (np. `chat.completions` bez streamu albo stream z agregacją do stringa) używającą tych samych **sterowników** co `llm_service` (Ollama/OpenAI przez `httpx`) albo krótkiego wywołania w dedykowanym serwisie.
- **`AI_TEST_STUB_LLM=1`:** globalnie **podmienia** strumień w `generate_chat_stream` — dotyczy **ścieżki gry**, nie nowego endpointu, o ile ten endpoint **nie** woła `generate_chat_stream` w tej samej formie. Generator YAML w nowym kodzie powinien **jawnie** używać innej ścieżki (osobny prompt, ewent. dedykowany stub env) albo trybu bez stuba, żeby nie dostać z góry ustalonej „narracji” zamiast YAML.
- **Ollama / OpenAI bez stuba:** tak — gdy `AI_TEST_STUB_LLM` **nie** jest `1` i skonfigurowany jest provider, backend może wołać prawdziwe API; w DEV może być problem **osiągalności Ollamy** z kontenera — to osobno od designu endpointu.

---

### 4. Screenshot z Playwright

- **Obecny stan (9A-4):** `orchestrator.js` ustawia Playwright **`recordVideo`** do `playwright-results/videos/` — **wideo** po sesji, **brak** zapisu **statycznego screenshota co krok** w agencie. Pojedynczy `page.screenshot` jest w PoC Playwright (`poc_manual_flow.spec.js` — jeden plik na końcu), nie w pętli agenta.
- **GET `/agent/screenshot`:** w **`agent/server.js` obecnie nie ma** tego endpointu (dok. REV 1 proponuje dopisać + `activePage`) — **da się** zwrócić JPEG/base64, jeśli podczas runu trzymany jest handle `page`.
- **Kolizja / blokada:** `page.screenshot()` blokuje wątek automacji na krótki czas; przy pollingu co ~1,5 s ryzyko jest **niskie**, o ile screenshot nie jest wykonywany równolegle z tym samym krytycznym `execute` bez kolejności await.

---

### 5. Uruchomienie agenta z backendu vs. z frontu

- **Rekomendacja: Opcja B — proxy w backendzie** (np. `POST /api/test_runner/start` → backend do `agent` na `127.0.0.1:4000` lub sieć docker, ewent. proxy streamu). Uzasadnienie: ten sam **origin** co `/api` (bez CORS do :4000), spójne **logowanie** i konfiguracja po stronie serwera.
- **Opcja A** (front → `:4000` bezpośrednio) wymaga CORS i osłabia spójność z `adminFetch`.
- **Bez dodatkowej preferencji użytkownika** — przyjmij **B**, zgodnie z rekomendacją Perplexity w dokumencie.
```

---

## Co zostało zrobione *(uzupełnia Cursor po implementacji)*

```
- Router `backend/app/routers/test_runner.py`: generate_scenario (LLM + stub AI_TEST_STUB_SCENARIO), start (proxy SSE do agenta), status, stream, screenshot, save_scenario, scenarios, GET scenario/{filename}. Auth: Bearer lub ?token= (EventSource). Pojedyncza sesja agenta (409 gdy test trwa).
- `main.py`: `test_runner` tylko przy `AI_TEST_MODE=1` (obok debug).
- Agent: `orchestrator.js` — sessionRef do live screenshot; `server.js` — POST /agent/run z ciałem { scenario } inline lub scenario_file, GET /agent/screenshot.
- Admin: `index.html` — sekcja test-runner, `maybeInitTestRunner`, `test_runner.js`, `layout.css?v=26`.
- `requirements.txt`: pyyaml (parsowanie YAML w polu start).
- `docker-compose.dev.yml`: `AI_TEST_AGENT_URL`, `AI_TEST_SCENARIOS_DIR`, volume `ai_test_agent/scenarios` → /data/ai_test_scenarios.
- Testy: `backend/tests/test_phase9a_admin_ui.py` (4 szt., pytest na `.61`).
- Docker: po zmianach w backendu — **rebuild/restart** kontenera `backend`. Agent Node nadal osobno na :4000 (lub zgodnie z `AI_TEST_AGENT_URL`).
```

---

## Notatki po implementacji *(uzupełnia Perplexity)*

```
[OCZEKUJE NA RAPORT]
```

---

## Następny krok: 9A-6 Katalog scenariuszy

Prompt: `docs/Phase_9A_AI_Test_Agent/9A-6_scenarios_catalog.md`
