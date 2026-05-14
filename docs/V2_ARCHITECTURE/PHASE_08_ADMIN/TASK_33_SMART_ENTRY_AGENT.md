# TASK 33 — Smart Entry Agent (Universal AI-Assisted Admin Creation)

**Status:** ⚠️ Partially Done
**Phase:** 08 — Admin Tools
**Depends on:** Task 01 (DB Schema), all game_config tables seeded
**Unlocks:** Admins can create/edit world content via conversation instead of raw forms

---

## Implementation Status

**Built (Smart Entry v3 — form-first approach):**
- `GET /api/admin/smart-entry/schema?table=X` — field definitions used to render the right-pane form
- `GET /api/admin/smart-entry/list?table=X` — existing records for the "load existing" dropdown
- `GET /api/admin/smart-entry/record?table=X&key=Y` — single record fetch for edit mode
- `POST /api/admin/smart-entry/message` — LLM fills all form fields in one shot (schema-constrained JSON output)
- `POST /api/admin/smart-entry/save` — INSERT (new) or UPDATE (edit) mode
- Effect Builder UI: visual card-based editor for `effect_json` field on weapons (no raw JSON needed)
- LLM always generates description and note fields; auto-slug derived from label
- Load existing record from dropdown enables edit/UPDATE mode
- Tables supported: `game_config_weapons`, `game_config_items`, `game_config_consumables`, `game_config_enemies`

