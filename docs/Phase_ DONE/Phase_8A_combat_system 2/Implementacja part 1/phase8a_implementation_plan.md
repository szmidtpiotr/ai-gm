# 🎯 Phase 8A — Combat System Implementation Plan
**Kolejność kroków uwzględnia zależności między komponentami**

---

## 📋 ETAP 1: Foundation (Database + Data Loading)

### **Step 1.1: Database Migration — active_combat table**

**Zależności:** BRAK (foundational step)

**Cursor Prompt:**
```
SAFETY CHECK FIRST:

Before implementing, please analyze:
1. Check if table `active_combat` already exists in the database schema
2. Verify there are no existing combat-related tables that might conflict
3. Check if any existing code references "active_combat" table
4. List any potential migration conflicts with existing schema

If NO BLOCKERS found, proceed with implementation:

---

IMPLEMENTATION TASK:

Create database migration for `active_combat` table.

Reference file: `active_combat_ddl.sql` (generated, check output folder)

Requirements:
- Add new table `active_combat` with all columns from DDL
- Create index on `campaign_id` for fast lookup
- Add migration script to `backend/migrations/` or equivalent
- Ensure migration is reversible (include DROP TABLE in rollback)

Files to modify:
- `backend/migrations/XXXX_add_active_combat.sql` (new file)
- OR equivalent migration system file

Acceptance criteria:
- [ ] Table created successfully
- [ ] Can INSERT sample combat state
- [ ] Can UPDATE turn state
- [ ] Can DELETE combat state
- [ ] Foreign key constraint works (campaign_id)
- [ ] Migration script includes rollback

Run migration and verify with: SELECT * FROM active_combat LIMIT 1;
```

---

### **Step 1.2: Enemy Catalog Injection into System Prompt**

**Zależności:** BRAK (parallel to 1.1)

**Cursor Prompt:**
```
SAFETY CHECK FIRST:

Before implementing, please analyze:
1. Check how current system prompt is loaded (file: `backend/prompts/system_prompt.txt`)
2. Verify if there's already enemy data injected anywhere in the prompt
3. Check if `game_config_enemies` table is accessible from where system prompt is built
4. Identify where system prompt is constructed for LLM calls (likely `gm.py` or `llm_service.py`)
5. Verify current system prompt length — adding enemy catalog must not exceed LLM context limits

If NO BLOCKERS found, proceed with implementation:

---

IMPLEMENTATION TASK:

Inject active enemy catalog into system prompt when session starts.

Requirements:
- Query `game_config_enemies` WHERE `is_active = 1` at session start
- Format as readable list for GM (key, label, tier, HP, damage_die)
- Inject into system prompt BEFORE sending to LLM
- Format example:

```
Available enemies in this world:
- bandit (Bandyta) — tier: weak, HP: 8, damage: d6+0
- arena_fighter (Gladiator Areny) — tier: standard, HP: 30, damage: d8+3
- assassin (Skrytobójca) — tier: elite, HP: 34, damage: d6+3
[...continue for all active enemies]

When combat starts, you must choose ONE enemy key from this list.
Emit: [COMBAT_START:enemy_key]
```

Files to modify:
- `backend/app/services/llm_service.py` OR `gm.py` (wherever system prompt is built)
- Possibly `backend/app/system_prompt_loader.py`

Acceptance criteria:
- [ ] Enemy list loaded from DB on session start
- [ ] Injected into system prompt before LLM call
- [ ] System prompt length checked (must fit in context window)
- [ ] Test: start new session, verify prompt includes enemy list
- [ ] GM can see enemy options when narrating combat scenarios
```

---

## 📋 ETAP 2: Combat Initiation

### **Step 2.1: Combat Start Detection + Snapshot Creation**

**Zależności:** Step 1.1 (active_combat table), Step 1.2 (enemy catalog)

