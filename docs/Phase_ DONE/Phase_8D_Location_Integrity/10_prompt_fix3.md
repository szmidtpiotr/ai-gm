<!-- STATUS: DONE -->
<!-- DATE: 2026-04-28 -->

# PROMPT 10 — Fix: Tryb A blokada (pre-LLM hook + UI strip)

Projekt ai-gm, branch: `phase-8d-location-integrity`

---

## Problemy do naprawienia

### PROBLEM 1 — Quickfix: strip `[LOCATION_BLOCKED]` z UI

W `frontend/js/ui.js` w funkcji `parseGMResponse()`:
Po wyciągnięciu `parsed.narrative` dodaj:

```js
narrative = narrative.replace(/\s*\[LOCATION_BLOCKED:[^\]]*\]/g, '').trim();
```

Bump cache w `index.html`: `ui.js?v=8d-location-debug-3`

### PROBLEM 2 — Architektoniczny: LLM generuje narrację ZANIM dostaje blokadę

Zły flow:
```
user → LLM generuje narrację ruchu → hook blokuje → appenduje [LOCATION_BLOCKED] do gotowego tekstu
```

Poprawny flow (Tryb A):
```
user → hook sprawdza intent z user_text → jeśli BLOCKED → wstrzykuje ostrzeżenie do system context
      → LLM generuje odmowę narracyjną → brak artefaktów
```

W `backend/app/api/turns.py` dla stream flow — hook location działa na `user_text` PRZED wysyłką do LLM.

---

## Co zostało zrobione

- **PROBLEM 1:** `frontend/js/ui.js` — `parseGMResponse()` usuwa znaczniki `[LOCATION_BLOCKED:…]` z narracji (`stripLocationBlocked`); `frontend/index.html` — `ui.js?v=8d-location-debug-3`.
- **PROBLEM 2:** `backend/app/api/turns.py` — `_inject_pre_llm_unknown_location_denial()` wywoływana po `build_narrative_messages` w `create_turn_stream`:
  - przy `location_auto_create_enabled=0` i blokadzie typu „niez\u0105ana lokalizacja” dopisywany jest blok `[SYSTEM: …]` do pierwszego komunikatu `system`
  - stream wywołuje `_process_location_intent(..., skip_post_process=True)` — nie dopisuje `[LOCATION_BLOCKED]` ani nie aktualizuje `current_location_id`
- Tryb **B** (`location_auto_create_enabled=1`): bez zmian (post-processing na pełnym `full_raw`)
- Testy: `test_pre_llm_unknown_injection_sets_system_block_and_skips_post_hook` w `test_phase8d_location_hook.py` — **10 passed**
- Commit: [`09bbe01`](https://github.com/szmidtpiotr/ai-gm/commit/09bbe01) na `origin/phase-8d-location-integrity`

---

## Notatki po implementacji *(Perplexity)*

### Status
✅ DONE — 2026-04-28

### Co to zmienia architektonicznie

Przed tym fixem `[LOCATION_BLOCKED]` był appendowany do gotowej narracji LLM — LLM nie wiedział o blokadzie i opisywał ruch do miejsca które nie istnieje. Teraz w Trybie A:
- blokada trafia do `system` **przed** wywołaniem LLM
- LLM sam generuje narracyjną odmowę (mgła, strzeżnik, przepaść...)
- `current_location_id` nie zmienia się
- UI nie widzi żadnych artefaktów

### Znane ograniczenie
Pre-LLM hook dodany tylko dla **stream flow** (`create_turn_stream`). Non-stream flow (`run_narrative_turn`) nadal używa post-processingu. Przy wyłączonym streamingu Tryb A może wciąż pokazać artefakty — do naprawy jeśli non-stream będzie używany.

### Wymagany rebuild DEV
```bash
docker compose -f docker-compose.dev.yml up -d --build backend frontend
```

### Następny krok
Po rebuild i weryfikacji manualnej Trybu A → commit hotfixów (working tree) → merge `phase-8d-location-integrity` → `main` → Phase 8F Economy.
