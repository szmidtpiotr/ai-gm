# TASK 20 — Inventory and Equipment

**Phase:** 06 — Economy  
**Status:** Pending  
**Related tasks:** TASK 21 (shop), TASK 22 (loot), TASK 23 (healing)

---

## Overview

The inventory system tracks everything a character carries and manages what equipment is actively worn or wielded. The right sidebar panel (already present in the frontend) is the primary UI surface. In v1: no drag-and-drop, no encumbrance — clean and functional.

---

## Equipment Slots

Each character has exactly these slots, one item per slot:

| Slot Key | Display Name | Allowed Categories |
|----------|-------------|-------------------|
| `main_hand` | Prawa Ręka | weapon |
| `off_hand` | Lewa Ręka | weapon, shield |
| `body` | Pancerz | armor |
| `head` | Hełm | armor |
| `hands` | Rękawice | armor |
| `feet` | Buty | armor |
| `accessory_1` | Akcesorium | misc, accessory |
| `accessory_2` | Akcesorium | misc, accessory |

Slots are stored in a `character_equipment` table:

```sql
CREATE TABLE character_equipment (
  character_id INTEGER REFERENCES characters(id),
  slot TEXT NOT NULL,
  item_key TEXT REFERENCES game_config_items(item_key),
  equipped_at DATETIME,
  PRIMARY KEY (character_id, slot)
);
```

---

## Item Categories

All items in `game_config_items` have an `item_type` field:

| Type | Description |
|------|-------------|
| `weapon` | Equippable to hand slots; provides ATK bonus |
| `armor` | Equippable to body/head/hands/feet; provides AC bonus |
| `consumable` | Single-use; usable from inventory or combat panel |
| `quest_item` | Cannot be dropped, sold, or equipped; always visible in inventory |
| `misc` | Everything else; equippable to accessory slots if meaningful |

---

## Equip Rules

- **One item per slot.** Equipping a new item to an occupied slot automatically unequips the old one (swap, not drop — old item returns to unequipped inventory).
- **Unequip** by clicking an equipped item again (toggle). Item returns to unequipped inventory.
- **Swapping weapons/armor is out-of-combat only.** If `combat.active=true` for this character, the equip/unequip API returns 400 with message: *"Nie możesz zmieniać ekwipunku podczas walki."*
- **Consumables** (potions, bandages) can be used during combat via the [Użyj Przedmiot] button in the combat panel. Using a consumable costs the player's action for that round.
- No equipping weapons you don't have proficiency in (proficiency check: `character_skills` must contain the relevant weapon skill at rank ≥ 1, or archetype default proficiency applies).

---

## API

### GET /api/inventory/{character_id}

Returns:
```json
{
  "equipped": {
    "main_hand": { "item_key": "shortsword", "name": "Krótki Miecz", "atk_bonus": 1 },
    "body": { "item_key": "leather_armor", "name": "Skórzana Zbroja", "ac_bonus": 2 },
    ...
  },
  "unequipped": [
    { "item_key": "health_potion", "name": "Eliksir Zdrowia", "item_type": "consumable", "quantity": 2 },
    ...
  ],
  "gold": 47
}
```

### POST /api/inventory/{character_id}/equip

```json
{ "item_key": "shortsword", "slot": "main_hand" }
```

Returns updated equipped state or 400 on rule violation.

### POST /api/inventory/{character_id}/unequip

```json
{ "slot": "main_hand" }
```

### POST /api/inventory/{character_id}/use

For consumables. See TASK 23 (healing) for consumable use logic.

---

## Combat Access to Consumables

During combat, the combat panel shows a [Użyj Przedmiot] button. Clicking reveals a mini-list of consumables currently in inventory. Selecting one calls `POST /inventory/{id}/use` with `combat=true` parameter.

Weapons and armor are greyed out in the combat inventory view with tooltip: *"Nie możesz zmieniać broni podczas walki."*

---

## Equipment Effects

### Armor (AC bonus)

AC is recalculated on each equip/unequip:

```python
base_ac = 10
ac_bonus = sum(item.ac_bonus for item in equipped_armor_items)
dex_mod = floor((character.dex - 10) / 2)
character.armor_class = base_ac + ac_bonus + dex_mod
```

Write the new AC to `characters.armor_class` on every equip/unequip event.

### Weapons (ATK bonus)

The `game_config_items` table needs a `weapon_bonus` column (add via migration if missing):

```sql
ALTER TABLE game_config_items ADD COLUMN weapon_bonus INTEGER DEFAULT 0;
```

During combat attack resolution, `weapon_bonus` from the equipped `main_hand` item is added to the attack roll total.

```python
atk_bonus = character.str_mod + equipped_weapon.weapon_bonus + skill_rank + proficiency
```

---

## Gold Display

Gold is always visible as a small indicator near the character name in the right sidebar panel. Format: `⚙ 47 sz` (sz = szylinga, the currency unit). Updates in real time after any gold-changing transaction (buy, sell, loot pickup, reward).

---

## No Encumbrance (V1)

There is no carrying capacity limit in v1. Characters can hold unlimited items. A note in the codebase: `# TODO v2: encumbrance system`. Do not implement or allude to encumbrance in any user-facing text.

---

## Frontend Panel (Right Sidebar)

The inventory panel already exists in the frontend. This task wires it to real data.

**Equipment section:** Visual slot grid (2 columns × 4 rows + 2 accessory slots). Each slot shows item icon and name if equipped, or "— Puste —" if empty. Click equipped item to unequip. Click empty slot to open item picker filtered to valid item types for that slot.

**Inventory list:** Below equipment grid. Shows all unequipped items with quantity for stackable items (consumables stack). Click consumable to use (if out of combat). Click equipment to equip (assigns to first valid empty slot, or prompts slot choice if multiple valid slots open).

---

## Open Questions

These questions remain unresolved and must be answered before implementing the shop and loot systems:

- **Selling price ratio:** What fraction of `base_price` does the merchant pay when player sells? (Proposed: 50%. Confirm before TASK 21.)
- **Inventory full behavior:** Since v1 has no encumbrance, there is no "full" state. If a future v2 cap is added, items refused at cap should not be silently discarded — they must be clearly rejected with a message. Flag in code: `# FUTURE: inventory_cap enforcement here`.
