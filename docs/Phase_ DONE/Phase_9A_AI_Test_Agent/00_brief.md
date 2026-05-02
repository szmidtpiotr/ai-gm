<!-- STATUS: DONE -->
<!-- PHASE: 9A | DATE_START: — | DATE_END: — -->

# Phase 9A — AI Test Agent · Brief archiwalny

> **README:** zsynchronizowany (rev 2) — faza **DONE**; szczegóły per task w plikach `9A-*.md`.

---

## 1. Cel fazy

Automatyczne testowanie gry przez **agenta AI + Playwright**: Debug API do inspekcji stanu, osobne środowisko testowe, scenariusze YAML, serwis agenta (observe → decide → act), UI Test Runnera w panelu admin, observability.

---

## 2. Zakres (taski)

| Task | Opis |
|------|------|
| 9A-1 | Debug API |
| 9A-2 | Środoćowisko testowe (baza, flagi, konta) |
| 9A-3 | Playwright PoC |
| 9A-4 | AI Agent Service |
| 9A-5 | Admin — Test Runner UI |
| 9A-6 | Katalog scenariuszy |
| 9A-7 | CI / observability |

---

## 3. Osiągnięcia (podsumowanie)

- Możliwość uruchamiania scenariuszy testowych przeciwko DEV z poziomu dokumentowanego stacku (`ai_test_agent`, kontenery w `docker-compose.dev.yml`).
- Debug / walidacja stanu gry pod automatyczne asercje (szczegóły w promptach DONE).

---

## 4. Konserwacja dokumentacji

Przy zmianach w stacku testowym aktualizuj odpowiedni `9A-*.md` oraz — jeśli zmienia się zakres fazy — ten README / `00_brief.md`.

---

## Analiza po fazie *(Perplexity)*

### Ocena implementacji
- **Zgodność z Briefem:** ✅ pełna — 7 tasków pokrywa pełny stack testowy od Debug API po CI
- **Pokrycie testami:** faza sama w sobie *jest* infrastrukturą testową; scenariusze YAML definiują pokrycie funkcjonalne gry
- **Ryzyka i dług techniczny:**
  - Agent AI (observe → decide → act) zależy od jakości LLM — zmiany modelu (`gemma4:e4b` / `llama3.1:8b`) mogą wpłynąć na deterministyczność scenariuszy
  - Playwright PoC — nie full suite; dalsze rozszerzenie wymaga nakładu przy każdej zmianie UI
  - `AI_TEST_MODE=1` flaga — krytyczne żeby nigdy nie była aktywna na PROD
  - Debug API (`debug.py` router) dostarcza wrażliwych danych — guard `AI_TEST_MODE` musi być sprawdzany w każdym review

### Decyzje przeniesione do kolejnych faz
- Rozszerzenie scenariuszy YAML o flow sklepu (8F) i dialogów NPC (Phase 9)
- Integracja z CI/CD pipeline — kandydat na Phase 14 (stabilizacja)
- Możliwość parametryzacji modelu LLM per scenariusz — ułatwi debugowanie regresji modelu

### STATUS: DONE
