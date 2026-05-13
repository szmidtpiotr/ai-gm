<!-- last_updated: 2026-04-26 00:05 CEST | rev: 3 -->

# Phase 8C — Task 8C-5: Admin Panel — Items Config

> **STATUS: ✅ DONE** — commit `0c5e6c3` na `phase-8c-inventory-system`
> PR: https://github.com/szmidtpiotr/ai-gm/pull/2
> Testy: **118 passed** (bez zmian — task czysto frontendowy)

---

## Zrealizowane zmiany

| Plik | Zmiana |
|------|--------|
| `frontend/admin_panel/sections/game_design.js` | Zaktualizowany tab "Przedmioty" (był: "Items") |

### Co dodano / zmieniono

- **Zakładka:** „Przedmioty" (rename z "Items")
- **Filtr** po `item_type`: All / weapon / armor / consumable / misc / quest
  (konwencja `filterable` + `filterOptions`, spójnie z Skills)
- **Tabela:** `key` | `label` | `item_type` | `weight_kg` | `value_gp` | Akcje
  (usunięte z widoku: legacy `weight`, `proficiency_json`, `note`)
- **Formularz:** `description` jako textarea; legacy `weight` wysyłane jako `0` przez ukryte pole
- **Endpointy:** `GET/POST/PATCH/DELETE /api/admin/items` (istniały przed 8C-5)

### Uwagi

- Rebuild/restart backendu niepotrzebny — zmiana tylko w statycznym JS.
- Endpointy admin items istniały przed 8C-5 — został tylko zaktualizowany UI.
- Rozbieżność numeracji: w Notion "8C-5" oznacza `pending_loot` (inna rzecz);
  w repo docs "8C-5" = admin items config.
