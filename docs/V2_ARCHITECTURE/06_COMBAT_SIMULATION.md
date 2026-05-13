# AI-GM V2 — Full Combat Simulation

> Complete data flow trace for 4 combat scenarios. Shows exactly what comes from DB, what the system resolves mechanically, and what the LLM does. Use this as a verification reference and as a guide when implementing Phase 05 tasks.

---

## Character & Enemy Setup

### Warrior: Aldric (Level 2)
```
FROM DB (characters.sheet_json):
  STR 14 (+2) | DEX 12 (+1) | CON 12 (+1) | INT 10 | WIS 11 | CHA 10
  HP: 12    (base 10 + CON_mod +1 × level 2)
  AC: 14    (chain mail: ac_bonus 4 + base 10)
  Weapon: Sword — damage d8
  ATK total: d20 + STR(+2) + Combat_skill(3) + proficiency(+2) = d20+7
  Zone default: ENGAGED
```

### Scholar: Mira (Level 2)
```
FROM DB (characters.sheet_json):
  STR 10 | DEX 11 | CON 10 | INT 14 (+2) | WIS 11 | CHA 10
  HP: 6     (base 6 + CON_mod 0 × level 2)
  Mana: 14  (8 + INT_mod +2 × 3)
  AC: 10    (no armour)
  Spells: Magic Bolt R1 (2d6+INT, 2M), Mend Wounds R1 (2d6+INT, 2M), Arcane Shield R1 (+3AC 1rnd, 2M)
  Spell ATK: d20 + INT_mod(+2)
  Spell DC: 10 + INT_mod(+2) = 12
  Zone default: RANGED
```

### Enemy: Goblin Scout
```
FROM DB (game_config_enemies — key: goblin_scout):
  hp: 12, ac_base: 11, dex_modifier: +1, tier: weak
  attack_bonus: +2, damage_dice: 1d6, damage_bonus: 1
  xp_reward: 10
  loot_table: {
    guaranteed: [{item_key:"gold_coins", qty_min:2, qty_max:6}],
    random: [{item_key:"sword_rusty", chance:0.30}]
  }
  behavior_profile_key: "goblin_standard"
  fear_aura: false

FROM DB (enemy_behavior_profiles — goblin_standard):
  default_action: "attack_player"
  hp_threshold_flee: 0.25    ← flees at or below 25% HP (3 HP)
  special_ability_key: "throw_rock"
  special_ability_cooldown_turns: 3
  dialogue_on_aggro: "Goblin warczy i wyciąga zakrzywiony nóż."
  dialogue_on_death: "Goblin pada z cichym świstem."
```

### Enemy: Goblin Archer
```
FROM DB (game_config_enemies — key: goblin_archer):
  hp: 8, ac_base: 10, dex_modifier: +2, tier: weak
  attack_bonus: +3, damage_dice: 1d6, damage_bonus: 0
  behavior_profile: attack_from_ranged (stays RANGED zone, uses bow)
  default_zone: RANGED
  special_ability: "aimed_shot" (ATK+1, DMG+1d4, cooldown 3)
```

---

## SIMULATION A: Warrior vs 1 Goblin Scout

### A1 — Combat Initiation

```
GM text streamed to player includes: [COMBAT_START:goblin_scout]
         ↓
⚙️ SYSTEM: regex detects tag
📦 FROM DB: game_config_enemies WHERE key='goblin_scout'
📦 FROM DB: enemy_behavior_profiles WHERE enemy_key='goblin_scout'
📦 FROM DB: current location → combat_location_id = thornwood_forest
         ↓
⚙️ init_combat():
  Create active_combat record
  Store combat_location_id for loot expiry tracking
         ↓
⚙️ INITIATIVE (d20 + DEX modifier):
  Aldric:       roll 11 + DEX(+1) = 12
  Goblin Scout: roll  7 + DEX(+1) =  8
  Order locked: Aldric(12) → Goblin(8)
  Tie rule: player always wins ties
         ↓
⚙️ ZONE ASSIGNMENT:
  Aldric:  ENGAGED (Warrior default)
  Goblin:  ENGAGED (melee enemy default)
         ↓
⚙️ active_combat stored in DB:
  {status:"active", round:1, combat_location_id:"thornwood_forest",
   combatants:[
     {key:"player", hp:12, max_hp:12, ac:14, zone:"ENGAGED", initiative:12},
     {key:"goblin_scout_1", hp:12, max_hp:12, ac:11, zone:"ENGAGED", initiative:8,
      ability_cooldown_remaining:0}
   ], current_actor:"player"}
```

