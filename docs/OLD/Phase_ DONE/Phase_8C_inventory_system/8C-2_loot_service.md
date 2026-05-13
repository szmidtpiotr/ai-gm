<!-- last_updated: 2026-04-25 23:32 CEST | rev: 3 -->

# Phase 8C — Task 8C-2: Loot Service — `loot_service.py`

> **STATUS: ✅ DONE** — commit `00f43e5` na `phase-8c-inventory-system`
> PR: https://github.com/szmidtpiotr/ai-gm/pull/2
> Testy: **8 passed** (suite: **110 passed**)

---

## Zrealizowane zmiany

| Plik | Zmiana |
|------|--------|
| `backend/app/services/loot_service.py` | Nowy serwis — 5 funkcji |
| `backend/tests/test_phase8c_loot_service.py` | 8 testów |

### Zaimplementowane funkcje

- `get_loot_table(enemy_key)` — pobiera wpisy z `game_config_loot_entries` JOIN `game_config_loot_tables`
- `roll_loot(enemy_key)` — losuje loot wg `chance`; brak tabeli → `[]`
- `grant_loot_to_character(character_id, loot_items, source)` — zapisuje do `character_inventory`;
  waliduje klucze w katalogach przed zapisem; stackuje consumable/item, osobny wiersz dla weapon
- `get_character_inventory(character_id)` — zwraca ekwipunek z JOIN na katalogi
- `equip_item(character_id, inventory_id, slot)` — załóż na slot, zdejmuje poprzedni

---

## ⚠️ Uwagi implementacyjne

- **Brak FK do katalogów** (dziedziczone z 8C-1): walidacja kluczy w `grant_loot_to_character`
  przed każdym `INSERT`; brakujący klucz → **pomiń + log WARNING** (nie blokuj całego lootu).
- **Brak importu z `combat_service`** — serwis niezależny zgodnie z wymaganiem.

---

## Deployment

```bash
docker compose restart backend
```
