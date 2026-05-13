<!-- last_updated: 2026-04-27 08:47 CEST | rev: 4 -->

# Phase 8E — Task 8E-4: Loot Popup po walce

> **Status: ✅ DONE** | Branch: `phase-8e-frontend` | Commit: `ab22dfd`
> **PR:** https://github.com/szmidtpiotr/ai-gm/pull/5
> **Notion:** https://www.notion.so/Phase-8E-frontend-34d8842467a8805db44ce68c3612dcb9

---

## Co zostało zrobione

### Pliki zmienione
| Plik | Zmiana |
|------|--------|
| `backend/app/migrations_admin.py` | `gold_min`, `gold_max` w `game_config_loot_tables` |
| `backend/app/services/loot_service.py` | `roll_gold_drop(enemy_key)` |
| `backend/app/services/combat_service.py` | `gold_drop` po killu, `apply_character_gold_delta`, `out["gold_drop"]` |
| `backend/tests/test_phase8_combat.py` | Asercja `gold_drop` w teście zwycięstwa |
| `backend/tests/test_phase8c_loot_service.py` | `test_roll_gold_drop_returns_zero_when_no_table`, `test_roll_gold_drop_within_range` |
| `frontend/js/combat_panel.js` | `_pendingGold`, `_showLootPopupAsync` z gold, render `💰 +X GP`, popup także przy samym gold |
| `frontend/css/combat.css` | `.combat-loot-gold` |
| `frontend/js/api.js` | Fallback historii tur gdy filtr `user_id` wycina wszystko |
| `frontend/js/death_screen.js` | Defensywne zamknięcie przy 404 "campaign not ended" |

### Testy (3/3 ✅)
```
test_roll_gold_drop_returns_zero_when_no_table
test_roll_gold_drop_within_range
test_combat_victory_has_gold_drop  (rozszerzony)
```
Uruchomione na `.61`: `3 passed, 49 deselected`

### Dodatkowe poprawki (ten sam commit)
- `api.js` — fallback historii tur
- `death_screen.js` — defensywne 404

## Deploy checklist
- [ ] `git pull` na `.61` (branch `phase-8e-frontend`)
- [ ] **Restart backendu** (migracje + Python)
- [ ] Redeploy frontendu (JS/CSS)
- [ ] Zabij wroga w walce — popup musi pokazać loot + gold (jeśli > 0)
- [ ] `main` NIE był mergowany

## Następny krok: 8E-5 Przedmioty Fabularne GM

Prompt: `docs/Phase_8E_frontend/8E-5_gm_items.md`
