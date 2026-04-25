# Phase 8D — Prompt 04: Admin Flags + Log Endpoint

> **Zadania:** 8D-13, 8D-14
> **Branch:** `phase-8d-location-integrity`
> **Warunek ukończenia:** `python3 -m pytest` → wszystkie passed

---

## Prompt do wklejenia w Cursor

```
Jesteś programistą Python/FastAPI pracującym nad projektem ai-gm.
Repozytorium: github.com/szmidtpiotr/ai-gm
Branch: phase-8d-location-integrity

## KONTEKST (przeczytaj zanim cokolwiek zrobisz)

W tym projekcie NIE istnieje tabela `game_sessions`.
Jednostką sesji jest `campaigns`. Zatwierdzone mapowanie:
- `campaigns.current_location_id` → FK do `game_locations(id)`
- `campaigns.session_flags` → JSON z flagami location_integrity
- `location_integrity_log.campaign_id` → FK do `campaigns(id)`

Już wdrożone (110 passed):
- 8D-1..4: migracje DB
- 8D-5..7: Locations API
- 8D-8..12: parser, validator, injector, /move, integracja w turns.py

Znana architektura:
- Główny loop GM: `backend/app/api/turns.py`
- Komendy (w tym /helpme, /move): `backend/app/api/slash_command_registry.py`
- Flagi globalne: `game_config_meta` (key/value)
- Flagi per kampania: `campaigns.session_flags` (JSON)
- Merge flag: `get_effective_flag(key, campaign_id)` w `location_integrity_config.py`
- Autoryzacja: sprawdź jak działa w istniejących endpointach admin

---

## ZANIM ZACZNIESZ IMPLEMENTOWAĆ

Przejrzyj istniejący kod i odpowiedz na poniższe pytania.
Jeśli którakolwiek odpowiedź wskazuje na problem — powiedz mi o tym ZANIM napiszesz
jakikolwiek kod:

1. Jak działa autoryzacja admin w istniejących endpointach?
   Pokaż mi fragment kodu gdzie sprawdzana jest rola admin.
   (szukaj w backend/app/api/ lub middleware)
2. Czy jest już jakiś endpoint PATCH dla campaigns?
   żebym nie tworzył konfliktu w routerze.
3. Czy prefix /api/admin jest już używany? Jakie endpointy tam istnieją?
4. Czy `get_effective_flag` z `location_integrity_config.py` mogę użyć bezpośrednio,
   czy potrzebuje refaktoru żeby obsłużyć DELETE (reset do global)?
5. Czy cokolwiek może failować w testach po dodaniu nowych endpointów admin?

Jeśli nie widzisz blokerów — zaimplementuj poniższe endpointy.

---

## Zadanie 8D-13: Zarządzanie flagami kampanii

Trzy endpointy — dostęp tylko admin:

### PATCH /api/admin/campaigns/{campaign_id}/flags

Body (dowolna kombinacja flag):
```json
{
  "location_integrity_enabled": 0,
  "location_parser_json_enabled": 1,
  "location_parser_fallback_enabled": 0
}
```

Logika:
1. Sprawdź autoryzację admin
2. Pobierz aktualne `campaigns.session_flags` JSON
3. Merge z nowymi wartościami (NIE nadpisuj całego JSON — tylko zmienione klucze)
4. Zapisz z powrotem do `campaigns.session_flags`
5. Zwróć 200 + pełny stan flag

Response:
```json
{
  "campaign_id": 42,
  "effective_flags": {
    "location_integrity_enabled": 0,
    "location_parser_json_enabled": 1,
    "location_parser_fallback_enabled": 0
  },
  "session_overrides": {
    "location_integrity_enabled": 0,
    "location_parser_fallback_enabled": 0
  },
  "global_defaults": {
    "location_integrity_enabled": 1,
    "location_parser_json_enabled": 1,
    "location_parser_fallback_enabled": 1
  }
}
```

### GET /api/admin/campaigns/{campaign_id}/flags

Podgląd aktualnych flag (effective + overrides + global defaults).
Ten sam format response co PATCH.

### DELETE /api/admin/campaigns/{campaign_id}/flags/{flag_key}

Usuwa nadpisanie per kampania dla konkretnej flagi.
Efekt: kampania wraca do global defaultu dla tej flagi.
Zwróć 200 + zaktualizowany stan flag.

---

## Zadanie 8D-14: Log viewer blokad lokalizacji

### GET /api/admin/campaigns/{campaign_id}/location-log

Query params:
- `?limit=50` (default: 50, max: 200)
- `?since=2026-04-25T00:00:00` (opcjonalny filtr daty ISO)

Response:
```json
[
  {
    "id": 1,
    "campaign_id": 42,
    "character_id": 7,
    "attempted_move": "Las Czarny",
    "current_location_key": "tavern_hanged_man",
    "reason_blocked": "Teleportacja między makro-lokalizacjami",
    "created_at": "2026-04-25T10:32:11"
  }
]
```

### GET /api/admin/location-log

Log ze wszystkich kampanii (overview dla admina / Grafana).
Dodaj query param `?campaign_id=<id>` jako opcjonalny filtr.
Ten sam format response.

---

## Wymagania końcowe
- Autoryzacja admin — zgodna z istniejącym wzorcem w projekcie
- Testy: PATCH merge logic, GET flags, DELETE reset, GET log
- Testowa baza in-memory (nie data/ai_gm.db)
- python3 -m pytest → wszystkie passed
- Commit po zakończeniu:
  git add backend/app/api/ tests/
  git commit -m "feat(8D-13..14): admin flags API + location integrity log endpoints"
```
# Phase 8D — Prompt 04: Admin Flags + Log Endpoint

