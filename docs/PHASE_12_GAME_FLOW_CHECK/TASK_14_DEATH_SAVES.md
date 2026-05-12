# TASK 14 — Death Save System

**Status:** 🔶 Partially Built
**Blocking:** N2 (CON modifier or no modifier), N3 (does mid-combat heal reset counter?)
**Depends on:** Task 01 (HP formula — death triggers at 0 HP, which requires correct HP values)
**Unlocks:** Task 23 (Campaign End & Death screen)

---

## Overview

When a player reaches 0 HP during combat, they don't die instantly — they get a death save roll. Each time they reach 0 HP in the same combat, the save gets harder. Fail enough saves and the character dies. Survive and they continue fighting with 1 HP.

The current code has a fixed DC 10 with a 3-failure system (D&D 5e style). This task replaces it with an escalating DC ladder that fits the gritty WFRP-inspired design.

---

## Design Context

### Why escalating DC instead of D&D's 3-failure race?
D&D 5e's death save system (roll 3 successes vs 3 failures, DC 10) is a race mechanic — tension builds as failures and successes accumulate. It's well-designed for D&D's pacing but creates situations where a player can succeed at DC 10 multiple times in a single combat, almost trivializing repeated near-deaths.

The escalating DC ladder is a LADDER mechanic: the first near-death is survivable (DC 10), the second is dangerous (DC 13), the third is desperate (DC 16), the fourth is nearly hopeless (DC 19). This matches WFRP's philosophy that each wound leaves you worse off. A character at their fourth death save is genuinely near the end.

### Why does CON modifier improve death saves? (Recommendation for N2)
In the current system, CON affects max HP but nothing else. Adding CON modifier to death saves creates a natural "tough characters are harder to kill" synergy. A Warrior with high CON (mod +2) has better survivability at every stage of danger. A Scholar who dumped CON is fragile in every sense.

Counter-argument for "no modifier": death saves should be pure fate — the roll is "does life cling on?" which is beyond physical toughness. This is the WFRP philosophy. Both are valid; this task requires the owner to decide.

### Why doesn't a mid-combat heal reset the counter? (Recommendation for N3)
If drinking a potion resets the death save counter, it trivializes the escalation. A player who goes to 0 HP, drinks a potion, goes to 0 HP again, and drinks another potion starts each death save at DC 10. The whole ladder is irrelevant.

The ladder should track "how close to death did this combat bring you" — surviving the fight is good enough. The counter resets AFTER combat (win or flee), and on long rest. That way, a near-lethal combat leaves a scar: "I nearly died four times in that dungeon corridor."

---

## Current State (Code)

**File:** `backend/app/services/solo_death_service.py`

- `DEATH_SAVE_FAILURE_THRESHOLD = 3` — dies after 3 failures
- DC is hardcoded at `10` — no escalation
- Current roll: `d20 + CON modifier` vs DC 10 (code already uses CON — this is a GOOD starting point)
- Nat 1 = 2 failures (very punishing)
- Nat 20 = auto-success + failures reset to 0
- Success = failures reset to 0, character survives with 1 HP

---

## Decisions Required

### N2 — Death save roll: d20 + CON modifier OR d20 no modifier?

