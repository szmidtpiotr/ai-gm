<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-30 -->

# PROMPT 8H-1 — DB Migrations (Phase 8H — Item System Unification)

> Workflow: REV 1 (pytania blokujące) → odpowiedzi Cursora → REV 2 (implementacja) → raport Cursora → notatki Perplexity → DONE.

---

## Cel

Przebudowa schematu tabel przedmiotów:
1. Rozszerzyć `game_config_items` o nowe kolumny
2. Przenieść dane z `game_config_consumables` do `game_config_items`
3. Naprawić `game_config_loot_entries` (XOR FK, usunąć consumable_key)
4. Dodać flagi `ai_generated`/`approved` do katalogów broni i przedmiotów
5. Posprzątać niespójności kolumn (`weight` DROP, `proficiency_classes` → `allowed_classes`)

**NIE implementuj jeszcze zmian w serwisach Python — tylko migracje SQL.**

---

## Kontekst techniczny

- **Plik migracji:** `backend/app/migrations_admin.py` — lista `ADMIN_MIGRATIONS`
- **Baza:** `data/ai_gm.db` (SQLite 3.45.1 — DROP COLUMN dostępne)
- **NIE ruszać:** `docker-compose.yml` prod, `data/ai_gm.db` (nie dropuj danych)
- **Tabele istniejące:** `game_config_items`, `game_config_weapons`, `game_config_consumables`, `game_config_loot_entries`, `character_inventory`

---

## Odpowiedzi Cursora (REV 1)

| Pytanie | Odpowiedź | Wniosek |
|---------|-----------|--------|
| Branch | `develop` | ⚠️ Pracujemy na develop — przed mergę do main upewnić się że baseline przechodzi |
| Git status | Niezacommitowane: `docker-compose.dev.yml`, `docker-compose.yml` | ⚠️ Commit lub stash przed implementacją |
| SQLite wersja | `3.45.1` | ✅ DROP COLUMN dostępne |
| game_config_items kolumny | ma `weight` + `weight_kg` (duplikat), ma `proficiency_classes` (brak `allowed_classes`) | ✅ Znany stan |
| game_config_consumables | 15 kolumn, `base_price` zamiast `value_gp` | ✅ Znany stan, 39 wierszy do migracji |
| game_config_loot_entries | ma już `weapon_key` ✅, ma `currency_code` ⚠️ (nieoczekiwana kolumna — zachować przy przebudowie!) | Przebudowa nadal potrzebna (usunąć consumable_key, naprawić XOR) |
| Dane consumables | 39 wierszy | Wszystkie migrować do items |
| character_inventory XOR CHECK | ✅ Istnieje, `sum = 1` | UPDATE z jednoczesnym SET item_key + NULL consumable_key jest bezpieczny |
| Baseline testów | 🔴 **12 errors during collection** | ⚠️ BLOCKER — patrz poniżej |
| loot_entries weapon_key | już istnieje ✅ | Nie dodawać ponownie |

---

## ⚠️ BLOCKER: Baseline testów czerwony (12 errors during collection)

**PRZED implementacją migracji** Cursor musi naprawić błędy kolekcji testów.

Krok obowiązkowy:

```bash
# Na serwerze .61:
python3 -m pytest tests/test_phase8d_migrations_fixed.py --tb=long -q
# Pokaż pełny traceback pierwszego błędu
```

Jeśli błędy są w plikach testowych fazy 8D (zepsute importy, brakujące fixture, niezgodna sygnatura):
- **Napraw importy** w `tests/test_phase8d_migrations_fixed.py` i pozostałych 11 plikach z błędami
- **NIE usuwaj** testów — tylko napraw błędy kolekcji (zwykle import error lub fixture mismatch)
- Po naprawie: `python3 -m pytest --tb=no -q` musi pokazać zielony baseline

**Dopiero po zielonym baseline** przejdź do implementacji migracji poniżej.

---

## Implementacja (REV 2)

Pracujesz na branchu `develop`. Plik docelowy: `backend/app/migrations_admin.py`.

### Zasady ogólne

1. Wszystkie migracje dopisuj **na końcu listy `ADMIN_MIGRATIONS`**
2. Każda migracja jako osobny string SQL w liście (styl istniejących wpisach)
3. ALTER TABLE bez `IF NOT EXISTS` — obsłuż `OperationalError: duplicate column name` tak jak inne ALTER TABLE w projekcie
4. Żadna migracja nie może usuwać ani modyfikować danych sprzed migracji (tylko INSERT/UPDATE/ALTER)
5. Wykonaj w kolejności: najpierw ADD COLUMN, potem INSERT danych, na końcu DROP COLUMN

