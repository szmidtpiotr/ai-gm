<!-- last_updated: 2026-04-26 07:45 CEST | rev: 2 -->

# Phase 8E — Frontend: Inventory UI + Starter Items + Economy

**Status:** 🔴 PLANOWANA  
**Zależności:** Phase 8C ✅ DONE

---

## Zakres tasków

| Task | Opis | Status |
|------|------|--------|
| `8E-1_starter_items.md` | Starter items + gold_gp w archetypach | 🔴 planned |
| `8E-2_foldable_panels.md` | Zwijane sekcje UI gracza + ustawienia admin | 🔴 planned |
| `8E-3_inventory_panel.md` | Panel ekwipunku w UI gracza (sloty + plecak) | 🔴 planned |
| `8E-4_loot_popup.md` | Popup loot + gold drop po walce | 🔴 planned |
| `8E-5_gm_items.md` | Przedmioty fabularne GM (osobna sekcja) | 🔴 planned |
| `8E-6_economy.md` | System ekonomii: sklep NPC, sprzedaż, gold flow | 🔴 planned |

---

## Decyzje projektowe

### 💰 Waluta — Gold (GP)

**Gdzie trzymać:** nowa kolumna `characters.gold_gp INTEGER NOT NULL DEFAULT 0`
- Prosta migracja `ALTER TABLE characters ADD COLUMN gold_gp INTEGER NOT NULL DEFAULT 0`
- Łatwy SELECT/UPDATE, czytelny, bez grzebania w `sheet_json`

**Skąd gracz dostaje złoto:**

| Źródło | Mechanika |
|--------|----------|
| Loot po walce | `loot_table` ma pole `gold_min` / `gold_max` — losuje drop i dodaje do `characters.gold_gp` |
| Sprzedaż przedmiotów | Wartość = `item.value_gp` (lub negocjacja?) — tylko u NPC ze statusem `shop` |
| Znalezisko fabularne | GM nadaje przez komendę lub specjalny loot entry `gold_fixed: N` w narracji |

**Na co wydaje:**
- Zakup przedmiotów z `game_config_items/weapons/consumables` — tylko u NPC z flagą `is_shop=1`

---

### 👜 Starter items (8E-1)

| Archetype | Przedmioty startowe | Gold startowe |
|-----------|--------------------|--------------|
| **Warrior** | `sword` (weapon), `shield` (weapon), `shortbow` (weapon), `leatherarmor` (armor) | 10 GP |
| **Scholar** | `staff` (weapon), `health_potion_small` (consumable), `mana_potion` (consumable) | 15 GP |

- Klucze z `game_config_weapons` i `game_config_items` — Cursor weryfikuje przed implementacją
- Pole `starter_items_json` + `starter_gold_gp` w `game_config_archetypes`
- Edytowalne z admin panelu
- Przyznawane przy kreacji → `character_inventory` (source=`'start'`) + `characters.gold_gp`

---

### 🧹 UI — zwijane sekcje (8E-2)

- Sekcje: `Statystyki`, `Postać`, `Umiejętności` — każda może się zwijać/rozwijać
- Default (zwinięte/rozwinięte) konfigurowalny w Admin Panelu — nowa sekcja **Ustawienia UI**
- Stan zwijania zapisywany lokalnie (localStorage) per gracz

---

### 📜 Panel ekwipunku (8E-3)

- Foldable panel (spójny z resztą UI)
- Sloty: `main_hand`, `off_hand`, `armor` z wizualną reprezentacją
- Plecak: lista pozostałych `character_inventory` z przyciskami Załóż/Upuść
- Widoczne `gold_gp` (portfel gracza)
- Pozycja: foldable obok/pod chatem — dokładna pozycja do ustalenia w sesji

---

### 🎁 Loot popup (8E-4)

- Wyzwalany gdy `out["loot"]` lub `out["gold_drop"]` niepuste po walce
- **Systemowy loot:** popup z nazwą, ikoną i parametrami z katalogu
- **Gold drop:** osobna linia "+X GP" w popupie
- GM LLM **nie wymyśla** przedmiotów z parametrami — tylko bierze z tabel

---

### 🎭 Przedmioty fabularne GM (8E-5)

- GM może nadać przedmiot "fabularny" (bez statystyk) — np. "Złamany Amulet"
- Trafia do osobnej sekcji (np. `narrative_items` w `sheet_json` lub osobna tabela)
- **NIE** do `character_inventory` (brak XOR constraint, brak katalogu)
- Widoczne w UI w osobnej sekcji plecaka: "Przedmioty fabularne"
- Może mieć tylko: `label`, `description`, `source` (GM)

---

### 🏪 Ekonomia — Sklep NPC (8E-6)

**NPC z flagą `is_shop=1`:**
- Nowe pole w tabeli NPC (do stworzenia w Phase 9 NPC System)
- Jeśli gracz wejdzie w interakcję z NPC-sklepem → UI pokazuje listę dostępnych przedmiotów
- Zakup: `characters.gold_gp -= item.value_gp` + item do `character_inventory`
- Sprzedaż: `characters.gold_gp += item.value_gp` (100%? 50%?) + usuń z inventory

**Znalezisko fabularne (gold):**
- GM może wpisać specjalną komendę / system rozpoznaje "znalazłeś X złotych"
  – albo przez dedykowany endpoint `POST /api/characters/{id}/gold` `{"delta": +50, "reason": "fabularnie"}`
  – decyzja: czy GM LLM emituje specjalny cue (jak Roll d20) czy tylko admin może dodawać ręcznie?

> ⚠️ **8E-6 zależy od Phase 9 (NPC System)** — sklep bez NPC nie ma sensu.
> Na razie: `gold_gp` w DB + endpoint delta to minimum które można zrobić w 8E.

---

## Kolejność implementacji (rekomendacja)

```
8E-1  Starter items + gold_gp kolumna + archetype config    ← ZACZYNAĆ TU
8E-2  Foldable panels + admin UI settings
8E-3  Panel ekwipunku (sloty + plecak + gold display)
8E-4  Loot popup + gold drop
8E-5  Przedmioty fabularne GM
8E-6  Economy / sklep (po Phase 9 NPC)
```