**Cursor Prompt:**
```
SAFETY CHECK FIRST:

Before implementing, please analyze:
1. Check where player input is currently processed (likely `main.py` or `gm.py`)
2. Verify if there's already a combat detection mechanism in place
3. Check if GM response parsing exists (looking for special markers like [COMBAT_START:...])
4. Identify where to hook into the response processing pipeline
5. Check if `game_config_enemies` table has all required fields (key, label, hp_base, ac_base, attack_bonus, damage_die, damage_bonus, dex_modifier)

If NO BLOCKERS found, proceed with implementation:

---

IMPLEMENTATION TASK:

Detect [COMBAT_START:enemy_key] marker in GM response and create combat state.

Reference file: `combat_resolver_example.py` (check combatants JSON structure)

Requirements:
- Parse GM response for pattern: `[COMBAT_START:enemy_key]`
- When detected:
  1. Query `game_config_enemies` WHERE `key = enemy_key` AND `is_active = 1`
  2. Create enemy snapshot with unique ID (e.g., "enemy_1")
  3. Load player stats from `characters` table (HP, stats from sheet_json)
  4. Create combatants JSON array: [player_object, enemy_object]
  5. INSERT into `active_combat` with phase='initiative', combatants, turn_order=[]

Files to modify:
- `backend/app/services/combat_service.py` (new file)
- `main.py` or `gm.py` (add combat detection hook)
- Possibly `backend/app/api/routes.py` (if endpoint-based)

Acceptance criteria:
- [ ] Marker detected correctly in GM response
- [ ] Enemy record fetched from DB
- [ ] Player stats loaded from character sheet
- [ ] Combatants JSON created with correct structure
- [ ] active_combat row inserted successfully
- [ ] Test: trigger combat, verify DB row created
- [ ] Test: invalid enemy_key handled gracefully (error message)
```

---

## 📋 ETAP 3: Initiative & Turn Management

### **Step 3.1: Initiative Roll System**

**Zależności:** Step 2.1 (combat state created)

**Cursor Prompt:**
```
SAFETY CHECK FIRST:

Before implementing, please analyze:
1. Check if dice rolling function exists (likely in utils or dice module)
2. Verify dice roll result is stored somewhere for roll cards (check Phase 7 roll system)
3. Check if initiative skill exists in `game_config_skills` table
4. Identify where to trigger initiative rolls (immediately after combat starts?)
5. Verify if roll results need to be displayed to player (roll card UI from Phase 7)

If NO BLOCKERS found, proceed with implementation:

---

IMPLEMENTATION TASK:

Roll initiative for all combatants and establish turn order.

Reference: combat_resolver_example.py (see resolve_attack function for dice rolling)

Requirements:
- Immediately after combat state created (phase='initiative'):
  1. Roll d20 for player: d20 + DEX modifier + initiative skill rank
  2. Roll d20 for each enemy: d20 + dex_modifier (from enemy record)
  3. Sort results descending (highest goes first)
  4. Create turn_order array: ["enemy_1", "player"] or ["player", "enemy_1"] etc.
  5. UPDATE active_combat SET turn_order=JSON, current_actor_id=turn_order[0], current_actor_index=0, phase='in_progress'

- Store initiative rolls in roll_history for display

Files to modify:
- `backend/app/services/combat_service.py` (add initiative_roll function)
- Integration point: after combat start detection

Acceptance criteria:
- [ ] Initiative rolled for all combatants
- [ ] Turn order sorted correctly (highest first)
- [ ] active_combat.turn_order updated
- [ ] active_combat.current_actor_id set to first actor
- [ ] Roll results stored in roll_history
- [ ] Test: start combat, verify turn order makes sense
- [ ] Test: player with high DEX goes first
- [ ] Test: ties handled (random or DEX stat as tiebreaker)
```

---

### **Step 3.2: Turn State Management**

**Zależności:** Step 3.1 (turn order established)