🤖 LLM narrates `dialogue_on_aggro` as combat opening flavour.

Frontend: combat panel opens, initiative order shown, buttons [⚔ Attack] [🏃 Flee] [🧪 Item].

---

### A2 — Round 1: Aldric Attacks, Goblin Counter-Attacks

**Aldric's turn:**
```
Player clicks [⚔ Attack] → structured input, skips Intent Parser

⚙️ WSM validates:
  state=COMBAT ✓ | target alive ✓ | sword (melee) vs goblin (ENGAGED) ✓

⚙️ Roll Popup:
  FROM DB: STR mod+2, Combat skill 3 → proficiency+2
  Shows: "Sword: d20+7"
  Player rolls → 8, total 8+7=15

⚙️ MECHANIC RESOLVER:
  Hit: 15 vs AC 11 → HIT ✓
  Crit: 15-11=4 → NOT crit (threshold 5)
  Damage: d8 roll 4 + STR(+2) = 6
  Goblin HP: 12-6 = 6
```

**Enemy auto-turn (immediately after, same response):**
```
⚙️ BEHAVIOR PROFILE CHECK:
  hp% = 6/12 = 50% → above flee threshold (25%) → no flee
  special_ability throw_rock: triggers only when goblin is RANGED → skip
  default_action: attack_player

⚙️ ENEMY ATK RESOLVER:
  Roll: d20+2 = 12+2=14 vs Aldric AC 14 → HIT (meets AC = hit)
  Damage: d6 roll 3 + 1 = 4
  Aldric HP: 12-4=8

⚙️ WOUND LABEL: 8/12 = 66% → "Hurt"
⚙️ ACTION LOG: written to DB (both actions, all rolls, all results)
```

🤖 LLM NARRATOR — receives full round mechanical facts, writes 4 sentences (2 per action):
> *"Miecz śmiga i trafia goblina w bok — ten odskakuje, lecz nie pada. Za karę zakrzywiony nóż orze w twoje ramię, ciepła krew spływa po łokciu. Goblin tańczy wokół ciebie, zwinny jak szczur w ścieku. Jesteś ranny, ale wciąż stoisz."*

---

### A3 — Round 2: Critical Hit

```
Player rolls → 16, total 16+7=23

⚙️ MECHANIC RESOLVER:
  Hit: 23 vs AC 11 → HIT ✓
  Crit: 23-11=12 > threshold 5 → CRITICAL HIT ✓
  
  📦 FROM DB: enemy.hit_location_table = "standard"
  Roll d6 → 5 = Right leg
  Effect on goblin: Hobbled (cannot flee for 3 rounds)
  Store: character_conditions {type:"hobbled", target:"goblin_scout_1", duration:3}
  
  Damage: d8 roll 5 + STR(+2) = 7, doubled = 14
  Goblin HP: 6-14 = -8 → DEAD

⚙️ ALL ENEMIES DEAD → VICTORY

⚙️ XP GRANT (system only):
  FROM DB: goblin xp_reward = 10
  INSERT character_xp_grants (amount=10, source="enemy_kill:goblin_scout")

⚙️ LOOT GENERATION (system only):
  FROM DB: goblin.loot_table
  Guaranteed: gold_coins roll d5+2 → 5 gold
  Random: sword_rusty chance 0.30 → roll 0.71 → NO drop
  CREATE combat_loot {location_id:"thornwood_forest", items:[{gold:5}], status:"available"}
```

🤖 LLM NARRATOR — receives: CRIT, right leg, Hobbled, 14 damage, goblin DEAD:
> *"Miecz opada jak topór kata — ląduje w kolano goblina z trzaskiem, który słyszysz zanim poczujesz opór. Goblin próbuje uciec, ale noga już go nie słucha. Przez chwilę patrzy na ciebie z niedowierzaniem, po czym po prostu się poddaje."*

