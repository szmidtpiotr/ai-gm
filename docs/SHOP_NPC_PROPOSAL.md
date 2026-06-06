# Shop NPC System — Design Proposal

## Overview

Shops are **interactive NPCs** that let players buy/sell equipment, consumables, and miscellaneous items. Anchored in named locations (karczma, sklep, rynek), shops drive gold economy and create trading gameplay loops.

## Mechanics

### 1. Shop NPC Entity (`game_config_shops`)

| Field | Type | Purpose |
|---|---|---|
| `key` | text | Unique identifier (e.g., `tavern_karczma_czarnogrodu`, `blacksmith_skansen`) |
| `label` | text | Display name (e.g., "Karczma Czarnego Grodu", "Kuźnia Halafarda") |
| `npc_type` | enum | `tavern`, `blacksmith`, `general_store`, `alchemist`, `weapons_shop` |
| `location_key` | text | FK to `game_locations.key` — where shop is anchored |
| `base_markup` | float | Markup % (1.0 = no markup, 1.5 = 50% margin) |
| `stock_reset_hours` | int | Restock interval (0 = static, 24 = daily) |
| `personality_prompt` | text | GM prompt hint for shop keeper (e.g., "gruff dwarf blacksmith") |
| `description` | text | Flavor text for entering shop |
| `is_active` | bool | Enabled in campaign |

### 2. Shop Stock (`game_shop_inventory`)

| Field | Type | Purpose |
|---|---|---|
| `id` | int PK | |
| `shop_key` | text | FK to `game_config_shops.key` |
| `item_key` | text | FK to `game_config_items.key` (weapon, armor, consumable) |
| `qty_available` | int | Current stock (depletes on buy, refills on reset) |
| `qty_base` | int | Restock quantity each cycle |
| `sell_price` | int | Sell TO player (in gold) |
| `buy_price` | int | NPC buys FROM player (usually ~70% of sell_price) |
| `added_at` | timestamp | |

### 3. Player Inventory Slots (Optional — defer to Phase 2)

For MVP, assume players carry unlimited items. Later: add weight/slot limits forcing strategic inventory management.

---

## Shop Interactions — Player Flow

### 1. Enter Shop (Narrative)

Player: *"Wchodzę do karczmy i podaję się za poszukiwacza przygód."*

**GM response:**
```
[LOCATION CONTEXT: karczma_czarnogrodu — zwykła karczma w miasteczku]
[SHOP: karczma_czarnogrodu (tavern)]
Zmęczeni twojej wędrówki spogląd na ciebie z ciekawością. Karczmarzy 
[sznurek oferuje jedzenie, picie, noclegi, a także drobiazgi: zioła, 
zużyte mapy, stare broń...]

Chcesz coś kupić? Oto lista: [MENU]
```

### 2. Browse Menu (`GET /api/shop/{key}/inventory`)

Response:
```json
{
  "shop": {
    "key": "tavern_karczma_czarnogrodu",
    "label": "Karczma Czarnego Grodu",
    "keeper_greeting": "Cześć! Co chcesz kupić?",
    "personality": "Friendly innkeeper"
  },
  "inventory": [
    { "item_key": "healing_potion", "label": "Mikstura uzdrawiająca", 
      "sell_price": 50, "qty_available": 3, "rarity": "common" },
    { "item_key": "leather_armor", "label": "Zbroja skórzana", 
      "sell_price": 150, "qty_available": 1, "rarity": "uncommon" },
    ...
  ],
  "player_gold": 27
}
```

### 3. Buy Item (`POST /api/shop/{key}/buy`)

**Request:**
```json
{
  "campaign_id": 1115,
  "character_id": 1125,
  "item_key": "healing_potion",
  "qty": 1
}
```

**Response:**
```json
{
  "success": true,
  "item": { "key": "healing_potion", "label": "..." },
  "gold_spent": 50,
  "gold_remaining": 27,
  "inventory_added": true,
  "shop_keeper_quip": "Zdrówko! Wróć, gdy zechcesz więcej."
}
```

### 4. Sell Item (`POST /api/shop/{key}/sell`)

Player can sell items back (at lower buy_price):
```json
{
  "campaign_id": 1115,
  "character_id": 1125,
  "item_key": "rusty_sword",
  "qty": 1
}
```

Response: gold received, item removed from inventory.

---

## Gameplay Rules

### Gold Economy Anchor

| Activity | Gold gain | Notes |
|---|---|---|
| Kill goblin | 2–5 gold | Loot drop |
| Kill bandit | 5–10 gold | Better loot |
| Complete location | 20–50 gold | Location bonus |
| Sell item to shop | varies | Typically 60–80% of buy_price |

| Activity | Gold spend | Notes |
|---|---|---|
| Buy healing potion | 50 gold | Single-use restore 1d6+CON_mod |
| Buy leather armor | 150 gold | AC +1 equipment |
| Buy greatsword | 300 gold | Heavy weapon, 2d6 dmg |
| Tavern lodging | 10 gold | Short rest (heal 1d4+level) |

