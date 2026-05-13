<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-29 -->

# PROMPT 12 — 8D-LOC-1: Wstrzykiwanie kontekstu lokacji do LLM

> **Workflow:** Perplexity generuje REV 1 z pytaniami blokującymi → Cursor odpowiada → Perplexity generuje REV 2 → Cursor implementuje.
> **Branch roboczy:** `phase-8d-location-integrity`
> **Plik:** `docs/Phase_8D_Location_Integrity/12_prompt_LOC1_llm_location_context_injection.md`

---

## Cel

Przed każdą turą backend dokłada do requestu LLM blok `[LOCATION CONTEXT]` zawierający:
- `current_location` — gdzie postać jest teraz (`key`, `label`, `location_type`)
- `known_locations[]` — lista lokacji powiązanych z bieżącą sesją kampanii (`key`, `label`, `parent_key`)

Dzięki temu GM "widzi mapę" przed generowaniem narracji i nie wymyśla lokacji z powietrza.

**Efekt:** LLM otrzymuje przed każdą turą blok (jako osobna wiadomość `role: system`):
```
[LOCATION CONTEXT]
current_location: { key: "village_square", label: "Rynek wioski", type: "macro" }
known_locations:
  - { key: "village_square", label: "Rynek wioski", parent_key: null }
  - { key: "tavern", label: "Karczma Pod Kogutem", parent_key: "village_square" }
```

---

## Kontekst techniczny (zaktualizowany po REV 1)

- **Pliki do modyfikacji:**
  - `backend/app/services/location_context_injector.py` — **już istnieje**, rozszerzyć funkcję `build_location_context()` lub dodać nową `build_location_context_block()`
  - `backend/app/services/game_engine.py` — funkcja `build_narrative_messages()` (~linie 121–224) — **tu wstrzykujemy**, nie w `turns.py`
- **Pliki NIE do modyfikacji:**
  - `backend/app/core/turn_engine.py` — `build_messages()` zostawiamy bez zmian
  - `backend/app/api/turns.py` — nie modyfikujemy bezpośrednio
  - `docker-compose.yml` prod
  - `data/ai_gm.db`
- **Schemat DB (potwierdzony przez Cursora):**
  - Kolumna to **`key`** (nie `location_key`) w tabeli `game_locations`
  - `game_locations` **nie ma kolumny `campaign_id`** — filtrowanie per kampania przez sesję
  - `game_sessions.current_location_id` może być NULL
  - `location_type` istnieje (`TEXT`, `CHECK('macro'/'sub')`, domyślnie `'macro'`)
- **Flaga:** `get_bool_flag("location_integrity_enabled", session_id)` z `location_config_service.py` — używać tej samej metody co inne hooki lokalizacji w `turns.py`

---

## ⛔ PRZED IMPLEMENTACJĄ — decyzja blokująca (wymagana od Cursora)

**Decyzja Cursora (Opcja A):** Przy braku `campaign_id` w `game_locations`, **`known_locations`** budowane jest jako **graf sąsiedztwa od `current_location_id`**: łańcuch przodków (`parent_id` w górę), dzieci jednego poziomu wzdłuż tego łańcucha oraz rodzeństwo bieżącej lokacji. Zbiór przycinany do ok. **120** wpisów; w liście są tylko `is_active = 1`, a `approved = 1` z wyjątkiem **bieżącej lokacji** (zawsze pokazana jako `current_location` nawet gdy pending).

> Opcja C wykluczona (brak migracji). Opcja B (globalny katalog) pomijana na rzecz Opcji A — mniejszy szum w prompcie.


## Implementacja (REV 2)

> ✅ Cursor implementuje poniższe po potwierdzeniu opcji filtrowania `known_locations`.

### Krok 0 — Przed implementacją

```bash
# Upewnij się że jesteś na właściwym branchu i commituj brudny working tree
git branch --show-current          # musi być: phase-8d-location-integrity
git add -A && git commit -m "wip: przed LOC-1 injection"
```

### Krok 1 — Rozszerz `location_context_injector.py`

Sprawdź istniejącą funkcję `build_location_context(session_id)`. Jeśli nie zwraca jeszcze struktury `[LOCATION CONTEXT]` z `known_locations[]`, **rozszerz ją lub dodaj nową funkcję** `build_location_context_block(session_id, db)` zgodnie z wybraną opcją filtrowania:

