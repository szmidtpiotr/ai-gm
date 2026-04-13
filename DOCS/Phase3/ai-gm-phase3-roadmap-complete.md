
# 🎲 AI Game Master - Complete Phase 3 Roadmap (Apr 12, 2026)

## 📋 Project Status
**Deployed:** FastAPI backend, Ollama Gemma3:4b, turn_number per-campaign, Polish RPG flow
**GitHub:** https://github.com/szmidtpiotr/ai-gm (2417a88)
**Campaign 16:** Working proof-of-concept (4 turns)

## 🎯 Phase 3 Goal
Generic fantasy mechanics template in `sheet_json` → Warhammer/D&D compatible
**Key Decisions:** Flat stats + modifiers, per-character HP, party/campaign sheets, hybrid rules, dice modes, XP economy, GM-first narration, backstory

## 🚀 5-Week Implementation

### PHASE 3.1: Schemas + Backstory + GM-First (Week 1)
**Idea:** Character creation form → backstory → GM auto-generates opening scene

**What it looks like:**
```
1. Player creates campaign "Klasztor Krwawego Kamienia"
2. Player creates character → fills stats + backstory:
   - Summary: "Były żołnierz szuka zemsty"
   - Appearance: "Siwe włosy, blizna na ramieniu"
   - Goals: "Zabić czarnoksiężnika"
3. Turn 1 AUTO: GM: "Kaelidring, czujesz zapach spalenizny. Blizna swędzi..."
4. Turn 2+: Player responds, GM narrates
```

**Backend Changes:**
```
CharacterCreateRequest → add backstory fields (summary, appearance, goals, fears)
runnarrativeturn() → if turn_number==1: GM opening prompt using backstory
LLM context → always include character.sheet_json + campaign.sheet_json
New endpoints:
  GET /api/characters/{id}/sheet
  GET /api/campaigns/{id}/summary  
```

**JSON Schemas:**
```json
// character.sheet_json
{
  "backstory": {
    "summary": "Były żołnierz szuka zemsty na czarnoksiężniku",
    "appearance": "Siwe włosy, blizna, przepalony płaszcz",
    "goals": ["Zemsta", "Spokój"],
    "fears": ["Utrata kontroli"]
  },
  "stats": {"strength": {"value": 15, "modifier": 2}},
  "hp": {"current": 12, "max": 12}
}

// campaign.sheet_json  
{
  "summary": "Hero explores monastery",
  "quests": [{"title": "Find dzidy origin", "status": "active"}],
  "world_state": {"current_location": "Klasztor Krwawego Kamienia"}
}
```

**Success:** Character creation → Turn 1 = GM opening scene using backstory

---

### PHASE 3.2: Dice Parser + Fiction-Driven Rolls (Week 2)
**Idea:** `/roll 1d20+3` inline parsing → only roll when fiction requires uncertainty

**What it looks like:**
```
Player: "Skradam się do dzidy /roll 1d20+3"
GM: "Rzut: 17+3=20 (sukces). Dzida nie zauważyła. Co robisz?"
```

**Modes:**
| Mode | Trigger | Who sees result |
|------|---------|-----------------|
| silent_gm | Enemy perception | Only GM |
| prompted_player | "Roll Stealth" | Player + GM |
| auto_roll | Solo mode | Everyone |

**Backend Changes:**
```
POST /api/campaigns/{id}/turns → 
1. Parse /roll NdM+X from user_text
2. Roll dice → store in turn JSON
3. Feed results to LLM context
```

**Success:** Player types `/roll 1d20+3` → GM narrates result

---

### PHASE 3.3: Combat State + Initiative (Week 3)
**Idea:** Track initiative order, HP changes, current encounter

**What it looks like:**
```
GM: "Dzidy atakują! Roll Initiative"
Player: "/roll 1d20+2" → 15
GM: "Kaelidring (15), dzida (12). Twoja kolej!"
```

**Data:**
```json
"current_encounter": {
  "initiative_order": [{"char_id": 17, "init": 15}, {"npc": "dzida", "init": 12}],
  "enemies": [{"name": "dzida", "hp": {"current": 8, "max": 12}}],
  "round": 1
}
```

**Success:** GM tracks combat order + HP from dice rolls

---

### PHASE 3.4: XP Economy + Progression (Week 4)
**Idea:** Earn XP → spend on stats/skills/abilities

**Catalog:**
```
Stat increase: 30 XP (max +2)
Skill increase: 20 XP
New ability: 50 XP
```

**What it looks like:**
```
GM: "Zabiłeś dzidę (+25 XP)"
Player: "/spend-xp stealth" 
GM: "Stealth +1 (20 XP). Pozostało 5 XP."
```

**Success:** Player spends XP → sheet updates → GM acknowledges

---

### PHASE 3.5: UI Integration + Summary Window (Week 5)
**Idea:** Frontend shows sheets, quest log, dice history

**Views:**
```
[Character Sheet] popup → stats, HP, backstory
[Campaign Summary] → quests, world state, XP total
[Dice History] → last 10 rolls
[Quest Log] → active/completed
```

**Success:** Full character creation → sheets display → summary window

---

## 🎲 Core Rules (Generic Fantasy)

```
Attack: d20 + stat modifier ≥ AC → hit
Damage: weapon dice + STR/DEX mod
Save: d20 + stat modifier ≥ DC
Skill: d20 + skill bonus ≥ DC

CRITICAL: 20 = crit success, 1 = crit failure
Advantage: 2d20 take highest
Disadvantage: 2d20 take lowest
```

## 📊 Data Flow (Full Loop)

```
1. Player creates character → backstory + stats → sheet_json
2. Turn 1 AUTO: GM opening using backstory + location
3. Player: "Skradam się /roll 1d20+3"
4. Backend: parse roll → update sheet → LLM context
5. GM: "Sukces! Co robisz?"
6. Frontend: show updated sheet + quest log
```

## ✅ Phase 3 Success = 

```
✅ Character creation → backstory → GM opening scene
✅ Dice rolls parsed + narrated  
✅ Combat initiative + HP tracking
✅ XP spendable on progression
✅ Campaign summary window + quest log
✅ Frontend displays everything
```

## 🚀 Phase 4: System-Specific
```
Warhammer → d100 skills, careers, corruption
D&D 5e → spell slots, class levels, feats
Cyberpunk → cyberware, netrunning
```

**Each = rules_text + skill extensions on generic base**

---

## 📝 Quick Start Reference

**When lost, start here:**

1. **Week 1:** Implement backstory fields + GM opening prompt
2. **Week 2:** Dice parser `/roll NdM+X`
3. **Week 3:** Combat state (initiative_order)
4. **Week 4:** XP spend endpoint
5. **Week 5:** Frontend sheets + summary

**Single JSON file holds everything:** `character.sheet_json` + `campaign.sheet_json`

**Always feed both to LLM context.**

Saved forever. Ping me when ready for Phase 3.1 code 🛡️
