# TASK 01 — HP & Mana Formulas

**Status:** ❓ Needs Decision (N1)
**Blocking:** N1 must be confirmed before implementation
**Depends on:** Nothing
**Unlocks:** Task 16 (Healing System), Task 17 (Wound Labels)

---

## Overview

Both HP and Mana are currently hardcoded constants in the game (`HP = 10` for all characters, `Mana = 0` for all characters). Stats exist in the database and character sheet but are completely ignored when setting HP and Mana. This task implements the correct dynamic formulas so that character stats have meaningful impact on survivability, and the Scholar archetype has a functioning Mana resource.

---

## Design Context

### Why dynamic HP?
The game is inspired by WFRP (gritty peril) + D&D (heroic quests). In both systems, a character's physical resilience (CON/Toughness) directly affects how many hits they can absorb. Hardcoded 10 HP means:
- A Scholar with CON 8 and a Warrior with CON 16 have identical survivability — this is wrong
- HP never grows with level — removing a core feel of character progression
- Healing items and death saves have no scaling — they feel the same at level 5 as level 1

### Why different archetype bases?
Warriors are combat-specialized fighters. Scholars are knowledge-focused and fragile. A flat base HP difference creates immediately legible asymmetry — even before stats, picking Scholar means "I will be more fragile." This matches the WFRP tradition of different character types having different wound thresholds.

### Why Mana scales with INT?
Scholar's defining resource should reward investing in their primary stat. A Scholar who dumps INT for STR should have less Mana — their magic is weaker. This creates a meaningful trade-off during character creation (stat redistribution in Step 2 of the wizard).

---

## Current State (Code)

**File:** `backend/app/api/characters.py` (lines ~1509-1545)

```python
# Current hardcoded initialization — WRONG
"current_hp": 10,
"max_hp": 10,
"current_mana": 0,
"max_mana": 0,
```

Warrior default stats: STR=12, DEX=12, CON=12, INT=10, WIS=11, CHA=10, LCK=10
Scholar default stats: STR=10, DEX=11, CON=10, INT=12, WIS=11, CHA=10, LCK=10

The stat modifier formula already exists: `(stat_value - 10) // 2`

---

## Decision Required — N1

> **Confirm: Warrior base HP = 10, Scholar base HP = 6?**

The recommendation is YES. Rationale:

| | Warrior | Scholar |
|---|---------|---------|
| Base HP | **10** | **6** |
| Default CON | 12 (mod +1) | 10 (mod 0) |
| HP at level 1 (default stats) | **11** | **6** |
| HP at level 3 (default stats) | **13** | **6** |

Scholar stays at 6 HP until they invest in CON or gain levels. This is intentionally fragile. Warrior at level 1 with default CON is only slightly ahead, but builds with high CON (14 = mod +2) reach 12 HP at level 1.

---

## Full Specification

### Stat Modifier Formula (already implemented — do not change)
```
modifier = (stat_value - 10) // 2

Examples:
  CON 8  → mod -1
  CON 10 → mod 0
  CON 12 → mod +1
  CON 14 → mod +2
  CON 16 → mod +3
  CON 18 → mod +4
```

### HP Formula
```
max_hp = archetype_base_hp + (CON_modifier × level)

Archetype base HP:
  Warrior → 10
  Scholar → 6

Minimum HP: always at least 1 (even if CON modifier is very negative at low level)
```

**Examples:**

| Character | CON | mod | Level | max_hp |
|-----------|-----|-----|-------|--------|
| Warrior, CON 12 | 12 | +1 | 1 | 11 |
| Warrior, CON 14 | 14 | +2 | 1 | 12 |
| Warrior, CON 12 | 12 | +1 | 5 | 15 |
| Warrior, CON 8  | 8  | -1 | 1 | 9  |
| Scholar, CON 10 | 10 | 0  | 1 | 6  |
| Scholar, CON 12 | 12 | +1 | 1 | 7  |
| Scholar, CON 10 | 10 | 0  | 5 | 6  |

