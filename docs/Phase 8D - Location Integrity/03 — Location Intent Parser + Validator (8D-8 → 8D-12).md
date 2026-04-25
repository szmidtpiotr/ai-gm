Jesteś programistą Python/FastAPI pracującym nad projektem ai-gm.
Repozytorium: github.com/szmidtpiotr/ai-gm
Branch: phase-8d-location-integrity

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

Dataclass zwracana:
@dataclass
class LocationIntent:
    action: str          # 'move' | 'create' | None
    target_label: str
    target_key: str | None
    parent_key: str | None
    description: str | None

Logika (dwa tryby — sterowane flagami):

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

Odczytuj flagi przez: get_effective_flag(key, session_id)
  merge logic: session_flag ?? global_flag z game_config_meta

---

## Zadanie 8D-9: Location Validator

Plik: backend/app/services/location_validator.py

@dataclass
class ValidationResult:
    allowed: bool
    resolved_location_id: int | None
    is_new_location: bool
    block_reason: str | None

Funkcja: validate_move(session_id, intent: LocationIntent) -> ValidationResult

Logika:
1. Pobierz current_location z sesji
2. Fuzzy match po label (rapidfuzz score >= 80 → match)
3. Score < 80 → zapytaj LLM: "Czy '{A}' to ta sama lokalizacja co '{B}'? TAK/NIE"
   - TAK → użyj istniejącej
   - NIE → nowa lokalizacja (tylko dla action='create')
4. Reguły przechodzenia:
   - Sub → Sub ten sam parent: zawsze OK
   - Sub/Makro → inne Makro: soft block (GM opisuje podróż)
   - Nieistniejąca lokalizacja + action != 'create': BLOKADA

---

## Zadanie 8D-10: PATCH /api/session/{session_id}/location

Body: {"location_key": "market_square"}
Logika: pobierz lokalizację, zaktualizuj current_location_id w game_sessions
Wywoływany WEWNĘTRZNIE przez backend — nie bezpośrednio przez gracza.

---

## Zadanie 8D-11: Location Context Injector

Plik: backend/app/services/location_context_injector.py
Funkcja: build_location_context(session_id) -> str

Zwraca blok do wstrzyknięcia NA POCZĄTEK system promptu:

"[KONTEKST LOKALIZACJI — nie zmieniaj bez uzasadnienia]
Aktualna lokalizacja: {label} ({type}, rodzic: {parent_label})
Opis: {description}
Zasady specjalne: {rules}
Możliwe sąsiednie lokalizacje: {adjacent}
Jeśli gracz próbuje przenieść się do odległej lokalizacji bez logicznej drogi:
opisz podróż lub powiedz że jest niemożliwa."

Gdy current_location_id = NULL → zwróć pusty string.

---

## Zadanie 8D-12: /move command handler

Dodaj do istniejącego command handlera (gdzie jest /helpme):
Komenda: /move [nazwa lokalizacji]

Logika:
1. Wyciągnij target z komendy
2. Stwórz LocationIntent z action='move'
3. Uruchom Location Validator
4. Allowed → zaktualizuj lokalizację, GM potwierdza narracyjnie
5. Blocked → GM wyjaśnia dlaczego niemożliwe

---

## Integracja w głównym loop GM

Po wygenerowaniu odpowiedzi LLM wepnij:

if get_effective_flag('location_integrity_enabled', session_id):
    intent = location_intent_parser.parse(gm_response, session_id)
    if intent:
        result = location_validator.validate_move(session_id, intent)
        if result.allowed:
            update_session_location(session_id, result.resolved_location_id)
        else:
            log_integrity_violation(session_id, intent, result.block_reason)

---

## Wymagania końcowe
- rapidfuzz dodany do requirements.txt
- Błąd parsera NIE może zatrzymać gry (try/except wszędzie)
- Testy: parser (Opcja A + B), validator (allowed/blocked), injector
- python3 -m pytest → wszystkie passed