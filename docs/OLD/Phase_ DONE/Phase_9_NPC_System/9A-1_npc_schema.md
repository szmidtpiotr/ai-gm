<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-29 -->

# PROMPT 9A-1 — Phase 9: Schemat DB i migracje NPC

> **Branch:** `phase-9a-1-npc-schema` | **Commit:** do merge z `develop`
> **Zależności:** Phase 8E ✔️, Phase 8D ✔️

---

## Cel

Dodanie tabeli `npcs` i `npc_locations` + seed 4 NPC Act 1.

**Ustalone decyzje:** `npc_locations` (Opcja B), `personality_json`, GM mówi za NPC, przypisanie lokacji = wskazówka nie blokada, `game_locations.npc_keys` ignorowane.

---

## Kontekst techniczny

- **Plik migracji:** `backend/app/migrations_admin.py`
- **`game_locations.npc_keys`:** istnieje jako martwa kolumna — **NIE synchronizujemy**
- **Klucze sklepu potwierdzone:** `shortsword`, `shortbow`, `health_potion`, `torch`
- **Czego NIE ruszano:** `docker-compose.yml` prod, `data/ai_gm.db`, istniejące tabele

---

## Implementacja (REV 2 — zrealizowana)

- Tabela `npcs`: `id`, `key`, `label`, `npc_type`, `description`, `personality_json`, `is_shop`, `shop_inventory_json`, `is_active`, `created_at`, `updated_at`
- Tabela `npc_locations`: `id`, `npc_id` (FK ON DELETE CASCADE), `location_key`, `UNIQUE(npc_id, location_key)` + indeksy
- Seed 4 NPC + `shop_inventory_json` dla merchantów
- Seed Marty do `inn_main` warunkowy (`EXISTS` — aktualnie pominiety bo `inn_main` nie istnieje w DB)
- Testy: `backend/tests/test_phase9a_npc_schema.py` — 8 testów

---

## Odpowiedzi Cursora (REV 1)

1. **Branch:** `phase-9a-1-npc-schema`
2. **Working tree:** czysty
3. **Migracje:** `migrations_admin.py`, wzorzec `CREATE TABLE IF NOT EXISTS` + `INSERT OR IGNORE`
4. **`npcs`/`npc_`:** nie istniały; `npc_keys` to kolumna w `game_locations` (stary szkic)
5. **`game_locations.key`:** potwierdzone
6. **Wzór seeda:** `INSERT OR IGNORE INTO game_config_weapons/enemies`
7. **Klucze sklepu:** `shortsword`, `shortbow`, `health_potion`, `torch` ✔️
8. **DB:** ~2.6 MB, OK

---

## Co zostało zrobione *(Cursor)*

- `migrations_admin.py`: migracje `npcs` + `npc_locations` + indeksy, seed 4 NPC, `shop_inventory_json` dla Aldrica i Gorana, warunkowy INSERT Marty do `inn_main`
- `test_phase9a_npc_schema.py`: **8 passed**
- Manual SQL: tabele istnieją, 4 NPC w seedzie, Marta globalna (brak `inn_main` w DB)
- Rebuild DEV wykonany

---

## Notatki po implementacji *(Perplexity)*

- **8 passed, tabele i seed potwierdzone manualnie** — fundament Phase 9 gotowy.
- **Marta globalna na razie** — `inn_main` nie istnieje w `game_locations`. Stanie się lokalna automatycznie gdy lokacja zostanie dodana i seed zostanie uruchomiony ponownie (lub ręczny INSERT do `npc_locations`). Warto o tym pamiętać przy tworzeniu świata w Act 1.
- **`game_locations.npc_keys` — martwa kolumna** — warto ją usunąć lub udokumentować jako deprecated przy okazji kolejnej migracji. Nie blokuje, ale może mylić przy code review.
- **Indeksy na `npc_locations`** — dobra inicjatywa Cursora (nie były w REV 2). Query `WHERE location_key = ?` będzie szybkie przy `[NPC CONTEXT]` injection (9A-3).
- **Następny krok: 9A-2** — CRUD API + Admin UI dla NPC.
