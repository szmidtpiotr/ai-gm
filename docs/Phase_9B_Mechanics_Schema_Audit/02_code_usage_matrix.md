# Macierz: kolumny vs użycie w kodzie

**Sesja 8 (**[S8](../04_decisions_log.md)**):** Macierz jest **spójna z uchwałami**; pola oznaczone jako „nie w silniku” lub „docelowo” opisują **stan kodu**, nie cofanie decyzji projektowych — szczegóły wdrożenia: [`06_schema_gaps.md`](../06_schema_gaps.md).

**Metoda:** przegląd [`backend/app/`](../../backend/app/) (głównie `services`, `api`, `routers`). Status **„nie znaleziono w silniku”** oznacza brak odczytu w logice deterministycznej walki/rzutów — pole może nadal być w panelu admin, eksporcie lub promptach.

**Definicja „używane w grze”** (Sesja 0): patrz [`00_brief.md`](00_brief.md) — obejmuje **mechanikę** i **twarde dane dla LLM** (anty-halucynacja katalogu). Kolumna może być „używana” w sensie produktu nawet jeśli nie jest w `combat_service`, o ile np. trafia do katalogu / metadanych dla modelu.

Legenda:

- **Silnik** — `combat_service`, `dice`, bezpośrednie obliczenia.
- **Config runtime** — `config_service.get_runtime_config`, `build_runtime_config_block`.
- **Metadata API** — `/mechanics/metadata`, `mechanics.py`.
- **Admin** — `admin_config`, `routers/admin`.
- **Loot / sklep** — `loot_service`, `shop_service`.
- **Prompt LLM** — tekst wstrzykiwany do modelu (katalogi, opisy).

---

## `game_config_weapons`

| Kolumna | Gdzie używane | Uwagi |
|---------|----------------|-------|
| `key` | Wszędzie (klucz FK, ekwipunek, `combat_service._weapon_key_from_sheet`) | |
| `label` | Admin, loot, opisy | |
| `damage_die` | **`combat_service._load_weapon_row`** → obrażenia gracza vs wróg | |
| `linked_stat` | **`combat_service`** — modyfikator obrażeń z arkusza (`_stat_mod`) | Pojedynczy stat; **brak logiki finesse (max STR/DEX)** |
| `allowed_classes` | Admin, walidacja / transfer; nie czytane wprost w `combat_service` przy ciosie | |
| `is_active` | Zapytania broni domyślnej / katalogi | |
| `weapon_type` | Admin + walidacja | **Nie** w SELECT w `combat_service._load_weapon_row` |
| `two_handed` | Admin | **Nie** w ścieżce obrażeń w `combat_service` |
| `finesse` | Admin | **Nie** w ścieżce obrażeń |
| `range_m` | Admin | **Nie** w ścieżce obrażeń |
| `description`, `note` | Admin, ewentualnie LLM przez inne ścieżki | |
| `value_gp` | Sklep, ekonomia | |
| `weight_kg` | Admin, ewentualnie encumbrance (sprawdź osobno) | Grep: poza adminem rzadko |
| `ai_generated`, `approved` | Filtrowanie katalogu / admin | |
| `locked_at`, `created_at`, `updated_at` | Admin / audyt | |

---

## `game_config_items`

| Kolumna | Gdzie używane | Uwagi |
|---------|----------------|-------|
| `key`, `label`, `item_type`, `value_gp`, `description` | Loot, sklep, panel, **`combat_service.get_item_catalog_for_prompt`** | |
| `effect_type`, `effect_dice`, `effect_bonus`, `effect_target`, `charges` | **`get_item_catalog_for_prompt`** dla `item_type=consumable` | Tekst w promptcie |
| `ac_bonus` | **`get_item_catalog_for_prompt`** gdy `item_type=armor` | Dodaje fragment „(AC +N)” |
| `effect_json` | **`loot_service`** (zwracany w payloadach), **admin** (`_normalize_effect_json`) | **Nie** parsowany w `get_item_catalog_for_prompt` |
| `allowed_classes` | Admin, item CRUD | |
| `is_active`, `approved`, `ai_generated` | Filtry katalogu promptu (`is_active`, `approved`) | |
| `weight_kg`, `note` | Admin, loot (część zapytań) | `loot_service` może nadal odwoływać się do `weight` na starych DB — sprawdź `PRAGMA` |

---

## `game_config_stats`

| Kolumna | Gdzie używane | Uwagi |
|---------|----------------|-------|
| `key`, `label`, `description` | **`config_service`** → runtime config; **`mechanics._build_test_descriptions`** (z `list_stats`) | Moduły z arkusza używają **kluczy** statów z arkusza, nie bezpośrednio tej tabeli przy każdym rzucie |
| `sort_order`, `locked_at` | Admin | |

---

## `game_config_skills`

| Kolumna | Gdzie używane | Uwagi |
|---------|----------------|-------|
| `key`, `label`, `description`, `linked_stat`, `rank_ceiling` | **`config_service`**, admin, **`mechanics`** (opisy testów) | |
| Rzuty w grze | **`dice.resolve_roll`** / **`skill_linked_stat_for_test`** — `linked_stat` z **`get_runtime_config()`** (DB gdy `USE_DB_CONFIG`), alias `melee_attack`→`attack`; fallback **`SKILL_STAT_MAP`** | [**S4b**](../04_decisions_log.md) wdrożone w `dice.py`; statyczna mapa zostaje zapasem dla testów spoza tabeli skills. |
| `rank_ceiling` | Admin, opisy w `config_service` | **`dice.resolve_roll`** bierze rangę z arkusza (`skills[key]`) i **nie** porównuje jej z `rank_ceiling` z DB. Ewentualny limit — do weryfikacji w [`characters` API](../../backend/app/api/characters.py) przy zapisie postaci. |

