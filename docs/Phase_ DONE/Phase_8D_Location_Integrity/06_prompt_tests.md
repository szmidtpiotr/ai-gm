<!-- STATUS: IN_PROGRESS -->
<!-- REV 2 | DATE: 2026-04-28 -->

# PROMPT 06 — Kompleksowe testy Phase 8D

> Workflow tego pliku: REV 1 (pytania blokujące) → odpowiedzi Cursora → REV 2 (implementacja) → raport Cursora → notatki Perplexity → DONE.

---

## Cel

Stworzyć kompletny zestaw testów Phase 8D i naprawić zepsute fixture.

**Zadania:** 8D-20, 8D-21, 8D-22, 8D-23, 8D-24  
**Branch:** `phase-8d-location-integrity`  
**Warunek ukończenia:** `python3 -m pytest` → **wszystkie passed, zero errors**

---

## Kontekst techniczny

| Parametr | Wartość |
|----------|----------|
| **Branch** | `phase-8d-location-integrity` |
| **Git status** | Clean (brak niezcommitowanych zmian) |
| **Baseline** | ~213 passed (po PROMPT 01–05) |
| **Problem otwarty** | `test_phase8d_migrations.py` — 15 errors (fixture nie obsługuje łańcucha migracji) |
| **Strategia fixture** | **Opcja B** — `tmp_path` SQLite + `run_admin_migrations()` na całości |
| **rapidfuzz** | ✅ w `requirements.txt`, używany w `location_validator.py` |
| **HTTP styl** | `PUT /api/locations/{key}` (nie PATCH) |

**Istniejące testy 8D (NIE duplikować):**
- `test_8d_locations_api.py` — 17 testów CRUD
- `test_8d_admin_flags.py` — testy flag admina
- `test_8d_intent_parser.py` — testy parsera intencji

**Nowe pliki do stworzenia:**
- `backend/tests/test_phase8d_migrations.py` — naprawa fixture
- `backend/tests/test_phase8d_location_integrity.py` — testy logiki walidacji
- `backend/tests/test_phase8d_api.py` — testy HTTP endpointów

**NIE ruszać:** `data/ai_gm.db`, `docker-compose.yml` prod

---

## Implementacja (REV 2) — Cursor implementuje

### Krok 0 — Naprawa `test_phase8d_migrations.py`

Użyj **Opcji B**: `tmp_path` SQLite + `run_admin_migrations()` na całości.

Naprawić fixture tak, żeby była **spójna ze stylem istniejących testów** w projekcie (`conftest.py`, `TestClient`). Nie zmieniać istniejących test caseów — tylko fixture.

```python
# backend/tests/test_phase8d_migrations.py
import sqlite3
import pytest
from backend.app.migrations_admin import run_admin_migrations  # dopasuj import do projektu

@pytest.fixture
def migrated_db(tmp_path):
    """Tymczasowa SQLite z pełnym łańcuchem migracji."""
    db_path = tmp_path / "test_migrations.db"
    conn = sqlite3.connect(str(db_path))
    run_admin_migrations(conn)  # uruchom WSZYSTKIE migracje włącznie z Phase 8D
    yield conn
    conn.close()

def test_game_locations_table_created(migrated_db):
    cursor = migrated_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='game_locations'"
    )
    assert cursor.fetchone() is not None

def test_current_location_id_column(migrated_db):
    cursor = migrated_db.execute("PRAGMA table_info(game_sessions)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "current_location_id" in columns
    assert "session_flags" in columns

def test_location_flags_present(migrated_db):
    cursor = migrated_db.execute(
        "SELECT key FROM game_config_meta WHERE key LIKE 'location_%'"
    )
    keys = [row[0] for row in cursor.fetchall()]
    assert "location_integrity_enabled" in keys
    assert "location_parser_json_enabled" in keys
    assert "location_parser_fallback_enabled" in keys

def test_location_integrity_log_table(migrated_db):
    cursor = migrated_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='location_integrity_log'"
    )
    assert cursor.fetchone() is not None
```

> ⚠️ Jeśli `run_admin_migrations()` wymaga połączenia inaczej niż przez `conn`, dopasuj do rzeczywistego API funkcji w `migrations_admin.py`.

---

### Krok 1 — `test_phase8d_location_integrity.py` (nowy plik)

Pełne implementacje testów walidacji logiki. Cursor **nie kopiuje szkieletów z `pass`** — pisze działające testy.

