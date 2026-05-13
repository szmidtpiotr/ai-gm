<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-29 -->

# PROMPT 14 — 8D-LOC-3: Backend guard — walidacja `location_intent` przed zapisem do DB

> **Workflow:** Perplexity generuje REV 1 z pytaniami blokującymi → Cursor odpowiada → Perplexity generuje REV 2 → Cursor implementuje.
> **Branch roboczy:** `phase-8d-location-integrity`
> **Plik:** `docs/Phase_8D_Location_Integrity/14_prompt_LOC3_backend_guard_location_intent.md`
> **Zależności:**
> - PROMPT 12 (8D-LOC-1) — blok `[LOCATION CONTEXT]` wstrzykiwany ✔️
> - PROMPT 13 (8D-LOC-2) — reguły w system_prompt ✔️
> - **Commit z LOC-1 + LOC-2 wymagany** przed implementacją (krok 0 poniżej)

---

## Cel

Nawet jeśli LLM "oszuka" system prompt — backend blokuje niespójny ruch na poziomie kodu.

Zanim backend zapisze `location_intent` z odpowiedzi GM do DB:
- **`action: move`** — sprawdza czy `target_key` należy do zbioru `known_locations` z LOC-1 (graf sąsiedztwa Opcja A, cap 120). Jeśli nie — odrzuca move, zapisuje do `location_integrity_log`, loguje `location_move_blocked`, zwraca `allowed=False`.
- **`action: create`** — sprawdza czy `parent_key` istnieje w `game_locations`. Jeśli nie — fallback do `key` bieżącej lokacji z sesji.

---

## Kontekst techniczny (potwierdzony przez Cursora)

- **Plik do modyfikacji:** `backend/app/services/location_validator.py`
- **Punkt integracji:** funkcja **`validate_move(session_id, intent, campaign_id=...)`** (~linie 406–554) — guard przed dotychczasową logiką fuzzy match
- **Istniejące API do użycia:**
  - **`_collect_related_location_ids(session_id, db)`** z `location_context_injector.py` — zbiór ID lokacji z grafu sesji (Opcja A z LOC-1)
  - **`log_integrity_violation(session_id, intent, reason)`** — wrapper na `_log_integrity_event()` → INSERT do `location_integrity_log`
  - **`_find_all_locations()`** — globalny katalog; nie zastępujemy, guard jest przed nim
- **Schemat DB:** kolumna `key`, brak `campaign_id`, `game_sessions.id: TEXT`, tabela `location_integrity_log`
- **`LocationIntent` dataclass:** `action`, `target_label`, `target_key: Optional[str]`, `parent_key: Optional[str]`, `description: Optional[str]`
- **Czego NIE ruszać:** fuzzy match w `validate_move`, `docker-compose.yml` prod, `data/ai_gm.db`, opening scene z PROMPT 11, LOC-1 helpers

---

## Implementacja (REV 2)

### Krok 0 — Commit przed implementacją

```bash
git branch --show-current
git add -A && git commit -m "feat: LOC-1 context injection + LOC-2 system prompt rules"
```

### Krok 1 — Helper `_get_available_location_keys(session_id, db)`

Import `_collect_related_location_ids` z `location_context_injector.py`, zwraca `set[str]` kluczy z grafu sesji. Fail-open przy wyjątku lub pustym grafie (`return set()`).

### Krok 2 — Guard `action: move` w `validate_move()`

Na początku `validate_move`, przed fuzzy match: jeśli `available_keys ≠ ∅` i `target_key ∉ available_keys` → `allowed=False`, `log_integrity_violation`, `location_move_blocked`. Fail-open gdy zbiór pusty.

### Krok 3 — Guard `action: create` — fallback `parent_key`

`_apply_create_parent_key_fallback`: przy nieznanym `parent_key` → log + `log_integrity_violation(reason=parent_key_not_found_fallback)` + fallback na `key` bieżącej lokacji sesji lub `None`. `create` nie jest blokowane.

### Krok 4 — Logi

| Event | Kiedy |
|---|---|
| `location_move_blocked` | `target_key` nie w grafie sesji |
| `location_create_parent_fallback` | `parent_key` nie istnieje, fallback |
| `location_guard_keys_fetch_failed` | wyjątek w helperu — fail open |

### Krok 5 — Testy: `backend/tests/test_loc3_location_guard.py`

4 testy: blokada spoza grafu, przepuszczenie z grafu, fail-open bez `current_location_id`, fallback `parent_key`.

### Krok 6 — Weryfikacja manualna na DEV

