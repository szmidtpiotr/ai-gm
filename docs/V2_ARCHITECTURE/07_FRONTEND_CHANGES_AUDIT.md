# AI-GM V2 — Frontend Changes Audit (Accurate)

> Based on actual inspection of `frontend/front/` — the new mobile-first frontend.
> This replaces the earlier estimate which was based on the old desktop frontend.

---

## The Actual Frontend (frontend/front/)

The new frontend is a clean, mobile-first single-page app. Key architecture:
- Full-screen screens (login → campaigns → wizard → game)
- Slide-up panels for sheet/settings/journal (excellent pattern, reuse for V2)
- Separate `composer` (normal text input) and `combat-composer` (Attack + Flee, replaces normal during combat)
- Dark fantasy aesthetic with Cinzel/Lora/IM Fell typography — matches the tone perfectly

### What Already Works Well

| Component | Status | Notes |
|-----------|--------|-------|
| Login screen | ✅ | Clean dark design |
| Campaigns list screen | ✅ | Card-based, new campaign button |
| New campaign form | ✅ | With suggested name chips |
| Character wizard (4 steps) | ✅ | Step 2 stats with +/- controls, looks great |
| Game screen header | ✅ | Character name, HP bar, journal + settings buttons |
| Character sheet panel (slide-up) | ✅ | Tabs: Stats, Skills, Inventory, Appearance |
| Stats tab | ✅ | HP bar (green → health colour), Level, all 7 stats with modifiers |
| Inventory tab | ✅ | Gold display, equipment slots section, backpack, lore items |
| Combat banner | ✅ | Round counter, turn label, enemy list with HP bars |
| Combat composer | ✅ | Attack + Flee buttons, separate from normal input |
| Death screen overlay | ✅ | Skull, epitaph, ember particles, Resurrect + Return buttons |
| Combat-end overlay | ✅ | "Zwycięstwo!", loot display |
| Combat loot popup | ✅ | Claim / Skip buttons |
| Journal panel (slide-up) | ✅ | Summary with regenerate button |
| Settings panel (slide-up) | ✅ | Font/size, bubble metadata, voice, admin section |
| Admin section in settings | ✅ | Hidden for non-admins, debug toggle, service dots, reset buttons |
| Voice (TTS/STT) | ✅ UI | Toggles exist, Piper service exists, integration partial |
| Mobile/responsive | ✅ | Built mobile-first from the start |

---

## What's Actually Missing for V2

### CRITICAL — Must build before combat is usable

**1. Roll Popup System**

Completely absent. V2 combat requires player to roll dice. Three distinct popups needed:

```
ATTACK ROLL               FEAR TEST               DEATH SAVE
(neutral styling)         (darker, horror)        (most dramatic)
┌──────────────┐         ┌──────────────┐        ┌──────────────┐
│ ⚔️ Atak      │         │ 😱 Test      │        │ 💀 Rzut na   │
│ Mieczem      │         │ Strachu      │        │ Śmierć       │
│ d20 + 7      │         │ MĄD vs DC 16 │        │ DC: 13 (2×)  │
│              │         │ WIS mod: +0  │        │ KON mod: +1  │
│ [🎲 Rzuć]   │         │ [🎲 Walcz]  │        │ [🎲 Walcz]  │
└──────────────┘         └──────────────┘        └──────────────┘
```

**2. Combat Zone Display (ENGAGED / RANGED)**

Combat banner shows enemy HP bars but no spatial zones. Need to split the banner into two zones:

```
Current combat banner:
  Runda 1 | Twoja tura
  [Goblin  8/12 ████░]
  [Wolf   12/12 ████████]

V2 needs:
  Runda 1 | Twoja tura
  ┌─DYSTANS─┐ ┌────ZWARCIE────┐
  │ 🏹Archer│ │ ⚔Goblin 8/12 │
  │  8/8   │ │ 🐺Wolf  12/12 │
  └────────┘ └───────────────┘
```

**3. Death Save Flow — Wrong Order**

Current death screen = "you died already." V2 needs a roll-first flow:
1. Player HP = 0 → Death Save popup appears (roll d20 + CON)
2. Success → HP=1, combat continues
3. Only after all saves fail → existing death screen

**4. Target Picker**

When multiple enemies exist, Attack button fires blindly. Need a target selection step:
- After clicking Attack: show enemy list buttons, player taps which to target
- Or: tap enemy HP bar directly in combat banner to select target

---

### HIGH PRIORITY — Core V2 mechanics

**5. Mana Bar (Scholar)**

Only HP bar exists. Scholar needs a blue Mana bar below HP. Should appear/disappear based on archetype. Lives in: header HP bar area AND stats tab.

**6. XP Progress Bar + Pending Indicator**

No XP display anywhere. Needs:
- Small XP bar in stats tab (or header)
- "⬆ +25 PD oczekujące" notification badge when XP is earned
- After long rest: advancement screen triggered

