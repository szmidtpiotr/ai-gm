
# 🎲 AI Game Master - Phase 3 Roadmap: Human-Readable Guide

## 📋 What is Phase 3? (Your 5-week plan)
**Goal:** Turn basic chat into full RPG game with characters, combat, progression, and story tracking.

**Why this matters:** Right now you have working chat. Phase 3 adds the **RPG game layer** — stats, dice, XP, quests — that makes it feel like a real tabletop game.

---

## 🗣️ PHASE 3.1: Characters Come Alive (Week 1)
**What we achieve:** Player creates hero with personality → GM starts adventure automatically

**Player experience:**
```
1. Create campaign "Klasztor Krwawego Kamienia"
2. Create character:
   Name: Kaelidring
   Stats: STR 15, DEX 14
   Backstory: "Były żołnierz szuka zemsty. Blizna na ramieniu."
3. Click "Start Adventure"
4. AUTOMATIC: GM: "Kaelidring, czujesz zapach spalenizny. Blizna swędzi..."
```

**No more awkward:** "Kim jesteś? Co robisz?" on turn 1.

**Technical:** 
- Add backstory fields to character form
- Turn 1 = special GM opening prompt
- Always feed character sheet to AI brain

**Success:** Character creation → GM starts story using your backstory.

---

## 🎲 PHASE 3.2: Dice Rolls Work (Week 2)
**What we achieve:** Player types `/roll 1d20+3` → AI understands and narrates result

**Player experience:**
```
You: "Skradam się do strażnika /roll 1d20+3"
GM: "Rzut: 17+3=20 (sukces). Strażnik nie zauważył. Co robisz?"
```

**Three roll modes:**
- **Silent GM:** Enemy secretly checks if they see you
- **Player roll:** GM says "Roll Stealth" → you roll
- **Auto roll:** Everything automatic (solo play)

**Technical:**
- Parse `/roll NdM+X` from chat messages
- Store results in turn history
- Feed dice to AI brain

**Success:** Type `/roll 1d20` → AI responds with result.

---

## ⚔️ PHASE 3.3: Combat System (Week 3)
**What we achieve:** Battles with initiative order and HP tracking

**Player experience:**
```
GM: "Dzidy atakują! Roll Initiative"
You: "/roll 1d20+2" → 15
GM: "Kaelidring (15), dzida (12). Twoja kolej!"
You: "Atakuję /roll 1d20+4" → 18 (hit)
GM: "Trafienie! /roll 1d8+3 → 7 obrażeń. Dzida pada."
```

**Technical:**
- Track who's turn it is (initiative_order)
- Update HP from damage rolls
- Know when combat ends

**Success:** Full combat flow with HP going down.

---

## 📈 PHASE 3.4: Character Growth (Week 4)
**What we achieve:** Earn XP → spend on better stats/skills

**Player experience:**
```
GM: "Zabiłeś dzidę! +25 XP"
You: "/spend-xp stealth"
GM: "Stealth wzrasta z 3 do 4 (20 XP wydane). Pozostało 5 XP."
```

**Upgrade catalog:**
- Raise stat: 30 XP
- Raise skill: 20 XP  
- New ability: 50 XP

**Technical:**
- Track XP earned/spent
- `/spend-xp` command
- Update character sheet

**Success:** Kill enemies → get stronger.

---

## 🖥️ PHASE 3.5: Full Game Interface (Week 5)
**What we achieve:** Frontend shows your character, quests, dice history

**Player sees:**
```
[Character Sheet] → STR 15, HP 12/12, Stealth 4
[Quests] → "Find dzidy origin" (active)
[Dice History] → 1d20+3=17, 1d8+2=6
[Campaign Summary] → "You're in monastery ruins..."
```

**Technical:**
- Frontend loads `sheet_json`
- Popups for sheets/quests
- Real-time dice log

**Success:** Complete RPG game interface.

---

## 🎮 How the game flows (full loop)

```
Week 1: Create Kaelidring → backstory → GM starts: "Czujesz zapach spalenizny..."
Week 2: "Skradam się /roll 1d20+3" → "Sukces!"
Week 3: "Dzidy atakują!" → Initiative → Combat
Week 4: "Zabiłeś! +25 XP" → "/spend-xp stealth"
Week 5: See character growth + quest progress in UI
```

## 📊 Generic Fantasy Rules (all systems use these)

```
Attack: d20 + stat modifier ≥ AC → trafienie
Damage: weapon dice + STR/DEX mod
Save: d20 + stat modifier ≥ DC
Skill: d20 + skill bonus ≥ DC
20 = critical success, 1 = critical failure
```

## ✅ End of Phase 3 = Working RPG Game

```
✅ Create hero with personality → GM starts adventure
✅ Roll dice → AI understands results  
✅ Fight battles with HP/ininitiative
✅ Earn XP → get stronger
✅ See quests/character growth in UI
```

## 🌟 Later Phases (after generic works)

```
Phase 4: Warhammer Fantasy → d100 skills, careers
Phase 5: D&D 5e → spells, classes
Phase 6: Cyberpunk → cyberware
```

**Each new system = new rules text on same generic foundation.**

---

## 🆘 If You Get Lost

**Always check:**
1. `character.sheet_json` → has backstory, stats, HP?
2. `campaign.sheet_json` → has quests, location?
3. Turn 1 → GM opening, not player intro?
4. `/roll` → parsed and narrated?
5. Frontend → shows sheets/quests?

**Week 1 priority:** Backstory fields + GM opening prompt.

**Saved forever. Resume anytime.** 🛡️