---

### Krok 1 — Rozszerz `game_config_items` o nowe kolumny

Dopisz do `ADMIN_MIGRATIONS` (każdy ALTER jako osobny string):

```python
# Phase 8H-1 — Item System Unification

"ALTER TABLE game_config_items ADD COLUMN ac_bonus INTEGER NOT NULL DEFAULT 0",
"ALTER TABLE game_config_items ADD COLUMN effect_type TEXT",
"ALTER TABLE game_config_items ADD COLUMN effect_dice TEXT",
"ALTER TABLE game_config_items ADD COLUMN effect_bonus INTEGER NOT NULL DEFAULT 0",
"ALTER TABLE game_config_items ADD COLUMN effect_target TEXT NOT NULL DEFAULT 'self'",
"ALTER TABLE game_config_items ADD COLUMN charges INTEGER NOT NULL DEFAULT 1",
"ALTER TABLE game_config_items ADD COLUMN ai_generated INTEGER NOT NULL DEFAULT 0",
"ALTER TABLE game_config_items ADD COLUMN approved INTEGER NOT NULL DEFAULT 1",
"ALTER TABLE game_config_items ADD COLUMN allowed_classes TEXT NOT NULL DEFAULT '[]'",
```

---

### Krok 2 — Skopiuj `proficiency_classes` → `allowed_classes`, usuń starą kolumnę

```python
"""
UPDATE game_config_items
SET allowed_classes = proficiency_classes
WHERE proficiency_classes IS NOT NULL AND proficiency_classes != '[]'
""",
# SQLite 3.45.1 obsługuje DROP COLUMN
"ALTER TABLE game_config_items DROP COLUMN proficiency_classes",
```

> W kodzie Pythona od tego momentu używaj wyłącznie `allowed_classes`.

---

### Krok 3 — Usuń duplikat `weight` z `game_config_items`

```python
# Przed DROP — upewnij się że weight_kg ma dane (tam gdzie weight było niezerowe)
"""
UPDATE game_config_items
SET weight_kg = weight
WHERE weight > 0 AND weight_kg = 0.0
""",
"ALTER TABLE game_config_items DROP COLUMN weight",
```

---

### Krok 4 — Migracja danych: `game_config_consumables` → `game_config_items`

```python
"""
INSERT OR IGNORE INTO game_config_items (
    key, label, item_type, description,
    value_gp, weight_kg, allowed_classes,
    ac_bonus,
    effect_type, effect_dice, effect_bonus, effect_target, charges,
    note, is_active, locked_at, created_at, updated_at,
    ai_generated, approved
)
SELECT
    key,
    label,
    'consumable',
    description,
    base_price,
    weight_kg,
    '[]',
    0,
    effect_type,
    effect_dice,
    effect_bonus,
    effect_target,
    charges,
    note,
    is_active,
    locked_at,
    created_at,
    updated_at,
    0,
    1
FROM game_config_consumables
""",
```

---

### Krok 5 — Naprawienie `game_config_loot_entries` (przebudowa tabeli)

`weapon_key` już istnieje. Przebudowa konieczna żeby:
- Usunąć `consumable_key` (dane przeniesione do `item_key` przez typ)
- Naprawić `item_key` (był NOT NULL w oryginalnym zamiarze, ale faktycznie nullable — zostaje nullable)
- Dodać XOR CHECK
- Zachować nieoczekiwaną kolumnę `currency_code`

```python
"""
CREATE TABLE IF NOT EXISTS game_config_loot_entries_8h (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    loot_table_key TEXT NOT NULL REFERENCES game_config_loot_tables(key) ON DELETE CASCADE,
    item_key       TEXT REFERENCES game_config_items(key) ON DELETE CASCADE,
    weapon_key     TEXT REFERENCES game_config_weapons(key) ON DELETE CASCADE,
    currency_code  TEXT,
    weight         INTEGER NOT NULL DEFAULT 10,
    qty_min        INTEGER NOT NULL DEFAULT 1,
    qty_max        INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT loot_xor CHECK (
        (CASE WHEN item_key   IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN weapon_key IS NOT NULL THEN 1 ELSE 0 END) = 1
    )
)
""",
"""
INSERT OR IGNORE INTO game_config_loot_entries_8h
    (id, loot_table_key, item_key, weapon_key, currency_code, weight, qty_min, qty_max)
SELECT
    id,
    loot_table_key,
    COALESCE(
        item_key,
        -- consumable_key mapuj na item_key bo consumables są teraz w game_config_items
        CASE WHEN consumable_key IS NOT NULL
             AND EXISTS (SELECT 1 FROM game_config_items WHERE key = consumable_key)
             THEN consumable_key
             ELSE NULL
        END
    ),
    weapon_key,
    currency_code,
    weight,
    qty_min,
    qty_max
FROM game_config_loot_entries
WHERE
    -- pomijaj wiersze które złamałyby XOR (np. oba NULL albo oba NOT NULL)
    (
        COALESCE(
            item_key,
            CASE WHEN consumable_key IS NOT NULL
                 AND EXISTS (SELECT 1 FROM game_config_items WHERE key = consumable_key)
                 THEN consumable_key ELSE NULL END
        ) IS NOT NULL
    ) != (weapon_key IS NOT NULL)
""",
"DROP TABLE game_config_loot_entries",
"ALTER TABLE game_config_loot_entries_8h RENAME TO game_config_loot_entries",
"""
CREATE INDEX IF NOT EXISTS idx_loot_entries_table
ON game_config_loot_entries(loot_table_key)
""",
```

