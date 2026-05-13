<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-28 -->

# PROMPT 08 — Location Validator Hook + Auto-Create

> **Workflow:** Perplexity generuje REV 1 z pytaniami blokującymi → Cursor odpowiada → Perplexity generuje REV 2 → Cursor implementuje.
> Plik zapisany w `docs/Phase_8D_Location_Integrity/08_prompt_location_validator_hook.md`

---

## Cel

Podłączyć `location_intent_parser` i `location_validator` do **głównej pętli gry** (`backend/app/api/turns.py`), tak żeby każda odpowiedź GM z `location_intent` powodowała realną walidację i (opcjonalnie) tworzenie lokalizacji w bazie.

System obsługuje **dwa tryby** przełączane flagą `location_auto_create_enabled`:

- **Tryb B (auto-create):** nieznana lokalizacja → tworzona automatycznie z `ai_generated=1, approved=0` → ruch dozwolony, admin zatwierdza później w panelu
- **Tryb A (blokada):** nieznana lokalizacja → `[LOCATION_BLOCKED]` → GM narruje odmowę, `current_location_id` nie zmienia się

### Pełny flow

```
GM zwraca JSON z location_intent
        ↓
location_integrity_enabled = 0? → pomiń całość, ruch dozwolony
        ↓
fuzzy_match >= 80% w game_locations (approved=1)? → move ✅ → update current_location_id
        ↓
Nie znaleziono...
        ↓
location_auto_create_enabled = 1 → utwórz z ai_generated=1, approved=0 → ruch dozwolony ✅
location_auto_create_enabled = 0 → zwróć [LOCATION_BLOCKED: powód] ❌
        ↓
Każdy ruch (dozwolony lub zablokowany) → zapisz do location_integrity_log
```

---

## Kontekst techniczny

**Główny plik do modyfikacji:**
- `backend/app/api/turns.py` — 1985 linii, JEDYNE źródło prawdy dla pętli gry

**Serwisy już istniejące (NIE modyfikuj interfejsu publicznego):**
- `backend/app/services/location_intent_parser.py` (6108 B)
- `backend/app/services/location_validator.py` (12257 B)
- `backend/app/services/location_config_service.py` (6152 B)
- `backend/app/services/location_context_injector.py` (6152 B)

**Pliki do modyfikacji/dodania:**
- `backend/app/migrations_admin.py` — nowe migracje
- `backend/app/routers/admin_location.py` — nowe endpointy pending/approve/reject
- `frontend/admin_panel/` — UI zatwierdzania (sekcja)

**NIE ruszać:**
- `docker-compose.yml` prod
- `data/ai_gm.db`
- Interfejsu publicznego serwisów location (tylko dodajemy wywołania)

---

## Odpowiedzi Cursora (REV 1)

### 1. Główny endpoint gry
`backend/app/api/turns.py` — 1985 linii, 75305 bajtów. To jedyny plik obsługujący turn/chat/stream.

### 2. Flow odpowiedzi LLM
Dwa miejsca w `turns.py`:
- **Non-streaming** (linie ~1273-1309): `run_narrative_turn()` zwraca dict, `assistant_text = result.get("message")`
- **Streaming** (linie ~1814-1878): `full_raw` zbierany z chunków, następnie przetwarzany (COMBAT_START, grant_item, roll_cue). Hook location istnieje częściowo tylko w streaming.

### 3. Serwisy location
Wszystkie 4 pliki istnieją w `backend/app/services/`.

### 4. Kolumny ai_generated / approved
**Nie istniały** — dodane migracją 8D-5.

### 5. Flaga location_auto_create_enabled
**Nie istniała** — dodana migracją 8D-5, domyślna wartość `'1'`.

### 6. game_config_meta (stan przed migracją)
```
('config_version', '1.0.0')
('loki_url', 'http://192.168.1.61:3100')
('ui_panel_defaults', '{...}')
('location_integrity_enabled', '1')
('location_parser_json_enabled', '1')
('location_parser_fallback_enabled', '1')
```

### 7. location_integrity_log
Tabela istniała, 0 wierszy — hook niepodłączony przed tą implementacją.

### 8. Git status
Branch: `phase-8d-location-integrity`
Working tree brudny przed KROKiem 1 — zacommitowany porządkującym commitem.

### Blokery zidentyfikowane przez Cursora (wszystkie rozwiązane)
- ✅ Brak kolumn `ai_generated`, `approved` → migracja 8D-5
- ✅ Brak flagi `location_auto_create_enabled` → migracja 8D-5
- ✅ `validate_move()` przyjmował `session_id` → zmienione na `campaign_id`
- ✅ Auto-create nie ustawiał flag → naprawione w `location_validator.py`
- ✅ Non-streaming flow bez hooka → hook dodany w obu flow
- ✅ Logowanie tylko blokad → logowane również `move_ok` i `create_ok`

