```
Jesteś programistą Python/SQLite pracującym nad projektem ai-gm.
Repozytorium: github.com/szmidtpiotr/ai-gm

## KROK 0: Wyczyść repo przed branchwaniem

NIE zakładaj brancha phase-8d-location-integrity dopóki nie wykonasz poniższych kroków.

### 0A. Sprawdź diff ui.js
```
git diff frontend/js/ui.js
```
Pokaż mi pełny output. Chcę wiedzieć co zostało zmienione i do jakiego zadania należy ta zmiana.

### 0B. Sprawdź untracked katalogi
```
ls -la docs/
ls -la ai-gm/ 2>/dev/null || echo "brak"
```
Pokaż mi zawartość — chcę wiedzieć czy to pliki z promptami Phase 8D które właśnie tworzyliśmy.

### 0C. Czekaj na moją decyzję co commitować

Na podstawie outputu z 0A i 0B powiedz mi:
- Do jakiego zadania/fazy należy zmiana ui.js?
- Co jest w untracked katalogach?

Zaproponuj:
- Co commitować osobno przed 8D
- Co dodać do .gitignore
- Co zostawić jako untracked

NIE commituj nic samodzielnie. Czekaj na moją decyzję.

---

## KROK 1: Zbadaj kolumnę characters.location

Po wyczyszczeniu repo — zanim napiszesz jakąkolwiek migrację, uruchom:

```
sqlite3 data/ai_gm.db "SELECT id, name, location FROM characters LIMIT 10;"
sqlite3 data/ai_gm.db "SELECT COUNT(*) FROM characters WHERE location IS NOT NULL AND location != '';"
```

Pokaż mi wyniki i zaproponuj strategię koegzystencji z nowym `current_location_id` w `campaigns`:

| Pytanie | Twoja propozycja |
|---|---|
| Czy `characters.location` (TEXT) zostaje jako legacy bez usuwania? | ? |
| Czy `campaigns.current_location_id` (FK) jest nowym source of truth? | ? |
| Czy migracja powinna backfillować cokolwiek ze starej kolumny? | ? |

NIE pisz migracji dopóki nie zatwierdzę strategii koegzystencji.

---

## KROK 2: Implementacja migracji (dopiero po zatwierdzeniu)

Po moim zatwierdzeniu — zaimplementuj poniższe migracje idempotentnie
w stylu istniejącego migrations_admin.py (CREATE IF NOT EXISTS, ALTER z obsługą
"already exists", INSERT OR IGNORE).

### 8D-1: Tabela game_locations (globalna, bez FK do campaigns)
```sql
CREATE TABLE IF NOT EXISTS game_locations (
  id            INTEGER PRIMARY KEY,
  key           TEXT UNIQUE NOT NULL,
  label         TEXT NOT NULL,
  description   TEXT,
  parent_id     INTEGER REFERENCES game_locations(id),
  location_type TEXT DEFAULT 'macro' CHECK(location_type IN ('macro', 'sub')),
  rules         TEXT,
  enemy_keys    TEXT DEFAULT '[]',
  npc_keys      TEXT DEFAULT '[]',
  is_active     INTEGER DEFAULT 1,
  created_at    TEXT DEFAULT (datetime('now')),
  updated_at    TEXT DEFAULT (datetime('now'))
);
```

### 8D-2: Nowe kolumny w tabeli campaigns
```sql
ALTER TABLE campaigns ADD COLUMN current_location_id INTEGER
  REFERENCES game_locations(id);

ALTER TABLE campaigns ADD COLUMN session_flags TEXT DEFAULT '{}';
```
Obsłuż "duplicate column" gracefully (już istnieje = pomiń, zaloguj INFO).

### 8D-3: Flagi Location Integrity w game_config_meta
```sql
INSERT OR IGNORE INTO game_config_meta (key, value) VALUES
  ('location_integrity_enabled', '1'),
  ('location_parser_json_enabled', '1'),
  ('location_parser_fallback_enabled', '1');
```

### 8D-4: Tabela logów blokad
```sql
CREATE TABLE IF NOT EXISTS location_integrity_log (
  id                   INTEGER PRIMARY KEY,
  campaign_id          INTEGER NOT NULL REFERENCES campaigns(id),
  character_id         INTEGER REFERENCES characters(id),
  attempted_move       TEXT NOT NULL,
  current_location_key TEXT,
  reason_blocked       TEXT,
  created_at           TEXT DEFAULT (datetime('now'))
);
```

---

## KROK 3: Test schematu

Po migracji napisz test w tests/test_phase8d_location_integrity.py:
- Sprawdza że tabela game_locations istnieje i ma oczekiwane kolumny
- Sprawdza że campaigns ma kolumny current_location_id i session_flags
- Sprawdza że game_config_meta ma 3 nowe flagi
- Sprawdza że tabela location_integrity_log istnieje

Użyj testowej bazy in-memory (nie data/ai_gm.db).

---

## Wymagania końcowe
- Migracje w migrations_admin.py (istniejący pattern)
- Każda migracja loguje INFO przy wykonaniu
- Branch: phase-8d-location-integrity (zakładamy DOPIERO po decyzji z KROK 0)
- python3 -m pytest → wszystkie passed
```