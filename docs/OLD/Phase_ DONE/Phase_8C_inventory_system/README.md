<!-- last_updated: 2026-04-26 00:05 CEST | rev: 7 -->

# Phase 8C — Inventory System

## Kolejność wykonania

| Plik | Task | Opis | Status | Commit |
|------|------|------|--------|--------|
| `8C-0_pre_check.md` | Pre-Check | Audyt repozytorium | ✅ DONE | — |
| `8C-1_db_schema.md` | 8C-1 | `character_inventory` + migracja | ✅ DONE | `9f108cf` |
| `8C-2_loot_service.md` | 8C-2 | `loot_service.py` (8 funkcji, 8 testów) | ✅ DONE | `00f43e5` |
| `8C-3_api_endpoints.md` | 8C-3 | FastAPI endpointy + 3 funkcje w loot_service | ✅ DONE | `b625647` |
| `8C-4_combat_loot_integration.md` | 8C-4 | Podmiana resolve_enemy_loot → loot_service | ✅ DONE | `2f3a471` |
| `8C-5_admin_items_config.md` | 8C-5 | Admin Panel — tab "Przedmioty" | ✅ DONE | `0c5e6c3` |
| `8C-6_tests.md` | 8C-6 | Testy (17 przypadków) | 🔴 NEXT | — |

**Branch:** `phase-8c-inventory-system` | **PR:** https://github.com/szmidtpiotr/ai-gm/pull/2
**Suite:** 118 passed (26.04.2026)

---

## Kluczowe decyzje projektowe

- **Ścieżka B zatwierdzona:** `inventory_items` → `character_inventory` (zombie table).
- **XOR constraint (3 klucze):** `item_key`, `weapon_key`, `consumable_key` —
  dokładnie jeden NOT NULL (CHECK constraint SQLite).
- **Brak FK do katalogów** (celowe — błąd kolejności init `install.sh`):
  walidacja w `loot_service.grant_loot_to_character` przed zapisem.
- **Stackowanie:** consumable/item → quantity++; weapon → osobny wiersz.
- **Loot po walce:** `combat_service.resolve_attack()` → `roll_loot()` +
  `grant_loot_to_character()` po HP ≤ 0. Wynik w `out["loot"]`.
  Fallback: wyjątek w grant → log `combat_loot_grant_failed` + `loot=[]`.
- **Combat nie zmienia się:** broń z `sheet_json` → `game_config_weapons`.
- **Admin UI:** `/api/admin/items` (pełny CRUD); `/api/items` = read-only gracz.
- **Rozbieżność Notion vs docs:** w Notion "8C-5" = `pending_loot`;
  w repo docs "8C-5" = admin items config.

---

## Wzorzec pre-check w każdym prompcie

Każdy prompt zaczyna się od:
```
ZANIM napiszesz kod, odpowiedz na te pytania i poczekaj na moje potwierdzenie:
```