---

## Co zostało zrobione *(uzupełnił Cursor)*

Zaimplementowano kroki 1-9:

- Zapisano wcześniejsze niezacommitowane zmiany commitem porządkującym przed hookiem location.
- Dodano migrację 8D-5: `game_locations.ai_generated`, `game_locations.approved` oraz globalną flagę `location_auto_create_enabled = '1'`.
- Rozszerzono `location_validator.py`:
  - walidacja obsługuje mapowanie `campaign_id` → `game_sessions.id`,
  - fuzzy match działa tylko na aktywnych i zatwierdzonych lokalizacjach,
  - auto-create tworzy lokalizacje z `ai_generated=1`, `approved=0`,
  - logowane są również udane ruchy (`move_ok`, `create_ok`), nie tylko blokady.
- Podpięto hook `_process_location_intent()` w `backend/app/api/turns.py` dla flow non-streaming i streaming.
- Dodano admin endpointy:
  - `GET /api/admin/locations/pending`,
  - `POST /api/admin/locations/{location_id}/approve`,
  - `POST /api/admin/locations/{location_id}/reject`.
- Dodano w admin panelu sekcję **Lokalizacje do zatwierdzenia** z licznikiem oczekujących, tabelą oraz przyciskami `Zatwierdź` / `Odrzuć`.
- Dodano `backend/tests/test_phase8d_location_hook.py` z testami hooka, auto-create, blokady, pending/approve/reject i logowania udanych ruchów.
- Zaktualizowano istniejący test `test_8d_locations_api.py` do aktualnego kontraktu API, gdzie `rules` wraca jako obiekt JSON.
- Wykonano rebuild DEV i pełny test suite w kontenerze:
  - wynik: `321 passed, 3 warnings`.
- Commit: `7baff34b4c9f61b6660460fc2b9f2b2ef7234c5d`

---

## Hotfix po wdrożeniu DEV *(2026-04-28)*

### Wykryte problemy (z logów Loki)

1. **`location_intent_parse_error: '"moved"'`** — GM owijał JSON w markdown code fence (` ```json ... ``` `), hook crashował zanim dotarł do auto-create. `session_id: null` — mapowanie campaign → session nie działało.
2. **Artefakty JSON w UI** — gracz widział surowe ` ```json {"narrative": ...} ``` ` zamiast tekstu narracji.

### Naprawione pliki

- `backend/app/services/location_intent_parser.py` — naprawiony błąd `'"moved"'` przez escapowanie `{}` w fallback prompt
- `backend/app/api/turns.py` — hook stripuje ` ```json ` fences przed parsowaniem i przed wstrzyknięciem `[LOCATION_BLOCKED]`; mapowanie sesji przez `campaign_id → latest game_sessions.id`
- `frontend/js/ui.js` — `parseGMResponse()` wyciąga `narrative` z JSON/fenced JSON, fallback do plain text; podpięte dla stream, non-stream i historii tur
- `frontend/index.html` — bump cache `ui.js?v=8d-location-debug-2`
- `backend/prompts/system_prompt.txt` — dodana instrukcja: zwracaj czysty JSON bez markdown code fence

### Wynik po hotfixie
- Lokalizacje tworzą się w bazie (auto-create działa)
- Tekst narracji wyświetla się czysto w UI
- Testy DEV: `81 passed, 3 warnings`
- Zmiany w working tree — **niezacommitowane**

---

## Notatki po implementacji *(Perplexity)*

### Status
✅ DONE — 2026-04-28

### Podsumowanie
Phase 8D jest teraz w pełni funkcjonalna i zweryfikowana manualnie. System lokalizacji przeszedł od samej infrastruktury (PROMPT 01–07) do działającego hooka w pętli gry z potwierdzonym auto-create i czystym renderem UI.

### Kluczowe decyzje architektoniczne
- **`_process_location_intent()` jako izolowana funkcja** w `turns.py` — łatwa do wyłączenia/testowania bez dotykania głównego flow
- **Strip code fence po stronie backendu i frontendu** — defensywne podejście, LLM może zawsze zwrócić owiniety JSON
- **Fuzzy match tylko na `approved=1`** — lokalizacje AI-generated czekają na zatwierdzenie
- **Dwa tryby przez jedną flagę** (`location_auto_create_enabled`) — przełączalne z panelu admina bez restartu

### Znane ograniczenia / do monitorowania
- `location_context_injector.py` nie jest jeszcze podłączony do promptu systemowego — do rozważenia przed merge'em lub w fazie 9
- Hotfix nie zacommitowany — wymaga `git commit + push` przed merge'em na `main`

### Następny krok
✅ Commit hotfixu → push `phase-8d-location-integrity` → merge do `main` → Phase 8F Economy