```python
# backend/tests/test_phase8d_location_integrity.py
import json
import pytest
from backend.services.location_validator import LocationValidator
from backend.services.location_intent_parser import LocationIntentParser
# dopasuj importy do rzeczywistej struktury projekt

# ----- Fixtures -----

@pytest.fixture
def db_with_locations(migrated_db):
    """Baza z przykładową hierarchią lokalizacji."""
    migrated_db.execute("""
        INSERT INTO game_locations (key, label, location_type, parent_id)
        VALUES
          ('city_varen', 'Miasto Varen', 'macro', NULL),
          ('forest_black', 'Czarny Las', 'macro', NULL)
    """)
    migrated_db.execute("""
        INSERT INTO game_locations (key, label, location_type, parent_id)
        SELECT 'tavern_hanged_man', 'Karczma Pod Wisielcem', 'sub', id
        FROM game_locations WHERE key = 'city_varen'
    """)
    migrated_db.execute("""
        INSERT INTO game_locations (key, label, location_type, parent_id)
        SELECT 'market_square', 'Rynek Miejski', 'sub', id
        FROM game_locations WHERE key = 'city_varen'
    """)
    migrated_db.execute("""
        INSERT INTO game_locations (key, label, location_type, parent_id)
        SELECT 'forest_clearing', 'Polana w Lesie', 'sub', id
        FROM game_locations WHERE key = 'forest_black'
    """)
    migrated_db.commit()
    return migrated_db

@pytest.fixture
def session_in_tavern(db_with_locations):
    """Sesja z aktualną lokalizacją = tavern_hanged_man."""
    cursor = db_with_locations.execute(
        "SELECT id FROM game_locations WHERE key = 'tavern_hanged_man'"
    )
    loc_id = cursor.fetchone()[0]
    db_with_locations.execute(
        "INSERT INTO game_sessions (current_location_id, session_flags) VALUES (?, ?)",
        (loc_id, '{}')
    )
    db_with_locations.commit()
    session_id = db_with_locations.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"session_id": session_id, "db": db_with_locations}

# ----- 8D-20: Blokada teleportacji -----

def test_teleportation_blocked(session_in_tavern):
    """
    8D-20: Gracz próbuje przenieść się z karczmy (makro: city_varen)
    do polany w lesie (makro: forest_black). Powinno być zablokowane.
    """
    db = session_in_tavern["db"]
    session_id = session_in_tavern["session_id"]
    validator = LocationValidator(db)

    result = validator.validate(
        session_id=session_id,
        target_location_key="forest_clearing"
    )

    assert result.allowed is False
    assert result.reason is not None

    # Weryfikacja wpisu w logu
    log = db.execute(
        "SELECT * FROM location_integrity_log WHERE session_id = ?", (session_id,)
    ).fetchone()
    assert log is not None

    # Lokalizacja sesji bez zmian
    current = db.execute(
        "SELECT current_location_id FROM game_sessions WHERE id = ?", (session_id,)
    ).fetchone()[0]
    tavern_id = db.execute(
        "SELECT id FROM game_locations WHERE key = 'tavern_hanged_man'"
    ).fetchone()[0]
    assert current == tavern_id

# ----- 8D-21: Dozwolony ruch sub→sub (ten sam rodzic) -----

def test_sub_to_sub_same_parent_allowed(session_in_tavern):
    """
    8D-21: Gracz idzie z karczmy na rynek — obie sub-lokalizacje Varen.
    Ruch powinien być dozwolony.
    """
    db = session_in_tavern["db"]
    session_id = session_in_tavern["session_id"]
    validator = LocationValidator(db)

    result = validator.validate(
        session_id=session_id,
        target_location_key="market_square"
    )

    assert result.allowed is True

    # Brak wpisu w logu
    log = db.execute(
        "SELECT * FROM location_integrity_log WHERE session_id = ?", (session_id,)
    ).fetchone()
    assert log is None

    # Lokalizacja zaktualizowana
    current_id = db.execute(
        "SELECT current_location_id FROM game_sessions WHERE id = ?", (session_id,)
    ).fetchone()[0]
    market_id = db.execute(
        "SELECT id FROM game_locations WHERE key = 'market_square'"
    ).fetchone()[0]
    assert current_id == market_id

# ----- 8D-22: Session flag wyłącza walidację -----

def test_admin_flag_disables_validation(session_in_tavern):
    """
    8D-22: Session override location_integrity_enabled=0.
    Ten sam ruch co 8D-20 teraz przechodzi.
    """
    db = session_in_tavern["db"]
    session_id = session_in_tavern["session_id"]

    # Ustaw session flag: wyłącz walidację
    db.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
        (json.dumps({"location_integrity_enabled": "0"}), session_id)
    )
    db.commit()

    validator = LocationValidator(db)
    result = validator.validate(
        session_id=session_id,
        target_location_key="forest_clearing"
    )

    assert result.allowed is True

    # Brak wpisu w logu (walidacja pominięta)
    log = db.execute(
        "SELECT * FROM location_integrity_log WHERE session_id = ?", (session_id,)
    ).fetchone()
    assert log is None

# ----- 8D-23a: GM tworzy nową lokalizację dynamicznie -----

def test_gm_creates_new_location_dynamically(session_in_tavern):
    """
    8D-23a: GM zwraca JSON z action='create' dla nowej lokalizacji.
    Parser powinien stworzyć wpis w game_locations.
    """
    db = session_in_tavern["db"]
    session_id = session_in_tavern["session_id"]
    parser = LocationIntentParser(db)

    gm_response = json.dumps({
        "narrative": "Odkrywasz ukrytą grotę...",
        "location_intent": {
            "action": "create",
            "target_label": "Grota za Wodospadem",
            "parent_key": "forest_black",
            "description": "Wilgotna grota."
        }
    })

    result = parser.process(gm_response=gm_response, session_id=session_id)

    # Nowy wpis w game_locations
    new_loc = db.execute(
        "SELECT * FROM game_locations WHERE key = 'grota_za_wodospadem'"
    ).fetchone()
    assert new_loc is not None

    # parent_id = forest_black
    forest_id = db.execute(
        "SELECT id FROM game_locations WHERE key = 'forest_black'"
    ).fetchone()[0]
    assert new_loc["parent_id"] == forest_id  # lub new_loc[4] jeśli nie dict

    # Sesja zaktualizowana na nową lokalizację
    current_id = db.execute(
        "SELECT current_location_id FROM game_sessions WHERE id = ?", (session_id,)
    ).fetchone()[0]
    assert current_id == new_loc["id"]  # lub new_loc[0]

# ----- 8D-23b: Fuzzy match — reuse istniejącej lokalizacji -----

def test_gm_reuses_existing_location_fuzzy(session_in_tavern):
    """
    8D-23b: GM używa wariacji nazwy istniejącej lokalizacji.
    rapidfuzz powinien dopasować do istniejącej (score >= 80).
    Brak duplikatu w DB.
    """
    db = session_in_tavern["db"]
    session_id = session_in_tavern["session_id"]
    parser = LocationIntentParser(db)

    # Policz istniejące lokalizacje przed
    count_before = db.execute(
        "SELECT COUNT(*) FROM game_locations"
    ).fetchone()[0]

    gm_response = json.dumps({
        "narrative": "Wracasz do karczmy...",
        "location_intent": {
            "action": "move",
            "target_label": "karczma pod wisielcem"  # lowercase, fuzzy match
        }
    })

    result = parser.process(gm_response=gm_response, session_id=session_id)

    # Brak nowej lokalizacji
    count_after = db.execute(
        "SELECT COUNT(*) FROM game_locations"
    ).fetchone()[0]
    assert count_after == count_before

    # Dopasowano do istniejącej
    assert result.matched_key == "tavern_hanged_man"
    assert result.fuzzy_score >= 80
```