Victory screen: loot popup [✓ 5 monet złota] | XP: +10

---

## SIMULATION B: Scholar (Mira) vs Goblin Scout

### B1 — Zone Difference at Initiation

```
⚙️ INITIATIVE:
  Mira:   roll 14 + DEX(0) = 14
  Goblin: roll  9 + DEX(+1) = 10

⚙️ ZONE ASSIGNMENT:
  Mira:   RANGED  ← Scholar default (KEY DIFFERENCE from Warrior)
  Goblin: ENGAGED ← melee enemy default
```

Frontend combat display:
```
RANGED              ENGAGED
────────────────────────────────
👤 Mira             ⚔️ Goblin Scout
```

---

### B2 — Round 1: Magic Bolt + Goblin Flee Attempt

**Mira's turn:**
```
Player clicks [✨ Atak Magiczny] → structured, skips Intent Parser

⚙️ WSM validates:
  state=COMBAT ✓ | spell=Magic Bolt R1 ✓
  Mana: 14 ≥ cost 2 ✓
  Magic Bolt range: ANY zone → goblin in ENGAGED zone ✓

⚙️ Roll Popup: "Magic Bolt: d20+2"
  Player rolls → 13, total 13+2=15

⚙️ SPELL RESOLVER:
  Hit: 15 vs AC 11 → HIT ✓
  Crit: 15-11=4 → NOT crit
  Nat 1: 13 ≠ 1 → no miscast
  Damage: 2d6+INT_mod(+2) = 3+4+2 = 9
  Goblin HP: 12-9 = 3
  Mana: 14-2 = 12
```

**Goblin auto-turn:**
```
⚙️ BEHAVIOR PROFILE CHECK:
  hp% = 3/12 = 25% → AT flee threshold (≤ 0.25) → FLEE ATTEMPT

  Flee roll (opposed DEX):
  Goblin: d20+DEX(+1) = 6+1 = 7
  Mira:   d20+DEX(0)  = 12+0 = 12
  Goblin total(7) < Mira total(12) → FLEE FAILS
  Goblin loses turn (failed flee = turn consumed)

  NOTE: Goblin is still ENGAGED, Mira still RANGED.
  Goblin cannot reach Mira with melee this round.
```

---

### B3 — Round 2: Arcane Shield + Throw Rock

**Goblin's turn (goes second in round 2, actually first since initiative is Mira 14, Goblin 10):**

Wait — Mira went first round 1. Round 2 same order: Mira first.

**Mira's turn:**
```
Player sees goblin at 3 HP, Mira at 6 HP. Decides on defence.
Player clicks [🛡 Arcane Shield]

⚙️ RESOLVER: no roll needed — automatic
  Apply condition: {type:"arcane_shield", ac_bonus:3, duration:1}
  Mira AC this round: 10+3 = 13
  Mana: 12-2 = 10 remaining
```

**Goblin's turn:**
```
⚙️ BEHAVIOR PROFILE CHECK:
  hp still 3, still at flee threshold
  Flee check this round: 8+1=9 vs Mira 5+0=5 → Goblin wins → GOBLIN FLEES

  Wait: goblin's throw_rock special ability — does it try that instead?
  Behavior priority: 1) flee threshold → flee. Even if goblin has special ability,
  flee takes priority when hp_threshold_flee condition is met.
  
  Flee roll: d20+1=11 vs d20+0=4 → Goblin(12) > Mira(4) → FLEE SUCCESS
  Combat ends: goblin escaped
  
  No XP (fled combat)
  combat_loot.status = "abandoned"
```

---

### B4 — Miscast Demonstration (Alternative Round 3)

*Hypothetical: Goblin failed to flee, combat continued.*

