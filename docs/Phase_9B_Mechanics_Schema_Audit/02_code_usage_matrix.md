# Macierz: kolumny vs użycie w kodzie

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
| Rzuty w grze | **`dice.resolve_roll`** używa **`SKILL_STAT_MAP`** w kodzie, nie odczytuje `linked_stat` z DB w runtime | Ryzyko **rozjazdu** z `game_config_skills.linked_stat` |
| `rank_ceiling` | Admin, opisy w `config_service` | **`dice.resolve_roll`** bierze rangę z arkusza (`skills[key]`) i **nie** porównuje jej z `rank_ceiling` z DB. Ewentualny limit — do weryfikacji w [`characters` API](../../backend/app/api/characters.py) przy zapisie postaci. |

---

## `game_config_dc`

| Kolumna | Gdzie używane | Uwagi |
|---------|----------------|-------|
| `key`, `label`, `value`, `description` | **`config_service`**, **`/mechanics/metadata`** (`dc_tiers`) | |
| W `resolve_roll` | Parametr **`dc`** jest argumentem funkcji — **pochodzi z wywołania** (np. parser komendy), nie z automatycznego JOIN do `game_config_dc` | |

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
| Wszystkie | Głównie **admin** + walidacja `effect_json` | Wyszukaj `game_config_conditions` poza `admin_config` dla efektów w walce |

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
| `loot_service` (JOIN), `shop_service`, `admin_cheat` | Kompatybilność wstecz; nowe dane w `game_config_items` |

---

## Import / eksport

[`admin_config_transfer.py`](../../backend/app/services/admin_config_transfer.py) — kopiuje całe wiersze wybranych tabel. Jeśli kolumna jest **tylko wizualna**, nadal podróżuje w bundle — wpływa na **źródło prawdy** dla zespołu contentu.

---

## Następne kroki audytu

1. Dla każdej komórki „nie znaleziono” — uruchom `rg 'kolumna' backend/app --glob '!**/tests/**'`.
2. Oznacz pola **„tylko LLM”** vs **„martwe”** w [`04_decisions_log.md`](04_decisions_log.md).
3. Zaktualizuj [`player_rulebook/00_outline_and_tone.md`](player_rulebook/00_outline_and_tone.md) tak, by nie obiecywać mechanik oznaczonych jako niewdrożone.