---

### Krok 2 — `test_phase8d_api.py` (nowy plik — HTTP endpoints)

Użyć `TestClient` z `conftest.py`. Cursor dopasowuje `client` fixture do stylu projektu.

```python
# backend/tests/test_phase8d_api.py
import json
import pytest

# --- Locations CRUD ---

def test_get_locations_list(client):
    response = client.get("/api/locations")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data or isinstance(data, list)  # dopasuj do rzeczywistego formatu

def test_create_location(client):
    payload = {
        "key": "test_macro_loc",
        "label": "Test Macro Location",
        "location_type": "macro"
    }
    response = client.post("/api/locations", json=payload)
    assert response.status_code == 201
    assert response.json()["key"] == "test_macro_loc"

def test_get_location_by_key(client):
    # Najpierw stwórz
    client.post("/api/locations", json={"key": "get_test", "label": "Get Test", "location_type": "macro"})
    response = client.get("/api/locations/get_test")
    assert response.status_code == 200

def test_get_location_not_found(client):
    response = client.get("/api/locations/nonexistent_key_xyz")
    assert response.status_code == 404

def test_put_location_update(client):
    client.post("/api/locations", json={"key": "put_test", "label": "Put Test", "location_type": "macro"})
    response = client.put("/api/locations/put_test", json={"label": "Updated Label"})
    assert response.status_code == 200
    assert response.json()["label"] == "Updated Label"

def test_put_location_parent_id_immutable(client):
    """parent_id nie może być zmienione przez PUT."""
    client.post("/api/locations", json={"key": "parent_immut", "label": "Parent Immutable", "location_type": "macro"})
    response = client.put("/api/locations/parent_immut", json={"parent_id": 999})
    # Oczekujemy 400 lub zignorowania parent_id
    assert response.status_code in [200, 400]
    if response.status_code == 200:
        assert response.json().get("parent_id") is None  # parent_id bez zmian

def test_delete_location_leaf(client):
    client.post("/api/locations", json={"key": "del_leaf", "label": "Delete Leaf", "location_type": "macro"})
    response = client.delete("/api/locations/del_leaf")
    assert response.status_code == 200

def test_delete_location_with_children_blocked(client):
    """Soft-delete blokowany jeśli lokalizacja ma dzieci."""
    client.post("/api/locations", json={"key": "del_parent", "label": "Parent", "location_type": "macro"})
    # Stwórz dziecko (wymaga parent_id — pobierz z GET)
    parent = client.get("/api/locations/del_parent").json()
    client.post("/api/locations", json={
        "key": "del_child",
        "label": "Child",
        "location_type": "sub",
        "parent_id": parent["id"]
    })
    response = client.delete("/api/locations/del_parent")
    assert response.status_code == 409

# --- Admin Flags ---

def test_get_location_flags(client):
    response = client.get("/api/admin/config/location-flags")
    assert response.status_code == 200
    data = response.json()
    assert "location_integrity_enabled" in data
    assert "location_parser_json_enabled" in data
    assert "location_parser_fallback_enabled" in data

def test_put_location_flags(client):
    response = client.put(
        "/api/admin/config/location-flags",
        json={"location_integrity_enabled": "1"}
    )
    assert response.status_code == 200
    # Weryfikacja: GET powinno zwrócić zaktualizowaną wartość
    flags = client.get("/api/admin/config/location-flags").json()
    assert flags["location_integrity_enabled"] == "1"

def test_get_location_integrity_log(client):
    response = client.get("/api/admin/location-log")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list) or "items" in data
```

