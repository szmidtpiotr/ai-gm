<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-05-01 -->

# PROMPT 4 — Hotfix: `add weapon` / `add consumable` w parserze komend

> **STATUS: DONE** — implementacja w `frontend/js/admin_commands_tree.js` oraz `frontend/admin_panel/sections/admin_commands.js`.
> **Dokumentacja zrewidowana pod Phase 8H (Item System Unification).**

---

## Problem (oryginalny)

`/admin add item battleaxe` trafiał do kolumny **`item_key`**, mimo że chodziło o broń z katalogu **`game_config_weapons`**, bo parser nie przekazywał kontekstu typu przedmiotu.

---

## Rozwiązanie (aktualne: 8G + 8H)

1. **Frontend** rozszerza drzewo komend o gałęzie `add weapon` i `add consumable` i wysyła:
   ```json
   { "cmd": "add item", "key": "<wpisany_tekst>", "kind": "weapon" }
   ```
   lub
   ```json
   { "cmd": "add item", "key": "<wpisany_tekst>", "kind": "consumable" }
   ```
   Prefiks `weapon_` / `consumable_` w `key` **nie jest wymagany** — ułatwia to wpisywanie samej nazwy (np. `battleaxe`, `health_potion`).

2. **Backend** (`backend/app/routers/admin_cheat.py`):
   - `CheatRequest` zawiera opcjonalne pole **`kind`**.
   - Funkcja **`_resolve_inventory_add_key(conn, raw_key, kind)`** wybiera kolumnę docelową:
     - broń → insert do **`character_inventory.weapon_key`**
     - konsumowalny (Phase 8H) → insert do **`character_inventory.item_key`**, z katalogu **`game_config_items`** gdzie `item_type = 'consumable'` (stara tabela `game_config_consumables` może być jeszcze użyta jako fallback read-only, jeśli istnieje w DB).
   - Wartość **`result.added`** to **kanoniczny klucz z katalogu** (może różnić się od surowego wpisu użytkownika).

3. **Nieaktualne stwierdzenie** z pierwszej wersji promptu: routowanie „`consumable_*` → kolumna `consumable_key`” — po **8H** ścieżka katalogowa dla consumable to **`item_key`**, a kolumna `consumable_key` tylko dla **legacy** wierszy.

---

## Zakres plików (wtedy / teraz)

| Plik | Zmiana |
|------|--------|
| `frontend/js/admin_commands_tree.js` | `ADMIN_CMD_TREE`, hinty, `parseAdminCommand` + **`kind`** |
| `frontend/admin_panel/sections/admin_commands.js` | `parseCmd` + **`kind`** dla weapon/consumable |

**Nie ruszano:** `slash_commands.js` / `actions.js` poza istniejącym przekazywaniem pełnego body JSON (zawiera `kind` gdy parser go ustawi).

---

## Weryfikacja manualna

```text
# Czat (admin) — przykłady; dokładna wartość "added" zależy od kluczy w DB:
# /admin add weapon battleaxe
#   → 200, result.added = kanoniczny weapon key (np. weapon_battleaxe po lookup)
#
# /admin add consumable health_potion
#   → 200, wiersz w character_inventory z item_key = klucz z game_config_items (consumable)
#
# /admin add item some_misc_key
#   → 200, resolver bez kind (heurystyka prefiksów + katalog)
```

Po zmianach w plikach statycznych: **hard-refresh** panelu / gry (Ctrl+Shift+R). **Docker rebuild** nie jest potrzebny wyłącznie dla tych plików JS.

---

## Co zostało zrobione *(Cursor / sync z kodem)*

- Zaimplementowano rozszerzenie parsera i spójność z backendem 8H-2.
- Ten plik opisuje **docelowy** model; w razie rozbieżności obowiązuje kod w repozytorium.

---

## Notatki po implementacji *(Perplexity / maintainer)*

- Przy usunięciu tabeli `game_config_consumables` w produkcji usunąć gałąź fallback w `_resolve_inventory_add_key` w osobnym commicie.
- W hintach UI można stopniowo zastąpić sformułowanie „consumable_key” tekstem: **klucz w katalogu przedmiotów (consumable)**.
