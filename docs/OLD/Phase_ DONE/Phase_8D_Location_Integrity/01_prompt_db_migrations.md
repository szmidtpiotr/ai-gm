<!-- STATUS: IN_PROGRESS -->
<!-- REV: 2 | DATE: 2026-04-28 -->

# PROMPT 01 — DB Migrations (Phase 8D)

> Workflow tego pliku: REV 1 (pytania blokujące) → odpowiedzi Cursora → REV 2 (implementacja) → raport Cursora → notatki Perplexity → DONE.

---

## Cel

Wykonać migracje bazy danych dla Phase 8D — Location Integrity.  
Zadania: **8D-1, 8D-2, 8D-3, 8D-4** — nowe tabele i nowe kolumny w istniejących tabelach.

---

## Kontekst techniczny

- **Branch:** `phase-8d-location-integrity` (zweryfikowany przez Cursora w REV 1)
- **Baza:** `data/ai_gm.db` (SQLite) — dostępna, czysta, `156 passed` baseline
- **System migracji:** `backend/app/migrations_admin.py` — lista `ADMIN_MIGRATIONS`
- **NIE ruszać:** `docker-compose.yml` prod, `data/ai_gm.db` (nie dropuj nic)
- **Ważne:** `game_sessions` i `game_config_meta` **już istnieją** w `ADMIN_MIGRATIONS` — tylko ALTER TABLE / INSERT, NIE CREATE TABLE

---

## ⛔ PRZED IMPLEMENTACJĄ — pytania blokujące

*(Cursor odpowiedział na te pytania w REV 1 — wszystkie ✅)*

| Pytanie | Odpowiedź Cursora |
|---------|-------------------|
| Branch? | ✅ `phase-8d-location-integrity`, czysty working tree |
| System migracji? | ✅ `backend/app/migrations_admin.py` — lista `ADMIN_MIGRATIONS` |
| `game_config_meta` już istnieje? | ✅ Tak, linia 111–115 — tylko INSERT OR IGNORE |
| `game_sessions` już istnieje? | ✅ Tak, linia 318–324 — tylko ALTER TABLE |
| Baza SQLite zdrowa? | ✅ `/data/ai_gm.db` dostępna przez volumen |
| Baseline testów? | ✅ `156 passed` na `.61` |

---

## Implementacja (REV 2)

Pracujesz w projekcie `ai-gm`. Branch: `phase-8d-location-integrity`.  
Plik docelowy: `backend/app/migrations_admin.py`.

### Zasady ogólne

1. Wszystkie nowe migracje dopisz **na końcu listy `ADMIN_MIGRATIONS`**, po istniejących wpisach
2. Każda migracja jako **osobny string SQL** w liście (styl istniejących wpisów w pliku)
3. Loguj wykonane migracje do konsoli (`INFO level`) — sprawdź jak robią to inne migracje
4. Żadna migracja nie może usuwać ani modyfikować istniejących danych

---

### Zadanie 8D-1 — Tabela `game_locations`

Dodaj do `ADMIN_MIGRATIONS`:

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

---

### Zadanie 8D-2 — Kolumna `current_location_id` w `game_sessions`

`game_sessions` już istnieje — dodaj ALTER TABLE jako osobny wpis w `ADMIN_MIGRATIONS`:

```sql
ALTER TABLE game_sessions ADD COLUMN current_location_id INTEGER
  REFERENCES game_locations(id);
```

> ⚠️ SQLite nie obsługuje `IF NOT EXISTS` w ALTER TABLE — obsłuż wyjątek `OperationalError: duplicate column name` przez `try/except` w loaderze migracji (sprawdź jak to robią inne ALTER TABLE w projekcie).

---

### Zadanie 8D-3 — Kolumna `session_flags` w `game_sessions` + flagi w `game_config_meta`

**3a.** Dodaj kolumnę `session_flags` (ALTER TABLE, osobny wpis):

```sql
ALTER TABLE game_sessions ADD COLUMN session_flags TEXT DEFAULT '{}';
```

**3b.** `game_config_meta` już istnieje — tylko INSERT OR IGNORE flag Location Integrity (osobny wpis):

```sql
INSERT OR IGNORE INTO game_config_meta (key, value) VALUES
  ('location_integrity_enabled', '0'),
  ('location_parser_json_enabled', '1'),
  ('location_parser_fallback_enabled', '1');
```

> 📝 `location_integrity_enabled = 0` domyślnie podczas development (zgodnie z zasadami Phase 8D). Włączymy w trakcie testów 8D-20 do 8D-24.

---

### Zadanie 8D-4 — Tabela `location_integrity_log`

```sql
CREATE TABLE IF NOT EXISTS location_integrity_log (
  id                    INTEGER PRIMARY KEY,
  session_id            INTEGER NOT NULL REFERENCES game_sessions(id),
  character_id          INTEGER,
  attempted_move        TEXT NOT NULL,
  current_location_key  TEXT,
  reason_blocked        TEXT,
  created_at            TEXT DEFAULT (datetime('now'))
);
```

---

### Zadanie 8D-5 — Testy migracji

Dopisz test w `tests/` (nowy plik: `tests/test_8d_migrations.py`):

```python
def test_game_locations_table_exists(db):
    """game_locations istnieje i ma wymagane kolumny"""

def test_game_sessions_has_location_columns(db):
    """game_sessions ma current_location_id i session_flags"""

def test_game_config_meta_has_location_flags(db):
    """game_config_meta zawiera 3 flagi location integrity"""

def test_location_integrity_log_table_exists(db):
    """location_integrity_log istnieje i ma wymagane kolumny"""
```

Dopasuj fixture `db` do stylu istniejących testów w projekcie.

---

### Po implementacji

```bash
# Na serwerze .61:
python3 -m pytest
# Oczekiwane: wszystkie 156+ testów passed (+ nowe z 8D-5)
```

---

## Odpowiedzi Cursora (REV 1)

```
✅ Branch: phase-8d-location-integrity, czysty working tree
✅ System migracji: backend/app/migrations_admin.py — lista ADMIN_MIGRATIONS
✅ game_config_meta już istnieje (linia 111–115) — tylko INSERT
✅ game_sessions już istnieje (linia 318–324) — tylko ALTER TABLE
✅ Baza SQLite: /data/ai_gm.db dostępna
✅ Testy baseline: 156 passed na .61
⚠️ Kolejność: nowe ALTER TABLE muszą być po istniejących CREATE TABLE w liście
```

---

## Co zostało zrobione *(uzupełnia Cursor)*

*(po implementacji)*

---

## Notatki po implementacji *(uzupełnia Perplexity)*

*(po raporcie Cursora)*