**7. Wound Label**

No narrative wound status shown. Add below HP bar:
- HP >75%: nothing
- HP 51-75%: small "Ranny" badge (yellow)
- HP 26-50%: "Poważnie Ranny" (orange)
- HP ≤25%: "Bliski Śmierci" (red, pulsing)

**8. Conditions Display**

No place to show active conditions (Frightened, Bleeding, Arm Wound, Stunned...). Needs a small condition chips row in stats tab and/or combat banner.

**9. Location Badge**

No current location shown anywhere in the game screen. Add to header subtitle area (currently shows "Poziom 1 • 29/29 HP"). Could become "Graustein · Poziom 1 · 29 HP".

**10. Spells Tab (Scholar)**

No spell UI whatsoever. Need a new tab in the character sheet for Scholar:
- Spell list with rank, mana cost, [Cast] button
- Shows available Arcane Points
- Collapsible "Available to learn" section

---

### MEDIUM PRIORITY — New screens

**11. Combat Composer — Missing Buttons**

Currently: only [Atak] + [Ucieczka]. V2 needs:
- [🧪 Przedmiot] — use item from inventory during combat
- [→ Zbliż się] / [← Cofnij się] — zone change (greyed when not applicable)
- [Cel: Goblin ▾] — target selector (greyed when only one enemy)

**12. Adventure Selection Screen**

After campaign ends, only "Resurrect" or "Return to campaign" options exist. V2 needs:
```
Co teraz, [hero name]?
[🗺 Nowa kampania] [⚔ Loch] [📜 Zlecenie] [💤 Odpoczynek]
```

**13. XP Advancement Screen**

No screen for spending pending XP. Triggered after long rest. Slide-up panel pattern works here:
- Tabs: Statystyki / Umiejętności / Zaklęcia
- Each item: current → +1 with cost shown

**14. World Map Panel**

No map anywhere. Use same slide-up pattern as sheet/settings/journal. Cytoscape.js, fog-of-war.

**15. Victory Screen (Campaign Ending)**

`combat-end-overlay` ("Zwycięstwo!") exists for single-combat wins. Campaign ending is different — needs a full-screen overlay with ending title, epilogue text, total XP/gold earned.

**16. Initiative Order in Combat**

Combat banner shows round counter but no ordered list of combatants. Need a small scrollable row:
```
[⚔ Łucznik 20] → [⚔ Aldric 16] → [⚔ Goblin B 13] → [⚔ Goblin A 9]
                    ↑ TERAZ
```

---

### LOW PRIORITY — Polish

**17. Hero-Centric Campaigns Screen**

Currently shows campaigns as primary entity. With persistent heroes, should show hero name/archetype/level at top, campaigns as their history.

**18. Crit Flash in Combat**

When crit lands: brief "KRYTYK! Noga" text flash in combat banner.

**19. Miscast Visual (Scholar)**

When Scholar rolls Nat 1: dark pulse animation on header HP area + small notification.

**20. Companion Display**

If NPCs travel with hero, they need an "ally" row in combat banner and a small section in stats tab.

**21. Debug Drawer Expansion**

Admin debug toggle exists (in settings admin section). For V2 it should expand to a proper drawer showing game state, last intent, mechanical result etc. The toggle currently just shows debug info under GM messages — keep that as one mode, add the full drawer for deeper inspection.

---

## What to Build vs What Already Exists

**Reuse the existing slide-up pattern for:**
- World map panel (new slide-up)
- XP advancement screen (new slide-up)
- Scholar spell management (new slide-up or tab in sheet)
- Debug drawer (new slide-up, admin only)

**Extend existing components:**
- Stats tab: add Mana bar, XP bar, wound label, conditions chips
- Combat banner: add zone split, initiative row, condition icons per enemy
- Combat composer footer: add Item + Zone-change buttons, target selector
- Death screen: add death save roll step BEFORE the "you died" screen
- Campaigns screen: add hero context header

**Build from scratch:**
- Roll popup system (3 styles: attack / fear / death save)
- Adventure selection screen
- Victory (campaign end) screen

---

## Implementation Priority Order

```
Phase 09 (Frontend) task order suggestion:

1. Task 33 — Hybrid input + dynamic context buttons (changes composer behaviour)
2. Task 34 — Combat UI:
   a. Roll popup system (critical — blocks all combat)
   b. Target picker
   c. Zone display
   d. Initiative row
   e. Extra composer buttons (Item, Zone-change)
3. Task 35 — Character sheet additions:
   a. Mana bar (Scholar)
   b. XP bar + pending badge
   c. Wound label
   d. Conditions row
   e. Spells tab (Scholar)
4. Task 38 — Campaign end: death save flow fix + victory screen
5. Task 42 — Persistent hero: adventure selection screen
6. Task 43 — Player world map panel
7. Task 44 — Debug drawer expansion
8. Task 45 — Hero journal (extends existing journal panel)
```