```bash
docker compose -f docker-compose.dev.yml up -d --build backend
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"
docker logs ai-gm-dev-backend-1 --tail=50 | grep -E "location_move_blocked|location_guard"
sqlite3 data/ai_gm.db "SELECT session_id, attempted_move, reason_blocked FROM location_integrity_log ORDER BY rowid DESC LIMIT 5;"
```

---

## Odpowiedzi Cursora (REV 1)

1. **Branch:** `phase-8d-location-integrity`
2. **Working tree:** nie czysty — zmiany LOC-1/LOC-2, `test_loc1_…`, validator/turns. Commit zbiorczy nie był robiony.
3. **Punkt zapisu:** `_process_location_intent` → `validate_move` (~406–554) → `UPDATE game_sessions`.
4. **Guard `target_key`:** brak — `validate_move` używaj `target_label` + fuzzy match na `_find_all_locations()`.
5. **Naruszenia:** `log_integrity_violation()` wrapper, tabela `location_integrity_log`, log `location_move_blocked`.
6. **`LocationIntent`:** dataclass, pola jak wyżej.
7. **Validator vs LOC-1:** `_collect_related_location_ids` tylko w `location_context_injector.py`; validator używa globalnego `_find_all_locations()`.
8. **`session_id`:** TEXT (np. `"105"`).
9. **DB:** ~2.6 MB, OK.

---

## Co zostało zrobione *(Cursor)*

- `location_validator.py`: import **`_collect_related_location_ids`** z LOC-1.
- **`_get_available_location_keys(resolved_session_id)`** — te same klucze co blok `[LOCATION CONTEXT]` (graf Opcja A + filtr approved / bieżąca lokacja).
- **`_apply_create_parent_key_fallback`** — przy `create` nieistniejący `parent_key` → log `location_create_parent_fallback` + `log_integrity_violation(reason=parent_key_not_found_fallback)`, potem ustawienie `parent_key` na `key` lokacji sesji lub `None`.
- **`validate_move`**: przy `action:move` i niepustym `target_key`, jeśli zbiór ≠ ∅ i `target_key ∉ zbiór` → `blocked` z `target_key_not_in_session_graph`, `log_integrity_violation`, `location_move_blocked`. Fail-open gdy brak `current_location_id`.
- **`test_loc3_location_guard.py`** — **4 passed**.
- Regresja `test_phase8d_location_hook` + `test_loc1_*` — **15 passed**.
- Backend DEV przebudowany przy testach.

**Pending:** commit zbiorczy LOC-1+LOC-2+LOC-3 — do wykonania przez właściciela.

---

## Notatki po implementacji *(Perplexity)*

- **Testy: 4 passed (LOC-3) + 15 passed (regresja)** — żadnych regresji, łańcuch LOC-1→LOC-2→LOC-3 działa spójnie.
- **Kluczowa decyzja architektoniczna:** `_get_available_location_keys()` współdzieli logikę z `_collect_related_location_ids()` z LOC-1 — guard i blok `[LOCATION CONTEXT]` są zawsze spójne. To eliminuje scenariusz gdzie LLM dostaje listę X, a guard waliduje listę Y.
- **Fail-open poprawnie zaimplementowany** — sesje bez `current_location_id` nie są blokowane. Ważne dla kampanii w trakcie migracji i dla opening scene (która `current_location_id` ustawia dopiero po pierwszej turze).
- **`_apply_create_parent_key_fallback` jako osobna funkcja** — dobra praktyka, można testować i wywoływać niezależnie. Spójna z wzorcem z LOC-1 (`_inject_location_llm_context` jako osobna funkcja w `game_engine.py`).
- **Pending: commit zbiorczy LOC-1 + LOC-2 + LOC-3** — Cursor nie wykonał kroku 0 w żadnym z trzech promptów. Przed merge do `main` (lub przed przekazaniem do Phase 8F) należy spiąć zmiany. Sugerowane commity:
  ```bash
  git add backend/app/services/location_context_injector.py \
            backend/app/services/game_engine.py \
            backend/tests/test_loc1_location_context_block.py
  git commit -m "feat(loc1): wstrzykiwanie [LOCATION CONTEXT] do LLM"

  git add backend/prompts/system_prompt.txt
  git commit -m "feat(loc2): reguły GM dla kontekstu lokacji w system_prompt"

  git add backend/app/services/location_validator.py \
            backend/tests/test_loc3_location_guard.py
  git commit -m "feat(loc3): backend guard — walidacja target_key przed zapisem do DB"
  ```
- **Phase 8D w całości zamknięta** (LOC-1, LOC-2, LOC-3 — DONE). LOC-4 odlozony do `docs/ToDo_Later/`. Gotowi do przejścia na **Phase 8F — Economy (Gold Flow + Shop)**.
