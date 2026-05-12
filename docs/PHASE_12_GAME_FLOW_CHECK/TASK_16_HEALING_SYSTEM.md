# TASK 16 — Healing System (Items, Rest, Spells)

**Status:** ❓ Needs Decision (N4, N5)
**Blocking:** N4 (Mend Wounds cost: 2 or 3 Mana), N5 (Scholar double-dip restriction)
**Depends on:** Task 01 (HP/Mana formulas), Task 09 (safe_for_rest on locations)
**Unlocks:** Task 17 (Wound Labels — needs HP tracking), Task 23 (Campaign End)

---

## Overview

Three healing vectors exist in the system:
1. **Healing items** — Bandage (out-of-combat) and Healing Potion (in-combat)
2. **Rest** — Short rest (partial recovery) and Long rest (full recovery)
3. **Scholar spell** — Mend Wounds (in-combat, costs Mana)

Each vector has different availability, cost, and power. Together they create a resource management game between combats: conserve potions for emergencies, use rest when available, Scholar manages Mana carefully.

---

## Design Context

### Why two item tiers?
A Bandage is cheap, accessible, and powerful out-of-combat but useless in the heat of a fight. A Healing Potion is expensive, rarer, but can turn the tide mid-combat. This creates a meaningful shop decision: buy more cheap bandages or save for one expensive potion? Both have their place.