**Cursor Prompt:**
```
SAFETY CHECK FIRST:

Before implementing, please analyze:
1. Check where player actions are currently processed
2. Verify if there's a way to query "whose turn is it?" from active_combat
3. Check if turn advancement logic exists anywhere
4. Identify potential race conditions (multiple requests during same turn)
5. Verify how to signal "turn ended" to frontend

If NO BLOCKERS found, proceed with implementation:

---

IMPLEMENTATION TASK:

Manage turn state progression and actor switching.

Requirements:
- Add function `get_current_actor(campaign_id)` → returns current_actor_id from active_combat
- Add function `advance_turn(campaign_id)`:
  1. Increment current_actor_index
  2. If index >= len(turn_order): reset to 0, increment turn_number
  3. UPDATE active_combat SET current_actor_id=turn_order[current_actor_index], current_actor_index, turn_number
  4. Return new current_actor_id

- Add function `is_combat_active(campaign_id)` → checks if active_combat row exists

Files to modify:
- `backend/app/services/combat_service.py` (add turn management functions)

Acceptance criteria:
- [ ] Can query current actor
- [ ] Turn advances correctly
- [ ] Turn wraps around to start of turn_order
- [ ] Turn number increments when full round completes
- [ ] Test: simulate 3 turns, verify turn_number and current_actor_id
- [ ] No race conditions (use DB transaction if needed)
```

---

## 📋 ETAP 4: Combat Mechanics (Attack Resolution)

### **Step 4.1: Attack Resolution — Player Turn**

**Zależności:** Step 3.2 (turn management), combat_resolver_example.py

**Cursor Prompt:**
```
SAFETY CHECK FIRST:

Before implementing, please analyze:
1. Check if player input during combat needs special routing (combat mode vs narrative mode)
2. Verify if weapon data is available (player's equipped weapon from inventory or character sheet)
3. Check if existing dice roll system (Phase 7) can be reused for attack rolls
4. Identify where to inject attack results for GM narration
5. Check if roll cards UI from Phase 7.8 can display combat rolls

If NO BLOCKERS found, proceed with implementation:

---

IMPLEMENTATION TASK:

Implement player attack resolution with extensible damage/defense formulas.

Reference: combat_resolver_example.py — functions calculate_damage() and calculate_defense()

Requirements:
- When player turn and player inputs attack action:
  1. Hit check: d20 + attack_bonus (from weapon/stats) vs enemy AC
  2. If miss → return outcome, advance turn
  3. Dodge check: enemy rolls d20 + DEX mod vs DC
  4. If dodge → return outcome, advance turn
  5. Damage roll: use calculate_damage() with PLACEHOLDERS (from .py example)
  6. Defense roll: use calculate_defense() for enemy
  7. Final damage: max(0, damage_total - defense_total)
  8. Update enemy hp_current in combatants JSON
  9. Store all rolls in roll_history
  10. Pass roll results to GM for narration
  11. Advance turn if enemy still alive

Files to modify:
- `backend/app/services/combat_service.py` (add resolve_player_attack function)
- Copy formula structure from combat_resolver_example.py

Acceptance criteria:
- [ ] Hit/miss detection works
- [ ] Dodge mechanic works
- [ ] Damage calculated with placeholder structure
- [ ] Defense calculated with placeholder structure
- [ ] Enemy HP updated in combatants JSON
- [ ] Roll history updated
- [ ] Test: player attacks, enemy HP decreases
- [ ] Test: enemy dodges, HP unchanged
- [ ] Test: miss, HP unchanged
- [ ] Placeholders all set to 0 initially (skill_bonus, armor_value, etc.)
```

---

### **Step 4.2: Attack Resolution — Enemy Turn**

**Zależności:** Step 4.1 (player attack works)