```
Mira casts Magic Bolt:
Player rolls → 1 ← NAT 1!

⚙️ MISCAST RESOLVER:
  FROM CHARACTER: Mira Level 2
  FROM DB (miscast table): Level 1-2 → stun only, NO HP damage
  
  Effects:
  - Spell fails (no damage to goblin)
  - Mana deducted: 10-2=8 remaining
  - Apply condition: {type:"stunned", duration:1} → Mira skips next action
  
  NOTE: if Mira were Level 3+, this would also deal 1d4 self-damage.
  Level scaling is key: 6 HP Scholar would be in danger from self-damage.
```

🤖 LLM NARRATOR (miscast):
> *"Zaklęcie wyrywa się spod kontroli — przez chwilę Mira stoi z rozłożonymi ramionami, oczy szeroko otwarte, ciało nie słucha poleceń. Goblin tego nie marnuje: odwraca się i znika w zaroślach z chichotem."*

**Design observation:** Scholar miscast caused goblin to escape. The lack of HP damage at low levels was intentional — but the stun cost Mira her action while the goblin fled. Fragile Scholar weakness vs resilient enemies is emergent and working correctly. ✓

---

## SIMULATION C: Warrior vs 3 Enemies

**Enemies:** Goblin Scout A, Goblin Scout B, Goblin Archer

### C1 — Initiation, 3-Way Initiative

```
[COMBAT_START:goblin_scout,goblin_scout,goblin_archer]

⚙️ SYSTEM: load 3 separate combatant slots from DB
  goblin_scout_A, goblin_scout_B: melee, zone=ENGAGED
  goblin_archer_1: ranged, zone=RANGED (different behavior!)

⚙️ INITIATIVE (all rolled once, locked for entire combat):
  Aldric:          roll 15 + DEX(+1) = 16
  Goblin Scout A:  roll  8 + DEX(+1) =  9
  Goblin Scout B:  roll 12 + DEX(+1) = 13
  Goblin Archer:   roll 18 + DEX(+2) = 20

  Order locked: Archer(20) → Aldric(16) → Scout B(13) → Scout A(9)
```

Frontend combat display:
```
RANGED              ENGAGED
────────────────────────────────────
🏹 Goblin Archer    ⚔️ Aldric
                    ⚔️ Goblin Scout A
                    ⚔️ Goblin Scout B

Initiative:
  1. 🏹 Archer  (20) ← CURRENT
  2. ⚔️ Aldric  (16)
  3. ⚔️ Scout B (13)
  4. ⚔️ Scout A  (9)
```

**Archer goes BEFORE the player!**

---

### C2 — Round 1: Archer Acts First

```
⚙️ ARCHER AUTO-TURN (before player gets to act):
  Behavior: attack_from_ranged → targets player
  FROM DB: bow (ranged) can hit ENGAGED targets from RANGED zone ✓
  ATK: d20+3 = 14+3=17 vs Aldric AC 14 → HIT
  Damage: d6=4+0=4
  Aldric HP: 12-4=8

  Now: Aldric's turn (already took an arrow)

Player clicks [⚔ Attack], selects Scout A (ENGAGED)

  Roll: 17+7=24 vs AC 11 → HIT
  Crit: 24-11=13 > 5 → CRITICAL HIT
  Location d6: 3 = Right arm → Disarmed (Scout A damage -2 for 3 turns)
  Damage: d8=6+2=8, doubled=16
  Scout A HP: 12-16=-4 → DEAD

⚙️ ALL REMAINING ENEMY TURNS AUTO-FIRE:

  Scout B (initiative 13):
  FROM DB behavior: default_action=attack_player, hp=12 → no flee
  ATK: d20+2=11+2=13 vs Aldric AC 14 → MISS

  Scout A (initiative 9): DEAD → skip

⚙️ FULL ROUND RESULT assembled, all in ONE response:
  Action 1: Archer → Aldric: HIT, 4 dmg
  Action 2: Aldric → Scout A: CRIT, 16 dmg, DEAD
  Action 3: Scout B → Aldric: MISS
  State: Aldric 8HP | Scout B 12HP | Archer 8HP
```

🤖 LLM narrates all 3 actions in sequence (1 call, 4-6 sentences total).

Frontend animates sequentially with 800ms delay between each action.

---

### C3 — Round 2: Archer Special Ability + Player Uses Potion

