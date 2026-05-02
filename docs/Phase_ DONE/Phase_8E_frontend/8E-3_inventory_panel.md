<!-- last_updated: 2026-04-27 08:23 CEST | rev: 3 -->

# Phase 8E — Task 8E-3: Panel Ekwipunku w UI gracza

> **Status: ✅ DONE** | Branch: `phase-8e-frontend` | Commit: `c954c47`
> **PR:** https://github.com/szmidtpiotr/ai-gm/pull/5
> **Notion:** https://www.notion.so/Phase-8E-frontend-34d8842467a8805db44ce68c3612dcb9

---

## Co zostało zrobione

### Backend
| Plik | Zmiana |
|------|--------|
| `backend/app/services/loot_service.py` | `unequip_item`: `equipped=0, slot=NULL` |
| `backend/app/api/inventory.py` | `equip_item`: przy podmianie slotów `SET equipped=0, slot=NULL`; `EquipRequest.slot` opcjonalny (null/brak = unequip) |
| `backend/tests/test_phase8e_inventory_panel.py` | **NOWY** — GET inventory, gold, equip, replace w slocie, unequip |
| `backend/tests/test_phase8c_inventory_api.py` | Dodany `test_post_equip_null_slot_unequips` |

### Frontend
| Plik | Zmiana |
|------|--------|
| `frontend/js/app.js` | Sekcja foldable `data-section="inventory"` (gold, 3 sloty, plecak); `applyFoldState` uwzględnia inventory; po renderze `loadInventory(character.id)` |
| `frontend/js/inventory.js` | **NOWY** — równoległy fetch inventory + gold, wypełnianie slotów/plecaka, heurystyka slotu, delegacja Załóż/Zdejmij |
| `frontend/index.html` | `<script src="./js/inventory.js">` za `app.js` |
| `frontend/styles.css` | Style panelu ekwipunku (`--muted`/`--border` spójne z projektem) |
| `frontend/js/combat_panel.js` | Po zamknięciu popupu łupów: `refreshInventoryPanel()` |

### Testy (7/7 ✅ na .61)
```
test_get_inventory_returns_items
test_get_inventory_gold
test_equip_item_sets_slot
test_equip_replaces_previous_in_slot
test_unequip_item_clears_slot
test_post_equip_null_slot_unequips
+ test z wariantu 8E-1 (gold endpoint)
```

### Poprawki bugów
- `slot` nie był zerowany przy zdejmowaniu (`equipped=0` ale `slot` zostawał) — naprawione
- Podmiana przedmiotu w slocie — stary dostawiał tylko `equipped=0`, teraz także `slot=NULL`

---

## ⚠️ Incydent operacyjny: korupcja DB

**Kiedy:** przy restarcie backendu po deployu `c954c47` (8E-3)
**Błąd:** `sqlite3.DatabaseError: database disk image is malformed`
**Przyczyna:** fizyczna korupcja pliku SQLite (nie bug kodu)

**Przywócono:**
- Backup: `backups/ai_gm_20260424_122704.db` → `data/ai_gm.db`
- Restart: backend + frontend
- Weryfikacja: `/api/healthz` → 200
- Uszkodzona kopia zachowana jako: `data/ai_gm.db.corrupt_`

**Utracone dane:** dane między 2026-04-24 12:27 a 2026-04-27 ~08:00 (kampanie, postacie stworzone w tym oknie)

**Rekomendacja:** patrz `docs/ops/db_backup_policy.md` (do stworzenia)

---

## Deploy checklist
- [ ] `git pull` na serwerze `.61` (branch `phase-8e-frontend`)
- [ ] **Restart backendu** (zmiany w `loot_service` + `inventory`)
- [ ] Redeploy frontendu (nowy `inventory.js` + zmiany `app.js`)
- [ ] Hard refresh przeglądarki
- [ ] Sprawdź czy panel Ekwipunek wyświetla sloty + plecak
- [ ] Utwórz postać warrior — starter items widoczne w plecaku
- [ ] Kliknij "Załóż" — item trafia do slotu
- [ ] Kliknij "Zdejmij" — slot pusty, item wrócił do plecaka
- [ ] Gold widoczny w portfelu
- [ ] `main` NIE był mergowany — zgodnie z regułą

## Następny krok: 8E-4 Loot Popup

Prompt: `docs/Phase_8E_frontend/8E-4_loot_popup.md`