**Cursor Prompt:**
```
SAFETY CHECK FIRST:

Before implementing, please analyze:
1. Check if enemy turn should auto-trigger or require user input (Design: Opcja B = button)
2. Verify if GM should narrate enemy attack or just show mechanics
3. Check if player HP update affects any other systems (death detection?)
4. Identify where to check for player death (HP <= 0)

If NO BLOCKERS found, proceed with implementation:

---

IMPLEMENTATION TASK:

Implement enemy attack resolution (mirror of player attack).

Requirements:
- When enemy turn (current_actor_id starts with "enemy_"):
  1. Use same flow as player attack BUT reversed:
     - Attacker = enemy from combatants JSON
     - Defender = player from combatants JSON
  2. Hit check: d20 + enemy.attack_bonus vs player AC
  3. Dodge check: player d20 + DEX mod vs DC
  4. Damage: enemy damage_die + damage_bonus + stat_modifier (use placeholder formula)
  5. Defense: player d20 + CON mod + armor_value (placeholder)
  6. Final damage → update player hp_current
  7. Store rolls in roll_history
  8. Pass to GM for narration
  9. Check if player HP <= 0 → trigger death flow (Step 6.2)
  10. Advance turn if player alive

Files to modify:
- `backend/app/services/combat_service.py` (add resolve_enemy_attack function)
- Reuse calculate_damage/defense from Step 4.1

Acceptance criteria:
- [ ] Enemy attacks player correctly
- [ ] Player HP decreases
- [ ] Death detected when HP <= 0
- [ ] Roll history updated
- [ ] Test: enemy attacks, player HP decreases
- [ ] Test: player death triggers correctly (HP <= 0)
```

---

## 📋 ETAP 5: Combat UI (Enemy Turn Trigger)

### **Step 5.1: Enemy Turn Button (Opcja B)**

**Zależności:** Step 4.2 (enemy attack resolver exists)

**Cursor Prompt:**
```
SAFETY CHECK FIRST:

Before implementing, please analyze:
1. Check where chat messages are appended in frontend (likely ui.js or similar)
2. Verify if there's an API endpoint to trigger enemy turn (/api/combat/enemy-turn ?)
3. Check if button styling matches existing UI design
4. Identify if there's risk of multiple button clicks (debounce needed?)

If NO BLOCKERS found, proceed with implementation:

---

IMPLEMENTATION TASK:

Add "Enemy Turn" button in chat after player's turn ends.

Requirements:

**Backend:**
- Create endpoint: POST /api/combat/enemy-turn
  - Verify combat is active
  - Verify current actor is enemy
  - Call resolve_enemy_attack()
  - Return: {rolls: [...], narration: "...", combat_status: "ongoing"|"ended"}

**Frontend:**
- After player action completes:
  1. Check if combat_active AND current_actor != "player"
  2. Show button: "⚔️ Tura wroga (kliknij aby kontynuować)"
  3. On click: POST /api/combat/enemy-turn
  4. Remove button, show loading indicator
  5. Display enemy attack results (roll cards + GM narration)

Files to modify:
- `backend/app/api/routes.py` (add /api/combat/enemy-turn endpoint)
- `frontend/js/ui.js` or `actions.js` (add button rendering logic)

Acceptance criteria:
- [ ] Button appears after player turn
- [ ] Button disappears after enemy turn completes
- [ ] Only one button shown at a time (no duplicates)
- [ ] Debounce prevents double-clicks
- [ ] Test: complete full combat round (player → button → enemy → player)
```

---

## 📋 ETAP 6: Combat End Conditions

### **Step 6.1: Enemy Death + Loot Generation**

**Zależności:** Step 4.1 (enemy HP tracking)

