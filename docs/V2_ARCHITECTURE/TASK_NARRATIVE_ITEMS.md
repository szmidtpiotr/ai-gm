# Task: Narrative Items — Full Inventory Tracking (Option B)

> **Status:** Pending implementation  
> **Priority:** High — blocks immersive gameplay when LLM invents items  
> **Depends on:** Existing `character_inventory` table, `grant_item_label` pipeline in `turns.py`

---

## Problem Statement

When the GM (LLM) narrates that a player **finds, picks up, or receives** an item that doesn't exist in the DB catalog, one of two things currently happens:

1. **`Grant Item` cue present in LLM response** → backend detects it, checks DB, item not found → saves to `sheet_json.narrative_items[]` (a JSON blob array). This is invisible to the player.
2. **No `Grant Item` cue** (player just picks something up narratively) → nothing happens anywhere. Item is completely lost.

**Result:** The rusty spear, iron key, paper note, wooden amulet — none of these show up in the player's inventory. They exist only in the narrative text.

---

## Current Architecture (Broken Flow)

```
LLM response
  └─ "Grant Item Żelazny Klucz"  (roll_cue field)
       └─ _resolve_grant_catalog_item()
            ├─ FOUND in DB → grant_loot_to_character() → character_inventory row ✅
            └─ NOT FOUND → append_narrative_item_to_sheet()
                              └─ sheet_json.narrative_items[] ← invisible JSON blob ❌

Player picks up spear (no Grant Item cue)
  └─ Nothing. ❌
```

**Two breakpoints:**
1. `narrative_items` in `sheet_json` are **never shown** in the frontend inventory tab
2. Many GM item grants don't emit `Grant Item` cue at all

---

## Solution: Option B — Free-form inventory rows

### Core Idea

Extend `character_inventory` to support rows where **no catalog key exists**, using a free-text `label` stored in `meta_json`. This makes all items — catalog OR narrative — live in the same table with the same tracking capabilities.

### DB Change

Add a `label` column to `character_inventory` for free-form item names:

```sql
ALTER TABLE character_inventory ADD COLUMN label TEXT DEFAULT NULL;
```

A row is **narrative** when ALL of `item_key`, `weapon_key`, `consumable_key` are NULL but `label` is set.  
A row is **catalog** when one of the three keys is set (existing behavior, unchanged).

The existing `meta_json` column holds extra data (e.g. `{"description": "Pognieciona kartka z mapą"}`, `{"weapon_type": "spear"}` for narrative weapons).

### Row Examples

```sql
-- Narrative item (quest note, amulet, map fragment)
INSERT INTO character_inventory
  (character_id, label, item_key, weapon_key, consumable_key, quantity, source, meta_json)
VALUES
  (42, 'Pogięta kartka z mapą', NULL, NULL, NULL, 1, 'gm', '{"description":"Prostokąt z trzema kropkami"}');

-- Narrative weapon (rusty spear picked up mid-story)
INSERT INTO character_inventory
  (character_id, label, item_key, weapon_key, consumable_key, quantity, source, meta_json)
VALUES
  (42, 'Zardzewiała włócznia', NULL, NULL, NULL, 1, 'gm',
   '{"item_type":"weapon","description":"Zimna, stara włócznia skrzepłą krwią"}');

-- Catalog item (unchanged)
INSERT INTO character_inventory
  (character_id, label, item_key, weapon_key, consumable_key, quantity, source)
VALUES
  (42, NULL, 'bandage', NULL, NULL, 2, 'loot');
```

---

## Backend Changes Required

### 1. Migration (`migrations_admin.py`)

```sql
ALTER TABLE character_inventory ADD COLUMN label TEXT DEFAULT NULL;
```

Add to `_ensure_dungeon_v2_schema` or a new migration function.

### 2. `turns.py` — Replace `append_narrative_item_to_sheet`

Current:
```python
append_narrative_item_to_sheet(conn, character_id=..., label=grant_item_label, source="gm")
```

New: insert into `character_inventory` with `label` set, all keys NULL.
```python
_grant_narrative_item_to_inventory(conn, character_id=..., label=grant_item_label, source="gm")
```

Function signature:
```python
def _grant_narrative_item_to_inventory(
    conn, *, character_id: int, label: str, source: str = "gm",
    item_type: str = "narrative",   # "narrative" | "weapon" | "consumable"
    description: str | None = None,
    given_at: str | None = None,
) -> None:
    meta = {"item_type": item_type}
    if description: meta["description"] = description
    if given_at: meta["given_at"] = given_at
    conn.execute("""
        INSERT INTO character_inventory
            (character_id, label, item_key, weapon_key, consumable_key,
             quantity, equipped, source, meta_json)
        VALUES (?, ?, NULL, NULL, NULL, 1, 0, ?, ?)
    """, (character_id, label, source, json.dumps(meta, ensure_ascii=False)))
```