```python
def build_location_context_block(session_id: int, db: sqlite3.Connection) -> str | None:
    """
    Zwraca blok tekstowy [LOCATION CONTEXT] do wstrzyknięcia jako osobna
    wiadomość systemowa w prompcie LLM.
    Zwraca None jeśli brak danych (graceful degradation).
    """
    session = db.execute(
        "SELECT current_location_id FROM game_sessions WHERE id = ?",
        (session_id,)
    ).fetchone()
    if not session or not session["current_location_id"]:
        return None

    current = db.execute(
        "SELECT key, label, location_type FROM game_locations WHERE id = ?",
        (session["current_location_id"],)
    ).fetchone()
    if not current:
        return None

    # known_locations — Cursor implementuje zgodnie z wybraną opcją (A/B/D)
    # Przykład dla Opcji B (approved=1, globalnie):
    known = db.execute(
        "SELECT key, label, parent_key FROM game_locations "
        "WHERE approved = 1 ORDER BY id"
    ).fetchall()
    # Limit zabezpieczający przed rozdmuchaniem kontekstu
    known = known[:100]

    lines = [
        "[LOCATION CONTEXT]",
        f'current_location: {{ key: "{current["key"]}", '
        f'label: "{current["label"]}", type: "{current["location_type"]}" }}',
        "known_locations:"
    ]
    for loc in known:
        parent = f'"{loc["parent_key"]}"' if loc["parent_key"] else "null"
        lines.append(
            f'  - {{ key: "{loc["key"]}", '
            f'label: "{loc["label"]}", parent_key: {parent} }}'
        )
    return "\n".join(lines)
```

> Jeśli istniejący `inject_into_system_prompt()` już buduje podobny blok — użyj go i dostosuj format do `[LOCATION CONTEXT]` z nagłówkiem, zamiast tworzyć nową funkcję.

### Krok 2 — Wstrzyknięcie w `build_narrative_messages()` w `game_engine.py`

W funkcji `build_narrative_messages()` (~linia 121+), **po** zbudowaniu `messages` (po `build_messages()`), **przed** dopisywaniem combat logu i innych bloków:

```python
if get_bool_flag("location_integrity_enabled", session_id):
    try:
        loc_block = build_location_context_block(session_id=session_id, db=db)
        if loc_block:
            # Wstaw jako osobną wiadomość systemową (index 1 — po głównym system prompt)
            messages.insert(1, {"role": "system", "content": loc_block})
            logger.info(
                "location_context_injected",
                session_id=session_id,
                known_count=loc_block.count("- { key:")
            )
        else:
            logger.info("location_context_skipped", session_id=session_id, reason="no_current_location")
    except Exception as e:
        logger.warning("location_context_injection_failed", session_id=session_id, error=str(e))
```

> `try/except` obowiązkowy — wstrzyknięcie kontekstu **nie może crashować tury**.

> Jeśli `build_narrative_messages()` buduje messages inaczej niż lista ze `role/content` (np. dopisuje do `messages[0]["content"]`) — Cursor **dopasowuje mechanizm wstrzyknięcia** do faktycznej struktury, zachowując sens: blok `[LOCATION CONTEXT]` trafia do LLM **przed** historią tur, ale **po** głównym system promptcie.

### Krok 3 — Logi

| Event | Kiedy | Pola |
|---|---|---|
| `location_context_injected` | blok wstrzyknięty pomyślnie | `session_id`, `known_count` |
| `location_context_skipped` | `current_location_id` = NULL lub flaga wyłączona | `session_id`, `reason` |
| `location_context_injection_failed` | wyjątek — łapany, nie reraise | `session_id`, `error` |

### Krok 4 — Weryfikacja manualna na DEV

```bash
cd /home/piotrszmidt/ai-gm
docker compose -f docker-compose.dev.yml up -d --build --remove-orphans
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"

# Wykonaj turę w kampanii z ustawioną current_location_id
# Sprawdź logi
docker logs ai-gm-dev-backend-1 --tail=50 | grep location_context
```

**Oczekiwane:**
- Log `location_context_injected` po każdej turze z aktywną kampanią i ustawioną `current_location_id`
- Log `location_context_skipped` gdy `current_location_id = NULL`
- Brak crashy / 500 przy wykonaniu tury

### Krok 5 — Test regresyjny

