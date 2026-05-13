<!-- last_updated: 2026-04-26 00:14 CEST | rev: 2 -->

# Phase 8C — Task 8C-6: Testy

> **Warunek wstępny:** 8C-1 – 8C-5 ✅ DONE (suite: 118 passed)

> **Pre-check ZALICZONY. Implementacja ODBLOKOWANA.**
>
> Odkrycia z pre-checku:
> - Brak `conftest.py` i `test_phase7.py` — wzorzec: `unittest.TestCase` + plik `.db` w `setUp/tearDown`
> - Baza: osobny plik SQLite (np. `_phase8c_*.db`), `unlink` w `tearDown`
> - Patch DB path: `patch.object(ls, "LOOT_DB_PATH", str(self._tmp))`
> - Testy HTTP: minimalna `FastAPI()` + `include_router` + `TestClient`
> - Duża część listy 8C-6 jest już pokryta w 3 plikach (szczegóły poniżej)

---

## Prompt dla Cursor — IMPLEMENTUJ

```
Implementuj Phase 8C-6 — uzupełnienie brakujących testów.

Zasady:
- NIE tworzysz nowego `test_phase8c.py` — uzupełniasz ISTNIEJĄCE pliki.
- NIE modyfikujesz istniejących testów (tylko dodajesz nowe metody).
- Wzorzec: `unittest.TestCase`, plik `.db` w setUp/tearDown, patch LOOT_DB_PATH.
- DELETE zwraca HTTP 200 z `{"ok": true}` — NIE 204 (dostosuj do faktycznego API).

Po każdym kroku pokaż mi dodane metody (diff) zanim przejdziesz dalej.

---

### Krok 1 — `backend/tests/test_phase8c_loot_service.py`

Dodaj następujące metody do klasy testowej:

```
[ ] test_xor_constraint_raises
    INSERT z item_key AND weapon_key jednocześnie nie-NULL
    → self.assertRaises(sqlite3.IntegrityError, ...)
    Uwaga: SQLite wymusza CHECK tylko gdy PRAGMA foreign_keys=ON lub PRAGMA check_constraint=ON
    — upewnij się że połączenie testowe ma włączone CHECK constraints.

[ ] test_grant_loot_skips_unknown_key_with_warning
    grant_loot_to_character z kluczem który nie istnieje w katalogu
    → nie rzuca wyjątku, zwraca pustą listę lub listę bez nieznanego klucza
    → sprawdzź że character_inventory jest puste / nie ma nieznanego wpisu

[ ] test_equip_item_rejects_invalid_slot
    equip_item z slot='invalid_slot'
    → powinno rzucić ValueError lub zwrócić błąd
    (sprawdź jak equip_item obsługuje błędny slot przed implementacją)
```

---

### Krok 2 — `backend/tests/test_phase8c_inventory_api.py`

Dodaj następujące metody:

```
[ ] test_delete_inventory_item_200
    DELETE /api/inventory/{character_id}/{inventory_id}
    → HTTP 200, body: {"ok": true}
    (nie 204 — API zwraca JSON)

[ ] test_delete_equipped_item_blocked
    DELETE przedmiotu z equipped=1 bez ?force=true
    → HTTP 400

[ ] test_delete_equipped_item_with_force
    DELETE przedmiotu z equipped=1 z ?force=true
    → HTTP 200

[ ] test_equip_invalid_slot_returns_400
    POST /api/inventory/{character_id}/equip z slot='invalid_slot'
    → HTTP 400

[ ] test_get_items_filter_by_type
    GET /api/items?item_type=armor
    → HTTP 200, wszystkie zwracane items mają item_type == 'armor'
    (jeśli ten test już istnieje jako `test_get_items_and_filter` — pomin, nie duplikuj)
```

---

### Krok 3 — Uruchom i pokaż wynik

```bash
# Tylko 8C testy:
python3 -m pytest backend/tests/test_phase8c_loot_service.py \
                   backend/tests/test_phase8c_inventory_api.py \
                   backend/tests/test_phase8c_combat_loot.py -v

# Pełny suite:
python3 -m pytest -q
```

Oczekiwane: wszystkie PASS, suite ≥ 118 (nowe testy dodają kilka punktów).
Pokaż wynik z liczbą PASS/FAIL.
```
