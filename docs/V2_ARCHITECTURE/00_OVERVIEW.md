# AI-GM V2 — Architecture Overview!

> **Core principle:** The system controls the world. The LLM describes it.

---

## The Paradigm Shift

### V1 (old): LLM as Game Master

```
Player input → LLM decides what happens → LLM narrates it
```

Problems: LLM hallucinates facts, invents NPCs/stats, inconsistent world state, 
unreliable tag emission, no guarantee of mechanical fairness.

### V2 (new): System as Game Master, LLM as Narrator

```
Player input → Intent Parser → World State Machine → Mechanic Resolver
                                                            ↓
                                              Context Injector → LLM Narrator → Polish prose
```

The LLM has two jobs only: **parse intent** and **narrate outcomes**. 
It never decides what happens. The system decides. The LLM describes.

---

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│                        PLAYER INPUT                          │
│   Free text OR contextual button (Attack / Flee / Rest ...)  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                    ┌───────▼────────┐
                    │ INTENT PARSER  │  (LLM job #1)
                    │                │  Converts text → structured
                    │ "I sneak past" │  ACTION tag
                    │ → STEALTH_ATTEMPT│ Or: button click → direct tag
                    └───────┬────────┘
                            │
              ┌─────────────▼──────────────┐
              │     WORLD STATE MACHINE    │
              │                            │
              │  Validates action against  │
              │  current world state:      │
              │  - Is player in this loc?  │
              │  - Does target exist?      │
              │  - Is action possible?     │
              └─────────────┬──────────────┘
                            │
     ┌──────────────────────▼─────────────────────────┐
     │              DB (SOURCE OF TRUTH)               │
     │                                                  │
     │  game_locations  │  npc_definitions             │
     │  game_config_enemies │ game_config_items        │
     │  characters      │  campaigns (plan)            │
     │  active_combat   │  game_sessions               │
     └──────────────────────┬─────────────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │    MECHANIC RESOLVER       │
              │                            │
              │  Rolls dice, resolves:     │
              │  - Skill tests (d20+mod)   │
              │  - Combat (ATK/DMG/AC)     │
              │  - Fear tests              │
              │  - Death saves             │
              │  Returns: mechanical facts │
              └─────────────┬──────────────┘
                            │
              ┌─────────────▼──────────────┐
              │    CONTEXT INJECTOR        │
              │                            │
              │  Builds LLM prompt from:  │
              │  - Location record         │
              │  - NPC personality data    │
              │  - Mechanical result       │
              │  - Campaign plan state     │
              │  - Wound label             │
              │  - Fear state              │
              └─────────────┬──────────────┘
                            │
                    ┌───────▼────────┐
                    │ LLM NARRATOR   │  (LLM job #2)
                    │                │  Receives: mechanical facts
                    │                │  Returns: Polish prose only
                    │                │  Never decides outcomes
                    └───────┬────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                      PLAYER OUTPUT                           │
│  Vivid Polish narrative + updated UI state (HP, location...) │
└─────────────────────────────────────────────────────────────┘
```

---

## The LLM's Two Jobs

### Job 1 — Intent Parser

**Input:** Free text player action  
**Output:** Structured ACTION tag  
**Constraints:**

- If intent is clear → emit one ACTION tag
- If ambiguous → emit CLARIFY request (system asks player)
- If impossible in current state → emit BLOCKED (system explains)
- Button clicks bypass this step entirely (already structured)

```
Example inputs → outputs:
"I try to sneak past the guard"  → [ACTION:STEALTH_ATTEMPT:target=guard_1]
"I attack the goblin with my sword" → [ACTION:ATTACK:target=goblin_1:weapon=sword]
"I talk to the innkeeper about the murders" → [ACTION:DIALOGUE:npc=innkeeper_key:topic=murders]
"I run away" → [ACTION:FLEE]
"I look around the room for clues" → [ACTION:SEARCH:location=current:focus=clues]
"I put the crown in my bag" → [ACTION:ITEM_PICKUP:item=crown_item_key]
```

### Job 2 — Narrator

**Input:** Mechanical facts (outcome, rolls, HP, NPC personality, location description)  
**Output:** 2-4 sentences of vivid Polish dark fantasy prose  
**Constraints:**

- Never contradict the mechanical facts given
- Never invent world content not in the provided context
- Never decide additional outcomes beyond what was given
- Keep it short in combat, atmospheric in exploration, personal in dialogue

---

## Turn Processing Pipeline (Full)

```
1. RECEIVE player input (text or button action)

2. INTENT PARSING
   a. If button action → structured tag directly (skip LLM parsing)
   b. If free text → LLM Intent Parser → ACTION tag
   c. Unknown/impossible → system returns CLARIFY/BLOCKED message

3. WORLD STATE VALIDATION
   - Check: can this action happen in current state?
   - Location exists? NPC exists? Item exists? Not in combat?
   - If invalid → return system message explaining why

4. DB LOOKUP
   - Load all relevant records: target NPC, enemy stat block, item record
   - Load current location record + linked entities
   - Load campaign plan current state

5. MECHANIC RESOLUTION
   - Roll dice (server-side, not LLM)
   - Apply all modifiers from character sheet + conditions + equipment
   - Determine outcome: success/fail/crit/fumble
   - Check side effects: combat start, fear trigger, death save, item consumed

6. WORLD STATE UPDATE
   - Write new state to DB: HP, location, inventory, combat status
   - Update campaign plan if key beats/events occurred

7. CONTEXT INJECTION
   - Build narrator prompt with:
     * Location description (from DB)
     * NPC personality + must_reveal flags (from DB)
     * Mechanical result (from step 5)
     * Character wound label
     * Fear/Terror state if active
     * Campaign tone (grim dark)

8. LLM NARRATION
   - Single LLM call with structured context
   - Returns: Polish prose only
   - Strip any attempts to decide outcomes or invent world content

9. DELIVER to frontend
   - Prose narrative
   - Updated UI state (HP bar, location badge, inventory, combat panel)
```

---

## World Content Rules

**The DB is the only source of truth for game world facts.**

| Content type                               | Source                   | LLM can invent?          |
| ------------------------------------------ | ------------------------ | ------------------------ |
| Location names, descriptions, atmosphere   | `game_locations` DB      | No — must use DB record  |
| NPC names, personality, knowledge          | `npc_definitions` DB     | No — must use DB record  |
| Enemy stats, abilities, behavior           | `game_config_enemies` DB | No — must use DB record  |
| Item descriptions, effects                 | `game_config_items` DB   | No — must use DB record  |
| Dice roll outcomes                         | Mechanic Resolver        | No — mechanical          |
| Narrative prose (how things are described) | LLM Narrator             | Yes — this is its job    |
| NPC dialogue (within DB personality)       | LLM Narrator             | Yes — within constraints |

**When LLM needs content not in DB:** Emit `[CREATE_*]` tag. System creates DB record with `pending_review` status. Admin reviews and approves/rejects.

---

## Tone & World Design

**Dark Fantasy WFRP-inspired:**

- The world is dangerous, unfair, and morally grey
- Common people suffer; power corrupts
- Victories are often pyrrhic — solutions create new problems
- No chosen-one narratives — the player is a capable person in a hard world
- Death is possible and carries weight
- Horror elements: fear of the unknown, grotesque monsters, corruption

**D&D-clean mechanics:**

- 7 stats (STR, DEX, CON, INT, WIS, CHA, LCK) with simple modifiers
- d20 + modifier vs DC (no WFRP's complex advance system)
- Levels 1–10 (suggested cap)
- Two archetypes: Warrior, Scholar

**WFRP mechanical elements included:**

- Fear & Terror rolls for horrific encounters
- Critical hit location table (where the hit lands)
- Grim dark narrative tone enforced by LLM prompt
- Wounds have narrative weight (labels, not just HP numbers)

---

## Input Design: Hybrid

```
OUT OF COMBAT — narrative exploration:
┌────────────────────────────────────────────┐
│ 📍 Karczma Pod Złotym Pucharem             │
│                                            │
│ [GM narration here]                        │
│                                            │
│ Context buttons (smart, change by scene):  │
│ [🗣 Talk to Heinz] [🔍 Search room]        │
│ [💤 Rest] [🚪 Leave tavern]               │
│                                            │
│ Or type anything: [_________________] →   │
└────────────────────────────────────────────┘

IN COMBAT:
┌────────────────────────────────────────────┐
│ ⚔ COMBAT — Goblin Scout (HP 8/12)         │
│ Round 2 | Your turn                        │
│                                            │
│ [⚔ Attack] [🏃 Flee] [🧪 Use Item]       │
│                                            │
│ Or describe your action: [___________] →  │
└────────────────────────────────────────────┘
```

Context buttons are generated by the system based on: current location's available NPCs, available exits, and game state. They don't replace free text — they accelerate common actions.

---

## Campaign Structure

**Generation:** LLM creates a structured campaign plan from character data (bonds, weaknesses, secret predisposition) + sampled content from the Ideas Bank.

**Ideas Bank:** A curated library of scenario seeds and scene modules, built collaboratively by admin + AI Workshop agent. The LLM draws from this bank as raw material — producing campaigns that improve over time as the bank grows.

**Plan schema:** Formal JSON with acts, endings, key NPCs (with importance flags), key locations, deviation tracker. System reads this schema directly — not through LLM interpretation.

---

## Hero Architecture (KEY — Inverted from V1)

**Heroes are the primary entity. Campaigns and adventures are assigned TO heroes.**

```
PLAYER
  └── Heroes (multiple allowed)
        ├── Aldric (Warrior, Level 3) [ACTIVE]
        │     └── Current adventure: "Zdrada pod Graustein"
        ├── Mira (Scholar, Level 1) [AT REST]
        │     └── No active adventure — visiting world map
        └── Bogdan (Warrior) [FALLEN]
              └── Legacy in world as NPC/lore
```

Rules: Hero has one active adventure at a time. Hero without active adventure is "at rest" (can spend XP, shop, explore map). Player can own and switch between multiple heroes.

---

## Conditions System

All game conditions (fear, wounds, poison, bleeding, blinded) have a fully specified lifecycle:

- Duration tracked in **combat rounds**
- Ongoing damage ticks at **end of each round**
- Stacking: **admin-configurable global switch** (off by default = refresh duration)

Full specification: `11_CONDITIONS_SYSTEM.md`

---

## New Systems vs V1

| System            | V1                        | V2                                                         |
| ----------------- | ------------------------- | ---------------------------------------------------------- |
| Player intent     | LLM decides how to handle | Intent Parser → structured tag                             |
| Enemy behavior    | LLM narrates + decides    | DB behavior profiles, rule-based                           |
| World content     | LLM invents freely        | DB first, CREATE tag for new                               |
| Combat resolution | Strict (mostly)           | Strict + crit table + fear + conditions                    |
| NPC dialogue      | LLM free-form             | LLM within DB personality + keyword triggers               |
| Campaign plan     | Unstructured JSON         | Formal schema, system-readable                             |
| Fear/Terror       | Not implemented           | Full mechanic (WIS test) → conditions                      |
| Critical hits     | Not implemented           | Hit location table + wound conditions                      |
| Input UX          | Free text only            | Hybrid: buttons + free text                                |
| Admin tools       | Basic CRUD                | Ideas Workshop + Smart Entry Agent (visual questionnaire)  |
| Hero model        | Campaign-centric          | **Hero-centric** (campaigns assigned to heroes)            |
| Conditions        | Not tracked               | Full lifecycle: apply/tick/clear (11_CONDITIONS_SYSTEM.md) |