### Mana Formula (Scholar only)
```
max_mana = 8 + (INT_modifier × level)

Warriors: max_mana = 0 (always, no mana resource)
Minimum Mana: always at least 1 for Scholar (even if INT is dumped)
```

**Examples:**

| Scholar | INT | mod | Level | max_mana |
|---------|-----|-----|-------|----------|
| Default INT 12 | 12 | +1 | 1 | 9  |
| High INT 16    | 16 | +3 | 1 | 11 |
| Low INT 8      | 8  | -1 | 1 | 7  |
| Default INT 12 | 12 | +1 | 5 | 13 |

### On Character Creation
When a character is finalized:
1. Calculate `max_hp` from archetype + CON modifier + level (always level 1 at creation)
2. Set `current_hp = max_hp`
3. If Scholar: calculate `max_mana` from INT modifier + level
4. If Scholar: set `current_mana = max_mana`
5. If Warrior: `max_mana = 0`, `current_mana = 0`

### On Level Up (future — note for now)
When level increases by 1:
- `max_hp += CON_modifier` (can be negative if CON < 10, but never reduces below 1)
- If Scholar: `max_mana += INT_modifier`
- `current_hp` and `current_mana` are NOT automatically restored on level up

---

## Code Changes Required

### 1. `backend/app/api/characters.py` — character creation
Replace hardcoded `current_hp: 10, max_hp: 10, current_mana: 0, max_mana: 0` with calculated values.

```python
def calculate_hp(archetype: str, con: int, level: int) -> int:
    base = 10 if archetype == "warrior" else 6
    mod = (con - 10) // 2
    return max(1, base + (mod * level))

def calculate_mana(archetype: str, int_stat: int, level: int) -> int:
    if archetype != "scholar":
        return 0
    mod = (int_stat - 10) // 2
    return max(1, 8 + (mod * level))
```

### 2. `backend/app/services/character_service.py` — sheet generation
Wherever default sheet values are set, apply the same formula.

### 3. `backend/app/api/characters.py` — PATCH sheet endpoint
When stats are changed (e.g., during wizard Step 2 redistribution), recalculate `max_hp` and `max_mana` before saving. Do NOT change `current_hp` if combat is in progress.

### 4. Migration (if HP/Mana stored in separate columns)
If HP/Mana are stored in a DB column (not just sheet_json), add a data migration to recalculate existing characters. Check whether `active_combat` uses `hp_current` vs `sheet_json.current_hp` — align them.

---

## Edge Cases

- **Negative CON modifier at level 1:** Scholar with CON 8 (mod -1): `6 + (-1 × 1) = 5`. Still valid.
- **Very high CON:** Warrior with CON 18 (mod +4): `10 + 4 = 14 HP` at level 1. Highest possible at level 1.
- **Scholar with 0 INT modifier (INT 10):** `8 + (0 × 1) = 8 Mana`. Reasonable.
- **Stat redistribution mid-wizard:** If player changes CON in Step 2, max_hp must recalculate live in the UI and on save.
- **Two HP stores:** Code uses both `sheet_json.current_hp` and a runtime `hp_current` in combat. They must stay in sync.

---

## Test Plan

**Pass condition:** At level 1 with default stats, Warrior has 11 HP and Scholar has 6 HP and 9 Mana.

1. Create a Warrior with default stats → verify `max_hp = 11`, `current_hp = 11`
2. Create a Scholar with default stats → verify `max_hp = 6`, `max_mana = 9`
3. Create a Scholar with INT 16 → verify `max_mana = 11`
4. Create a Warrior with CON 8 → verify `max_hp = 9`
5. Create a Scholar with CON 8, INT 8 → verify `max_hp = 5`, `max_mana = 7`
6. Redistribute stats in wizard Step 2, set CON to 16 → verify HP preview updates live

---

## Related Tasks
- Task 16 (Healing System) — uses max_hp to calculate how much potions/rest restore
- Task 17 (Wound Labels) — uses HP percentage thresholds
- Task 14 (Death Saves) — triggers at 0 HP; CON modifier affects saves (see N2)