---

## `game_config_dc`

| Kolumna | Gdzie używane | Uwagi |
|---------|----------------|-------|
| `key`, `label`, `value`, `description` | **`config_service`**, **`/mechanics/metadata`** (`dc_tiers`) | **`value`** = jedyne źródło prawdy dla liczbowego DC przy danym **`key`** ([**S5**](../04_decisions_log.md)). |
| W `resolve_roll` | Parametr **`dc`**: liczba po **`resolve_dc_for_roll`** w [`turns.py`](../../backend/app/api/turns.py); komenda `/roll … hard` — klucz → `value` (**[S9](../04_decisions_log.md)**) | Orchestracja LLM: mapowanie narracji na klucz z `game_config_dc` (**[S5]**) |

---

## `game_config_enemies`

| Kolumna | Gdzie używane | Uwagi |
|---------|----------------|-------|
| `hp_base`, `ac_base`, `attack_bonus`, `damage_die`, `dex_modifier` | **`combat_service`** (inicjacja wrogów, ataki, lista do promptu) | Zob. `_fetch_enemy_row` i pomocnicze listy |
| `loot_table_key`, `drop_chance` | Loot po zabiciu | |
| `tier`, `xp_award`, `damage_type`, `attacks_per_turn`, `damage_bonus`, `conditions_immune` | Część pól może być **tylko** w adminie / meta — potwierdź grep dla każdego w `combat_service` | Uzupełnij w kolejnej iteracji audytu |

---

## `game_config_conditions`

| Kolumna | Gdzie używane | Uwagi |
|---------|----------------|-------|
| `effect_json` | Admin + walidacja; docelowo **wspólny schemat** z `game_config_items.effect_json` ([**S6**](../04_decisions_log.md), [**S2**](../04_decisions_log.md)) — **inne znaczenie gry**: „stan” vs bonus z przedmiotu (+STR itd.), rozróżniane w JSON / meta |
| Pozostałe | Głównie **admin** | Wyszukaj `game_config_conditions` poza `admin_config` dla efektów w walce |

_Szybki grep (backend/app, bez testów): poza adminem warunki mogą być rzadkie — jeśli brak, wpisz: **„tylko admin / przyszły combat pipeline”**._

---

## `game_config_loot_tables` / `game_config_loot_entries`

| Obszar | Użycie |
|--------|--------|
| `loot_service`, `combat_service` (loot po zabiciu), ekonomia | Klucze łączą wpisy z bronią/przedmiotami |

---

## `game_config_archetypes`

| Obszar | Użycie |
|--------|--------|
| [`characters.create_character`](../../backend/app/api/characters.py) | `starter_items_json`, `starter_gold_gp` → `grant_loot_to_character` |

---

## `game_config_meta`

| Obszar | Użycie |
|--------|--------|
| Flagi globalne (location integrity, itd.) | Różne serwisy — poza mechaniką broni, raczej świat/sesja |

---

## `game_config_consumables`

| Obszar | Użycie |
|--------|--------|
| `loot_service` (JOIN), `shop_service`, `admin_cheat` | **Legacy** — docelowo wyłącznie **`game_config_items`** z `item_type = consumable`; jeden **`key`** jak dla każdego przedmiotu ([**S6**](../04_decisions_log.md)) |

---

## Import / eksport

[`admin_config_transfer.py`](../../backend/app/services/admin_config_transfer.py).

| Ścieżka | Zakres | Uwagi |
|---------|--------|--------|
| **`export_catalog_snapshot` / `import_catalog_snapshot`** | M.in. `items`, `consumables`, `loot_*`, broń, wrogowie, warunki… | **Kanoniczny** import pełnego katalogu treści — INSERT wg **wszystkich** kolumn z JSON (**[S7](../04_decisions_log.md)**). `game_config_meta` w pliku przy imporcie **ignorowane**. |
| **`export_config` / `import_config`** | Stats, skills, dc; opcjonalnie broń, wrogowie, warunki | **Bez** przedmiotów i lootu w standardowym bundle; przy broni **węższy** zestaw kolumn w INSERT niż pełna migracja — **nie** zastępuje snapshotu przy pełnym wdrożeniu treści. |

LLM / generator: kontekst i round-trip treści → preferuj **snapshot**; zapis wyłącznie przez **API**; backup pliku DB przed importem + **retencja** kopii — **[S7a](../04_decisions_log.md)**; jedna baza — **[S7]** / **[S7a](../04_decisions_log.md)**.

---

## Następne kroki (faza implementacji)

1. Zamknąć pozycje z [`06_schema_gaps.md`](../06_schema_gaps.md) w kodzie / migracjach zgodnie z uchwałami (**[S4b]**, **[S5]**, **[S6]**, **[S7]**…).
2. Po zmianach w silniku — ewentualna aktualizacja komórek macierzy (grep) i **[AUDIT]**.
3. Pełna redakcja [`player_rulebook/`](player_rulebook/) według outline (**[S8]**).
