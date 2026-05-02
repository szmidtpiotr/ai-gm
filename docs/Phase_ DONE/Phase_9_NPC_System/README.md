<!-- last_updated: 2026-04-27 09:16 CEST | rev: 1 -->

# Phase 9 — NPC System

**Status:** 🔴 IN PROGRESS
**Notion:** https://www.notion.so/3428842467a88155b626e4985d15b2ff
**Branch:** `phase-9-npc-system` (do utworzenia)

---

## Cel fazy

Dodanie systemu NPC: postacie niezależne w świecie gry z typami, dialogami,
flotami `is_shop` i powiązaniem z systemem ekonomii (Phase 8F).

---

## Zakres

| Task | Opis | Status | Warunek |
|------|------|--------|---------|
| `9A-1_npc_schema.md` | Tabela `npcs`, typy, schemat DB, migracje, seed | 🔴 planned | — |
| `9A-2_npc_api.md` | CRUD endpoints NPC, Admin UI | 🔴 planned | 9A-1 |
| `9A-3_npc_dialogue.md` | GM cue `NPC_SPEAK`, NPC w kontekście LLM | 🔴 planned | 9A-2 |
| `9A-4_npc_shop.md` | `is_shop=1`, `shop_inventory_json`, integracja z 8F | 🔴 planned | 9A-2 |

---

## Powiązania z innymi fazami

| Faza | Zależność |
|------|----------|
| **8F Economy** | Czeka na `is_shop` + `shop_inventory_json` z 9A-4 |
| **8E-5 Grant Item** | `Grant Gold N` cue — można dodać przy 9A-3 (GM nadaje złoto przez NPC) |
| **Phase 10 Main Quest** | NPC są quest-giverami — potrzebne przed Act 1 |

---

## Architektura NPC

### Typy NPC
| Typ | Opis |
|-----|------|
| `merchant` | Sklep (`is_shop=1`), kupno/sprzedaż |
| `quest_giver` | Daje questa, może nagradzać złotem/przedmiotami |
| `ally` | Towarzyszy graczowi, nie walczy |
| `neutral` | Tło fabularne, tylko dialog |
| `enemy` | Wrogi (już obsługiwany przez Phase 8A combat) |

### Schemat tabeli `npcs` (docelowy)
```sql
CREATE TABLE IF NOT EXISTS npcs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT NOT NULL UNIQUE,
    label       TEXT NOT NULL,
    npc_type    TEXT NOT NULL DEFAULT 'neutral',
    description TEXT,
    is_shop     INTEGER NOT NULL DEFAULT 0,
    shop_inventory_json TEXT DEFAULT '[]',
    dialogue_json       TEXT DEFAULT '{}',
    location_key        TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);
```

### Starter NPC (seed dla Act 1)
| key | label | typ | is_shop |
|-----|-------|-----|---------|
| `merchant_aldric` | Aldric, kupiec | merchant | 1 |
| `innkeeper_marta` | Marta, karczmarka | neutral | 0 |
| `quest_giver_eldran` | Eldran, mag | quest_giver | 0 |
| `blacksmith_goran` | Goran, kowal | merchant | 1 |

---

## Otwarte decyzje

- **Lokacje NPC:** czy NPC jest przypisany do `location_key`? (rekomendacja: tak)
- **Dialogue system:** statyczne JSON dialogi vs dynamiczne przez LLM?
- **NPC w kontekście LLM:** czy GM dostaje listę NPC obecnych w scenie?
- **Grant Gold cue:** `Grant Gold N` — dodać przy 9A-3 czy osobny task?
