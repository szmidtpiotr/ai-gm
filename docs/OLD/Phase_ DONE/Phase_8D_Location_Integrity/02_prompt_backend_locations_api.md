<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-28 -->

# PROMPT 02 — Backend Locations API (Phase 8D)

> Workflow tego pliku: REV 1 (pytania blokujące) → odpowiedzi Cursora → REV 2 (implementacja) → raport Cursora → notatki Perplexity → DONE.

---

## Cel

Zaimplementować REST API dla systemu lokalizacji (CRUD + drzewo makro/sub).  
Zadania: **8D-5 GET /locations**, **8D-6 POST /locations**, **8D-7 GET /locations/{key}**.

---

## Kontekst techniczny

- **Branch:** `phase-8d-location-integrity`
- **Zależność:** wymaga ukończenia PROMPT 01 (tabela `game_locations` musi istnieć w DB)
- **Baseline po PROMPT 01:** `164 passed`
- **Pliki do stworzenia:** `backend/app/routers/locations.py` (lub analogiczny — Cursor weryfikuje styl)
- **Pliki do modyfikacji:** `backend/app/main.py` lub plik rejestracji routerów
- **NIE ruszać:** `docker-compose.yml` prod, `data/ai_gm.db`, migracje z PROMPT 01
- **Testy:** styl i fixture z istniejących testów w `backend/tests/`

---

## ⛔ PRZED IMPLEMENTACJĄ — pytania blokujące

*(Cursor odpowiedział na pytania blokujące — wszystkie ✅)*

| Pytanie | Odpowiedź Cursora |
|---------|-------------------|
| Branch? | ✅ `phase-8d-location-integrity` |
| Struktura routerów? | ✅ `backend/app/routers/`, rejestracja przez `include_router` w `main.py` |
| Wzorzec Pydantic + `get_db()`? | ✅ Pydantic `BaseModel` dla schema, wspólny `get_db()` dependency |
| Tabela `game_locations` w DB? | ✅ Istnieje z pełną schemą z PROMPT 01 |
| Fixture `TestClient` w `conftest.py`? | ✅ Zidentyfikowany, testy API używają TestClient |
| Testy `test_phase8d_migrations.py`? | ⚠️ 15 errors — znany problem z fixture tymczasowej bazy (nie blokuje) |

---

## Implementacja (REV 2)

Pracujesz w projekcie `ai-gm`. Branch: `phase-8d-location-integrity`.  
Nowy plik: `backend/app/routers/locations.py`. Rejestracja w `main.py`.

### Zadanie 8D-5 — `GET /api/locations`

Endpoint zwracający drzewo lokalizacji.

**Query params:**
- `?type=macro|sub|all` (default: `all`)
- `?parent_id=<id>` — tylko dzieci danego parenta
- `?active_only=1` (default: `1`)

**Response schema (zagnieżdżone children):**
```json
[
  {
    "id": 1, "key": "city_varen", "label": "Miasto Varen",
    "description": "...", "location_type": "macro", "parent_id": null,
    "rules": null, "enemy_keys": [], "npc_keys": [],
    "children": [
      { "id": 2, "key": "tavern_hanged_man", "label": "Karczma Pod Wisielcem",
        "location_type": "sub", "parent_id": 1, "children": [] }
    ]
  }
]
```

### Zadanie 8D-6 — `POST /api/locations`

Tworzenie nowej lokalizacji (GM internal + admin).

**Logika:**
1. `key` już istnieje → 422 Unprocessable
2. `parent_id` podany, ale parent nie istnieje → 404
3. Zapisz do DB, zwroć 201 + pełny obiekt

### Zadanie 8D-7 — `GET /api/locations/{key}`

Szczegóły z parentem i dziećmi. 404 gdy nie istnieje lub `is_active = 0`.

### Testy (8D-8)

Nowy plik: `backend/tests/test_8d_locations_api.py`

Pokryć:
- `GET /api/locations` — pusta lista, lista z danymi, filtr `type=macro`
- `POST /api/locations` — happy path (201), duplikat key (422), zły parent_id (404)
- `GET /api/locations/{key}` — istniejący, nieistniejący (404)

---

## Co zostało zrobione *(Cursor)*

- ✅ `backend/app/routers/locations.py` (198 linii) — nowy router
- ✅ `backend/app/main.py` — rejestracja routera (+2 linie)
- ✅ `backend/tests/test_8d_locations_api.py` — 17 testów
- ✅ Drzewo makro/sub z zagnieżdżonymi children
- ✅ Filtrowanie po `type`, `parent_id`, `active_only`
- ✅ Walidacja duplikatów key (422) i istnienia parenta (404)
- ✅ Parsowanie JSON `enemy_keys`, `npc_keys`
- ✅ Autentykacja admin tokenem (Header Authorization)
- ✅ Response schemas z Pydantic
- ✅ Docker rebuild wykonany
- **Wynik testów:** 181 passed (164 baseline + 17 nowych API)
- **Znany problem:** `test_phase8d_migrations.py` — 15 errors (fixture tymczasowej bazy, nie blokuje)

---

## Notatki po implementacji *(Perplexity)*

- ✅ Implementacja zgodna ze specyfikacją Phase 8D
- ⚠️ `test_phase8d_migrations.py` wymaga poprawy fixture — do naprawy w ramach PROMPT 06 (testy) lub osobnego zadania
- ⚠️ Zweryfikować czy `location_integrity_enabled` w DB to `'0'` czy `'1'` — powinno być `'0'` na czas dev (patrz PROMPT 01)
- API gotowe jako fundament dla PROMPT 03 (parser intentów) — `POST /api/locations` będzie wywoływane przez validator przy `action: "create"`
