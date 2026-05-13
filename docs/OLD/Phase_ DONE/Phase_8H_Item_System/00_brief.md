<!-- STATUS: DONE -->
<!-- PHASE: 8H | DATE_START: 2026-04-30 | DATE_END: 2026-05-01 -->

# Phase 8H — Item System Unification · Brief

> **Kanoniczna dokumentacja wdrożenia:** pliki `8H-1` … `8H-5` w tym folderze (`*_DONE.md` oraz `8H-5_tests.md`). Po zamknięciu fazy folder można skopiować do `docs/!Phase DONE/` według przyjętego workflow repo.

---

## 1. Cel fazy

Ujednolicenie i naprawa systemu przedmiotów:
- Scalenie `game_config_consumables` → `game_config_items` (nowy `item_type='consumable'`)
- Naprawa niespójności kolumn (`base_price` → `value_gp`, duplikat `weight` usunięty, `proficiency_classes` → `allowed_classes`)
- Dodanie kolumny `ac_bonus` dla zbroi
- Naprawienie `game_config_loot_entries` (item_key NOT NULL → XOR z weapon_key)
- Dodanie flag `ai_generated` / `approved` w katalogach (fundament pod Phase 8I — Item Integrity)
- Wstrzyknięcie katalogu itemów do kontekstu LLM (zapobieganie halucynacjom)

---

## 2. Zakres tasków

| Task | Opis | Stan |
|------|------|------|
| 8H-1 | DB migrations — scalenie tabel + naprawa kolumn + flagi AI | ✅ Zob. `8H-1_db_migrations_DONE.md` |
| 8H-2 | Backend services — migracja referencji z consumable_key → item_key | ✅ Zob. `8H-2_backend_services_DONE.md` |
| 8H-3 | Admin panel — zakładka Items + CRUD pod zunifikowany katalog | ✅ Zob. `8H-3_admin_panel_items_DONE.md` |
| 8H-4 | Item catalog context — katalog w promptcie LLM + resolver Grant Item | ✅ Zob. `8H-4_item_catalog_llm_context_DONE.md` |
| 8H-5 | Testy dedykowane (`test_8h_item_system.py`) | ✅ Zob. `8H-5_tests.md` |

---

## 3. Kluczowe decyzje projektowe

- `game_config_weapons` — zostaje bez zmian strukturalnych (7 unikalnych kolumn bojowych)
- `game_config_items` — rozszerzona, pochłania consumables przez `item_type`
- **`game_config_consumables` — dane przeniesione do `game_config_items`; sama tabela na PROD/DEV może nadal istnieć (brak `DROP` w 8H-1).** Usunięcie tabeli = osobna migracja po potwierdzeniu, że żaden kod ani zewnętrzne narzędzia jej nie czytają — patrz notatki w `8H-1` / `8H-2`.
- Armor zostaje w `game_config_items` z `item_type='armor'` + nowa kolumna `ac_bonus INTEGER DEFAULT 0`
- AC postaci obliczane z `sheet_json.defense.base` (bez zmian) — `ac_bonus` to dane źródłowe dla przyszłej automatyzacji
- `character_inventory.consumable_key` — zachowany tymczasowo (nulled, FK przeniesione na item_key)
- `game_config_loot_entries` — naprawiony XOR: item_key nullable, weapon_key nullable, consumable_key usunięty

---

## 4. Pliki których NIE ruszamy (granice fazy)

- `docker-compose.yml` prod (bez zmian poza ustalonymi wyjątkami)
- `data/ai_gm.db` — wyłącznie przez `ADMIN_MIGRATIONS` na środowisku
- **`backend/prompts/system_prompt.txt`** — nie był celem edycji w 8H; katalog przedmiotów dopinany jest **programowo** (`game_engine` + `combat_service.get_item_catalog_for_prompt`), patrz 8H-4
- Istniejące testy — bez zbędnego łamania baseline; nowy pakiet w `test_8h_item_system.py`

---

## 5. Zależności

- Phase 8F (economy) — jako kontekst sklepu / waluty przed 8H
- Serwisy zaktualizowane w ramach 8H-2 (`loot_service`, `shop_service`, `game_engine`, `combat_service`, `admin_config`, …)

---

## 6. Uwagi zamknięciowe

- **Pełny `pytest` na całym repo** może nadal wymagać osobnego debugu (timeout / zawieszenia) — nie jest to brak wdrożenia 8H-1–8H-5; szczegóły w `8H-1_db_migrations_DONE.md` i `8H-5_tests.md`.
- **Phase 8I (Item Integrity)** — flagi `ai_generated` / `approved` przygotowują grunt pod kolejną fazę.

---

## 7. Nowa struktura `game_config_items`

```sql
CREATE TABLE game_config_items (
    key                TEXT PRIMARY KEY,
    label              TEXT NOT NULL,
    item_type          TEXT NOT NULL DEFAULT 'misc'
                         CHECK(item_type IN ('armor','misc','quest','consumable','narrative')),
    description        TEXT NOT NULL DEFAULT '',
    value_gp           INTEGER NOT NULL DEFAULT 0,
    weight_kg          REAL NOT NULL DEFAULT 0.0,
    allowed_classes    TEXT NOT NULL DEFAULT '[]',   -- było: proficiency_classes
    ac_bonus           INTEGER NOT NULL DEFAULT 0,   -- nowe: dla armor
    effect_json        TEXT,                         -- zachowany dla misc/quest
    -- pola consumable (NULL dla non-consumable):
    effect_type        TEXT,
    effect_dice        TEXT,
    effect_bonus       INTEGER DEFAULT 0,
    effect_target      TEXT DEFAULT 'self',
    charges            INTEGER DEFAULT 1,
    -- kontrola GM/AI:
    ai_generated       INTEGER NOT NULL DEFAULT 0,
    approved           INTEGER NOT NULL DEFAULT 1,
    -- standard:
    note               TEXT,
    is_active          INTEGER NOT NULL DEFAULT 1,
    locked_at          TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
```

---

## 8. Mapa migracji danych

```
game_config_consumables → game_config_items:
  base_price → value_gp
  item_type  = 'consumable'
  allowed_classes = '[]'
  ac_bonus   = 0
  ai_generated = 0, approved = 1

game_config_weapons:
  + ai_generated INTEGER DEFAULT 0
  + approved INTEGER DEFAULT 1

game_config_items:
  + ac_bonus INTEGER DEFAULT 0
  + effect_type, effect_dice, effect_bonus, effect_target, charges (z consumables)
  + ai_generated INTEGER DEFAULT 0
  + approved INTEGER DEFAULT 1
  - weight (stara kolumna, usunąć jeśli SQLite >= 3.35)
  RENAME proficiency_classes → allowed_classes

game_config_loot_entries:
  item_key: NOT NULL → nullable
  weapon_key: nowa nullable FK → game_config_weapons(key)
  consumable_key: usunięta (dane przeniesione na item_key)
  CHECK XOR: dokładnie jeden z (item_key, weapon_key) NOT NULL

character_inventory:
  consumable_key: kolumna zostaje (NULL-owana dla istniejących wierszy gdzie jest item w nowym katalogu)
  XOR CHECK zaktualizowany (item_key OR weapon_key; consumable_key deprecated → NULL allowed)
```
