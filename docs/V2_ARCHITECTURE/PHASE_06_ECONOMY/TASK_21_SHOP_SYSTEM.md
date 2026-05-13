# TASK 21 — Shop System

**Phase:** 06 — Economy  
**Status:** ❌ Not Started  
**Related tasks:** TASK 20 (inventory), TASK 11 (turn pipeline), TASK 12 (skill tests)

---

## Overview

There is no "Shop" button. Players buy things by talking to merchants — the same way they interact with any NPC. The shop UI opens naturally when the player engages a merchant in dialogue. This keeps commerce embedded in the world's social fabric rather than abstracted into a menu system.

---

## Entry Flow

```
Player action: "Chcę coś kupić od Heinza" or clicks [Rozmawiaj z Heinzem]
  → Intent Parser → ACTION:TALK:heinz_the_armorer:shopping
  → World State Machine: Heinz present in location? → YES
  → DB lookup: load NPC record heinz_the_armorer
    → npc.is_shop = true
    → npc.shop_items: [{item_key, quantity_available, price_override}]
  → Response:
    - Left panel: narrator prose (Heinz greets the player, describes wares)
    - Right panel: shop UI opens alongside existing inventory panel
```

The shop panel is a layer that slides open over the inventory panel (or alongside it, depending on screen width). The narrator's prose handles the social encounter — the player may continue talking to Heinz while browsing. Both panels remain active simultaneously.

---

## Shop UI

```
┌──────────────────────────────────┐
│  SKLEP: HEINZ RÜSTIG, PŁATNERZ   │
├──────────────────────────────────┤
│  Twoje złoto: 47 sz              │
├──────────────────────────────────┤
│  Towary:                         │
│  Miecz Długi        60 sz  [Kup] │
│  Kolczuga           80 sz  [Kup] │
│  Eliksir Zdrowia    30 sz  [Kup] │
│  Bandaż              5 sz  [Kup] │
├──────────────────────────────────┤
│  Twoje przedmioty na sprzedaż:   │
│  Zardzewiały Kindżał  3 sz [Sprzedaj] │
└──────────────────────────────────┘
```

Close button (X) or navigating away from the location closes the shop panel. Closing does not require a narrator call.

---

## NPC Shop Configuration

Shop inventory is defined per NPC in `npc_definitions.shop_items` (JSON column). Structure:

```json
[
  {
    "item_key": "longsword",
    "price_override": null,
    "quantity_available": null
  },
  {
    "item_key": "health_potion",
    "price_override": 30,
    "quantity_available": null
  }
]
```

- `price_override`: if set, overrides `game_config_items.base_price` for this merchant
- `quantity_available`: null = unlimited stock; integer = limited (decrements on purchase)

**Static inventory in v1:** shop stock does not refresh between visits. What's sold is sold (if quantity limited). What remains in stock stays indefinitely.

Admin panel: `Admin → NPCs → Edit NPC → Shop Items`. Table editor for shop_items JSON array. Toggle `is_shop` boolean to enable/disable shop behavior.

---

## API

### GET /api/shop/{npc_id}

Returns the shop's current inventory with resolved prices:

```json
{
  "npc_id": "heinz_the_armorer",
  "npc_name": "Heinz Rüstig",
  "items": [
    {
      "item_key": "longsword",
      "name": "Miecz Długi",
      "item_type": "weapon",
      "price": 60,
      "quantity_available": null,
      "description": "Dobrej jakości stalowy miecz..."
    }
  ],
  "player_gold": 47,
  "player_sellable_items": [
    {
      "item_key": "rusty_dagger",
      "name": "Zardzewiały Kindżał",
      "sell_price": 3
    }
  ]
}
```

`sell_price = floor(game_config_items.base_price × 0.5)`. Sell price ratio is 50% of base price (see TASK 20 open question — confirm this is the resolved answer).

### POST /api/shop/{npc_id}/buy

```json
{ "item_key": "longsword", "character_id": 42 }
```

**Backend steps:**
1. Verify NPC `is_shop=true` and item is in NPC's `shop_items`
2. Verify character gold >= item price
3. Deduct gold: `characters.gold -= price`
4. Add item to character inventory: insert into `character_inventory`
5. Decrement `quantity_available` if not null
6. Return updated gold balance and inventory

**Insufficient gold:** return 400 with message body:
```json
{ "error": "insufficient_gold", "message": "Nie masz wystarczająco złota. Potrzebujesz 60 sz, masz 47 sz." }
```
Frontend shows this as an inline error below the item — no popup, no narrator call.

### POST /api/shop/{npc_id}/sell

```json
{ "item_key": "rusty_dagger", "character_id": 42 }
```

**Backend steps:**
1. Verify item exists in character inventory
2. Verify item `item_type != 'quest_item'` (quest items cannot be sold)
3. Calculate sell_price: `floor(base_price × 0.5)`
4. Add gold: `characters.gold += sell_price`
5. Remove item from character inventory (or decrement quantity if stackable)
6. Return updated gold balance

---

## Access Restrictions

**During combat:** `GET /api/shop/{npc_id}` returns 403 if `character.in_combat=true`:
```json
{ "error": "in_combat", "message": "Nie możesz handlować podczas walki." }
```

The shop panel close button is shown. No buy/sell operations permitted.

**NPC not present:** If `ACTION:TALK:npc_id` fails World State Machine check (NPC not in current location), the shop does not open. Standard `SYSTEM_MESSAGE` from State Machine: *"[System] Heinz nie jest tutaj."*

---

## Test Cases

1. **Buy item — success:** Character has 100 gold, longsword costs 60. Buy longsword. Verify gold = 40, longsword in inventory, `longsword` in `character_inventory` table.

2. **Sell item — success:** Character has rusty_dagger (base_price=6). Sell it. Verify gold += 3 (50% of 6), dagger removed from inventory.

3. **Insufficient gold rejected:** Character has 40 gold, item costs 60. Buy attempt returns 400 with `insufficient_gold` error. Gold unchanged. Item not added to inventory.

4. **Shop not accessible in combat:** Set `character.in_combat=true`. Call `GET /api/shop/{npc_id}`. Verify 403 returned.

5. **Quest item not sellable:** Attempt to sell item with `item_type='quest_item'`. Verify 400 returned. Gold unchanged.
