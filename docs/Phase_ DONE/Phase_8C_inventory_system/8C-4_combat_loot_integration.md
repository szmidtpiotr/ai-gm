<!-- last_updated: 2026-04-25 23:56 CEST | rev: 3 -->

# Phase 8C — Task 8C-4: Integracja Loot z Combat

> **STATUS: ✅ DONE** — commit `2f3a471` na `phase-8c-inventory-system`
> PR: https://github.com/szmidtpiotr/ai-gm/pull/2
> Testy: **41 passed** (suite: **118 passed**)

---

## Zrealizowane zmiany

| Plik | Zmiana |
|------|--------|
| `backend/app/services/combat_service.py` | Podmiana `game_engine.resolve_enemy_loot` → `loot_service.roll_loot` + `grant_loot_to_character` |
| `backend/tests/test_phase8_combat.py` | Mocki przestawione na `loot_service` |
| `backend/tests/test_phase8c_combat_loot.py` | 2 nowe testy combat loot |

### Logika po `dead=True`

```python
# combat_service.py — resolve_attack(), gałąź if dead:
loot_items = roll_loot(ek)
if loot_items:
    granted = grant_loot_to_character(ch_id, loot_items, source="loot")
    out["loot"] = granted
else:
    out["loot"] = []
# Fallback: wyjątek w grant → log combat_loot_grant_failed + loot=[] (bez crasha walki)
```

### Testy

- `test_enemy_death_grants_loot_to_inventory`
- `test_enemy_death_no_loot_table_returns_empty_list`