### 3. `loot_service.py` — Update `get_character_inventory`

The existing function builds the inventory list from DB rows. Extend it to handle `label IS NOT NULL AND item_key IS NULL AND weapon_key IS NULL AND consumable_key IS NULL`:

```python
# Narrative item — label stored directly on the row
if r["label"] and not r["item_key"] and not r["weapon_key"] and not r["consumable_key"]:
    meta = json.loads(r["meta_json"] or "{}")
    item_type = meta.get("item_type", "narrative")
    out.append({
        "id": int(r["id"]),
        "slot": None,
        "equipped": 0,
        "quantity": int(r["quantity"] or 1),
        "source": r["source"],
        "acquired_at": r["acquired_at"],
        "label": r["label"],
        "item_type": item_type,    # "narrative" | "weapon" | "consumable"
        "key": None,               # no catalog key
        "can_use": False,
        "description": meta.get("description"),
        "is_narrative": True,
    })
```

### 4. `characters.py` — Deprecate `narrative_items` in `sheet_json`

- Remove `append_narrative_item_to_sheet` calls and the `/characters/{id}/narrative-item` endpoint (or keep for backward compat but route through the new system)
- Migration: on character load, if `sheet_json.narrative_items` exists and is non-empty, migrate those entries to `character_inventory` rows

### 5. New endpoint: `DELETE /inventory/{character_id}/item/{inventory_id}` 

This already exists as `delete_inventory_item` in `loot_service.py` and is exposed. No new endpoint needed — the same delete works for narrative rows.

---

## Frontend Changes Required

### 1. `loot_service.py` already feeds `renderInventoryTab`

The `/api/inventory/{character_id}` endpoint returns all inventory rows. Once `get_character_inventory` returns narrative rows, they auto-appear in the inventory without frontend changes.

**Routing in `renderInventoryTab`:**
```javascript
// Existing check _invIsLore
function _invIsLore(item) {
    const t = String(item.item_type || '').toLowerCase();
    return t === 'misc' || t === 'quest' || t === 'narrative';  // add 'narrative'
}
```

### 2. Show description tooltip on narrative items

The `meta_json.description` field should appear as a tooltip on lore items.

### 3. "Wyrzuć" (Drop) button on narrative items

Narrative items should show a drop/remove button in the lore section. Clicking it calls the existing `DELETE /inventory/{character_id}/item/{inventory_id}`.

---

## LLM Prompt Update

The system prompt currently instructs the LLM to use `Grant Item <label>` in the `roll_cue` field. This works for explicit pickups but the LLM often forgets it for implicit pickups ("you pick up the spear").

Add to the system prompt:
```
When the hero acquires any physical object — weapon, tool, document, or trinket — 
always include in roll_cue: "Grant Item <Polish name of item>"
Example: picking up a spear → roll_cue: "Grant Item Zardzewiała włócznia"
Example: finding a note → roll_cue: "Grant Item Pognieciona kartka"
```

---

## Migration Plan for Existing Data

On first startup after migration:
1. For each character, read `sheet_json.narrative_items[]`
2. For each entry, insert into `character_inventory` with `label` = entry.label
3. Clear `sheet_json.narrative_items` array (set to `[]`)

This is idempotent — only migrate if `narrative_items` is non-empty.

---

## Narrative Weapon Review Flow

Narrative weapons (LLM-invented weapon-like items) follow a **separate path** — they enter the Pending Review pipeline so the admin decides their scope.

### Full Flow

```
GM narrates: "chwytasz zardzewiałą włócznię"
LLM emits: roll_cue = "Grant Item Zardzewiała włócznia"

Backend detects weapon intent → label contains weapon keyword (włócznia, miecz, etc.)
  │
  ├─ Creates row in game_config_weapons:
  │     key        = "narrative_wlocznia_<campaign_id>_<ts>"
  │     label      = "Zardzewiała włócznia"
  │     ai_generated = 1, approved = 0
  │     campaign_id  = <current_campaign>   ← new column
  │     review_status = 'pending_review'
  │     damage_die   = "1d6"  (default or LLM-suggested)
  │     weapon_type  = "melee"
  │
  └─ Grants to character_inventory via weapon_key (normal weapon row)
       → Player sees it as a REAL weapon, can equip it immediately
```

### Admin Review (Oczekujące → "Broń" section)