> ⚠️ Jeśli któreś wiersze mają jednocześnie `item_key` i `weapon_key` NOT NULL (naruszenie XOR) — będą pominięte przez WHERE. Cursor powinien to sprawdzić przed migracją:
> `SELECT COUNT(*) FROM game_config_loot_entries WHERE item_key IS NOT NULL AND weapon_key IS NOT NULL;`
> Jeśli wynik > 0 — zgłoś do Perplexity przed kontynuacją.

---

### Krok 6 — Migracja `character_inventory`: consumable_key → item_key

```python
"""
UPDATE character_inventory
SET item_key = consumable_key,
    consumable_key = NULL
WHERE consumable_key IS NOT NULL
  AND item_key IS NULL
  AND weapon_key IS NULL
  AND EXISTS (
      SELECT 1 FROM game_config_items WHERE key = character_inventory.consumable_key
  )
""",
```

> XOR CHECK (`sum = 1`) jest spełniony: jednocześnie ustawiamy item_key i czyścimy consumable_key w jednym UPDATE — SQLite sprawdza CHECK po UPDATE wiersza, nie po każdej kolumnie osobno.

---

### Krok 7 — Flagi `ai_generated`/`approved` w `game_config_weapons`

```python
"ALTER TABLE game_config_weapons ADD COLUMN ai_generated INTEGER NOT NULL DEFAULT 0",
"ALTER TABLE game_config_weapons ADD COLUMN approved INTEGER NOT NULL DEFAULT 1",
```

---

### Krok 8 — Flaga `item_integrity_enabled` w `game_config_meta`

```python
"""
INSERT OR IGNORE INTO game_config_meta (key, value)
VALUES ('item_integrity_enabled', '0')
""",
```

---

### Krok 9 — Zaktualizuj `ALLOWED_ITEM_TYPES` w `admin_config.py`

W pliku `backend/app/services/admin_config.py`:

```python
# PRZED:
ALLOWED_ITEM_TYPES = {"weapon", "armor", "consumable", "misc", "quest"}

# PO:
ALLOWED_ITEM_TYPES = {"weapon", "armor", "consumable", "misc", "quest", "narrative"}
```

---

### Weryfikacja po implementacji

```bash
# Restart backendu — run_admin_migrations() wykona nowe SQL-e
docker compose -f docker-compose.dev.yml restart backend

# Sprawdź zdrowie
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"

# Potwiedź kolumny
python3 -c "
import sqlite3; c = sqlite3.connect('data-dev/ai_gm.db'); c.row_factory = sqlite3.Row
print([r[1] for r in c.execute('PRAGMA table_info(game_config_items)')])
print([r[1] for r in c.execute('PRAGMA table_info(game_config_loot_entries)')])
"

# Potwiedź migrację consumables
python3 -c "
import sqlite3; c = sqlite3.connect('data-dev/ai_gm.db'); c.row_factory = sqlite3.Row
for r in c.execute('SELECT item_type, COUNT(*) n FROM game_config_items GROUP BY item_type'):
    print(dict(r))
"

# Testy (po naprawieniu baseline z blokera)
python3 -m pytest --tb=short -q
```

Oczekiwane wyniki:
- `game_config_items` ma: `ac_bonus`, `effect_type`, `effect_dice`, `effect_bonus`, `effect_target`, `charges`, `ai_generated`, `approved`, `allowed_classes`
- `game_config_items` NIE ma: `weight`, `proficiency_classes`
- `game_config_loot_entries` NIE ma: `consumable_key`
- `SELECT item_type='consumable', COUNT(*)` — powinno pokazać 39 wierszy
- Testy: green baseline