> **Zadania:** 8D-13, 8D-14
> **Branch:** `phase-8d-location-integrity`
> **Warunek ukończenia:** `python3 -m pytest` → wszystkie passed

---

## Prompt do wklejenia w Cursor

```
Jesteś programistą Python/FastAPI pracującym nad projektem ai-gm.
Repozytorium: github.com/szmidtpiotr/ai-gm
Branch: phase-8d-location-integrity

## KONTEKST (przeczytaj zanim cokolwiek zrobisz)

W tym projekcie NIE istnieje tabela `game_sessions`.
Jednostką sesji jest `campaigns`. Zatwierdzone mapowanie:
- `campaigns.current_location_id` → FK do `game_locations(id)`
- `campaigns.session_flags` → JSON z flagami location_integrity
- `location_integrity_log.campaign_id` → FK do `campaigns(id)`

Już wdrożone (110 passed):
- 8D-1..4: migracje DB
- 8D-5..7: Locations API
- 8D-8..12: parser, validator, injector, /move, integracja w turns.py

Znana architektura:
- Główny loop GM: `backend/app/api/turns.py`
- Komendy (w tym /helpme, /move): `backend/app/api/slash_command_registry.py`
- Flagi globalne: `game_config_meta` (key/value)
- Flagi per kampania: `campaigns.session_flags` (JSON)
- Merge flag: `get_effective_flag(key, campaign_id)` w `location_integrity_config.py`
- Autoryzacja: sprawdź jak działa w istniejących endpointach admin

---

## ZANIM ZACZNIESZ IMPLEMENTOWAĆ

Przejrzyj istniejący kod i odpowiedz na poniższe pytania.
Jeśli którakolwiek odpowiedź wskazuje na problem — powiedz mi o tym ZANIM napiszesz
jakikolwiek kod:

1. Jak działa autoryzacja admin w istniejących endpointach?
   Pokaż mi fragment kodu gdzie sprawdzana jest rola admin.
   (szukaj w backend/app/api/ lub middleware)
2. Czy jest już jakiś endpoint PATCH dla campaigns?
   żebym nie tworzył konfliktu w routerze.
3. Czy prefix /api/admin jest już używany? Jakie endpointy tam istnieją?
4. Czy `get_effective_flag` z `location_integrity_config.py` mogę użyć bezpośrednio,
   czy potrzebuje refaktoru żeby obsłużyć DELETE (reset do global)?
5. Czy cokolwiek może failować w testach po dodaniu nowych endpointów admin?

Jeśli nie widzisz blokerów — zaimplementuj poniższe endpointy.

---

## Zadanie 8D-13: Zarządzanie flagami kampanii

Trzy endpointy — dostęp tylko admin:

### PATCH /api/admin/campaigns/{campaign_id}/flags

Body (dowolna kombinacja flag):
```json
{
  "location_integrity_enabled": 0,
  "location_parser_json_enabled": 1,
  "location_parser_fallback_enabled": 0
}
```

Logika:
1. Sprawdź autoryzację admin
2. Pobierz aktualne `campaigns.session_flags` JSON
3. Merge z nowymi wartościami (NIE nadpisuj całego JSON — tylko zmienione klucze)
4. Zapisz z powrotem do `campaigns.session_flags`
5. Zwróć 200 + pełny stan flag

Response:
```json
{
  "campaign_id": 42,
  "effective_flags": {
    "location_integrity_enabled": 0,
    "location_parser_json_enabled": 1,
    "location_parser_fallback_enabled": 0
  },
  "session_overrides": {
    "location_integrity_enabled": 0,
    "location_parser_fallback_enabled": 0
  },
  "global_defaults": {
    "location_integrity_enabled": 1,
    "location_parser_json_enabled": 1,
    "location_parser_fallback_enabled": 1
  }
}
```

### GET /api/admin/campaigns/{campaign_id}/flags

Podgląd aktualnych flag (effective + overrides + global defaults).
Ten sam format response co PATCH.

### DELETE /api/admin/campaigns/{campaign_id}/flags/{flag_key}

Usuwa nadpisanie per kampania dla konkretnej flagi.
Efekt: kampania wraca do global defaultu dla tej flagi.
Zwróć 200 + zaktualizowany stan flag.

---

## Zadanie 8D-14: Log viewer blokad lokalizacji

### GET /api/admin/campaigns/{campaign_id}/location-log

Query params:
- `?limit=50` (default: 50, max: 200)
- `?since=2026-04-25T00:00:00` (opcjonalny filtr daty ISO)

Response:
```json
[
  {
    "id": 1,
    "campaign_id": 42,
    "character_id": 7,
    "attempted_move": "Las Czarny",
    "current_location_key": "tavern_hanged_man",
    "reason_blocked": "Teleportacja między makro-lokalizacjami",
    "created_at": "2026-04-25T10:32:11"
  }
]
```

### GET /api/admin/location-log

Log ze wszystkich kampanii (overview dla admina / Grafana).
Dodaj query param `?campaign_id=<id>` jako opcjonalny filtr.
Ten sam format response.

---

## Wymagania końcowe
- Autoryzacja admin — zgodna z istniejącym wzorcem w projekcie
- Testy: PATCH merge logic, GET flags, DELETE reset, GET log
- Testowa baza in-memory (nie data/ai_gm.db)
- python3 -m pytest → wszystkie passed
- Commit po zakończeniu:
  git add backend/app/api/ tests/
  git commit -m "feat(8D-13..14): admin flags API + location integrity log endpoints"
```
==========AFTER REPORT========