```
⚙️ ARCHER AUTO-TURN:
  Check special ability: aimed_shot cooldown=0 → AVAILABLE
  Aimed shot: ATK+1 bonus, +1d4 damage on hit
  ATK: d20+4=16+4=20 vs AC 14 → HIT
  Damage: d6=3 + aimed_shot d4=2 = 5
  Aldric HP: 8-5=3
  Cooldown set: aimed_shot_cooldown=3

⚙️ WOUND LABEL: 3/12=25% → "Severely Wounded"

Player sees: 3 HP, two enemies remaining. Decides to heal.
Player clicks [🧪 Item] → selects Healing Potion

⚙️ ITEM RESOLVER:
  FROM DB (inventory): healing_potion qty=1 → consume 1
  Heal: d8 roll 5 + CON_mod(+1) = 6 HP
  Aldric HP: 3+6=9 (max 12, not exceeded)
  Player turn SPENT — no attack this round

⚙️ SCOUT B AUTO-TURN:
  ATK: 8+2=10 vs AC 14 → MISS

  Full round: Archer HIT(5) | Aldric healed(+6) | Scout B MISS
  State: Aldric 9HP | Scout B 12HP | Archer 8HP
```

---

### C4 — Round 3-5: Zone Mechanics — Closing with Archer

```
Rounds 3: Aldric kills Scout B (roll 19+7=26, crit, head wound, stunned, dead)

Round 4: only Archer remains (RANGED). Aldric is ENGAGED.
  Archer ATK: HIT for 2 damage. Aldric 7HP.
  Aldric attacks Archer:
    Sword (melee) targeting RANGED enemy → BLOCKED by WSM
    Frontend: [⚔ Attack] button greyed → tooltip "Enemy out of melee range"

  Player types: "Rzucam się na łucznika przez zarośla"

  ⚙️ INTENT PARSER (LLM call #1):
    Input: free text + state=COMBAT
    Output: [ACTION:MOVEMENT:destination=ranged_zone]

  ⚙️ WSM: MOVEMENT in COMBAT = valid, costs player's attack turn
    Result: Aldric moves to Archer's zone → both now ENGAGED
    No attack this round.

Round 5: Aldric now ENGAGED with Archer
  Archer ATK (bow in ENGAGED): d20+3=9+3=12 vs AC 14 → MISS (bow penalty -2 applied? 
    Actually: bow penalty: -2 to attack if attacker is ENGAGED, from our rules.
    Archer in ENGAGED: bow ATK+3 - 2 = +1. Roll 9+1=10 vs AC 14 → MISS)
  
  Aldric ATK (melee, both ENGAGED): roll 11+7=18 vs AC 10 → HIT
  Crit: 18-10=8 > 5 → CRIT
  Location d6: 6=Left leg → Hobbled
  Damage: d6=3+2=5, doubled=10
  Archer HP: 8-10=-2 → DEAD

VICTORY — all 3 enemies defeated.

⚙️ XP: 10+10+10=30 total
⚙️ LOOT: each loot_table resolved separately, pool merged:
  Scout A: 4 gold (guaranteed)
  Scout B: 3 gold + sword_rusty (roll 0.22 < 0.30 → YES)
  Archer: 3 gold + arrow_bundle (roll 0.45 > 0.30 → NO)
  Final: 10 gold + 1 sword_rusty
```

---

## SIMULATION D: Fear Trigger (Vampire Entry)

```
[COMBAT_START:vampire_lord] detected in GM narrative

📦 FROM DB (game_config_enemies — vampire_lord):
  fear_aura: true
  fear_dc: 16
  tier: elite, hp:45, ac:16

⚙️ FEAR AURA DETECTED — before initiative:
  WSM transitions to FEAR_TEST_PENDING state

Frontend: Fear Test popup (darker styling):
  "Oblicze nieśmiertelnego jest jak maska śmierci."
  "Test Strachu — Mądrość (DC 16)"
  Shows WIS modifier: Aldric WIS 11 → mod 0
  [Rzuć k20 — walcz ze strachem]

Player rolls → 11, total 11+0=11 vs DC 16 → FAIL

⚙️ CONDITION APPLIED:
  character_conditions: {type:"frightened", severity:1, expires_at:current_turn+2}

⚙️ FRIGHTENED effects:
  Valid actions: ATTACK, FLEE only
  Blocked: ITEM_USE, MOVEMENT, SKILL_ATTEMPT
  Frontend: [🧪 Item] greyed, [← Step back] greyed

Combat now proceeds normally. Aldric can fight but is restricted.

IF Aldric rolls Nat 1 on any action while FRIGHTENED:
  → Re-roll fear vs same DC → could escalate to TERROR
  TERROR fail → PANICKED: {skip_next_turn:true, frightened_after:2}
  TERROR Nat 1 → BREAK: must flee, cannot re-enter this combat
```