### Stock Reset Logic

```python
# On campaign turn boundary or explicit /admin/shop/restock call
for shop in shops:
  if shop.stock_reset_hours > 0:
    if now - last_restock >= hours(shop.stock_reset_hours):
      for item in shop.inventory:
        item.qty_available = item.qty_base
      last_restock = now
```

### Markup Adjustment

Optional: **dynamic pricing** based on player level or campaign difficulty:

```python
sell_price = base_price * (1 + base_markup) * (1 + level_factor * 0.1)
# E.g., base 50g healing potion, markup 1.2, level 5 → 60g
```

---

## Shop Types & Specialization

| Type | Inventory Focus | Personality |
|---|---|---|
| **Tavern** | Food, drink, basic supplies, healing potions | Friendly, gossipy. Offers rumors & quests. |
| **Blacksmith** | Weapons, heavy armor, tools. High prices. | Gruff. Quality-focused. May refuse to sell to unworthy. |
| **General Store** | Mixed: rope, torches, lanterns, mundane gear | Practical, efficient. "Got everything?" |
| **Alchemist** | Potions, herbs, magical components | Mysterious. May offer custom brews. |
| **Weapons Shop** | Swords, bows, crossbows, shields | Boastful. May offer rentals or trade-ins. |

---

## Admin Interface (`/admin2/#kampanie → Warsztat → Sklepy`)

**Tab: Sklepy**
- List all active shops per campaign
- Card per shop: label, npc_type, location, stock display
- "Browse inventory" → table of items + sell/buy prices
- Restock button (manual trigger)
- Edit shop: personnel, prices, personality
- Link to GM plan (suggest shop encounters)

---

## Implementation Roadmap

### Phase 1 (MVP — this iteration)
- ✓ Create `game_config_shops` + `game_shop_inventory` tables
- ✓ `POST /api/shop/{key}/buy` endpoint
- ✓ `POST /api/shop/{key}/sell` endpoint
- ✓ `GET /api/shop/{key}/inventory` endpoint
- ✓ GM prompt hint for shop in system_prompt
- ✓ Add 2–3 test shops to DEV DB (tavern, blacksmith, general store)
- ✓ Seed with baseline stock + prices

### Phase 2 (Enhancement — later sprint)
- Inventory weight/slot limits
- Dynamic pricing by level
- Shop keeper dialogue/reputation
- Customizable shop quests ("Bring me dragon scales for 500g")
- Campaign-specific inventory overrides
- Shop bankrupty / restocking drought narrative hooks

### Phase 3 (Polish)
- Rental system (borrow gear, pay daily)
- Trade-in system (sell old sword, discount on new)
- Auction / bidding mechanics (for rare items)

---

## Database Setup

```sql
CREATE TABLE game_config_shops (
  key TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  npc_type TEXT CHECK(npc_type IN ('tavern','blacksmith','general_store','alchemist','weapons_shop')),
  location_key TEXT,
  base_markup REAL DEFAULT 1.2,
  stock_reset_hours INT DEFAULT 24,
  personality_prompt TEXT,
  description TEXT,
  is_active BOOLEAN DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE game_shop_inventory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  shop_key TEXT NOT NULL REFERENCES game_config_shops(key),
  item_key TEXT NOT NULL REFERENCES game_config_items(key),
  qty_available INT DEFAULT 0,
  qty_base INT NOT NULL,
  sell_price INT NOT NULL,
  buy_price INT NOT NULL,
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(shop_key, item_key)
);

CREATE TABLE shop_transaction_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  campaign_id INT,
  character_id INT,
  shop_key TEXT,
  transaction_type TEXT CHECK(transaction_type IN ('buy','sell')),
  item_key TEXT,
  qty INT,
  gold_delta INT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Example Shops (DEV Seed Data)

### Tavern Czarnogrodu
```json
{
  "key": "tavern_czarnogrodu",
  "label": "Karczma Czarnego Grodu",
  "npc_type": "tavern",
  "location_key": "karczma_czarnogrodu",
  "base_markup": 1.15,
  "stock_reset_hours": 24,
  "personality_prompt": "Friendly innkeeper, loves gossip about local bandits"
}
```

Stock: healing potions (qty 5 @ 50g), bread (qty 10 @ 5g), ale (qty 8 @ 3g)

### Blacksmith Halafarda
```json
{
  "key": "blacksmith_halafarda",
  "label": "Kuźnia Halafarda",
  "npc_type": "blacksmith",
  "location_key": "blacksmith_halafarda",
  "base_markup": 1.5,
  "stock_reset_hours": 48,
  "personality_prompt": "Gruff dwarf, demands respect, quality-focused"
}
```

Stock: longsword (qty 2 @ 300g), shield (qty 3 @ 150g), chainmail (qty 1 @ 500g)

---

## Next Steps

1. Commit schema migrations
2. Add test shops to DEV database
3. Implement buy/sell endpoints
4. Wire into GM narrator (suggest shop visits)
5. Add admin UI tab
6. Test via gameplay (playtest continues)
7. Document in game design wiki

