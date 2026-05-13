<!-- STATUS: DONE -->
<!-- PHASE: 8C | DATE_START: — | DATE_END: — -->

# Phase 8C — Inventory System · Brief archiwalny

> Źródło szczegółów: `README.md` oraz prompty `8C-0` … `8C-6` w tym folderze.

---

## 1. Cel fazy

Jednolite **character_inventory** z regułami stackowania, **loot_service** jako pojedyncza ścieżka przyznawania przedmiotów, API odczytu/ekwipunku dla gracza, integracja z walką i panelem admin (katalog przedmiotów).

---

## 2. Zakres (taski w dokumentacji)

| Task | Opis (skrót) |
|------|----------------|
| 8C-1 | Schema + migracja `character_inventory` |
| 8C-2 | `loot_service` — grant, walidacja kluczy katalogu |
| 8C-3 | Endpointy FastAPI inventory |
| 8C-4 | Integracja combat → loot |
| 8C-5 | Admin — konfiguracja przedmiotów |
| 8C-6 | Testy (stan w README historycznym) |

---

## 3. Kluczowe decyzje (z README)

- XOR jednego klucza: `item_key` / `weapon_key` / `consumable_key`.
- Walidacja katalogu w serwisie (bez FK — kolejność init).
- Loot po walce przez `grant_loot_to_character`.

---

## 4. Podsumowanie osiągnięć

- Spójny model ekwipunku dla lootu, starterów (8E) i późniejszej ekonomii (8F).
- Admin może zarządzać katalogiem przedmiotów z poziomu dokumentowanego flow.

---

## Analiza po fazie *(Perplexity)*

### Ocena implementacji
- **Zgodność z Briefem:** ✅ pełna — 6 tasków pokrywa kompletny stack inventory od DB po UI admin
- **Pokrycie testami:** testy opisane w `8C-6` i README; `grant_loot_to_character` jako central point — krytyczne do regresji przy zmianach
- **Ryzyka i dług techniczny:**
  - Brak FK w DB (celowe — kolejność init) — integralność danych zależy od walidacji serwisowej
  - XOR kluczy (`item_key`/`weapon_key`/`consumable_key`) — reguła musi być egzekwowana na poziomie API i serwisu spójnie; rozszerzenie typów wymaga zmian w wielu miejscach
  - `loot_service` jest współdzielony przez 8A (combat), 8E (starter), 8F (sklep) — breaking change propaguje się szeroko

### Decyzje przeniesione do kolejnych faz
- **8E** — starter items używają `grant_loot_to_character` zdefiniowanego tutaj
- **8F** — sklep (`buy_item`) korzysta z tej samej ścieżki inventory
- Rozszerzenie typów przedmiotów (np. armor jako osobna kategoria) — kandydat na Phase 10+

### STATUS: DONE