---

### Krok 3 — Uruchomienie i weryfikacja

```bash
# Naprawione testy migracji
python3 -m pytest backend/tests/test_phase8d_migrations.py -v --tb=short

# Nowe testy logiki
python3 -m pytest backend/tests/test_phase8d_location_integrity.py -v --tb=short

# Nowe testy HTTP
python3 -m pytest backend/tests/test_phase8d_api.py -v --tb=short

# Coverage nowych plików
python3 -m pytest \
  --cov=backend/routers/locations \
  --cov=backend/routers/admin_location \
  --cov=backend/routers/session_location \
  --cov=backend/services \
  --cov-report=term-missing --tb=no -q

# Pełny suite — zero regresji
python3 -m pytest --tb=no -q 2>&1 | tail -5
```

**Cel:**
- `0 failed, 0 errors`
- Coverage ≥ 85% dla nowych plików
- Liczba testów ≥ 213 + nowe (8D-20–23: 5 testów, API: 11 testów)

---

### Po implementacji (8D-24 — manual)

Po ukończeniu kroków 0–3, wykonaj ręcznie przez MCP `loki_query`:

```
Szukaj sesji gdzie game_turns wskazują zmianę lokalizacji między turnami.
Sprawdzi sekcję message.user pod kątem nagłych zmian miejsca akcji.
Wyniki wpisz jako komentarz w sekcji Notatki po implementacji.
```

---

## Odpowiedzi Cursora (REV 1)

| # | Pytanie | Odpowiedź |
|---|---------|----------|
| 1 | Branch + git status | ✅ `phase-8d-location-integrity`, clean |
| 2 | Błędy fixture migracji | ⚠️ Tymczasowa baza nie obsługuje pełnego łańcucha — Opcja B wybrana |
| 3 | Istniejące testy 8D | ✅ 3 pliki: `locations_api`, `admin_flags`, `intent_parser` (17+ testów) |
| 4 | Endpointy | ✅ PUT (nie PATCH), soft-delete z blokadą na dzieci, log endpoint: `/api/admin/location-log` |
| 5 | rapidfuzz | ✅ `requirements.txt` + używany w `location_validator.py` |
| 6 | TestClient fixture | ✅ `conftest.py`, baza in-memory |

---

## Co zostało zrobione *(Cursor)*

*(Cursor wypełnia po implementacji)*

---

## Notatki po implementacji *(Perplexity)*

*(Perplexity wypełnia po raporcie Cursora)*
