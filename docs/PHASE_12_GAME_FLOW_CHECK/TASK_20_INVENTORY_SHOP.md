# TASK 20 — Inventory & Shop

**Status:** ❓ Needs Design
**Blocking:** Full design discussion needed before this can be specced
**Depends on:** Task 18 (Loot System — items flow into inventory), Task 16 (Healing items need to be purchasable)

---

## What Needs to Be Designed

This task requires a full design discussion covering:

1. **Shop entry point** — How does the player access a shop? Via NPC interaction? A dedicated command? Only in certain locations?
2. **Equip UX** — Drag-and-drop equipment slots vs click-to-equip? During gameplay or only between scenes?
3. **Inventory limits** — Is there a carrying capacity? Weight system? Slot limits?
4. **Item categories** — What can players carry: weapons, armor, consumables, quest items, gold?
5. **Equipment slots** — What slots exist: main hand, off hand, body, head, hands, feet?
6. **Selling items** — Can players sell loot to NPCs? At what price multiplier?
7. **Shop inventory** — Is shop inventory fixed (admin-configured per NPC) or dynamic (refreshes over time)?

## Current State

- Inventory panel exists in the right sidebar
- `POST /inventory/{char_id}/equip`, `/use`, `DELETE` endpoints exist
- Shop modal HTML exists but no navigation entry point
- Equip/unequip works mechanically but drag-drop not implemented
- `npc_definitions.is_shop` flag exists for marking merchant NPCs
- `GET /api/shop/{npc_id}` and buy/sell endpoints exist

## Open Questions to Discuss

1. **Shop entry point** — Via NPC narrative interaction ("I approach the merchant") or a dedicated UI button? Currently no entry point exists — `#shop-modal` HTML exists but is unreachable.
2. **Equip UX** — Click-to-equip (simpler, works now) or drag-drop (more engaging, slots exist in HTML but no DnD logic)? During narrative play or only between scenes?
3. **Inventory limits** — Carrying capacity / weight system, or unlimited in v1?
4. **Combat access** — Is non-consumable inventory accessible during combat? (Consumables already allowed via Task 12 [Use Item] action)
5. **Gold display** — Visible in main UI at all times, or only when inventory is open?
6. **Equipment slots** — Confirm: main hand, off hand, body, head, hands, feet?
7. **Selling** — Can players sell loot to merchants? At what price ratio (e.g. 50% of buy price)?
8. **Shop inventory** — Fixed per NPC (admin-configured) or refreshes over time / per session?
9. **Inventory full state** — What happens when loot is claimed but inventory is full? Drop oldest item? Player chooses what to swap?
10. **Gold in combat** — Gold found in loot: auto-added to wallet, or player must claim like items?

---

*This file will be filled with full specification after the design discussion.*
