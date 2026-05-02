<!-- last_updated: 2026-04-29 | rev: 1 -->

# Phase 9 — NPC System: Plan i ustalenia projektowe

---

## Cel fazy

Dodanie systemu NPC: postacie niezależne z typami, dialogami (przez GM/LLM),
flotami `is_shop` i powiązaniem z systemem ekonomii (Phase 8F) oraz lokacjami (Phase 8D).

---

## Ustalone decyzje projektowe

### 1. Lokacje NPC

- NPC **może mieć** przypisaną lokację lub być globalny (`NULL` = wędrowny / wszechobecny)
- NPC może być przypisany do **wielu lokacji jednocześnie** (np. wędrowny kupiec odwiedza Rynek i Bramę)
- **❓ Otwarte:** jak przechowujemy wiele lokacji?
  - **Opcja A:** `location_keys TEXT` jako JSON array w tabeli `npcs` (np. `["rynek", "brama"]`) — proste, bez JOIN
  - **Opcja B:** osobna tabela `npc_locations (npc_id, location_key)` — czyste relacyjnie, łatwe do query
  - *Do decyzji przed implementacją 9A-1*

### 2. Dialogi NPC — GM jako NPC

- **GM (LLM) jest głosem każdego NPC** — brak statycznych kwestii
- `dialogue_json` w tabeli `npcs` przechowuje **osobowość i tematy** NPC (nie gotowe kwestie):
  ```json
  {
    "personality": "sknerski, podejrzliwy, lubi plotki",
    "topics": ["handel", "lokalne wiadomości", "ceny broni"],
    "secret": "przemyca towary dla gildii złodziei"
  }
  ```
- Backend wstrzykuje opis NPC do kontekstu GM gdy gracz wchodzi w interakcję
- GM generuje dialog naturalnie na podstawie osobowości + kontekstu sceny

### 3. `[NPC CONTEXT]` dla GM

- TAK — backend wstrzykuje blok `[NPC CONTEXT]` do GM (analogia do `[LOCATION CONTEXT]` z Phase 8D)
- Zawiera listę **aktywnych NPC w aktualnej lokacji** gracza
- **Przypisanie do lokacji = wskazówka dla GM, nie twarda blokada**:
  - NPC może narracyjnie opuścić lokację (GM decyduje)
  - GM może wprowadzić NPC spoza listy jeśli narracja tego wymaga
  - Backend NIE blokuje ruchów NPC tak jak blokuje `location_intent` gracza
- Przykład bloku:
  ```
  [NPC CONTEXT]
  Postacie obecne w tej lokacji:
  - Marta, karczmarka (neutral) — "gadatliwa, zna plotki, dobra gospodyni"
  - Aldric, kupiec (merchant, is_shop=1) — "sknerski, oferuje towary po zawyżonych cenach"
  ```

### 4. `Grant Gold` cue

- **Osobny cue GM** niezależny od źródła: `[GRANT GOLD N]`
- Działa dla obu przypadków:
  - NPC quest giver nagradza gracza (`[GRANT GOLD 50]` po wykonaniu zadania)
  - Gracz znajduje złoto w lochu (`[GRANT GOLD 20]` z loot dropu)
- Backend parsuje cue z odpowiedzi GM i wykonuje `UPDATE characters SET gold_gp = gold_gp + N`
- Może być wdrożony **przed Phase 9** jako osobny mały task (nie zależy od tabeli `npcs`)

---

## Architektura NPC

### Typy NPC

| Typ | Opis | `is_shop` |
|---|---|---|
| `merchant` | Sklep, kupno/sprzedaż | 1 |
| `quest_giver` | Daje questa, nagradza złotem/przedmiotami | 0 |
| `ally` | Towarzyszy graczowi, tylko dialog | 0 |
| `neutral` | Tło fabularne, tylko dialog | 0 |

### Schemat tabeli `npcs` (docelowy)

```sql
CREATE TABLE IF NOT EXISTS npcs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    key                 TEXT NOT NULL UNIQUE,
    label               TEXT NOT NULL,
    npc_type            TEXT NOT NULL DEFAULT 'neutral',
    description         TEXT,
    personality_json     TEXT NOT NULL DEFAULT '{}',  -- osobowosc + tematy + secret
    is_shop             INTEGER NOT NULL DEFAULT 0,
    shop_inventory_json TEXT NOT NULL DEFAULT '[]',
    location_keys       TEXT NOT NULL DEFAULT '[]',   -- JSON array lub NULL (globalny)
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);
-- UWAGA: dialogue_json -> personality_json (zmiana nazwy wzgledem starego planu)
-- location_key (singular) -> location_keys JSON array (zmiana wzgledem starego planu)
```

### Starter NPC (seed dla Act 1)

| key | label | typ | is_shop | lokacje |
|---|---|---|---|---|
| `merchant_aldric` | Aldric, kupiec | merchant | 1 | NULL (wędrowny) |
| `innkeeper_marta` | Marta, karczmarka | neutral | 0 | `["inn_main"]` |
| `quest_giver_eldran` | Eldran, mag | quest_giver | 0 | NULL |
| `blacksmith_goran` | Goran, kowal | merchant | 1 | NULL |

---

## Kolejność implementacji

```
[opcjonalnie teraz] Grant Gold cue — niezależny od Phase 9
        ↓
9A-1  Tabela npcs + migracja + seed
        ↓
9A-2  CRUD API NPC + Admin UI
        ↓
9A-3  [NPC CONTEXT] injection do GM + NPC_SPEAK cue
        ↓
9A-4  is_shop + shop_inventory + integracja z Phase 8F Economy
```

---

## Powiązania z innymi fazami

| Faza | Zależność |
|---|---|
| **8D Location** | `[NPC CONTEXT]` wzorowany na `[LOCATION CONTEXT]`; `location_keys` nawiązuje do `game_locations.key` |
| **8F Economy** | Czeka na `is_shop` + `shop_inventory_json` z 9A-4 |
| **Phase 10 Main Quest** | NPC są quest-giverami — potrzebne przed Act 1 |

---

## Otwarte kwestie (do decyzji przed 9A-1)

- [ ] **Lokacje NPC:** Opcja A (JSON array w kolumnie) vs Opcja B (osobna tabela `npc_locations`)?
- [ ] **`Grant Gold` cue:** wdrażamy teraz (przed Phase 9) czy razem z 9A-3?
