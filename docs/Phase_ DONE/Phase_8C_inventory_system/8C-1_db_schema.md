<!-- last_updated: 2026-04-25 23:11 CEST | rev: 5 -->

# Phase 8C — Task 8C-1: DB Schema — `character_inventory` + migracja

> **STATUS: ✅ DONE** — commit `9f108cf` na `phase-8c-inventory-system`
> PR: https://github.com/szmidtpiotr/ai-gm/pull/2
> Testy: **102 passed**

---

## Zrealizowane zmiany

| Plik | Zmiana |
|------|--------|
| `backend/sql/002_turn_engine.sql` | `inventory_items` → `character_inventory` (CHECK XOR, indeksy) |
| `backend/app/migrations_admin.py` | 3 nowe wpisy w `ADMIN_MIGRATIONS` + `DROP TABLE IF EXISTS inventory_items` |
| `backend/app/api/characters.py` | `DELETE FROM character_inventory` |
| `backend/app/services/admin_character_recreate.py` | `DELETE FROM character_inventory` + docstring |
| `frontend/admin.html` | Tekst pomocy: `character_inventory` |

---

## ⚠️ Odchylenie od pierwotnego schematu — brak FK do katalogów

**Problem:** `002_turn_engine.sql` jest wczytywany przez `install.sh` przed startem backendu
i przed `run_admin_migrations()`. W tym momencie tabele `game_config_items`,
`game_config_weapons`, `game_config_consumables` jeszcze nie istnieją.
`REFERENCES ...(key)` złamałoby świeży `sqlite3 < 002_turn_engine.sql`.

**Rozwiązanie:** `item_key` / `weapon_key` / `consumable_key` są `TEXT` **bez FK do katalogów**.
CHECK XOR i FK do `characters(id)` pozostają. Integralność względem katalogu
bezpieczna na warstwie aplikacji (spójnie ze starym `item_key` w `inventory_items`).

> **Konsekwencja dla 8C-2:** `loot_service.py` musi samodzielnie walidować
> czy `item_key` / `weapon_key` / `consumable_key` istnieją w odpowiednich
> tabelach katalogowych PRZED zapisem do `character_inventory`.

---

## Finalny schemat (jak w bazie)

```sql
CREATE TABLE IF NOT EXISTS character_inventory (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id   INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    item_key       TEXT,
    weapon_key     TEXT,
    consumable_key TEXT,
    quantity       INTEGER NOT NULL DEFAULT 1,
    equipped       INTEGER NOT NULL DEFAULT 0,
    slot           TEXT,
    acquired_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    source         TEXT,
    meta_json      TEXT,
    CONSTRAINT inv_xor CHECK (
        (CASE WHEN item_key       IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN weapon_key     IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN consumable_key IS NOT NULL THEN 1 ELSE 0 END) = 1
    )
);

CREATE INDEX IF NOT EXISTS idx_inv_character ON character_inventory(character_id);
CREATE INDEX IF NOT EXISTS idx_inv_equipped   ON character_inventory(character_id, equipped);
```

---

## Deployment na istniejącej bazie

```bash
# Restart kontenera backendu wystarczy — run_admin_migrations() wykona nowe SQL-e
docker compose restart backend

# Pełny rebuild tylko jeśli budujesz obraz bez mounta
docker compose up --build backend
```

Świeża instalacja przez `install.sh` dostaje już nowy `002` automatycznie.
