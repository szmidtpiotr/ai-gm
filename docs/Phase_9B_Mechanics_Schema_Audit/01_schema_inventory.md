# Inwentaryzacja schematu — tabele `game_config_*`

**Źródło pierwotne:** skonsolidowany opis z [`backend/app/migrations_admin.py`](../../backend/app/migrations_admin.py) (migracje addytywne + funkcje `_finalize_phase_8h_*`). Kolejność migracji na świeżej bazie może nieznacznie różnić się od starszej instancji — **kanoniczny snapshot** dla tej fazy uzyskaj przez `PRAGMA` na docelowej bazie (patrz [`00_brief.md`](00_brief.md)).

**Uwaga:** istnieje też tabela `gameconfig_encounter_templates` (bez podkreślnika w środku) — szablony starć; poniżej skupiamy się na prefiksie `game_config_`.

---

## Snapshot PRAGMA (do uzupełnienia)

_Wstaw tutaj wynik `PRAGMA table_info(...)` z żywej bazy + data._

---

## `game_config_stats`

| Kolumna | Typ / domyślne | Uwagi |
|---------|-----------------|-------|
| `key` | TEXT PK | Klucz statu (np. STR, DEX) |
| `label` | TEXT | Etykieta |
| `description` | TEXT | Opis |
| `sort_order` | INTEGER DEFAULT 0 | Kolejność list |
| `locked_at` | TEXT | Blokada edycji w adminie |

---

## `game_config_skills`

| Kolumna | Typ / domyślne | Uwagi |
|---------|-----------------|-------|
| `key` | TEXT PK | Klucz umiejętności (np. stealth) |
| `label` | TEXT | Nazwa |
| `linked_stat` | TEXT FK logiczny → `game_config_stats.key` | Walidacja w adminie względem stats |
| `rank_ceiling` | INTEGER DEFAULT 5 | Cap rangi w konfiguracji |
| `sort_order` | INTEGER DEFAULT 0 | |
| `locked_at` | TEXT | |
| `description` | TEXT | Opis (m.in. dla LLM w `config_service`) |

---

## `game_config_dc`

| Kolumna | Typ / domyślne | Uwagi |
|---------|-----------------|-------|
| `key` | TEXT PK | Np. easy, medium |
| `label` | TEXT | |
| `value` | INTEGER | Numeryczna wartość DC |
| `sort_order` | INTEGER DEFAULT 0 | |
| `locked_at` | TEXT | |
| `description` | TEXT | |

---

## `game_config_weapons`

| Kolumna | Typ / domyślne | Uwagi |
|---------|-----------------|-------|
| `key` | TEXT PK | |
| `label` | TEXT | |
| `damage_die` | TEXT | Np. d6, 1d8 |
| `linked_stat` | TEXT | Modyfikator do obrażeń w `combat_service` |
| `allowed_classes` | TEXT (JSON) | Klasy mogące używać |
| `is_active` | INTEGER DEFAULT 1 | |
| `locked_at` | TEXT | |
| `created_at` / `updated_at` | TEXT | |
| `description` | TEXT | |
| `weapon_type` | TEXT DEFAULT 'melee' | melee / ranged / spell (walidacja admin) |
| `two_handed` | INTEGER DEFAULT 0 | |
| `finesse` | INTEGER DEFAULT 0 | |
| `range_m` | INTEGER NULL | Zasięg (broń dystansowa) |
| `weight_kg` | REAL DEFAULT 0 | |
| `note` | TEXT | |
| `value_gp` | INTEGER DEFAULT 0 | Cena |
| `ai_generated` / `approved` | INTEGER | Flagi katalogu 8H |

---

## `game_config_enemies`

| Kolumna | Typ / domyślne | Uwagi |
|---------|-----------------|-------|
| `key`, `label` | TEXT | |
| `hp_base`, `ac_base`, `attack_bonus` | INTEGER | Baza walki |
| `dex_modifier` | INTEGER DEFAULT 0 | M.in. obrona / inicjatywa w zależności od ścieżki kodu |
| `damage_die` | TEXT | |
| `description` | TEXT | |
| `is_active`, `locked_at`, `created_at`, `updated_at` | | |
| `tier` | TEXT DEFAULT 'standard' | |
| `attacks_per_turn` | INTEGER DEFAULT 1 | |
| `damage_bonus` | INTEGER DEFAULT 0 | |
| `damage_type` | TEXT DEFAULT 'physical' | |
| `xp_award` | INTEGER DEFAULT 0 | |
| `conditions_immune` | TEXT | |
| `loot_table_key` | TEXT NULL → `game_config_loot_tables` | Możliwy duplikat migracji — sprawdź `PRAGMA` |
| `note` | TEXT | |
| `drop_chance` | REAL | Dodane migracją idempotentną (jeśli kolumna istnieje) |