| Action | `approved` | `campaign_id` | Result |
|---|---|---|---|
| **Zatwierdź** | `1` | `NULL` cleared | **Globally available** — enters the full catalog, appears in loot tables and shops everywhere |
| **Odrzuć / Modyfikuj** | `1` | stays set | **Campaign-scoped** — exists in DB, works in that campaign, never leaks to other campaigns or global loot |

The admin can **edit all stats** (damage_die, attack_bonus, description, effect_json) before either decision.

### DB Changes

```sql
-- Weapon campaign scope
ALTER TABLE game_config_weapons ADD COLUMN campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL;
-- Weapon review status (mirrors game_locations, npcs, game_config_enemies)
ALTER TABLE game_config_weapons ADD COLUMN review_status TEXT DEFAULT 'permanent';
-- Existing weapons stay 'permanent'. Narrative weapons start as 'pending_review'.
```

### Visibility Rule (everywhere weapons are looked up)

```sql
-- Catalog lookups filter: global OR scoped to current campaign
WHERE is_active = 1 AND (campaign_id IS NULL OR campaign_id = :campaign_id)
```

### Weapon Detection from Label

```python
WEAPON_LABEL_KEYWORDS = [
    "miecz", "sztylet", "włócznia", "topór", "łuk", "kusza",
    "nóż", "halabarda", "buzdygan", "rapier", "laska", "różdżka",
    "broń", "ostrze", "spear", "sword", "dagger", "axe", "bow",
]

def _is_weapon_label(label: str) -> bool:
    return any(kw in label.lower() for kw in WEAPON_LABEL_KEYWORDS)
```

### Default Stats for Narrative Weapons

```python
NARRATIVE_WEAPON_DEFAULTS = {
    "melee":  {"damage_die": "1d6", "linked_stat": "STR"},
    "ranged": {"damage_die": "1d6", "linked_stat": "DEX"},
    "spell":  {"damage_die": "2d4", "linked_stat": "INT"},
}
```

Admin adjusts in review. Safe defaults mean it's usable immediately even before review.

---

## What This Unlocks

| Feature | Before | After |
|---|---|---|
| Player sees found items (quest notes, amulets) | ❌ | ✅ Lore section in inventory |
| Player can drop/remove narrative items | ❌ | ✅ Same delete endpoint |
| Rusty spear equippable immediately | ❌ | ✅ Enters DB as pending weapon, player can equip |
| Admin reviews narrative weapons | ❌ | ✅ Oczekujące → Broń section |
| Approved weapon = global catalog | ❌ | ✅ campaign_id cleared, globally available |
| Rejected weapon = campaign-only | ❌ | ✅ campaign_id stays, invisible outside that campaign |
| Quest notes visible | ❌ | ✅ |
| Admin can tune narrative weapon stats | ❌ | ✅ Edit modal before approve/reject |

---

## Files to Change

### Narrative items (notes, amulets, misc)
| File | Change |
|---|---|
| `migrations_admin.py` | `ALTER TABLE character_inventory ADD COLUMN label TEXT` + migrate `sheet_json.narrative_items` |
| `backend/app/api/turns.py` | Replace `append_narrative_item_to_sheet` with `_grant_narrative_item_to_inventory`; detect weapon labels and route to weapon flow |
| `backend/app/services/loot_service.py` | Handle `label IS NOT NULL, key IS NULL` rows in `get_character_inventory` |
| `backend/app/api/characters.py` | Migrate old `sheet_json.narrative_items` on first load |
| `frontend/front/js/app.js` | Add `'narrative'` to `_invIsLore`; description tooltip; drop button |
| `backend/prompts/system_prompt.txt` | Reinforce `Grant Item` for all pickups |

### Narrative weapons (spears, swords, etc.)
| File | Change |
|---|---|
| `migrations_admin.py` | `ALTER TABLE game_config_weapons ADD COLUMN campaign_id INTEGER` + `ADD COLUMN review_status TEXT DEFAULT 'permanent'` |
| `backend/app/api/turns.py` | `_grant_narrative_weapon()` — creates pending weapon row, grants via weapon_key |
| `backend/app/services/admin_config.py` | Weapon visibility filter: `campaign_id IS NULL OR campaign_id = ?` |
| `backend/app/routers/world_review.py` | Add `weapons` to `entity_type` for approve/discard; approve clears `campaign_id` |
| `backend/app/routers/admin.py` | Add weapon review endpoints; edit modal for pending weapons |
| `frontend/admin_panel_v2/sections/world.js` | Add "Broń" subtab in Oczekujące; edit+approve+reject buttons |

---

## Out of Scope (Future Tasks)

- **Item stacking:** Same narrative label appearing twice → qty=2
- **Item inspection UI:** Tap-to-expand showing description in inventory
- **Narrative consumables:** Items that can be "used" (drink a potion found mid-story)