```python
def test_location_context_injected_in_messages(db, session_with_location):
    """build_location_context_block zwraca niepusty blok gdy current_location_id ustawione."""
    block = build_location_context_block(session_id=session_with_location.id, db=db)
    assert block is not None
    assert "[LOCATION CONTEXT]" in block
    assert "current_location:" in block
    assert "known_locations:" in block

def test_location_context_skipped_when_no_location(db, session_without_location):
    """build_location_context_block zwraca None gdy current_location_id = NULL."""
    block = build_location_context_block(session_id=session_without_location.id, db=db)
    assert block is None
```

---

## Odpowiedzi Cursora (REV 1)

1. **Aktualny branch:** `phase-8d-location-integrity`
2. **Working tree:** **nie czysty** — zmienione pliki m.in.: `backend/app/api/characters.py`, `backend/app/api/turns.py`, `backend/app/services/location_intent_parser.py`, `backend/app/services/location_validator.py`, testy Phase 8D/8E.
3. **Gdzie budowany jest prompt / lista wiadomości:**
   - `build_messages()` w `backend/app/core/turn_engine.py` (~linie 61–103)
   - `build_narrative_messages()` w `backend/app/services/game_engine.py` (~121–224) — wywołuje `build_messages()`, potem dopisuje bloki do `messages[0]["content"]`
   - Non-stream: `create_turn()` w `turns.py` → `run_narrative_turn()` → `build_narrative_messages()`
   - Stream SSE: `create_turn_stream()` w `turns.py` → `messages = build_narrative_messages()` (~1827–1834)
4. **Mechanizm dokładania kontekstu:** przez modyfikację treści `messages[0]["content"]`; parametry `runtime_config_block`, `combat_context_block` w `build_messages()`; istniejący `location_context_injector.py` z `build_location_context()` i `inject_into_system_prompt()` — używany w `session_location.py`, import w `turns.py` obecny, ale wpięcie w ścieżkę narracji wymaga dopięcia.
5. **`current_location_id`:** może być NULL (kolumna bez NOT NULL).
6. **Schemat `game_locations`:** kolumna **`key`** (nie `location_key`); `location_type TEXT CHECK('macro'/'sub')`, domyślnie `'macro'`; **brak `campaign_id`** w tabeli.
7. **Długość kontekstu:** brak twardego limitu w DB — rekomendowany limit ~50–150 lokacji w implementacji.
8. **Flaga:** `get_bool_flag("location_integrity_enabled", session_id)` z `location_config_service.py`.
9. **Stan bazy:** `data/ai_gm.db` istnieje (~2.6 MB).

**Blokery zgłoszone przez Cursora:**
- Kolumna to `key`, nie `location_key` — poprawione w REV 2
- `game_locations` bez `campaign_id` — wymaga decyzji o filtracji known_locations (Opcja A/B/D powyżej)
- Istniejący `location_context_injector.py` może już częściowo rozwiązywać problem — Cursor ma go użyć/rozszerzyć

---

## Co zostało zrobione *(uzupełnia Cursor)*

- Dodano **`build_location_context_block(session_id, conn)`** oraz **`get_session_id_for_campaign(conn, campaign_id)`** w `backend/app/services/location_context_injector.py`: format `[LOCATION CONTEXT]` + JSON-owe pola (bezpieczne `json.dumps`), `parent_key` przez `LEFT JOIN` na `parent_id`, **known_locations = Opcja A** (graf + cap 120).
- W `backend/app/services/game_engine.py`: **`_inject_location_llm_context`** wywoływana **zaraz po `buildmessages(...)`**, **przed** dopisaniem combat logu — wstawia **drugą** wiadomość `role: system`; logi: `location_context_injected` / `location_context_skipped` / `location_context_injection_failed`.
- Flaga: **`get_bool_flag("location_integrity_enabled", session_id, default=True)`**.
- Testy: `backend/tests/test_loc1_location_context_block.py` (DEV container: pytest OK).
- Istniejący `build_location_context()` (polski nagłówek, sąsiedzi do admin/debug) **bez zmian**.

**Restart/rebuild:** po wdrożeniu kodu backend wymaga **rebuild obrazu DEV** (`docker compose -f docker-compose.dev.yml up -d --build backend`).

---

## Notatki po implementacji *(uzupełnia Perplexity)*

*(Perplexity uzupełni po raporcie Cursora)*
