<!-- last_updated: 2026-04-25 23:43 CEST | rev: 3 -->

# Phase 8C — Task 8C-3: API Endpoints — `/api/inventory/*`

> **STATUS: ✅ DONE** — commit `b625647` na `phase-8c-inventory-system`
> PR: https://github.com/szmidtpiotr/ai-gm/pull/2
> Testy: **6 passed** (suite: **116 passed**)

---

## Zrealizowane zmiany

| Plik | Zmiana |
|------|--------|
| `backend/app/api/inventory.py` | Nowy router — 5 endpointów |
| `backend/app/main.py` | `app.include_router(inventory.router, prefix="/api")` |
| `backend/app/services/loot_service.py` | +3 funkcje: `delete_inventory_item`, `list_config_items`, `get_config_item` + walidacja postaci w `get_character_inventory` |
| `backend/tests/test_phase8c_inventory_api.py` | 6 testów API |

### Endpointy

```
GET    /api/inventory/{character_id}          → loot_service.get_character_inventory()
POST   /api/inventory/{character_id}/equip    → loot_service.equip_item() | 400 invalid slot
DELETE /api/inventory/{character_id}/{id}     → loot_service.delete_inventory_item() | 400 equipped bez force
GET    /api/items                             → loot_service.list_config_items() | ?item_type=...
GET    /api/items/{key}                       → loot_service.get_config_item() | 404 brak
```

### Kontrakt
- Response: `{"ok": true, "data": ...}` / `{"ok": false, "error": "..."}`
- 404: brak postaci / wpisu / itemu
- 400: invalid slot, invalid item_type, DELETE equipped bez `?force=true`
==========after report=================

Zrobione — **8C-3 zaimplementowane, brak blokerów**.

## Co wdrożyłem

- Dodałem nowy router: `backend/app/api/inventory.py`
  - `GET /api/inventory/{character_id}`
  - `POST /api/inventory/{character_id}/equip`
  - `DELETE /api/inventory/{character_id}/{inventory_id}`
  - `GET /api/items`
  - `GET /api/items/{key}`
- Rejestracja routera w `backend/app/main.py` (`app.include_router(inventory.router, prefix="/api")`).
- Rozszerzyłem `backend/app/services/loot_service.py` o logikę delegowaną przez router:
  - `delete_inventory_item(...)`
  - `list_config_items(...)`
  - `get_config_item(...)`
  - plus walidacja istnienia postaci w `get_character_inventory(...)`.

## Kontrakt API

- Odpowiedzi endpointów: `{"ok": true, "data": ...}`
- Obsługa błędów:
  - 404 dla brakującej postaci / wpisu inventory / itemu
  - 400 dla `invalid slot`, `invalid item_type`, usuwania equipped bez `force=true`

## Testy

Dodałem testy API: `backend/tests/test_phase8c_inventory_api.py` (6 testów).  
Wcześniejsze testy loot service pozostają: `backend/tests/test_phase8c_loot_service.py` (8 testów).

Wyniki na `.61`:
- subset 8C-2 + 8C-3: **14 passed**
- pełny suite: **116 passed, 1 warning**

## Git / PR

- Commit: `b625647`
- Branch: `phase-8c-inventory-system`
- Push: wykonany
- PR: https://github.com/szmidtpiotr/ai-gm/pull/2 (OPEN, zaktualizowany)

## Notion

Zaktualizowałem stronę Phase 8C o wpis 8C-3 (commit, testy, PR, nowy wynik `pytest`).

## Co zostało pominięte

- `docs/Phase_8c_inventory_system/` nadal jest lokalnie untracked (nie było częścią tego commita).

## Docker / restart

Po wdrożeniu kodu backendu: **wystarczy restart backendu** (bez koniecznego rebuilda obrazu, chyba że Twój deploy pipeline tego wymaga).