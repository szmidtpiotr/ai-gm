# T46 Narrative Items — Test Plan

> Written after implementation on 2026-05-17.  
> Run these tests to verify T46 is working correctly.

---

## Test 1: Narrative Items (quest notes, amulets, keys)

**Setup:** Enter an active campaign with any hero.

**In game chat, type:**
```
schylam się i podnoszę pogniętą kartkę z podłogi
```
or
```
biorę amulet ze stołu
```
or
```
zabieram klucz z kieszeni trupa
```

**Expected results:**
- [ ] After the turn, open **Character Sheet → Inventory → Przedmioty fabularne** section
- [ ] The item appears with its Polish name (e.g. "Pogięta kartka")
- [ ] If the GM's narration included a description, hovering shows a tooltip
- [ ] Clicking **✕** drops the item — it disappears from inventory immediately

---

## Test 2: Narrative Weapons (spears, swords, daggers)

**In game chat, type:**
```
podnoszę zardzewiałą włócznię z ziemi
```
or
```
biorę leżący w kącie stary miecz
```

**Expected results:**
- [ ] After the turn, open **Character Sheet → Inventory → Wyposażenie**
- [ ] The weapon appears as a real equippable item (NOT in lore section)
- [ ] You can equip it to the main_hand slot
- [ ] In **Admin Panel → Świat → Oczekujące → ⚔ Broń**: the weapon appears

**Admin review flow:**
- [ ] Edit form shows: damage_die, weapon_type, linked_stat, description fields
- [ ] **✓ Globalna** → weapon enters global catalog, `campaign_id` cleared
- [ ] **📌 Tylko kampania** → weapon stays in this campaign only, `review_status` = permanent
- [ ] **✕ Odrzuć** → weapon removed from pending queue (discarded)

---

## Test 3: Migration of Old narrative_items

**If any character had items in `sheet_json.narrative_items` before this update:**
- [ ] After the first backend restart post-deployment, those items should appear in the **Przedmioty fabularne** section automatically
- [ ] No manual action required — migration runs on startup

**To check manually:**
```bash
ssh claude@192.168.1.61 "sqlite3 /home/piotrszmidt/ai-gm/data-dev/ai_gm.db \
  \"SELECT character_id, label, source FROM character_inventory WHERE label IS NOT NULL AND item_key IS NULL LIMIT 10;\""
```

---

## Test 4: Grant Item Cue Reliability

Play through a scene where the GM naturally gives items. The updated system prompt instructs the LLM to always add `Grant Item <name>` for any physical pickup.

**Verify the cue appears:**
```
"schylam się po klucz"           → roll_cue: "Grant Item Żelazny klucz"
"biorę kartkę"                   → roll_cue: "Grant Item Kartka z notatkami"  
"podnoszę miecz z podłogi"       → roll_cue: "Grant Item Stary miecz"   (weapon!)
```

- [ ] Item/weapon appears in inventory after turn
- [ ] No "Grant Item" text visible in the chat bubble (cue is stripped from display)

---

## Test 5: Drop Button Doesn't Break Non-Narrative Items

- [ ] Regular catalog items (bandage, shortsword) do NOT show the ✕ drop button
- [ ] Only `item_type = 'narrative'` rows show the drop button

---

## DB Verification Queries

```sql
-- Check narrative items in inventory
SELECT id, character_id, label, source, meta_json 
FROM character_inventory 
WHERE label IS NOT NULL AND item_key IS NULL AND weapon_key IS NULL;

-- Check pending narrative weapons
SELECT key, label, weapon_type, damage_die, campaign_id, review_status
FROM game_config_weapons 
WHERE review_status = 'pending_review';

-- Confirm new columns exist
PRAGMA table_info(character_inventory);  -- should show 'label' column
PRAGMA table_info(game_config_weapons);  -- should show 'campaign_id', 'review_status'
```