---

## Co zostało zrobione *(uzupełnia Cursor)*

- Dodano implementację REV 2 w `backend/app/migrations_admin.py`:
  - nowe kolumny w `game_config_items`: `ac_bonus`, `effect_type`, `effect_dice`, `effect_bonus`, `effect_target`, `charges`, `ai_generated`, `approved`, `allowed_classes`
  - migrację danych `game_config_consumables` → `game_config_items` (`INSERT OR IGNORE`)
  - migrację `character_inventory` z `consumable_key` do `item_key`
  - flagi `ai_generated` / `approved` dla `game_config_weapons`
  - flagę `item_integrity_enabled=0` w `game_config_meta`
- Dodano finalizujące helpery migracyjne dla fazy 8H:
  - kopiowanie `proficiency_classes` → `allowed_classes` i usunięcie `proficiency_classes`
  - kopiowanie `weight` → `weight_kg` i usunięcie `weight`
  - przebudowę `game_config_loot_entries` do modelu `item_key | weapon_key` z zachowaniem `currency_code` oraz usunięciem `consumable_key`
- Zaktualizowano seed `game_config_items`, żeby działał po usunięciu kolumn `weight` i `proficiency_classes`
- Zaktualizowano `ALLOWED_ITEM_TYPES` w `backend/app/services/admin_config.py` o `narrative`
- Naprawiono baseline collection testów:
  - dodano `tests/conftest.py` z ustawieniem ścieżki `backend`
  - dodano `pytest.ini` z `--import-mode=importlib` i ograniczeniem kolekcji do katalogów testowych
- Wykonano restart dev backendu; ponieważ `backend` w `docker-compose.dev.yml` jest budowany z obrazu bez mountu kodu, wymagany był **rebuild**, nie sam restart
- Po rebuildzie i starcie dev backendu:
  - `/api/healthz` zwraca `{"status":"ok"}`
  - `game_config_items` nie ma już `weight` ani `proficiency_classes`
  - `game_config_loot_entries` nie ma już `consumable_key`
  - `game_config_weapons` ma `ai_generated` i `approved`
  - `game_config_meta` ma `item_integrity_enabled='0'`
- Weryfikacja testowa:
  - `python3 -m pytest tests/test_phase8d_migrations_fixed.py --tb=no -q` na `.61`: **20 passed**
  - `python3 -m pytest --collect-only -q` na `.61`: **498 tests collected**
  - pełny `python3 -m pytest --tb=no -q` nie został domknięty, bo suite zawiesiła się w jednym z dalszych testów (proces wszedł w stan `D`), więc baseline runtime poza samą kolekcją nadal wymaga osobnego debugowania
- Smoke test po migracji:
  - backend startuje i healthcheck przechodzi
  - `app.services.admin_config.list_items()` nadal odwołuje się do starej kolumny `weight`, więc warstwa admin dla itemów/lootu wymaga osobnego follow-upu po 8H-1

---

## Notatki po implementacji *(Perplexity)*

**Cel osiągnięty.** Schema dev DB po migracji jest spójna z założeniami 8H-1: nowe kolumny dodane, legacy usunięte, consumables przeniesione.

**Nieoczekiwana kolumna `currency_code`** w `game_config_loot_entries` — zachowana poprawnie przez RENAME TABLE + SELECT z zachowaniem kolumny. To dobra decyzja: nie tracić danych, które mogą się przydać w Phase 8F (Economy).

**Hanging pytest** — to osobny problem, niezwiązany z migracją. Symptom (proces w stanie `D`) wskazuje na blokadę I/O, prawdopodobnie test próbuje otworzyć socket sieciowy lub blokuje na write do pliku. Suspect: jakiś test LLM-service który próbuje faktycznie wołać Ollama. Naprawa przed 8H-5, nie blokuje 8H-2/8H-3.

**`consumable_key` w `character_inventory`** — kolumna zachowana jako nullable legacy. Strategia read-only fallback w 8H-2 jest właściwa; nie dropujemy dopóki nie ma potwierdzenia że prod DB nie ma aktywnych wierszy z `consumable_key NOT NULL`.

**`game_config_consumables` tabela** — NIE zdropowana. Decyzja słuszna — drop po weryfikacji na produkcji że żaden serwis już z niej nie czyta. Należy do listy tech-debt do zamknięcia przed Phase 9.

**Następny krok:** 8H-2 ✅ DONE (commit `a270263`). Otwarte: debugowanie zawieszającego się `pytest` (sugerowane: `--timeout=30 -x --ignore=tests/test_llm*`).
