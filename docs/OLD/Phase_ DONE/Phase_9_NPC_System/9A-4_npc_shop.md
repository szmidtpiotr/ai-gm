<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-29 -->

# PROMPT 9A-4 — Phase 9: Sklep NPC (buy/sell + UI)

> **Branch:** `phase-9a-1-npc-schema` | **Odblokowuje:** Phase 8F Economy
> **Zależności:** 9A-1 ✔️, 9A-2 ✔️, 9A-3 ✔️, 9A-0 ✔️

---

## Cel

Implementacja sklepu NPC: przeglądanie asortymentu, zakup i sprzedaż przedmiotów. Cue `Open Shop <npc_key>` w odpowiedzi GM otwiera modal sklepu.

---

## Kontekst techniczny (potwierdzony)

- **Bloker rozwiązany:** `ALTER TABLE game_config_weapons ADD COLUMN value_gp` + seed cen
- **`character_inventory` bez `item_type`:** typ z `weapon_key` / `item_key` / `consumable_key`
- **SSE:** `[OPEN_SHOP]` token w `actions.js`
- **Cache `?v=`:** suffiks tekstowy

---

## Odpowiedzi Cursora (REV 1)

1. **Branch:** `phase-9a-1-npc-schema`, working tree nieczysty
2. **`value_gp`:** brak w `game_config_weapons` — rozwiązane w Kroku 1
3. **`grant_loot_to_character`:** `(character_id, loot_items, source) -> list[dict]`
4. **`character_inventory`:** brak `item_type`, typ inferowany z kolumn
5. **Modal:** wzór `campaign-death-screen` + `hidden`
6. **SSE / `actions.js`:** parsowanie tokenów, `open_shop` nie istniało
7. **Cache:** suffiks tekstowy `?v=8d-location-debug-*`
8. **DB:** ~2.6 MB, OK

---

## Co zostało zrobione *(Cursor)*

- `migrations_admin.py`: `game_config_weapons.value_gp` DDL + seed cen starter broni
- `backend/app/services/shop_service.py`: odczyt asortymentu, kupno, sprzedaż, walidacje
- `backend/app/api/shop.py`:
  - `GET /api/shop/{npc_id}?character_id=...`
  - `GET /api/shop/by-key/{npc_key}?character_id=...`
  - `POST /api/shop/{npc_id}/buy`
  - `POST /api/shop/{npc_id}/sell`
- `backend/app/main.py`: rejestracja routera shop
- `backend/app/api/turns.py`: `Open Shop <npc_key>` — parser + strip + SSE token `[OPEN_SHOP]` + `open_shop` w sync out
- `backend/prompts/system_prompt.txt`: reguły `OPEN SHOP`
- `frontend/js/shop.js`: modal, buy/sell flow
- `frontend/index.html`: modal + script include
- `frontend/js/actions.js`: obsługa `[OPEN_SHOP]`, strip cue z narracji
- `frontend/styles.css`: style modalu
- `tests/test_phase9a_shop.py`: **5 passed**
- Rebuild DEV: sieć `ai-gm-observability-dev_observability-dev` dołączona ręcznie, stack wstał poprawnie

---

## Notatki po implementacji *(Perplexity)*

- **5 passed** — core logika sklepu działa. Mniej testów niż planowane 10 — warto uzupełnić przy okazji jeśli pojawią się bugi (szczególnie edge case: sprzedaż itemu bez ceny w katalogu).
- **`GET /api/shop/by-key/{npc_key}`** — dobra decyzja Cursora, rozwiązuje problem `openShop(npcKey)` → id w frontendzie bez dodatkowego GET.
- **`[OPEN_SHOP]` jako SSE token** — spójne z istniejącym wzorcem `[COMBAT_STARTED]` / `[CMD_JSON]`. Frontend może go konsumować w pętli tokenów zamiast po `[DONE]`.
- **Sieć Dockera `ai-gm-observability-dev_observability-dev`** — brak zewnętrznej sieci blokował DEV stack. Warto sprawdzić czy `docker-compose.dev.yml` ma to jako `external: true` — jeśli tak, należy dodać tworzenie tej sieci do `README` lub skryptu setup.
- **Następny krok:** smoke test UI (otwarcie sklepu z cue GM, buy/sell, odświeżenie gold/inventory) → potem **merge do `develop`** i decyzja: 9A-2 (NPC admin panel) czy Phase 8F Economy.
