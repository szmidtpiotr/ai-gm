# Game Test Plan — Inventory, Items, Enemies, Loot, Plans, Hex Movement

## Test Heroes
- **1075** Test_Warrior (warrior archetype)
- **1076** Test_Scholar (scholar archetype, mana)
- **1077** Test_Rogue (rogue archetype)

## Test Scenarios

### Test 1: Test_Warrior Campaign (hero_id=1075)

#### 1A — Campaign Setup
- [ ] Create campaign with Test_Warrior
- [ ] Verify campaign created
- [ ] Check initial hero hex position
- [ ] Verify campaign plan generated (arcs, scene goals, roadmap)

#### 1B — Inventory & Items
- [ ] Do 5 turns to trigger item generation
- [ ] Check inventory for **new items** — are they created or pulled from DB?
  - [ ] If consumable created: does it appear in "Używalne" category?
  - [ ] If equipment created: does it appear in correct slot?
  - [ ] If weapon created: appears in weapons?
- [ ] Check admin → Zawartość → Przedmioty to see if GM created new records or reused seeded ones
- [ ] Check if created items have `created_by='gm_runtime'`

#### 1C — Enemy Generation
- [ ] Do 3 more turns to trigger combat/enemies
- [ ] Check admin → Świat → Oczekujące → Wrogowie
  - [ ] Are enemies in pending review or approved?
  - [ ] Check `created_by` field (should be 'gm_runtime' if GM-created)
- [ ] Check if enemies are seeded ones (from DB) or newly created

#### 1D — Weapons & Loot
- [ ] During combat, check if weapons offered are from DB or created
- [ ] After defeating enemies, check loot:
  - [ ] Does loot come from `loot_tables`?
  - [ ] Are items correct category (weapon, item, consumable)?
  - [ ] Gold amount reasonable?

#### 1E — Campaign Plan
- [ ] Open admin → Kampanie → Test_Warrior campaign → Plan GM
- [ ] Verify plan has:
  - [ ] 3+ arcs with narrative
  - [ ] Scene goals
  - [ ] NPCs/locations/items hooks
  - [ ] Roadmap visible
- [ ] Check if plan updates after player actions

#### 1F — Hex Movement
- [ ] Check hero current hex (q, r)
- [ ] Do turn with movement action (e.g., "Idę na północ")
- [ ] Check admin → Świat → Mapa: 
  - [ ] Hex updated to new position?
  - [ ] Can see hex coordinates?
- [ ] Try moving to different hexes, verify map updates

### Test 2: Test_Scholar Campaign (hero_id=1076)
- [ ] Repeat 1A–1F
- [ ] Focus on: mana system, spell-based loot, Scholar-exclusive items
- [ ] Verify spells appear in inventory correctly
- [ ] Check if mana consumables offered

### Test 3: Test_Rogue Campaign (hero_id=1077)
- [ ] Repeat 1A–1F
- [ ] Focus on: rogue-specific equipment, lockpicks, poisons
- [ ] Verify rogue-exclusive items offered

## Acceptance Criteria

### Item Creation
- ✅ GM pulls 80% from seeded DB, creates 20% for narrative flavor
- ✅ New items have `created_by='gm_runtime'`
- ✅ Consumables → Używalne category
- ✅ Equipment → correct slot (broń/zbroja/etc.)
- ✅ All items appear in inventory correctly

### Enemy Generation
- ✅ Enemies mostly from DB (seeded)
- ✅ Pending enemies appear in review tab
- ✅ Enemy tier scales with hero level
- ✅ Enemies have loot_table assigned

### Loot System
- ✅ Loot comes from loot_tables
- ✅ Correct item categories (no weapons in consumables, etc.)
- ✅ Gold scaled reasonably (100–500 per fight)
- ✅ Rare items appear ~20% of kills

### Campaign Plans
- ✅ Plan generated on campaign create
- ✅ Plan has 3+ arcs with scene goals
- ✅ Plan hooks include NPCs, locations, items
- ✅ Roadmap visible

### Hex Movement
- ✅ Hero starts at valid hex
- ✅ Movement updates hero.location in DB
- ✅ Admin map shows correct hex
- ✅ Can move to any hex (no zone blocking)

## Notes
- Check pending tables for any unreviewed content
- Verify seeded locations appear in location offers
- Check if GM creates duplicate names (e.g., 2nd "Health Potion")