**Cursor Prompt:**
```
SAFETY CHECK FIRST:

Before implementing, please analyze:
1. Check if loot table system exists (table: game_config_loot_tables, game_config_loot_entries)
2. Verify if enemy records have loot_table_key and drop_chance fields
3. Check if there's existing inventory system to add loot to
4. Identify where to store generated loot before player collects it

If NO BLOCKERS found, proceed with implementation:

---

IMPLEMENTATION TASK:

Detect enemy death, generate loot, update combat state.

Requirements:
- After any attack, check all enemies in combatants:
  1. If enemy.hp_current <= 0:
     - Mark enemy as dead (set flag in combatants JSON)
     - Roll drop chance (random 0-1 vs enemy.drop_chance)
     - If dropped: query loot table, roll weighted items
     - Add rolled loot to active_combat.loot_pool JSON
     - Short GM narration: "Gladiator pada..."
  2. If ALL enemies dead:
     - UPDATE active_combat SET phase='victory'
     - Return {combat_status: 'victory', loot_available: true}

Files to modify:
- `backend/app/services/combat_service.py` (add check_enemy_death function)
- `backend/app/services/loot_service.py` (if loot system needs separate module)

Acceptance criteria:
- [ ] Enemy death detected when HP <= 0
- [ ] Loot rolled based on drop_chance
- [ ] Loot stored in loot_pool JSON
- [ ] Combat phase changes to 'victory' when all enemies dead
- [ ] Test: kill enemy, verify loot generated
- [ ] Test: multiple enemies, verify all deaths detected
```

---

### **Step 6.2: Player Death + Death Screen Integration**

**Zależności:** Step 4.2 (player HP tracking), existing solo_death_service.py

**Cursor Prompt:**
```
SAFETY CHECK FIRST:

Before implementing, please analyze:
1. Check how solo_death_service.py currently works
2. Verify if death screen UI exists (from Phase 7.6)
3. Check if player death during combat needs different handling than narrative death
4. Identify if character.is_dead flag is set correctly

If NO BLOCKERS found, proceed with implementation:

---

IMPLEMENTATION TASK:

Integrate combat death with existing death system.

Requirements:
- After enemy attack, check player HP:
  1. If player.hp_current <= 0:
     - Call solo_death_service.trigger_death(campaign_id, cause="combat", enemy_name=enemy.label)
     - UPDATE active_combat SET phase='defeat'
     - Return: {combat_status: 'defeat', death_screen: true, defeated_by: enemy.label}

**Frontend:**
- If response.death_screen == true:
  - Show death screen (existing UI from Phase 7.6)
  - Display: "Poległeś w walce z: [enemy.label]"
  - Show character secret (from sheet_json.identity.secret)
  - Button: "Start New Character"

Files to modify:
- `backend/app/services/combat_service.py` (check_player_death function)
- `frontend/js/death_screen.js` (extend to show defeated_by info)

Acceptance criteria:
- [ ] Player death detected when HP <= 0
- [ ] solo_death_service called correctly
- [ ] Death screen shows with enemy name
- [ ] Character secret revealed
- [ ] Combat state cleaned up (DELETE or mark phase='defeat')
- [ ] Test: let enemy kill player, verify death screen appears
```

---

## 📋 ETAP 7: Victory Flow (Loot Collection UI)

### **Step 7.1: Victory Screen + Loot Popup**

**Zależności:** Step 6.1 (loot generation)

**Cursor Prompt:**
```
SAFETY CHECK FIRST:

Before implementing, please analyze:
1. Check if there's existing modal/popup system in frontend
2. Verify if inventory system can accept new items
3. Check how items are stored in character inventory (DB structure)
4. Identify if loot can be partially collected (or must take all at once)

If NO BLOCKERS found, proceed with implementation:

---

IMPLEMENTATION TASK:

Create loot collection UI after victory.

Requirements:

**Backend:**
- Endpoint: GET /api/combat/loot
  - Return: {items: [...], weapons: [...], consumables: [...]} from active_combat.loot_pool
- Endpoint: POST /api/combat/loot/collect
  - Body: {selected_items: [item_ids]}
  - Add selected items to character inventory
  - Mark items as collected in loot_pool OR remove from pool
  - UPDATE active_combat SET loot_collected=1 if all collected

**Frontend:**
- After combat_status='victory':
  1. Show central button/card: "🔍 Przeszukaj pokonanych"
  2. On click: open modal with loot list
  3. Player selects items (checkboxes)
  4. Button: "Zabierz wybrane"
  5. POST /api/combat/loot/collect with selected items
  6. Update inventory UI
  7. Allow re-opening modal until location changes (tracked separately)

Files to modify:
- `backend/app/api/routes.py` (add loot endpoints)
- `frontend/js/loot_popup.js` (new file or extend existing modal system)
- `frontend/css/` (style loot popup)

Acceptance criteria:
- [ ] Loot button appears after victory
- [ ] Modal shows all available loot
- [ ] Can select items individually
- [ ] Selected items added to inventory
- [ ] Can re-open modal to collect more
- [ ] Test: kill enemy, collect loot, verify inventory updated
- [ ] Test: partial collection works (leave some items)
```

