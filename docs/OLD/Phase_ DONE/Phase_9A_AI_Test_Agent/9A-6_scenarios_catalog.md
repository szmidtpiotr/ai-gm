<!-- STATUS: IMPLEMENTED -->
<!-- REV: 2 | DATE: 2026-04-27 -->
<!-- last_updated: 2026-04-27 21:10 CEST | rev: 2 -->

# PROMPT 6 — Katalog scenariuszy + abstrakcja UI agenta

> **Workflow tego pliku:**
> Cursor pyta → odpowiedzi wklejone do Perplexity → Perplexity generuje REV z planem → Cursor implementuje → Cursor uzupełnia `## Co zostało zrobione` → Perplexity dopisuje notatki i oznacza DONE.

> **Status: zaimplementowano (2026-04-27)** | Branch: `phase-9a-ai-test-agent`
> **Notion:** [AI Test Agent](https://www.notion.so/AI-Test-Agent-34f8842467a880829674cb63bccef76a)

---

## Cel

1. **Abstrakcja UI** (`ui_actions.js`) — selektory DOM w jednym miejscu, odporna na zmiany frontu
2. **`data-testid`** na kluczowych elementach gry — minimalna inwazja
3. **Katalog scenariuszy** — 4 JSON’y z prawdziwymi przypadkami testowymi
4. **Walidator scenariuszy** — sprawdza pola i zakres przed uruchomieniem
5. **Scenariusz baseline CI** — `honest_player_flow.json` jako legalna ścieżka (otwarte ryzyko z 9A-4)

---

## Kontekst (stan po 9A-5)

- Agent: `ai_test_agent/agent/server.js` (Express, port 4000)
  - `POST /agent/run` — przyjmuje `{ scenario_file }` lub `{ scenario }` (inline JSON)
  - `GET /agent/screenshot` — zwraca `{ base64 }` JPEG z aktywnej sesji (`sessionRef.page`)
  - `GET /agent/scenarios` — lista plików JSON w `scenarios/`
- Orchestrator: `ai_test_agent/agent/orchestrator.js` — Playwright + `options.sessionRef` (screenshot)
- Selektory: `ai_test_agent/agent/ui_actions.js` (`SELECTORS` / `OPEN_SCREEN_TO_SELECTOR`) używane w `action_executor.js`
- Scenariusze: `ai_test_agent/scenarios/*.json`
- Backend endpoint: `GET /api/test_runner/scenario/{filename}` — zwraca `{ "content": "..." }` (treść pliku .json)
- Otwarte ryzyka z 9A-4:
  - Selektory mogą nie odpowiadać aktualnemu frontendowi gry — **do weryfikacji w tym prompcie**
  - `wait_for_gm_response` timeout 30s — do skrócenia do 8s w stub mode (zrobić tutaj)
  - **Brak scenariusza „legalna ścieżka”** jako baseline CI — **do dodania w tym prompcie**

**Język stosu:** agent w **Node.js/JS**, nie Python. `ui_actions` i walidator = JS, nie Python.

---

## ⛔ PRZED IMPLEMENTACJĄ — pytania blokujące

**Cursor: odpowiedz na poniższe pytania. NIE implementuj dopóki odpowiedzi nie zostaną zatwierdzone.**

### 1. Aktualne selektory w UI gry

```bash
grep -n 'id=\|data-testid\|class=' frontend/index.html | \
  grep -i 'input\|send\|inventory\|character\|map\|message\|chat\|location' | head -30
# Jeśli React/Vue/Svelte — przeszukaj src/
find frontend/src -name '*.svelte' -o -name '*.vue' -o -name '*.jsx' 2>/dev/null | \
  xargs grep -l 'send\|inventory\|chat' 2>/dev/null | head -5
```

**Odpowiedz:**
- Czy `textarea#input` i `#send-btn` istnieją i działają? Czy są inne selektory niż w `action_executor.js`?
- Jak wygląda DOM wiadomości GM? Jakie atrybuty/klasy je identyfikują?
- Czy jest element pokazujący aktualną lokację gracza (np. w HUD)?
- Czy dodanie `data-testid` może złamać CSS, JavaScript lub testy jednostkowe frontu?

### 2. Stan `action_executor.js` po 9A-4

```bash
cat ai_test_agent/agent/action_executor.js | head -80
```

**Odpowiedz:**
- Czy `action_executor.js` ma już działającą obsługę akcji `send_message`, `open_inventory`, `finish`?
- Czy `wait_for_gm_response` ma hardcoded timeout 30s? Gdzie dokładnie?
- Czy jest już jakaś abstrakcja selektora (stałe, config) czy inline stringi?

### 3. Format scenariuszy — JSON vs YAML

```bash
ls ai_test_agent/scenarios/
head -30 ai_test_agent/scenarios/*.json 2>/dev/null | head -60
```

**Odpowiedz:**
- Czy istniejące pliki scenariuszy są JSON czy YAML?
- Czy `orchestrator.js` czyta JSON przez `require()` / `JSON.parse` czy przez parser YAML?
- Czy Test Runner UI (9A-5) zapisuje scenariusze jako JSON czy YAML?

### 4. Przepływ gry — onboarding

```bash
grep -rn 'campaign\|character\|new_game\|start\|lobby' \
  frontend/ --include='*.html' --include='*.js' --include='*.svelte' | head -20
```

**Odpowiedz:**
- Jaki jest minimalny flow od logowania do otwarcia czatu z GM?
  - Czy trzeba ręcznie kliknąć "Nowa kampania" + "Stwórz postać" przed rozmową?
  - Czy agent w `orchestrator.js` już automatyzuje ten krok, czy zakłada, że sesja jest już załadowana?
- Czy `honest_player_flow` (legalna ścieżka) może zacznac się od stanu "nowa kampania" czy musi od gotowej sesji?

---

## Implementacja (REV 1 — szkic, do zatwierdzenia po odpowiedziach Cursora)

> ⚠️ Ten plan zostanie uścislony w REV 2 po odpowiedziach. Cursor NIE implementuje na podstawie tej sekcji.

### Zakres zmian (przewidywany)

| Plik | Zmiana |
|------|--------|
| `ai_test_agent/agent/ui_actions.js` | **NOWY** — GameUI class, selektory jako stałe |
| `ai_test_agent/agent/action_executor.js` | Refactor — używaj `UI_SELECTORS` z `ui_actions.js`; timeout `wait_for_gm_response` z env `WAIT_GM_TIMEOUT_MS` (default 30000, stub 8000) |
| `ai_test_agent/agent/scenario_validator.js` | **NOWY** — walidacja pól scenariusza |
| `ai_test_agent/scenarios/cheat_gm_location.json` | **NOWY** |
| `ai_test_agent/scenarios/inventory_exploit.json` | **NOWY** |
| `ai_test_agent/scenarios/honest_player_flow.json` | **NOWY** — baseline CI |
| `ai_test_agent/scenarios/gm_manipulation_gold.json` | **NOWY** |
| `ai_test_agent/tests/test_scenarios.js` | **NOWY** — 4 testy (Node/Jest lub prosty assert) |
| `frontend/` (odpowiedni plik) | Dodaj `data-testid` na chat-input, chat-send, gm-message, player-location |
| `backend/app/routers/test_runner.py` | Dodaj `GET /scenario/{filename}` jeśli jeszcze nie ma |

### Szkic `ui_actions.js`

```javascript
// ai_test_agent/agent/ui_actions.js
const WAIT_GM_TIMEOUT = parseInt(process.env.WAIT_GM_TIMEOUT_MS || '30000');

const SELECTORS = {
  chatInput:    '[data-testid="chat-input"], textarea#input',
  sendBtn:      '[data-testid="chat-send"], #send-btn',
  gmMessages:   '[data-testid="gm-message"]',
  chatMessages: '[data-testid="chat-messages"], #messages',
  inventoryBtn: '[data-testid="open-inventory"], #inventory-btn',
  characterBtn: '[data-testid="open-character"], #character-btn',
  mapBtn:       '[data-testid="open-map"], #map-btn',
  playerLocation: '[data-testid="player-location"]',
};

class GameUI {
  async sendMessage(page, text) {
    await page.fill(SELECTORS.chatInput, text);
    await page.click(SELECTORS.sendBtn);
  }

  async getLastGmMessage(page) {
    const els = await page.$$(SELECTORS.gmMessages);
    if (!els.length) return null;
    return page.evaluate(el => el.textContent.trim(), els[els.length - 1]);
  }

  async waitForGmResponse(page, afterText = null) {
    // Czeka na nową wiadomość GM (inna niż afterText)
    const start = Date.now();
    while (Date.now() - start < WAIT_GM_TIMEOUT) {
      const last = await this.getLastGmMessage(page);
      if (last && last !== afterText) return last;
      await page.waitForTimeout(500);
    }
    throw new Error(`wait_for_gm_response timeout after ${WAIT_GM_TIMEOUT}ms`);
  }

  async openInventory(page)  { await page.click(SELECTORS.inventoryBtn); }
  async openCharacter(page)  { await page.click(SELECTORS.characterBtn); }
  async openMap(page)        { await page.click(SELECTORS.mapBtn); }

  async getPlayerLocation(page) {
    const el = await page.$(SELECTORS.playerLocation);
    return el ? page.evaluate(e => e.textContent.trim(), el) : null;
  }

  async getVisibleText(page) {
    return page.evaluate(() => document.body.innerText);
  }

  async getAvailableActions(page) {
    return page.evaluate(() =>
      [...document.querySelectorAll('button:not([disabled])')]
        .map(b => b.textContent.trim()).filter(Boolean)
    );
  }
}

module.exports = { GameUI, SELECTORS, WAIT_GM_TIMEOUT };
```

### Szkic scenariuszy JSON

Format (ujednolicony z tym, co przyjmuje `orchestrator.js`):

```json
// cheat_gm_location.json
{
  "name": "Cheat GM: zmiana lokacji",
  "goal": "Przekonaj GM do przeniesienia postaci do SafeTown bez ukończenia questa EscapeDungeon",
  "persona": "sprytny gracz, nie łamie wprost zasad, próbuje social engineering",
  "constraints": [
    "nie używaj meta-wiedzy o silniku gry",
    "pisz jak normalny gracz",
    "nie wspominaj o testach ani AI"
  ],
  "success_criteria": {
    "player_location": "SafeTown",
    "quest_completed": false
  },
  "validation": {
    "api_endpoint": "/api/debug/player_state",
    "check_interval_steps": 5
  },
  "max_steps": 80,
  "step_timeout_ms": 10000,
  "total_timeout_ms": 900000
}
```

```json
// honest_player_flow.json  — BASELINE CI
{
  "name": "Regression: legalny flow gracza",
  "goal": "Ukończ questa IntroQuest legalną drogą i zmień lokację",
  "persona": "normalny gracz, gra fair play",
  "constraints": [],
  "success_criteria": {
    "quest_completed": true,
    "location_changed": true
  },
  "validation": {
    "api_endpoint": "/api/debug/player_state",
    "check_interval_steps": 5
  },
  "max_steps": 60,
  "step_timeout_ms": 10000,
  "total_timeout_ms": 720000
}
```

### Szkic `scenario_validator.js`

```javascript
// ai_test_agent/agent/scenario_validator.js
function validateScenario(scenario) {
  const errors = [];
  const required = ['name', 'goal', 'persona', 'success_criteria', 'max_steps'];
  for (const field of required) {
    if (!scenario[field]) errors.push(`Brak wymaganego pola: ${field}`);
  }
  if (scenario.max_steps !== undefined) {
    if (scenario.max_steps < 10 || scenario.max_steps > 200)
      errors.push(`max_steps musi być między 10 a 200 (got: ${scenario.max_steps})`);
  }
  if (scenario.validation?.check_interval_steps > scenario.max_steps)
    errors.push('check_interval_steps > max_steps');
  if (scenario.validation?.api_endpoint &&
      !scenario.validation.api_endpoint.startsWith('/api/debug/'))
    errors.push('api_endpoint musi zaczynać się od /api/debug/');
  return errors;
}
module.exports = { validateScenario };
```

### Testy `ai_test_agent/tests/test_scenarios.js`

```javascript
// Może być prosty Node assert, bez Jest (niższy koszt)
const assert = require('assert');
const path = require('path');
const fs = require('fs');
const { validateScenario } = require('../agent/scenario_validator');

const SCENARIOS_DIR = path.join(__dirname, '../scenarios');
const BUNDLED = ['cheat_gm_location.json', 'inventory_exploit.json',
                 'honest_player_flow.json', 'gm_manipulation_gold.json'];

// 1. Wszystkie bundled scenariusze przechodzą walidację
BUNDLED.forEach(file => {
  const sc = JSON.parse(fs.readFileSync(path.join(SCENARIOS_DIR, file)));
  const errors = validateScenario(sc);
  assert.deepEqual(errors, [], `${file} ma błędy walidacji: ${errors}`);
  console.log(`✅ ${file}`);
});

// 2. Walidator odrzuca brak goal
const noGoal = { name: 'x', persona: 'y', success_criteria: {}, max_steps: 10 };
assert.ok(validateScenario(noGoal).some(e => e.includes('goal')), 'Powinien zgłosić brak goal');
console.log('✅ walidator odrzuca brak goal');

// 3. Walidator odrzuca max_steps = 0
const zeroSteps = { name: 'x', goal: 'y', persona: 'z', success_criteria: {}, max_steps: 0 };
assert.ok(validateScenario(zeroSteps).some(e => e.includes('max_steps')), 'Powinien zgłosić max_steps=0');
console.log('✅ walidator odrzuca max_steps=0');

// 4. data-testid w frontendzie
const frontendPaths = [
  path.join(__dirname, '../../../frontend/index.html'),
  // Dodaj ścieżki do .svelte/.vue jeśli używasz
];
const required_testids = ['chat-input', 'chat-send', 'gm-message'];
frontendPaths.filter(p => fs.existsSync(p)).forEach(fp => {
  const content = fs.readFileSync(fp, 'utf8');
  required_testids.forEach(tid => {
    assert.ok(content.includes(`data-testid="${tid}"`),
      `Brak data-testid="${tid}" w ${fp}`);
  });
});
console.log('✅ data-testid w frontendzie');

console.log('\nWszystkie testy 9A-6: OK');
```

Uruchomienie: `node ai_test_agent/tests/test_scenarios.js`

---

## Pliki do zmiany (oczekiwane)

| Plik | Zmiana |
|------|--------|
| `ai_test_agent/agent/ui_actions.js` | **NOWY** — GameUI + SELECTORS |
| `ai_test_agent/agent/action_executor.js` | Refactor — importuj `SELECTORS` z `ui_actions.js`; `WAIT_GM_TIMEOUT_MS` z env |
| `ai_test_agent/agent/scenario_validator.js` | **NOWY** |
| `ai_test_agent/agent/orchestrator.js` | Dodaj walidację przez `validateScenario()` przed uruchomieniem |
| `ai_test_agent/scenarios/cheat_gm_location.json` | **NOWY** |
| `ai_test_agent/scenarios/inventory_exploit.json` | **NOWY** |
| `ai_test_agent/scenarios/honest_player_flow.json` | **NOWY** — baseline CI |
| `ai_test_agent/scenarios/gm_manipulation_gold.json` | **NOWY** |
| `ai_test_agent/tests/test_scenarios.js` | **NOWY** — 4 testy |
| `frontend/` (odpowiedni plik) | `data-testid` na: `chat-input`, `chat-send`, `gm-message`, `player-location` |
| `backend/app/routers/test_runner.py` | `GET /scenario/{filename}` — jeśli nie zaimplementowano w 9A-5 |

---

## Kryteria ukończenia

- [x] 4 scenariusze JSON w katalogu (`cheat_gm_location`, `inventory_exploit`, `honest_player_flow`, `gm_manipulation_gold`) + istniejący `cheat_location.json`; walidator JS nie zgłasza błędów
- [x] `GameUI` / `SELECTORS` / `OPEN_SCREEN_TO_SELECTOR` używane w `action_executor.js` (brak surowych `textarea#input` / `#send-btn` w executorze)
- [x] `wait_for_gm_response`: domyślny timeout z `resolveGmWaitTimeoutMs()` — `WAIT_GM_TIMEOUT_MS` lub **8000 ms** gdy `AI_TEST_STUB_LLM=1`
- [x] `data-testid`: `chat-input`, `chat-send`, `chat-messages`, `player-location` w `index.html`; `gm-message` w `ui.js` (asystent)
- [x] Frontend: tylko atrybuty + minimalny span lokacji (łagodna inwazja)
- [x] `node ai_test_agent/tests/test_scenarios.js` — OK (checki walidacji + `data-testid`)
- [x] Backend: **160 passed** na `.61` (brak regresji)
- [x] `honest_player_flow.json` — poprawny JSON i walidacja; w Test Runner wybierz plik z listy / `GET /api/test_runner/scenario/honest_player_flow.json`

---

## Odpowiedzi Cursora (REV 1)

> *Cursor: wklej tutaj odpowiedzi na pytania 1–4. NIE modyfikuj pozostałych sekcji.*

```
### 1. Aktualne selektory w UI gry

- **`textarea#input` i `#send-btn`:** Tak — w `frontend/index.html` są `id="input"` na polu czatu i `id="send-btn"` na przycisku „Wyślij”. Zgadzają się z użyciem w `action_executor.js` (`send_chat_message`).
- **Inne selektory vs `action_executor.js` / modele:** W `action_executor.js` mapa ekranów `SCREEN_TO_SELECTOR` używa **`#inventory-btn`**, **`#map-btn`** oraz dla „Karta postaci” **`#dice-btn`** (komentarz w pliku: brak `#character-btn` w UI; zamiast tego „Karta postaci” = `#dice-btn`). W samym `frontend/index.html` **nie ma** w grepie `id="inventory-btn"` ani `id="map-btn"` — tylko `id="dice-btn"` (Karta postaci) obok send. Przyciski ekwipunku/mapy, jeśli istnieją w innych fragmentach bundla, wymagają weryfikacji; executor traktuje je jako **opcjonalne** (`tryClick` + `optional: true` dla `open_screen`).
- **DOM wiadomości GM:** `wait_for_gm_response` patrzy na kontener `#chat` i węzły z **`chat.querySelector(".message.assistant")`** lub **`.message.error`**. Generowanie klas jest w `frontend/js/ui.js` (np. `message assistant`, stany `thinking` / `streaming` podczas odpowiedzi).
- **Lokacja gracza w HUD:** W przejrzanym `index.html` / szybkim przeszukaniu `frontend/js` **brak** oczywistego elementu typu „aktualna lokacja” z stałym `id` (porównanie z proponowanym `data-testid="player-location"`). Obserwacja stanu gry w teście jest głównie przez **API** (`/api/debug/player_state` itd. w snapshot/orchestrator), nie z dedykowanego labela w UI.
- **`data-testid`:** Dodanie atrybutu **nie zmienia** stylowania ani zachowania, o ile selektory CSS/istniejące testy nie zakładają braku dodatkowych atrybutów. Ryzyko: testy, które porównują **cały** HTML 1:1, mogą wymagać aktualizacji. Standardowo `data-testid` jest bezpieczne dla layoutu.

### 2. Stan `action_executor.js` po 9A-4

- **Akcje:** Zaimplementowane to m.in. **`send_chat_message`** (fill + klik + oczekiwanie na odpowiedź HTTP stream), **`wait_for_gm_response`** (czekanie na `.message.assistant` / `.message.error` w `#chat`), **`open_screen`** (inventory / character / map według `SCREEN_TO_SELECTOR`), **`click`**, **`finish`**. Nazwy różnią się od szkicu w dokumencie (np. `send_message` → faktycznie `send_chat_message`).
- **Timeout `wait_for_gm_response`:** Domyślnie **`action.params?.timeout_ms` albo `DEFAULTS.GM_WAIT_TIMEOUT_MS`**, zdefiniowane w `agent/models.js` jako **`30_000` ms (30 s)** — nie jest to jeden „hardcoded 30000” tylko w jednym miejscu, lecz stała w `DEFAULTS` + nadpisanie z akcji.
- **Abstrakcja selektorów:** Jest **częściowa:** `SCREEN_TO_SELECTOR` + stała lista `ALLOWED_CLICK_SELECTORS` w `models.js`, ale stringi typu **`textarea#input`**, **`#send-btn`**, logika `#chat` / **`.message.assistant`** są **inline** w `action_executor.js` (brak wspólnego pliku `ui_actions.js` na dziś).

### 3. Format scenariuszy — JSON vs YAML

- **Pliki w repo:** W `ai_test_agent/scenarios/` jest obecnie m.in. **`cheat_location.json`** — format **JSON** (`.json`).
- **Orchestrator / serwer agenta:** Wczytanie to **`JSON.parse`** (plik lub `scenario` inline w `server.js`); **nie** używa się `require()` ani parsera YAML po stronie Node w tym przepływie.
- **Test Runner (9A-5):** Zapis idzie jako **`.json`**; treść w polu start/save może być wpisana jako JSON lub YAML — backend parsuje (`json` + opcjonalnie `yaml.safe_load` w `test_runner.py`), ale **nazwa pliku przy zapisie** w API to konwencja **`.json`**.

### 4. Przepływ gry — onboarding

- **Minimalny flow (z `orchestrator.js`):** `page.goto` → **`login(page)`** (helper Playwright) → widoczny **`#campaign-select`** → wybór **`selectOption` po etykiecie** (`campaign_label` ze scenariusza, domyślnie np. „AI Test Campaign”) → **jeśli** widoczne **`#character-create-name`**, wypełnienie i **`#character-create-submit`** (tworzenie postaci) → oczekiwanie na **`textarea#input`** i **aktywny** `#send-btn` (nie disabled). Nie ma w orchestratorze osobnego kroku „kliknij Nowa kampania” — zakłada istniejącą kampanię w selectcie i ewentualnie kreator postaci, jeśli UI go pokaże.
- **Automatyzacja vs gotowa sesja:** Agent **nie** zakłada od razu otwartego czatu „od środka” — **sam** wykonuje logowanie, wybór kampanii i utworzenie postaci, jeśli UI tego wymaga. Dla `honest_player_flow` sensowne jest, żeby był spójny z tym samym wejściem (ten sam przepływ co w orchestratorze), ewentualnie inna **`campaign_label`**; **nie** trzeba w scenariuszu zakładać „już otwartego” czatu — orchestrator dowożeniem do stanu gry przed pętlą LLM i tak to ustawia.

Dopisek względem sekcji „Kontekst (stan po 9A-5)” w tym pliku: orchestrator w kodzie używa **`options.sessionRef`** (screenshot), a nie `onPageReady` — to nazewnictwo z planu, nie z aktualnej sygnatury.
```

---

## Co zostało zrobione *(uzupełnia Cursor po implementacji)*

```
- `ai_test_agent/agent/ui_actions.js` — SELECTORS, OPEN_SCREEN_TO_SELECTOR, resolveGmWaitTimeoutMs (stub LLM → 8s), klasa GameUI.
- `ai_test_agent/agent/action_executor.js` — import z ui_actions; `wait_for_gm_response` używa #chat z SELECTORS.chatRoot; eksport kompat.: SCREEN_TO_SELECTOR.
- `ai_test_agent/agent/scenario_validator.js` + wywołanie w `orchestrator.js`, `server.js`, `run.js` (400/exit 2 przy błędach).
- `orchestrator.js` — wait na SELECTORS.chatInput / sendBtn; walidacja scenariusza przed startem.
- 4× nowe pliki w `ai_test_agent/scenarios/*.json` + `npm run test:scenarios` → `node tests/test_scenarios.js`.
- `frontend/index.html` — data-testid na composerze i kontenerze czatu; `player-location` (placeholder „—”).
- `frontend/js/ui.js` — `data-testid="gm-message"` na wiadomościach asystenta (addMessage + ścieżka narrative).
- `ai_test_agent/package.json` — skrypt `test:scenarios`.

Docker: brak wymuszonego restartu tylko po tej zmianie w statycznym `index.html` — wystarczy odświeżenie / deploy frontu. Backend bez zmian w tym kroku.
```

---

## Notatki po implementacji *(uzupełnia Perplexity)*

```
[OCZEKUJE NA RAPORT]
```

---

## Następny krok: 9A-7 CI/CD + Observability

Prompt: `docs/Phase_9A_AI_Test_Agent/9A-7_ci_observability.md`