**Recommendation: d20 + CON modifier** (already in code — don't remove it)

Arguments FOR CON modifier:
- CON is the "toughness" stat — makes it mechanically meaningful beyond just HP
- Warrior with CON 14 (mod +2) vs Scholar with CON 10 (mod 0) — Warrior is harder to kill even at 0 HP
- Consistent with "stats matter" design philosophy

Arguments AGAINST (pure d20):
- WFRP-style brutal randomness — your fate is fate, not stats
- Simpler, cleaner

### N3 — Does mid-combat healing reset the death save counter?

**Recommendation: NO — counter persists for entire combat**

A potion restores HP — it doesn't "un-nearly-die." If you're at your second death save (DC 13), drinking a potion doesn't bring you back to DC 10. You're still a character who almost died twice this fight. The counter resets when:
- Combat ends (victory or flee)
- Long rest

---

## Full Specification (with recommendations applied)

### Death Save Ladder

| Nth time reaching 0 HP in combat | DC | With CON +2 needed | With CON 0 needed |
|---|---|---|---|
| 1st | 10 | 8 | 10 |
| 2nd | 13 | 11 | 13 |
| 3rd | 16 | 14 | 16 |
| 4th+ | 19 | 17 | 19 |

Probability of failure (no modifier, nat 20 not counted):
- DC 10: 45% fail
- DC 13: 60% fail
- DC 16: 75% fail
- DC 19: 90% fail

With CON modifier +2:
- DC 10: 35% fail
- DC 13: 50% fail
- DC 16: 65% fail
- DC 19: 80% fail

### Death Save Process

When player HP reaches ≤ 0 during combat:
1. Set player HP to exactly 0 (not negative)
2. Increment `death_save_count` for this combat (stored in `active_combat` JSON)
3. Calculate DC: `10 + (min(death_save_count - 1, 3) * 3)` → gives 10, 13, 16, 19
4. Frontend: show Death Save modal
   - "You're down! Roll to survive."
   - Shows current DC
   - Shows character's CON modifier (if using modifier)
   - Big "Roll d20" button
5. Player rolls
6. Backend receives roll:
   - `total = player_roll + CON_modifier` (if N2 = CON modifier)
   - OR `total = player_roll` (if N2 = no modifier)
7. Resolve:
   - **Nat 20:** Auto-success. Set HP to 1. Show "+1 HP, survived!". Combat continues.
   - **Total ≥ DC:** Success. Set HP to 1. Show "+1 HP, survived!". Combat continues.
   - **Nat 1:** Failure, counts as 2. Increment death_save_fail_count by 2.
   - **Total < DC:** Failure. Increment death_save_fail_count by 1.
8. If `death_save_fail_count ≥ 3`: Character dies → Campaign End flow (Task 23)
9. If survived: combat continues with player at 1 HP, still in their initiative slot

### Stored State in active_combat

```json
{
  "death_save_state": {
    "times_reached_zero": 2,
    "current_dc": 13,
    "fail_count": 1,
    "last_save_result": "success"
  }
}
```

### Counter Reset Rules

| Event | death_save_state reset? |
|-------|------------------------|
| Combat ends (victory) | YES — full reset |
| Combat ends (flee) | YES — full reset |
| Player drinks healing potion during combat | NO — counter persists |
| Player receives Mend Wounds spell during combat | NO — counter persists |
| Long rest | YES — full reset |
| Short rest | NO |

### Nat 1 Behavior — Clarification

Current code: Nat 1 = 2 failures. This is very punishing:
- At death save 1 (DC 10): Nat 1 = immediate 2 failures. Combined with the DC failure: 3 fails total possible in first save.
- Wait — actually: if Nat 1 counts as 2 failures and the threshold is 3 total failures, a Nat 1 on save 1 means 2/3 failures. Not instant death, but extremely dangerous.
- Recommendation: KEEP Nat 1 = 2 failures. It's thematic (critical fumble on a death save is spectacularly bad) and the failure threshold of 3 still gives a chance.

---

## Code Changes Required

### `backend/app/services/solo_death_service.py`

Replace fixed DC 10 with escalating ladder:

```python
DEATH_SAVE_FAILURE_THRESHOLD = 3

def get_death_save_dc(times_reached_zero: int) -> int:
    """Returns escalating DC: 10, 13, 16, 19"""
    index = min(times_reached_zero - 1, 3)
    return 10 + (index * 3)

def apply_death_save_outcome(roll: int, con_modifier: int, times_reached_zero: int) -> dict:
    dc = get_death_save_dc(times_reached_zero)
    total = roll + con_modifier  # Remove con_modifier if N2 = no modifier
    
    is_nat20 = roll == 20
    is_nat1 = roll == 1
    
    if is_nat20 or total >= dc:
        return {"result": "success", "failures_added": 0, "hp_restored": 1}
    elif is_nat1:
        return {"result": "failure", "failures_added": 2}
    else:
        return {"result": "failure", "failures_added": 1}
```

### `active_combat` table or JSON

Store `death_save_state` per combat session (add to combatants JSON or as a separate field).

---

## Edge Cases

- **Player healed above 0 HP by Scholar's Mend Wounds before their death save triggers:** If HP goes from 0 back to positive due to Scholar healing them in the same round, death save does NOT trigger — they never actually hit 0.
- **Death save on the 5th+ time reaching 0:** DC caps at 19 (not 22, 25, etc.)
- **Player tries to flee instead of rolling death save:** Cannot flee while at 0 HP — must roll death save first, survive with 1 HP, then flee action available next round
- **All enemies defeated while player is at 0 HP:** Combat ends — player "survived" at 0 HP, set to 1 HP, no death save needed. Victory condition takes priority.

---

## Test Plan

1. Reach 0 HP first time → verify DC = 10 modal appears
2. Survive, reach 0 HP again same combat → verify DC = 13
3. Survive again, reach 0 HP third time → verify DC = 16
4. Fail death save, fail again, fail third time (3 failures total) → verify death / campaign end
5. Nat 20 on death save → verify success regardless of DC
6. Nat 1 on death save → verify 2 failures added
7. Drink healing potion after surviving death save → verify DC does NOT reset (still 13 on next 0 HP)
8. Win combat → start new combat → verify DC resets to 10

---

## Related Tasks
- Task 01 (HP Formula) — HP must be correctly calculated for 0 HP trigger to work right
- Task 12 (Combat Round Flow) — death save triggered from within round resolution
- Task 13 (Combat Narrative) — "player falls" narration before death save modal
- Task 16 (Healing System) — potions restore HP but don't reset death save counter
- Task 23 (Campaign End & Death) — triggered when all death saves fail