---

## 📋 ETAP 8: Integration & Testing

### **Step 8.1: End-to-End Combat Flow Test**

**Zależności:** ALL previous steps

**Cursor Prompt:**
```
SAFETY CHECK FIRST:

Before declaring Phase 8A complete, please verify:
1. Run through FULL combat scenario: initiation → initiative → player attack → enemy attack → victory
2. Check logs for any errors during combat flow
3. Verify DB state after combat ends (active_combat cleaned up?)
4. Check if F5 (page refresh) during combat preserves state correctly
5. Verify roll cards display correctly for all combat rolls

If ANY ISSUES found, list them with steps to reproduce.

---

TESTING TASK:

Execute full combat test suite.

Test scenarios:
1. **Happy path — player wins:**
   - Start combat with weak enemy (bandit)
   - Player attacks and hits
   - Enemy attacks and misses
   - Player kills enemy
   - Verify loot popup
   - Collect loot
   - Verify inventory updated

2. **Player death:**
   - Start combat with strong enemy (assassin)
   - Let enemy attack multiple times
   - Verify death screen triggers when HP <= 0
   - Verify character marked as dead in DB

3. **F5 resilience:**
   - Start combat
   - Complete initiative
   - Before first attack: F5 page
   - Verify combat state restored (turn order, HP, etc.)
   - Continue combat normally

4. **Multiple enemies (if implemented):**
   - Start combat with 2+ enemies
   - Verify turn order includes all
   - Kill enemies one by one
   - Verify victory only after ALL dead

5. **Edge cases:**
   - Invalid enemy key in [COMBAT_START:invalid]
   - Double-click enemy turn button
   - Zero damage (perfect defense roll)
   - Exact HP = 0 (not negative)

Acceptance criteria:
- [ ] All test scenarios pass
- [ ] No errors in backend logs
- [ ] No errors in browser console
- [ ] DB state consistent after each scenario
- [ ] Roll cards display correctly
- [ ] Death screen works
- [ ] Loot system works
- [ ] Inventory updates correctly

Files to check:
- Backend logs (docker logs or console)
- Browser console (F12)
- Database: active_combat, characters, inventory tables
```

---

## 📋 FINAL CHECKLIST

Before marking Phase 8A as complete:

- [ ] All 8 steps implemented
- [ ] All acceptance criteria met
- [ ] All test scenarios pass
- [ ] Documentation updated (Notion page, code comments)
- [ ] No regression in existing features (narrative mode, rolls, character sheet)
- [ ] Git branch `phase-8-combat-system` ready for merge
- [ ] Code reviewed (or self-reviewed if solo)
- [ ] Migration scripts included in repo
- [ ] Example combat scenario documented for Phase 8B (frontend polish)

---

## 🚀 Ready for Phase 8B: Combat Frontend Polish

After Phase 8A completion, Phase 8B will add:
- Animated roll cards for combat
- Health bars (player + enemy)
- Combat log sidebar
- Turn indicator ("Your turn" / "Enemy turn")
- Damage numbers animation
- SSE streaming for narration (if Phase 12 earlier)