### Why is rest partial for Short rest but full for Long rest?
Short rest represents catching your breath, binding wounds, eating something. You recover somewhat but not completely. Long rest (a full night's sleep in safety) resets you to fighting shape. This pacing creates a natural dungeon-crawl rhythm: push through a few fights on short rests, then make the call about whether to push further or retreat for a long rest.

### Why does Scholar have in-combat healing?
Scholar's primary stat (INT) is least useful in melee. Without a unique survival tool, Scholar is strictly weaker at keeping themselves alive than Warrior. Mend Wounds gives Scholar a self-sustain mechanic that costs their primary resource (Mana). This creates asymmetric but balanced archetypes: Warrior wins through HP + armor, Scholar wins through spells + self-heal.

### The overheal concern (from design review)
At level 1, Mend Wounds (2d6+INT mod) heals an average of ~8-9 HP while Scholar's max HP is only 6. One cast effectively fully heals the Scholar. This is by design (Scholar can always self-heal to full after one spell) but means Scholar combat endurance is more about Mana than HP. With 9 Mana and 2 Mana/cast, Scholar can fully heal ~4 times before running out. This makes them MORE self-sufficient than Warrior in extended fights.

Whether this is too strong depends on how common combat is and how scarce rest opportunities are. The test plan below validates this.

---

## Decisions Required

### N4 — Mend Wounds cost: 2 Mana or 3 Mana?

**Starting value: 2 Mana**

Test condition: After implementing, run 5 test combats with a Scholar. If Scholar never feels threatened (always has Mana to heal) after 3+ combats without a long rest, increase to 3 Mana.

With 2 Mana cost, Scholar with default INT (9 Mana): 4 full heals per long rest cycle.
With 3 Mana cost: 3 full heals per long rest cycle.

**Recommendation: Start at 2, test, adjust if Scholar feels unkillable.**

### N5 — Can Scholar use Mend Wounds AND short rest in same rest period?

**Recommendation: NO — pick one per rest period**

If both are allowed:
- Scholar short rest: recovers 1d6+0 HP (avg 3.5) + recovers INT_mod Mana (1 Mana default)
- Then casts Mend Wounds: 2d6+1 (avg 8 HP) for 2 Mana
- Net result: Scholar at full HP after every short rest using 1 Mana net

This makes Scholar nearly invincible between combats. The restriction (rest OR spell, not both) forces a choice:
- Take short rest: recover HP passively, keep Mana
- Cast Mend Wounds: recover more HP, spend Mana

---

## Full Specification

### Healing Item 1 — Bandage

| Property | Value |
|---------|-------|
| HP restored | 1d6 |
| Combat use | ❌ No |
| When usable | Outside combat only; cannot be used during a rest where Mend Wounds is also cast (N5) |
| Price (suggested) | 5 gold |
| Inventory slot | Consumable |
| Item key | `bandage` |

**Use flow:**
- Player opens inventory → selects Bandage → "Use" button
- Backend checks: `combat_active = false`
- If true: reject with "Cannot use bandage during combat"
- If false: roll 1d6, restore HP (cap at max_hp), remove 1 bandage from inventory
- Return updated HP

### Healing Item 2 — Healing Potion

| Property | Value |
|---------|-------|
| HP restored | 1d8 + CON modifier |
| Combat use | ✅ Yes — uses player's combat action |
| When usable | Anytime, including combat |
| Price (suggested) | 30 gold |
| Inventory slot | Consumable |
| Item key | `healing_potion` |

**Use in combat:**
- Player selects [Use Item] → item picker shows healing potion
- Player selects healing potion
- Backend rolls 1d8 + character's CON modifier
- HP restored (cap at max_hp)
- Item consumed from inventory
- Player's combat turn is spent (enemy auto-fires next per Task 12)

**Use outside combat:**
- Same as bandage use flow but with potion's formula

### Short Rest

| Property | Value |
|---------|-------|
| HP restored | 1d6 + CON modifier (minimum 1) |
| Mana restored (Scholar) | INT modifier (minimum 1) |
| Max per long rest | 2 |
| Requires | safe_for_rest = true in current location, no active combat |
| Time | Narrative: "about an hour passes" — GM notes time skip |
| Can stack with bandage? | Yes — bandage before rest OR after rest is fine |
| Can stack with Mend Wounds? (N5) | No — if Mend Wounds cast this rest period, short rest not available |

**Short rest flow:**
- Player types "/rest" or clicks rest button (if in safe location)
- Backend checks: `safe_for_rest = true`, `combat_active = false`
- Backend checks: `short_rest_count < 2` for this long rest cycle
- If all checks pass:
  - Roll 1d6 + CON modifier, restore HP
  - If Scholar: restore INT modifier Mana
  - Increment `short_rest_count`
  - Store in `game_sessions.session_flags` or `campaign_turns` as a rest event
  - GM narrates time passing (short LLM call or template)

### Long Rest

| Property | Value |
|---------|-------|
| HP restored | Full (max_hp) |
| Mana restored | Full (max_mana) |
| Resets | Short rest counter, death save counter |
| Requires | safe_for_rest = true, no active combat |
| Time | Narrative: "night passes" — GM notes next morning |
| Limit | No limit per campaign |

**Long rest flow:**
- Backend checks: `safe_for_rest = true`, `combat_active = false`
- If checks pass:
  - Set `current_hp = max_hp`
  - If Scholar: set `current_mana = max_mana`
  - Reset `short_rest_count = 0`
  - Reset `death_save_state` (DC back to 10 on next encounter)
  - GM narrates rest (optional, can be template)
  - World time advances — GM may trigger a world event during the night (optional, not required v1)

### Scholar Mend Wounds Spell

| Property | Value |
|---------|-------|
| HP restored | 2d6 + INT modifier |
| Mana cost | 2 (starting value — see N4) |
| Combat use | ✅ Yes — uses player's combat action |
| Target | Self only (solo game) |
| Usable during rest? | Yes, but blocks short rest for that rest period (N5) |
| Scholar only | Yes — Warrior has no Mana |

**Mend Wounds in combat:**
- Appears in [Use Item] picker under "Spells" section (Scholar only)
- Backend checks: `current_mana >= 2` (or 3 if N4 = 3 Mana)
- Deduct Mana, roll 2d6 + INT modifier
- Restore HP (cap at max_hp)
- Player turn spent

**Mend Wounds out of combat:**
- Can be used freely outside combat
- If used during a rest period: marks rest as "spell-used" → short rest becomes unavailable until next rest period
- Backend: store `mend_wounds_used_this_rest = true` in session flags

---

## Wound Narrative Labels (Preview for Task 17)

HP percentage thresholds for GM narration tone (see Task 17 for full spec):
- 76-100%: Unharmed (no mention)
- 51-75%: Hurt ("bleeding cut")
- 26-50%: Wounded ("moving with a limp")
- 11-25%: Severely Wounded ("barely standing")
- 1-10%: Near Death ("one hit from the end")

---

## Mana Economy Summary (Scholar, Default INT 12, Level 1)

| Source | Amount |
|--------|--------|
| Max Mana | 9 |
| Short rest recovery | +1 (INT mod) per rest |
| Long rest | Full (9) |
| Mend Wounds cost | -2 per cast |
| Casts per long rest (without rests) | 4 casts |
| Casts per long rest (with 2 short rests) | 4 casts + 2 Mana recovered = ~5 casts |

Scholar can self-heal approximately 4-5 times between long rests. At average 8 HP per cast and Scholar max HP of 6, this means ~4 full heals per long rest cycle. This is the core "fragile but self-sustaining" identity of the Scholar archetype.

---

## Test Plan

**Starting values validation:**
1. Warrior uses Bandage out of combat → verify 1d6 HP restored, capped at max_hp
2. Scholar uses Healing Potion in combat → verify 1d8+CON HP restored, turn consumed
3. Scholar casts Mend Wounds → verify 2d6+INT HP restored, 2 Mana deducted
4. Scholar at 0 Mana → verify Mend Wounds blocked

**Rest validation:**
5. Short rest in inn → verify 1d6+CON HP restored, short rest counter increments
6. Third short rest attempt → verify blocked with "Need a long rest first"
7. Long rest → verify full HP+Mana, short rest counter reset, death save counter reset
8. Short rest in town square → verify blocked "not safe here"
9. Short rest during active combat → verify blocked

**N5 validation:**
10. Scholar casts Mend Wounds, then attempts short rest → verify blocked
11. Scholar takes short rest, then casts Mend Wounds → verify ALLOWED (restriction only applies to the rest period, not the other direction)

**Balance check (after implementation):**
12. Run Scholar through 3 combat encounters without long rest → count Mana remaining → if never below 3 Mana remaining, consider raising cost to 3

---

## Related Tasks
- Task 01 (HP/Mana Formulas) — max HP and max Mana values used here
- Task 09 (Location System) — safe_for_rest check for rest availability
- Task 12 (Combat Round Flow) — potion and Mend Wounds use combat action
- Task 14 (Death Saves) — long rest resets death save counter
- Task 17 (Wound Labels) — HP percentage thresholds for narrative flavor
- Task 20 (Inventory & Shop) — bandages and potions are purchasable items
