# Phase 8D — Prompt 03: Location Intent Parser + Validator

> **Zadania:** 8D-8, 8D-9, 8D-10, 8D-11, 8D-12
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

Migracje 8D-1..8D-4 wdrożone (106 passed).
Locations API 8D-5..8D-7 wdrożone (106 passed).

---

## ZANIM ZACZNIESZ IMPLEMENTOWAĆ

Przejrzyj istniejący kod i odpowiedz na poniższe pytania.
Jeśli którakolwiek odpowiedź wskazuje na problem — powiedz mi o tym ZANIM napiszesz
jakikolwiek kod:

1. Jak wygląda główny loop GM? (gm.py? który plik?) — gdzie jest miejsce żeby wpiąć
   parser po wygenerowaniu odpowiedzi LLM?
2. Czy odpowiedź LLM jest już parsowana jako JSON gdzieś w kodzie, czy jako plain text?
   Czy zmiana formatu odpowiedzi (dodanie JSON wrapper) coś złamie?
3. Jak wygląda config_service? Jak pobierane są flagi/ustawienia?
4. Czy jest już obsługa komend (np. /helpme)? Gdzie — żebym mógł tam dodać /move?
5. Czy llm_service.py umożliwia wysłanie osobnego krótkiego prompta
   (potrzebne dla Opcji B fallback)?
6. Czy rapidfuzz jest już w requirements.txt? Jeśli nie — czy mogę go dodać?
7. Czy cokolwiek w istniejących testach polega na formacie plain-text odpowiedzi GM
   i może failować po przejściu na JSON wrapper?

Jeśli nie widzisz blokerów — zaimplementuj poniższe komponenty.

---

## Zadanie 8D-8: Location Intent Parser

Plik: backend/app/services/location_intent_parser.py

```python
@dataclass
class LocationIntent:
    action: str          # 'move' | 'create' | None
    target_label: str
    target_key: str | None
    parent_key: str | None
    description: str | None
```

Logika (dwa tryby sterowane flagami):

Opcja A (flaga location_parser_json_enabled=1):
  - Próbuj sparsować odpowiedź GM jako JSON
  - Wyciągnij location_intent jeśli istnieje
  - Jeśli JSON parse fail → przejdź do Opcji B (jeśli włączona)