---

## Issues Found During Simulation

| # | Issue | Severity | Fix Needed |
|---|-------|---------|------------|
| I1 | Zone clarification: "Close in" must explicitly make player ENGAGED with the target enemy, not just move to a generic RANGED zone | **Important** | Update TASK_14: MOVEMENT:ranged_zone = move to target enemy's position, become ENGAGED with them |
| I2 | Flee threshold: ≤ 0.25 means exactly 25% HP triggers flee. Confirm this is ≤ not < | Minor | Document in TASK_15 as "at or below threshold" |
| I3 | Scholar miscast (stun) → goblin escaped. Valid emergent outcome but frustrating. Consider: stunned Scholar should still block goblin's flee attempt? | Design choice | No change — fragile Scholar losing to goblin via bad luck is correct grim dark feel |
| I4 | Multiple enemy loot: each enemy's random drops roll separately, guaranteed drops combined | **Important** | Document merge rule in TASK_22: guaranteed pool combined, each random item rolled per enemy |
| I5 | Item use = full turn (no attack). Enemy auto-turns fire after. Confirm intentional | Confirm | Yes, intended — this is D&D/WFRP standard |
| I6 | [Attack] button must grey with tooltip when enemy is out of range (RANGED enemy, player ENGAGED) | UX | Add to TASK_34 combat UI: greyed button + "Out of melee range — close in first" tooltip |
| I7 | Archer going before player (initiative 20 > 16) means player takes damage before first action. Working correctly but may feel unfair | Design | Correct — initiative can go against player. Good tension. |
| I8 | Bow penalty when attacker is ENGAGED: need to clarify it's the ATTACKER'S zone that determines penalty, not the target's | Clarification | Update TASK_14 range rules table: penalty applies when the ATTACKER is in ENGAGED zone using a ranged weapon |

---

## Data Source Summary

| Data | Source |
|------|--------|
| Enemy stats (HP, AC, DEX, ATK, DMG) | `game_config_enemies` DB |
| Enemy behavior (flee %, special ability, dialogue) | `enemy_behavior_profiles` DB |
| Enemy loot table | `game_config_enemies.loot_table` JSON |
| Character stats and skills | `characters.sheet_json` |
| Weapon damage dice | `game_config_items` DB (or sheet_json.equipment) |
| Initiative order | System: d20 + DEX mod per combatant |
| Hit/miss calculation | System: player roll + modifiers vs AC |
| Critical hit detection | System: total - AC ≥ threshold |
| Hit location | System: d6 + `game_config_enemies.hit_location_table` |
| Damage calculation | System: dice + modifiers, ×2 if crit |
| Condition application | System: writes to `character_conditions` |
| Fear trigger detection | System: reads `enemy.fear_aura` flag |
| Fear save DC | `game_config_enemies.fear_dc` DB |
| Enemy special ability trigger | System: reads behavior profile cooldown + trigger condition |
| XP grant | System: reads `enemy.xp_reward`, writes to `character_xp_grants` |
| Loot generation | System: resolves `enemy.loot_table`, writes to `combat_loot` |
| All Polish narration | LLM — receives completed mechanical facts |
| Intent parsing (free text) | LLM — converts to ACTION tag |
| NPC dialogue | LLM — within DB personality constraints |

**LLM called N times per combat round = 1 (narration). Plus 1 extra for intent parser if player uses free text.**
Zero game outcomes decided by LLM.