Zrobione — 8D-13 i 8D-14 zaimplementowane wg specyfikacji z pliku.

**Szybki audit (Twoje pytania „zanim implementować”):**
- Admin auth działa przez `Depends(require_admin_token)` + `Authorization: Bearer ...` i `verify_admin_token(...)` w `backend/app/routers/admin.py`.
- PATCH dla campaigns już istniał: `PATCH /api/campaigns/{campaign_id}/location` w `backend/app/api/campaigns.py` (brak konfliktu, bo nowe endpointy są pod `/api/admin/...`).
- Prefix `/api/admin` jest już szeroko używany w `admin.py` (prompts, config, accounts, campaigns, db, slash commands itd.).
- `get_effective_flag` nie musiał być refaktorowany do DELETE; dla endpointów admin zrobiłem jawny model `global_defaults + session_overrides => effective_flags`.
- Ryzyko testowe: głównie auth i DB path; pokryte testami in-memory.

Wdrożone endpointy w `backend/app/routers/admin.py`:
- `PATCH /api/admin/campaigns/{campaign_id}/flags`
- `GET /api/admin/campaigns/{campaign_id}/flags`
- `DELETE /api/admin/campaigns/{campaign_id}/flags/{flag_key}`
- `GET /api/admin/campaigns/{campaign_id}/location-log` (`limit`, `since`)
- `GET /api/admin/location-log` (`campaign_id`, `limit`, `since`)

Dodałem testy:
- `tests/test_phase8d_admin_flags_log.py`
  - PATCH merge logic
  - GET flags
  - DELETE reset override
  - GET campaign/global log filters

Wyniki testów na `.61`:
- `python3 -m pytest tests/test_phase8d_admin_flags_log.py -q --tb=no` → `2 passed`
- `python3 -m pytest -q --tb=no` → `112 passed, 2 warnings`

Nie commitowałem tych zmian (nie było jawnej prośby o commit w tej wiadomości).

Aktualnie zmienione/pliki do ewentualnego commita:
- `backend/app/routers/admin.py`
- `tests/test_phase8d_admin_flags_log.py`
- oraz wcześniejsze pending: `backend/app/main.py`, `backend/app/migrations_admin.py`, `tests/test_phase8d_location_integrity.py`, docs 8D.

Po tych zmianach backendu: **restart Dockera backendu jest potrzebny**, **rebuild obrazu nie jest wymagany** (chyba że wypychasz nowy image).