Opcja B (flaga location_parser_fallback_enabled=1, tylko gdy A nie zadziałała):
  - Wyślij osobny prompt do LLM:
    "Przeanalizuj narrację i odpowiedz TYLKO w JSON:
    {\"moved\": true/false, \"target_label\": \"nazwa lub null\"}
    Narracja: [TEKST GM]"
  - Parsuj wynik → zwróć LocationIntent lub None

Odczytuj flagi przez: get_effective_flag(key, campaign_id)
  merge logic: campaign.session_flags[key] ?? game_config_meta[key]

---

## Zadanie 8D-9: Location Validator

Plik: backend/app/services/location_validator.py

```python
@dataclass
class ValidationResult:
    allowed: bool
    resolved_location_id: int | None
    is_new_location: bool
    block_reason: str | None
```

Funkcja: validate_move(campaign_id, intent: LocationIntent) -> ValidationResult

Logika:
1. Pobierz current_location z campaigns (campaigns.current_location_id)
2. Fuzzy match po label (rapidfuzz score >= 80 → match)
3. Score < 80 → zapytaj LLM: "Czy '{A}' to ta sama lokalizacja co '{B}'? TAK/NIE"
   - TAK → użyj istniejącej
   - NIE → nowa lokalizacja (tylko dla action='create')
4. Reguły przechodzenia:
   - Sub → Sub ten sam parent: zawsze OK
   - Sub/Makro → inne Makro: soft block (GM opisuje podróż)
   - Nieistniejąca lokalizacja + action != 'create': BLOKADA

---

## Zadanie 8D-10: PATCH /api/campaigns/{campaign_id}/location

UWAGA: NIE ma tabeli game_sessions — używamy campaigns.

Body: {"location_key": "market_square"}
Logika: pobierz lokalizację po key, zaktualizuj campaigns.current_location_id
Wywoływany WEWNĘTRZNIE przez backend — nie bezpośrednio przez gracza.
Zwróć 200 + {campaign_id, current_location_id, location_key, location_label}

---

## Zadanie 8D-11: Location Context Injector

Plik: backend/app/services/location_context_injector.py
Funkcja: build_location_context(campaign_id) -> str

Zwraca blok do wstrzyknięcia NA POCZĄTEK system promptu:

"[KONTEKST LOKALIZACJI — nie zmieniaj bez uzasadnienia]
Aktualna lokalizacja: {label} ({type}, rodzic: {parent_label})
Opis: {description}
Zasady specjalne: {rules}
Możliwe sąsiednie lokalizacje: {adjacent}
Jeśli gracz próbuje przenieść się do odległej lokalizacji bez logicznej drogi:
opiś podróż lub powiedz że jest niemożliwa."

Gdy campaigns.current_location_id = NULL → zwróć pusty string.

---

## Zadanie 8D-12: /move command handler

Dodaj do istniejącego command handlera (gdzie jest /helpme):
Komenda: /move [nazwa lokalizacji]

Logika:
1. Wyciągnij target z komendy
2. Stwórz LocationIntent z action='move'
3. Uruchom Location Validator (validate_move(campaign_id, intent))
4. Allowed → zaktualizuj lokalizację, GM potwierdza narracyjnie
5. Blocked → GM wyjaśnia dlaczego niemożliwe

---

## Integracja w głównym loop GM

Po wygenerowaniu odpowiedzi LLM wepnij:

```python
if get_effective_flag('location_integrity_enabled', campaign_id):
    intent = location_intent_parser.parse(gm_response, campaign_id)
    if intent:
        result = location_validator.validate_move(campaign_id, intent)
        if result.allowed:
            update_campaign_location(campaign_id, result.resolved_location_id)
        else:
            log_integrity_violation(campaign_id, intent, result.block_reason)
```

---

## Wymagania końcowe
- rapidfuzz dodany do requirements.txt
- Błąd parsera NIE może zatrzymać gry (try/except wszędzie)
- Testy: parser (Opcja A + B), validator (allowed/blocked), injector
- Testowa baza in-memory (nie data/ai_gm.db)
- python3 -m pytest → wszystkie passed
- Commit po zakończeniu:
  git add backend/app/services/ backend/app/routers/ requirements.txt tests/
  git commit -m "feat(8D-8..12): location parser, validator, injector, /move command"
```
===============AFTER REPORT===================
Brak blockerów krytycznych — wdrożyłem 8D-8..12 i potwierdziłem testami.

**Odpowiedzi na Twoje 7 pytań (audit):**
- Główny loop GM jest w `backend/app/api/turns.py` (`create_turn` i `create_turn_stream`), a miejsce pod parser po odpowiedzi LLM to fragment po złożeniu `assistant_text`/`clean_text`.
- Odpowiedź LLM jest traktowana jako plain text (nie globalny JSON contract); JSON wrapper jako nowy globalny format mógłby łamać flow, więc parser działa defensywnie (próbuje JSON, fallback, bez wymuszania zmiany formatu całego systemu).
- `config_service` obsługuje runtime mechanik, ale flagi globalne są w `game_config_meta`; do 8D dodałem dedykowany merge `campaigns.session_flags ?? game_config_meta`.
- Obsługa komend jest w `backend/app/api/turns.py` (w tym `/helpme`), więc tam dodałem `/move`.
- `llm_service.py` pozwala wysłać osobny krótki prompt przez `generate_chat(messages=[...])` — użyte dla fallbacku parsera.
- `rapidfuzz` nie było w `backend/requirements.txt` — dodałem.
- Istniejące testy nie wymagają globalnego przejścia na JSON wrapper odpowiedzi GM; regresję powodował tylko nowy injector próbujący otworzyć DB w testach bez DB (naprawione defensywnie).

Wdrożone zmiany:
- `backend/app/services/location_intent_parser.py`  
  - `LocationIntent`, Opcja A (JSON parse), Opcja B (LLM fallback), pełne `try/except` (nie blokuje gry).
- `backend/app/services/location_validator.py`  
  - `ValidationResult`, `validate_move(...)`, fuzzy (`rapidfuzz`), fallback LLM TAK/NIE, reguły sub/sub, macro soft-block, unknown+!create block.
- `backend/app/services/location_context_injector.py`  
  - `build_location_context(campaign_id)` + bezpieczny fallback do pustego stringa przy błędach DB.
- `backend/app/services/location_integrity_config.py`  
  - `get_effective_flag(key, campaign_id)` z merge `session_flags ?? game_config_meta`.
- `backend/app/services/location_integrity_service.py`  
  - update kampanii po `location_id`/`key`, logowanie naruszeń.
- Integracja:
  - `backend/app/services/game_engine.py` — wstrzyknięcie bloku kontekstu lokalizacji na początek system promptu.
  - `backend/app/api/turns.py` — hook integralności po odpowiedzi LLM (sync + stream), logowanie violation, aktualizacja lokalizacji, obsługa `/move`.
  - `backend/app/api/campaigns.py` — `PATCH /api/campaigns/{campaign_id}/location`.
  - `backend/app/api/slash_command_registry.py` — dodana komenda `/move [lokacja]`.
- Zależność:
  - `backend/requirements.txt` — `rapidfuzz>=3.9.0`.
- Testy:
  - `tests/test_phase8d_location_services.py` (parser A/B, validator allowed/blocked, injector, PATCH endpoint in-memory).

Commit:
- `d8cda1f`
- message: `feat(8D-8..12): location parser, validator, injector, /move command`

Wynik testów na `.61`:
- `python3 -m pytest tests/test_phase8d_location_services.py -q --tb=no` → `4 passed`
- `python3 -m pytest -q --tb=no` → `110 passed, 2 warnings`

Stan repo po commicie: zostały jeszcze wcześniejsze, **niezacommitowane** pliki z poprzednich kroków:
- `backend/app/main.py`
- `backend/app/migrations_admin.py`
- `tests/test_phase8d_location_integrity.py`
- `docs/Phase 8D - Location Integrity/03 — ...`

Po tych zmianach backendu:
- **restart Dockera backendu: wymagany**
- **rebuild obrazu: niewymagany** (chyba że robisz deployment przez nowy image).