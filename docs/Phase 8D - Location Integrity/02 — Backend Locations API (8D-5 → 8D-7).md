Jesteś programistą Python/FastAPI pracującym nad projektem ai-gm.
Repozytorium: github.com/szmidtpiotr/ai-gm
Branch: phase-8d-location-integrity

## KONTEKST (przeczytaj zanim cokolwiek zrobisz)

W tym projekcie NIE istnieje tabela `game_sessions`.
Jednostką sesji jest `campaigns`. Mapowanie zatwierdzone:
- `campaigns.current_location_id` → FK do `game_locations(id)`
- `campaigns.session_flags` → JSON z flagami location_integrity
- `location_integrity_log.campaign_id` → FK do `campaigns(id)`
- `game_locations` → tabela globalna (bez FK do campaigns)

Migracje 8D-1..8D-4 są już wdrożone i przetestowane (103 passed).

---

## ZANIM ZACZNIESZ IMPLEMENTOWAĆ

Przejrzyj istniejący kod i odpowiedz na poniższe pytania.
Jeśli którakolwiek odpowiedź wskazuje na problem — powiedz mi o tym ZANIM napiszesz
jakikolwiek kod:

1. Jak zorganizowane są istniejące routery? (folder? prefix? rejestracja w main.py?)
2. Czy prefix /api jest już używany globalnie, czy per-router?
3. Czy istnieje już jakiś endpoint /locations lub podobny który trzeba nadpisać/scalić?
4. Czy jest system autoryzacji? Jak wygląda (JWT? session? brak?)
5. Czy są modele Pydantic dla innych zasobów których mogę użyć jako wzorzec?
6. Czy coś w istniejących testach może failować po dodaniu nowego routera?

Jeśli nie widzisz blokerów — zaimplementuj poniższe endpointy.

---

## Zadanie 8D-5: GET /api/locations

Zwraca drzewo lokalizacji (makro + zagnieżdżone sub jako "children").

Query params: ?type=macro|sub|all, ?parent_id=<id>, ?active_only=1 (default)

Response example:
{
  "id": 1, "key": "city_varen", "label": "Miasto Varen",
  "location_type": "macro", "parent_id": null,
  "children": [
    {"id": 2, "key": "tavern_hanged_man", "label": "Karczma Pod Wisielcem",
     "location_type": "sub", "parent_id": 1, "children": []}
  ]
}

## Zadanie 8D-6: POST /api/locations

Tworzy nową lokalizację. Dostępny dla GM (wewnętrznie) + admin.

Body: key, label, description, parent_id, location_type, rules, enemy_keys[], npc_keys[]

Logika:
- key już istnieje → 422
- parent_id podany ale nie istnieje → 404
- Sukces → 201 + pełny obiekt

## Zadanie 8D-7: GET /api/locations/{key}

Szczegóły lokalizacji z polem "parent" (key+label) i "children".
404 gdy nie istnieje lub is_active=0.

---

## Wymagania końcowe
- Plik: backend/app/routers/locations.py
- Zarejestruj router w głównym app z prefix /api (sprawdź istniejący pattern)
- Testy: happy path + error cases dla każdego endpointu
- Testowa baza in-memory (nie data/ai_gm.db)
- python3 -m pytest → wszystkie passed
- Commit po zakończeniu:
  git add backend/app/routers/locations.py tests/
  git commit -m "feat(8D-5..7): Locations API — GET tree, POST create, GET detail"