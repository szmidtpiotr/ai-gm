<!-- last_updated: 2026-04-27 00:23 CEST | rev: 3 -->

# Phase 8E — Task 8E-1: Starter Items + Gold GP

> **Status: ✅ DONE** | Branch: `phase-8e-frontend` | Commit: `8fadaeb`
> **PR:** https://github.com/szmidtpiotr/ai-gm/pull/5
> **Notion:** https://www.notion.so/Phase-8E-frontend-34d8842467a8805db44ce68c3612dcb9

---

## Co zostało zrobione

### Pliki zmienione
| Plik | Zmiana |
|------|--------|
| `backend/app/api/characters.py` | Starter items + gold_gp przy kreacji (warrior/scholar) |
| `backend/app/api/inventory.py` | GET + POST `/api/characters/{id}/gold` |
| `backend/app/migrations_admin.py` | CREATE TABLE game_config_archetypes + seedy broni + ALTER gold_gp |
| `backend/app/routers/admin.py` | Naprawa błędnego fragmentu admin_patch_archetype |
| `backend/app/services/admin_config.py` | Obsługa archetypes w admin |
| `backend/app/services/loot_service.py` | Bez zmian w logice, weryfikacja source='start' |
| `frontend/admin_panel/sections/game_design.js` | Tab Archetypes: refreshArchetypes, starter_gold_gp, starter_items_json |
| `backend/tests/test_phase8e_starter_items.py` | **NOWY** — 7 testów (wszystkie OK) |

### Kluczowe decyzje
- Archetypy: `warrior` / `scholar` — only, inne nie dostają startów
- `grant_loot_to_character(source='start')` ✔
- DB_PATH == LOOT_DB_PATH w runtime (Docker) ✔

### Zatwierdzone klucze starterów
| Archetype | Przedmioty | Gold |
|-----------|-----------|------|
| warrior | shortsword, wooden_shield, shortbow, leatherarmor | 10 GP |
| scholar | quarterstaff, health_potion_small, mana_potion | 15 GP |

### Doseedowane klucze broni
- `wooden_shield` — Drewniana Tarcza, d4, STR
- `shortbow` — Krótki Łuk, d6, DEX
- `quarterstaff` — Laska, d6, STR
- `leatherarmor` — Skórzana Zbroja, armor (game_config_items)

### Testy (7/7 ✅)
```
test_db_path_same_as_loot_db_path
test_create_character_warrior_grants_starter_items
test_create_character_warrior_grants_gold
test_create_character_scholar_starter_items
test_create_character_scholar_gold
test_gold_endpoint_get
test_gold_endpoint_delta_positive
test_gold_endpoint_delta_below_zero_returns_400
test_create_character_unknown_archetype_no_crash
```

## Następny krok: 8E-2 Foldable Panels

Prompt: `docs/Phase_8E_frontend/8E-2_foldable_panels.md`

## Deploy checklist
- [ ] `git pull` na serwerze `.61` (branch `phase-8e-frontend`)
- [ ] Restart kontenera backendu
- [ ] Odświeżenie cache przeglądarki (admin panel JS)
- [ ] `pytest -q` na `.61` na tym samym commicie
- [ ] `main` NIE był mergowany — zgodnie z reguł