**Missing from spec:**
- Q&A visual questionnaire mode (spec wants one decision at a time with option cards; current implementation fills all fields at once)
- DB balance-check queries ("compare to existing similar weapons before suggesting values")
- Tables not yet supported: `game_config_conditions`, `game_config_skills`, `game_config_archetypes`
- Q&A mode is tracked as a future improvement (to_do_ideas.md item #2); blocked until prioritised

---

## Overview

The Smart Entry Agent lets admin describe what they want to create or change in plain language. The agent:
1. Queries the DB to understand what already exists
2. Asks structured visual questions (option cards, not just text) to fill in required fields
3. Proposes a record (or change to existing record) for admin to approve
4. Saves on approval

It works for: `game_config_weapons`, `game_config_items`, `game_config_consumables`, `game_config_archetypes`, `game_config_enemies`, `game_config_conditions`, `game_config_skills`.

**Key design principle:** The agent asks questions the same way a good designer would — short, visual, one decision at a time. Admin describes the goal, agent handles the schema details.

---

## Design Context

### Why visual questionnaires, not just chat?

Pure chat agents tend to ask a wall of questions at once, then dump a JSON blob. The visual questionnaire approach:
- One question at a time with visual option cards
- Admin sees previews of what each choice means mechanically
- Much faster for non-technical admins
- Same experience as how the game design decisions were made in this project

### Why DB read access?

Before suggesting a new item, the agent should check:
- "Does a similar item already exist?" (prevent duplicates)
- "What's the strongest weapon of this type?" (inform balance)
- "What classes can use this?" (cross-check archetype rules)

Without this, the agent operates blind and produces inconsistent world content.

### Why update proposals, not just creation?

Admin often wants to say "make the goblin archer a bit weaker" or "increase the price of plate armor". This should be as easy as creation — describe the change, agent finds the record, proposes the diff, admin approves.

---

## Agent Architecture

### Single Endpoint

```
POST /api/admin/smart-entry/message
Body: {
  "session_id": "uuid",
  "table": "game_config_weapons",  -- optional, agent infers if not set
  "message": "I want a cursed sword that makes the warrior stronger but harder to control",
  "answer": null  -- or: {"question_id": "damage_die", "value": "d10"}
}

Response: {
  "reply": "Let me check existing cursed items first...",
  "questions": [...],         -- optional: structured visual questions
  "db_context": {...},        -- optional: what the agent found in DB (shown as info)
  "draft": {...},             -- optional: current record being built
  "proposed_changes": [...],  -- optional: changes to EXISTING records
  "ready_to_save": false,
  "save_table": null,         -- which table to save to when ready
  "save_key": null            -- null = new record, string = update existing
}
```

### Session State (server-side)

```python
{
  "session_id": "uuid",
  "table": "game_config_weapons",
  "history": [{"role": "user/agent", "content": "..."}],
  "draft": {},          # record being built
  "target_key": None,   # None = new record, string = editing existing
  "db_queries": [],     # queries already run this session
  "questions_asked": [] # which fields have been filled
}
```

Sessions stored in memory (or Redis), expire after 30 minutes inactivity.

---

## Visual Question Format

When the agent wants to ask a structured question, it includes a `questions` array in the response. The frontend renders each as an option card panel — exactly like the questionnaire format used in game design sessions.

```json
{
  "reply": "How hard should this sword hit?",
  "questions": [
    {
      "id": "damage_die",
      "type": "single_choice",
      "question": "What damage die?",
      "options": [
        {
          "label": "d8",
          "description": "Standard sword. Balanced, reliable.",
          "preview": "Sword tier: Standard\nAvg damage: 6.5 + STR\nComparable to: longsword"
        },
        {
          "label": "d10",
          "description": "Heavy weapon. High damage, slower feel.",
          "preview": "Sword tier: Heavy\nAvg damage: 8.5 + STR\nComparable to: battleaxe"
        },
        {
          "label": "d12",
          "description": "Two-handed. Maximum damage, no shield.",
          "preview": "Sword tier: Two-handed\nAvg damage: 10.5 + STR\ntwo_handed = true"
        }
      ]
    }
  ]
}
```

**Question types supported:**
- `single_choice` — pick one option card (most common)
- `multi_choice` — select multiple (e.g., "which classes can use this?")
- `number` — slider or number input with min/max/step
- `text` — free text for names, descriptions
- `boolean` — yes/no toggle

When admin answers a question, the answer is sent back as `"answer": {"question_id": "...", "value": "..."}` and the agent continues.

---

## DB Tools Available to Agent

The agent has access to these internal tools (not exposed to admin directly):

### `query_db(table, filters, limit)`
Read-only. Returns matching records.
```python
# Agent checks for existing cursed weapons
query_db("game_config_weapons", {"key__contains": "curse"}, limit=5)
query_db("game_config_weapons", {"weapon_type": "melee", "two_handed": False}, limit=20)
```

### `get_record(table, key)`
Get a single record by key.
```python
get_record("game_config_weapons", "longsword")
# Returns full longsword record for comparison
```

### `propose_update(table, key, changes, reason)`
Proposes a change to an EXISTING record. Does NOT save automatically.
```python
propose_update(
  "game_config_enemies", "goblin_archer",
  {"hp_base": 6, "ac_base": 9},  # was 8 and 10
  "Reducing goblin archer slightly — currently too strong for Act 1"
)
```
Returns a `proposed_changes` item in the response that admin sees and approves/rejects.

### `create_record(table, data)`
Creates a new record. Only called when `ready_to_save = true` and admin clicks confirm.
```python
create_record("game_config_weapons", {
  "key": "berserker_blade",
  "label": "Berserker's Blade",
  "damage_die": "d10",
  "linked_stat": "STR",
  ...
})
```

---

## Full Interaction Example

**Creating a new weapon:**

```
Admin: "I want a cursed sword that makes the warrior stronger but harder to control"
        ↓
Agent: [calls query_db("game_config_weapons", {"key__contains": "curse"})]
       [calls query_db("game_config_weapons", {"weapon_type": "melee"})]

Reply: "Checking existing cursed items... Found one: cursed_grimoire (Scholar spell focus, d8).
        No cursed melee weapons yet. Let me help you build one."

[Question 1 — visual card]
"How hard should it hit?"
  [d8 — Standard sword]  [d10 — Heavy weapon]  [d12 — Two-handed]

Admin selects: d10
        ↓
[Question 2 — visual card]
"What's the curse mechanic?"
  [STR +2 but DEX -2]    [Must attack nearest enemy (rage)]   [Gradual madness / corruption]

Admin selects: Must attack nearest enemy (rage)
        ↓
Reply: "Great. The 'rage' mechanic means I'll create a BLOODLUST condition that applies
        after the sword is used. Here's my proposal:"

[Draft preview]
  Key: berserker_blade
  Label: Berserker's Blade
  Damage: d10 + STR
  Type: Melee | Warrior only | Two-handed: No
  Special: On hit → apply BLOODLUST (2 rounds)
  
  BLOODLUST condition:
    +2 ATK, +2 DMG
    BUT: must target nearest enemy (no choice)
    Cannot flee while active

"Does this look right? You can ask me to change anything, or say 'save it'."

Admin: "Change the label to something more Polish sounding"
        ↓
Agent: [Asks question or suggests options]
"How about: 'Ostrze Berserkera', 'Miecz Szału', or 'Klinga Gniewu'?"

Admin: "Klinga Gniewu"
        ↓
Reply: "Updated. Ready to save:
  key: berserker_blade
  label: Klinga Gniewu
  ...
  [Final preview]"

Admin clicks [Save] → record created in game_config_weapons
              + BLOODLUST condition created in game_config_conditions
```

---

**Modifying an existing record:**

```
Admin: "The goblin archer feels too strong in early game, make it a bit weaker"
        ↓
Agent: [calls get_record("game_config_enemies", "goblin_archer")]
       
Reply: "Found goblin_archer: HP 8, AC 10, ATK +3, DMG d6, tier: weak.
        I agree it feels strong for a 'weak' tier enemy — ATK+3 is quite high.
        
        What should I reduce?"

[Question — visual card]
  [Lower HP (8→6)]    [Lower AC (10→8)]    [Lower ATK (+3→+1)]    [Both HP and ATK]

Admin selects: Both HP and ATK
        ↓
Agent: [calls propose_update("game_config_enemies", "goblin_archer",
        {"hp_base": 6, "attack_bonus": 1},
        "Reducing to better fit weak tier — HP 8→6, ATK +3→+1")]

Reply: "Proposed changes to goblin_archer:
  HP: 8 → 6  (-2)
  ATK: +3 → +1  (-2)
  
  [Approve] [Reject] [Adjust more]"

Admin clicks [Approve] → record updated in game_config_enemies
```

---

## Frontend Component

**Location:** Admin panel → any Zawartość/Mechaniki tab → `[🤖 Asystent]` button

Opens a split panel:
```
┌──────────────────────────────────────────────────────┐
│  🤖 Asystent kreacji                    [✕ Zamknij]  │
├──────────────────────┬───────────────────────────────┤
│  ROZMOWA             │  PODGLĄD REKORDU               │
│                      │                               │
│  Agent: Znalazłem    │  key: berserker_blade         │
│  podobne miecze...   │  label: Klinga Gniewu         │
│                      │  damage_die: d10              │
│  ┌─────────────────┐ │  linked_stat: STR             │
│  │ [d8 — Standardowy] │ weapon_type: melee          │
│  │ Śr. obrażenia 6.5│ │  allowed_classes: [warrior] │
│  └─────────────────┘ │  ...                          │
│  ┌─────────────────┐ │                               │
│  │ [d10 — Ciężki]  │ │  [✅ Zapisz]  [❌ Anuluj]   │
│  │ Śr. obrażenia 8.5│ │                              │
│  └─────────────────┘ │  Proponowane zmiany:          │
│                      │  (none)                       │
│  [_____Wpisz..._____]│                               │
│  [Wyślij]            │                               │
└──────────────────────┴───────────────────────────────┘
```

Left: conversation + visual questions
Right: live record preview (updates as answers are given) + proposed changes if modifying

---

## Scope of DB Access

| Table | Agent can read | Agent can propose create | Agent can propose update |
|-------|--------------|------------------------|------------------------|
| game_config_weapons | ✅ | ✅ | ✅ |
| game_config_items | ✅ | ✅ | ✅ |
| game_config_consumables | ✅ | ✅ | ✅ |
| game_config_enemies | ✅ | ✅ | ✅ |
| game_config_conditions | ✅ | ✅ | ✅ |
| game_config_skills | ✅ | ❌ | ⚠️ label/description only |
| game_config_archetypes | ✅ | ❌ | ⚠️ starter_items/hp_base only |
| game_config_loot_tables | ✅ | ✅ | ✅ |
| characters / campaigns | ✅ read-only | ❌ | ❌ |
| users | ❌ | ❌ | ❌ |

All proposed changes are **shown to admin before saving**. The agent NEVER auto-saves without explicit approval.

---

## Schema Descriptors

Each table has a `schema_descriptor` JSON (stored in `backend/app/admin_schema_descriptors/`) that tells the agent what questions to ask and in what order.

```json
{
  "table": "game_config_weapons",
  "friendly_name": "Broń",
  "opening_question": "Opisz broń, którą chcesz dodać — do czego służy i kto jej używa?",
  "fields": [
    {
      "key": "label",
      "question": "Jak się nazywa ta broń?",
      "type": "text",
      "required": true
    },
    {
      "key": "damage_die",
      "question": "Jak duże obrażenia zadaje?",
      "type": "single_choice",
      "options": ["d4","d6","d8","d10","d12"],
      "previews": {
        "d4": "Lekka, szybka — nóż, sztylet",
        "d6": "Standardowa — krótki miecz, maczuga",
        "d8": "Solidna — miecz, młot bojowy",
        "d10": "Ciężka — topór, halabarda",
        "d12": "Oburęczna — wielki topór"
      }
    },
    {
      "key": "weapon_type",
      "question": "Typ walki?",
      "type": "single_choice",
      "options": ["melee", "ranged", "spell"]
    },
    {
      "key": "allowed_classes",
      "question": "Kto może używać tej broni?",
      "type": "multi_choice",
      "options": ["warrior", "scholar", "ranger"]
    }
  ],
  "balance_checks": [
    "Compare damage_die to existing weapons of same type",
    "Warn if value_gp seems very high or low relative to similar items"
  ]
}
```

Adding a new table to the Smart Entry system = write one schema descriptor JSON. No new agent code.

---

## Test Checklist

- [ ] Admin describes new weapon → agent queries DB for similar weapons before asking questions
- [ ] Visual question cards render with previews
- [ ] Admin answers questions → draft updates live in right panel
- [ ] Admin asks to change something mid-conversation → agent adjusts draft
- [ ] Admin says "save" → record created in correct table
- [ ] Admin asks to modify existing record → agent finds it, proposes specific changes
- [ ] Admin approves proposed update → record updated in DB
- [ ] Admin rejects proposed update → no change made
- [ ] Proposed change to characters/users → blocked with "I can't modify player data"
- [ ] Session expires after 30 min inactivity → new session starts cleanly

---

## Related Tasks

- Task 30 (Ideas Workshop) — same visual questionnaire pattern, different purpose
- Task 40 (World Builder) — world entries can also be created via this agent
- Task 32 (World Review Queue) — GM-created entries go through review; agent-created go through same queue if ai_generated=1
