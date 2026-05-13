<!-- last_updated: 2026-04-25 23:04 CEST | rev: 1 -->

# Phase 8C — Pre-Check (Blocker Audit)

> **Uruchom ten prompt JAKO PIERWSZY przed jakąkolwiek implementacją 8C.**
> Jego zadaniem jest potwierdzenie stanu repozytorium i wykrycie potencjalnych kolizji.

---

## Prompt dla Cursor

```
Zanim zacznę implementować Phase 8C (Inventory System), przeprowadź pełny audyt
obecnego stanu repozytorium i odpowiedz na poniższe pytania.

NIE wprowadzaj żadnych zmian w kodzie — tylko analiza i raport.

### Pytania do sprawdzenia

1. **Tabele DB**
   - Czy istnieje tabela `character_inventory`? (grep po migrations_admin.py, migrations.py,
     lub jakimkolwiek pliku inicjalizującym SQLite)
   - Czy istnieje tabela `pending_loot`?
   - Czy kolumna `location_id` pojawia się gdziekolwiek w kontekście loot/inventory?

2. **game_config_items vs game_config_weapons**
   - Jakie kolumny ma `game_config_items`? (pokaż CREATE TABLE)
   - Jakie kolumny ma `game_config_weapons`? (pokaż CREATE TABLE)
   - Czy istnieje CHECK constraint określający dozwolone `item_type`? Jakie wartości?

3. **Loot system**
   - Czy istnieje tabela `loot_config` lub `loot_tables`?
   - Jaki jest schemat tej tabeli (jeśli istnieje)?
   - Czy loot rozróżnia `item_key` (→ game_config_items) vs `weapon_key`
     (→ game_config_weapons)? Pokaż CHECK constraint lub przykładowe dane.

4. **character_inventory — kontrakt broni**
   - Jeśli `character_inventory.item_key` wskazuje TYLKO na `game_config_items`,
     jak dziś combat_service.py pobiera broń gracza?
   - Czy gracz może posiadać broń bojową bez `character_inventory`?
     Jakie jest obecne źródło broni w combat (hardcode, sheetjson, starter_weapon)?

5. **Endpointy inventory**
   - Czy istnieje jakikolwiek endpoint `/api/inventory/*` lub `/api/items/*`?
   - Czy istnieje jakikolwiek frontend JS obsługujący ekwipunek?

6. **Migracje**
   - Jaki jest numer ostatniej migracji w `migrations_admin.py`?
   - Jaki jest numer ostatniej migracji w `migrations.py` (jeśli plik istnieje)?

7. **Konflikty z Phase 8D**
   - Czy Phase 8D (location integrity) dodała cokolwiek co dotyczy items / loot / inventory?
   - Sprawdź `_ensure_location_integrity_schema` i ewentualne migracje 8D.

### Format odpowiedzi

Odpowiedz w formie listy TAK/NIE/BRAK + krótkie wyjaśnienie dla każdego punktu.
Na końcu podaj: **"BLOKERÓW: X"** oraz listę blokerów (jeśli są).
Jeśli nie ma blokerów, napisz: **"GOTOWY DO IMPLEMENTACJI 8C"**.
```