---

## `game_config_conditions`

| Kolumna | Typ / domyślne | Uwagi |
|---------|-----------------|-------|
| `key` | TEXT PK | |
| `label` | TEXT | |
| `effect_json` | TEXT NOT NULL | JSON — walidacja składni w adminie |
| `description` | TEXT | |
| `is_active`, `locked_at`, `created_at`, `updated_at` | | |
| `stackable` | INTEGER DEFAULT 0 | |
| `auto_remove` | TEXT | |

---

## `game_config_meta`

| Kolumna | Typ / domyślne | Uwagi |
|---------|-----------------|-------|
| `key` | TEXT PK | Flagi globalne (np. location_integrity) |
| `value` | TEXT | |
| `updated_at` | TEXT | Po migracji 8D |

---

## `game_config_items`

Stan po fazie 8H: kolumny `proficiency_classes` oraz `weight` są **usuwane** migracją `_finalize_phase_8h_items_schema` (dane scalone do `allowed_classes` / `weight_kg`).

| Kolumna | Typ / domyślne | Uwagi |
|---------|-----------------|-------|
| `key` | TEXT PK | |
| `label` | TEXT | |
| `item_type` | TEXT DEFAULT 'misc' | armor, consumable, misc, … |
| `description` | TEXT | |
| `value_gp` | INTEGER | |
| `effect_json` | TEXT NULL | Dowolny JSON — semantyka do ustalenia w fazie |
| `is_active`, `locked_at`, `created_at`, `updated_at` | | |
| `note` | TEXT | |
| `weight_kg` | REAL | |
| `ac_bonus` | INTEGER DEFAULT 0 | Używane w tekście katalogu promptu (pancerz) |
| `effect_type`, `effect_dice`, `effect_bonus`, `effect_target` | | Konsumable / efekty w `get_item_catalog_for_prompt` |
| `charges` | INTEGER DEFAULT 1 | |
| `ai_generated`, `approved` | INTEGER | |
| `allowed_classes` | TEXT JSON | |

---

## `game_config_loot_tables`

| Kolumna | Typ / domyślne | Uwagi |
|---------|-----------------|-------|
| `key` | TEXT PK | |
| `label` | TEXT | |
| `description` | TEXT | |
| `is_active`, `locked_at`, `created_at`, `updated_at` | | |
| `gold_min`, `gold_max` | INTEGER | Złoto z tabeli |

---

## `game_config_loot_entries`

Po migracji 8H: **wyłącznie** `item_key` XOR `weapon_key` (konsumable jako wiersz w `game_config_items`). Opcjonalnie `currency_code` jeśli wcześniej dodano kolumnę (ścieżka migracji warunkowa).

| Kolumna | Uwagi |
|---------|-------|
| `id` | PK |
| `loot_table_key` | FK → `game_config_loot_tables` |
| `item_key` | FK → `game_config_items` |
| `weapon_key` | FK → `game_config_weapons` |
| `currency_code` | Opcjonalnie (stare bazy) |
| `weight`, `qty_min`, `qty_max` | Losowanie lootu |

---

## `game_config_consumables`

Tabela nadal może istnieć dla kompatybilności; część danych skopiowana do `game_config_items` (item_type `consumable`). [`admin_config`](../../backend/app/services/admin_config.py) oznacza CRUD konsumable jako deprecated na rzecz items.

Typowe kolumny z migracji: `key`, `label`, `description`, `effect_type`, `effect_dice`, `effect_bonus`, `effect_target`, `weight_kg`, `charges`, `base_price`, `note`, `is_active`, `locked_at`, `created_at`, `updated_at`.

---

## `game_config_archetypes`

| Kolumna | Uwagi |
|---------|-------|
| `key`, `label`, `description` | |
| `starter_items_json` | JSON listy `{weapon_key|item_key|consumable_key}` |
| `starter_gold_gp` | |
| `is_active`, `locked_at`, `created_at`, `updated_at` | |

---

## Notatka dla audytu

Przy aktualizacji tego pliku dopisz **krótki komentarz przy kolumnie**: „tylko admin”, „LLM”, „combat_service”, „dice”, jeśli już wiadomo z [`02_code_usage_matrix.md`](02_code_usage_matrix.md).
