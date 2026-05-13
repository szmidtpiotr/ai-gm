<!-- last_updated: 2026-04-26 07:50 CEST | rev: 1 -->

# Phase 8F — Economy: Sklep NPC + Gold Flow

**Status:** 🔴 PLANOWANA (zależy od Phase 9 NPC System)
**Notion:** https://www.notion.so/Phase-8F-Economy-34e8842467a880c092e5fcae8cfd340f

---

## Zakres

| Task | Opis | Status | Warunek |
|------|------|--------|---------|
| `8F-1_economy_gold_flow.md` | shop_service + buy/sell + UI sklepu | 🔴 planned | Phase 9 NPC |

---

## Mechanika Gold

| Źródło | Jak |
|--------|-----|
| Loot po walce | `roll_gold_drop(enemy_key)` z `gold_min/gold_max` w loot_table |
| Sprzedaż | `sell_item()` → `value_gp * SELL_RATIO` (default 50%) |
| Fabularne | GM cue: `Grant Gold N` → parser → `POST /api/characters/{id}/gold` |
| Starter | `game_config_archetypes.starter_gold_gp` przy kreacji postaci |

| Wydatek | Jak |
|---------|-----|
| Zakup | `buy_item()` → `gold_gp -= item.value_gp` |

---

## Otwarte decyzje

- **Procent sprzedaży:** 50% (rekomendacja) vs 100% vs CHA-based
- **Shop inventory:** stała lista w `npc.shop_inventory_json` vs dynamiczna?
- **Limit zakupów:** nielimitowane czy max sztuk na sesję?
