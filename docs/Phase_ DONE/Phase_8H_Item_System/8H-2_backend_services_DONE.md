<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-30 -->

# PROMPT 8H-2 — Backend Services (Phase 8H — Item System Unification)

> Wymaga ukończonego 8H-1. REV 2 — pełna implementacja na podstawie skanu kodu.

---

## Cel

Usunięcie wszystkich referencji do `game_config_consumables` i `consumable_key` jako ścieżki katalogu z warstwy serwisów i routerów. Consumables są teraz w `game_config_items` z `item_type='consumable'` i trafiają do inventory przez `item_key`.

---

## Mapa zmian (pełna, wynikająca z rzeczywistego kodu)

| Plik | Co zmienić | Pilność |
|---|---|---|
| `services/loot_service.py` | `_catalog_entry`, SQL queries, `grant_loot_to_character` | 🔴 Krytyczne |
| `services/shop_service.py` | Zapytanie `game_config_consumables`, `consumable_key` w buy/sell | 🔴 Krytyczne |
| `services/game_engine.py` | Loot processing `consumable_key` (linie 60-61) | 🔴 Krytyczne |
| `services/combat_service.py` | Grant consumable przez `consumable_key` (linie 236-238, 1413-1414) | 🔴 Krytyczne |
| `services/admin_config.py` | `list_items()` — kolumna `weight`, `_validate_proficiency_classes` | 🟡 Ważne |
| `services/admin_config_transfer.py` | `game_config_consumables` w EXPORT_TABLES | 🟡 Ważne |
| `routers/admin.py` | Pydantic models — `weight`, `proficiency_classes`, `base_price`, `consumable_key` | 🟡 Ważne |
| `routers/admin_cheat.py` | `_resolve_inventory_add_key` — caąły blok `game_config_consumables` | 🟡 Ważne |
| `routers/debug.py` | Linie 74, 87 — `consumable_key` w SELECT | 🟢 Minor |

---

## Kontekst techniczny

- **Branch:** `develop`
- **NIE ruszać:** `docker-compose.yml` prod, `data/ai_gm.db`, `system_prompt.txt`
- **Zasada:** `consumable_key` kolumna w `character_inventory` **pozostaje** (deprecated, ale nullable) — nie dropuj. Kod Pythona ma ją obsłużyć jako fallback read-only.
- **Zasada:** `game_config_consumables` tabela **pozostaje** (nie dropuj w tym tasku) — drop będzie w osobnej migracji po potwierdzeniu brak referencji w produkcji.

---

## Implementacja

*(Pełny kod REV 2 — patrz historia git, commit na branch `develop`)*

Główne zmiany wg mapy powyżej:
- `loot_service.py`: `_catalog_entry` czyta z `game_config_items`, `grant_loot_to_character` używa `item_key` dla consumable
- `shop_service.py`: catalog query z `game_config_items`, `buy_item` payload przez `item_key`
- `game_engine.py`: loot linie 60-61 fallback `item_key or consumable_key`
- `combat_service.py`: grant consumable przez `item_key`
- `admin_config.py`: `list_items` na nowych kolumnach 8H, `upsert_item` obsługuje `ac_bonus`, `effect_*`, `allowed_classes`, `approved`
- `admin.py`: modele `ItemCreateReq`/`ItemPatchReq`, `LootEntryReq` (XOR), `ConsumableCreateReq` z `value_gp`
- `admin_cheat.py`: `_resolve_inventory_add_key` zwraca `item_key` dla consumables
- `admin_config_transfer.py`: `game_config_consumables` usunięte z EXPORT_TABLES

---

## Co zostało zrobione *(uzupełnia Cursor)*

- **`admin_config.py`**: `list_items` / `create_item` / `update_item` / `delete_item` na kolumny 8H (`allowed_classes`, `ac_bonus`, efekty, `ai_generated`, `approved`; bez `weight` / `proficiency_classes`). `_serialize_allowed_classes`, `_normalize_item_row`. Consumable CRUD jako proxy na `game_config_items` (`item_type='consumable'`), loot `item_key` XOR `weapon_key` (`consumable_key` w API mapuje na `item_key`), `_validate_starter_items_json` normalizuje `consumable_key` → `item_key`.
- **`admin.py`**: modele `ItemCreateReq` / `ItemPatchReq`, `LootEntryReq` (XOR item/weapon; deprecated `consumable_key`), `ConsumableCreateReq`/`Patch` z `value_gp` zamiast `base_price` w modelu; handlery pod nowe pola.
- **`admin_cheat.py`**: `_resolve_inventory_add_key` zwraca **`item_key`** dla consumables (katalog `game_config_items`), fallback do starej tabeli `game_config_consumables` jeśli istnieje.
- **Wcześniej w tej fazie**: `loot_service`, `shop_service`, `game_engine`, `combat_service`, `admin_config_transfer`.

**Docker / deploy:** po wdrożeniu na środowisko z obrazem backendu bez bind-mount — **`docker compose -f docker-compose.dev.yml up -d --build backend`**.

**Testy:** suite odpalona na `192.168.1.61` po SSH (brak modułu lokalnie).

---

## Notatki po implementacji *(Perplexity)*

**Cel osiągnięty.** Warstwa serwisów i routerów obsługuje zunifikowany model — consumables przez `item_key`, nie `consumable_key`.

**Endpointy items** w kodzie to `/admin/items` (GET/POST/PATCH/DELETE), nie `/admin/config/items` jak w REV 2 — korekta udokumentowana w raportach 8H-3 i 8H-4. Testy 8H-5 napisane pod poprawne ścieżki.

**Scope 8H-2 vs REV 2:** Cursor zaimplementował głównie warstwę admin (`admin_config.py`, `admin.py`, `admin_cheat.py`). Serwisy krytyczne (`loot_service`, `shop_service`, `game_engine`, `combat_service`) zostały zaktualizowane wcześniej w tej samej sesji — commit na `develop` zawiera całość.

**`game_config_consumables` tabela** — NIE zdropowana. Tech debt: drop po weryfikacji prod. Zakładka `Consumables` nadal widoczna w panelu admin (screenshot 2026-05-01) — do ukrycia przed Phase 9 (nie blokuje).

**Falling pytest** — problem z zawieszającym się `pytest` (stan `D`) niezależny od 8H — do debugowania przed 8H-5 lub po. Sugestia: `--timeout=30 -x --ignore=tests/test_llm*`.
