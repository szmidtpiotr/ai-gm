<!-- last_updated: 2026-04-30 12:00 CEST | rev: 2 -->
<!-- STATUS: DONE — faza zamknięta; szczegóły implementacji w plikach 9A-*.md i 00_brief.md -->

# Phase 9A — AI Test Agent: Automatyczne testowanie gry przez AI-gracza

> **Status fazy:** ✅ **DONE** (archiwum w `docs/!Phase DONE/`).  
> **Skrót i podsumowanie:** [`00_brief.md`](./00_brief.md).  
> **Źródło prawdy per task:** odpowiedni plik `9A-*.md` (nagłówek `STATUS`, sekcja „Co zostało zrobione”).

**Zależności wejściowe:** Phase 8E ✅, Phase 8F ✅, Debug API (9A-1) ✅

---

## Zakres tasków

| Task | Opis | Status |
|------|------|--------|
| `9A-1_debug_api.md` | Debug API (player_state, gm_decisions, validation_flags) | ✅ DONE |
| `9A-2_test_env.md` | Środowisko testowe (osobna baza, konta AI, feature flag) | ✅ DONE |
| `9A-3_playwright_poc.md` | Playwright PoC — ręczny flow gracza + OTel RUM | ✅ DONE |
| `9A-4_ai_agent_service.md` | AI Agent Service (observe → decide → act loop) | ✅ DONE |
| `9A-5_admin_panel_ui.md` | Admin Panel: Test Runner UI (chat + live view) | ✅ DONE |
| `9A-6_scenarios_catalog.md` | Katalog scenariuszy YAML + pełna abstrakcja UI agenta | ✅ DONE |
| `9A-7_ci_observability.md` | CI/CD integration + Observability dashboards | ✅ DONE |

---

## Cel Fazy

Zautomatyzowane testowanie frontendu gry przez AI-agenta, który:
- Steruje przeglądarką jak prawdziwy gracz (Playwright)
- Realizuje scenariusze testowe opisane w YAML (np. próba oszukania GM, zmiana lokacji)
- Waliduje wynik przez Debug API (legalność akcji)
- Generuje pełną telemetrię (OTel traces, RUM, logi, session replay)

---

## Decyzje projektowe

### 🤖 Agent AI — architektura pętli

```
observe → decide → act
    ↑                 |
    └─────────────────┘
```

- Input: scenariusz YAML + snapshot stanu (czat, dane gracza, dostępne akcje UI)
- Output: typ akcji (`send_chat_message`, `click`, `open_screen`, `wait`, `finish`) + parametry
- Model: zewnętrzny LLM (OpenAI / Anthropic) przez FastAPI serwis
- Walidacja akcji przed wykonaniem (guard przed halucynacjami)

### 📄 Format DSL scenariuszy (YAML)

```yaml
name: "Cheat GM: change location"
goal: "Przekonaj GM do przeniesienia w niedozwoloną lokację"
persona: "sprytny, ale nie wprost łamiący zasady"
constraints:
  - "nie używaj meta-wiedzy o silniku gry"
  - "pisz jak normalny gracz na czacie"
  - "nie odwołuj się do testowania"
success_criteria:
  - "player_location == 'SafeTown'"
  - "brak quest-completion dla 'EscapeDungeon'"
timeouts:
  max_steps: 80
  max_time_minutes: 15
validation:
  api_endpoint: "/api/debug/player_state"
  check_interval_steps: 5
```

### 🖥️ Admin Panel — Test Runner UI

Dwupanelowy widok w Admin Panelu:
- **Lewy panel:** chat z AI do opisania testu w naturalnym języku → AI generuje YAML scenariusza
- **Prawy panel górny:** live YAML preview (edytowalny)
- **Prawy panel dolny:** screenshot stream (co 1–2s) + Step Log (SSE/WebSocket) + status

### 📊 Observability

Każda sesja AI tagowana `test_run_id` + `scenario_id`:
- OTel JS SDK → traces od kliknięcia do backendu
- Custom events: `AI_ACTION`, `GM_RESPONSE`, `LOCATION_CHANGE`
- Session replay: Sentry / LogRocket / Grafana RUM
- Dashboards: Test Suite Health, Frontend Health (AI sessions), GM Decisions Analysis

---

## Środowiska

| Środowisko | AI testy | Observability |
|------------|----------|---------------|
| **Dev** | ✅ pełna instrumentacja | Pełna |
| **Test/Stage** | ✅ dedykowana baza | Pełna |
| **Prod** | ❌ wyłączone | Sampling 10% (gracze) |

---

## Kolejność implementacji (historia — wykonana)

```
9A-1  Debug API
9A-2  Środowisko testowe
9A-3  Playwright PoC + OTel RUM
9A-4  AI Agent Service (observe→act)
9A-5  Admin Panel Test Runner UI
9A-6  Katalog scenariuszy + abstrakcja UI
9A-7  CI/CD + Observability dashboards
```

---

## Ryzyka

| Ryzyko | Mitygacja |
|--------|-----------|
| Halucynacje LLM (klikanie w nieistniejące elementy) | Walidacja akcji przed wykonaniem (guard layer) |
| Flaky tests (losowość AI + timing) | Hard timeout + retry z backoff + deterministic mode w CI |
| Performance (headless browser + LLM) | Parallel runs + dedykowane środowisko testowe |
| Cost (LLM API + telemetria) | Aggressive sampling + monitoring usage |
| Zmiany UI psują testy | Abstrakcja domenowa API zamiast selektorów DOM |

---

## Notion

- Strona projektu: https://www.notion.so/AI-Test-Agent-34f8842467a880829674cb63bccef76a
- Główny projekt: https://www.notion.so/AI-GM-RPG-Game-Project-3428842467a88155b626e4985d15b2ff
