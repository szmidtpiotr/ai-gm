# TASK 05 — HP & Mana Formulas

**Status:** ✅ Done — commit `2d10a45` (2026-05-13)
**Phase:** 02 — Character
**New file:** `backend/app/services/vitality_service.py`
**Test file:** `backend/tests/test_vitality_service.py` — 29 tests, all passing

**Implementation Notes:**
- `stat_modifier(1)` = (1-10)//2 = -9//2 = **-5** (Python floor division, not -4)
- Warrior base HP was previously hardcoded as **12** (wrong) — now correctly **10**
- `_default_playtest_sheet()` in `characters.py` also had hardcoded HP=10 — fixed
- Frontend `_wizardCalcHP()` / `_wizardCalcMana()` added to `app.js`; live preview shown in Step 2 below stat grid
- `apply_level_up()` uses `max(old, old + mod)` to prevent HP/Mana from decreasing

---

## Overview

Character vitality is derived from archetype and stats, not hardcoded. HP and Mana scale with level to reflect character growth without rebalancing fixed values across all content.

---

## Stat Modifier Formula

```
modifier = (stat - 10) // 2
```

Integer division, rounds toward negative infinity (Python `//` operator). Examples:

| Stat | Modifier |
|------|----------|
| 8    | -1       |
| 10   | 0        |
| 11   | 0        |
| 12   | +1       |
| 14   | +2       |
| 18   | +4       |

---

## Default Stats by Archetype

Archetype bonuses are already baked into these defaults. Players see final values; bonuses are not shown separately.

| Stat | Warrior | Scholar |
|------|---------|---------|
| STR  | 12      | 10      |
| DEX  | 12      | 11      |
| CON  | 12      | 10      |
| INT  | 10      | 12      |
| WIS  | 11      | 11      |
| CHA  | 10      | 10      |
| LCK  | 10      | 10      |

Archetype bonuses applied to reach these defaults:
- Warrior: STR +2, CON +1 (base STR 10 → 12, base CON 11 → 12)
- Scholar: INT +2, WIS +1 (base INT 10 → 12, base WIS 10 → 11)

---

## HP Formula

```
HP = base_hp + CON_mod × level
minimum HP = 1
```

Base HP by archetype:
- **Warrior:** 10
- **Scholar:** 6

CON_mod is derived from the character's current CON stat at time of calculation.

---

## Mana Formula

```
# Scholar only
Mana = 8 + INT_mod × level
minimum Mana = 1

# Warrior
Mana = 0  (no mana pool, never displayed)
```

---

## Examples Table

| Scenario                       | Archetype | Level | CON | INT | HP  | Mana |
|-------------------------------|-----------|-------|-----|-----|-----|------|
| Level 1, Warrior defaults     | Warrior   | 1     | 12  | 10  | 11  | 0    |
| Level 1, Scholar defaults     | Scholar   | 1     | 10  | 12  | 6   | 9    |
| Level 1, high CON Warrior     | Warrior   | 1     | 16  | 10  | 13  | 0    |
| Level 1, high CON Scholar     | Scholar   | 1     | 14  | 12  | 9   | 9    |
| Level 5, Warrior defaults     | Warrior   | 5     | 12  | 10  | 15  | 0    |
| Level 5, Scholar defaults     | Scholar   | 5     | 10  | 12  | 6   | 13   |

Notes:
- Level 1 Warrior defaults: base 10 + (CON_mod 1 × level 1) = 11
- Level 1 Scholar defaults: base 6 + (CON_mod 0 × level 1) = 6; Mana = 8 + (INT_mod 1 × 1) = 9
- Level 5 Scholar defaults: HP = 6 + (0 × 5) = 6; Mana = 8 + (1 × 5) = 13

---

## Code Change: `characters.py` Creation

**Target file:** `backend/app/api/characters.py`

**Current behaviour (to replace):**
```python
# Hardcoded values — remove these
max_hp = 10
max_mana = 0
```

**New behaviour:**

```python
ARCHETYPE_BASE_HP = {"warrior": 10, "rogue": 10, "scholar": 6}
ARCHETYPE_BASE_MANA = {"warrior": 0, "scholar": 8}

def stat_modifier(stat: int) -> int:
    return (stat - 10) // 2

def calculate_hp(archetype: str, con: int, level: int) -> int:
    base = ARCHETYPE_BASE_HP[archetype.lower()]
    return max(1, base + stat_modifier(con) * level)

def calculate_mana(archetype: str, int_stat: int, level: int) -> int:
    if archetype.lower() != "scholar":
        return 0
    base = ARCHETYPE_BASE_MANA["scholar"]
    return max(1, base + stat_modifier(int_stat) * level)
```

Call `calculate_hp` and `calculate_mana` wherever `max_hp` and `max_mana` are assigned during character creation. Pass `character.archetype`, the relevant stat value, and `character.level` (1 at creation).

---

## Level-Up Behaviour

On each level gain:

```
max_hp += CON_mod          # always, both archetypes
max_mana += INT_mod        # Scholar only
```

Rules:
- These deltas are **additive** — they accumulate from all previous levels.
- **Never reduces below previous value.** If CON_mod is negative (e.g. CON 8 → modifier -1), the increment is -1 but `max_hp` is floored at the value it held before this level-up. In practice: `new_max_hp = max(old_max_hp, old_max_hp + CON_mod)`.
- Current HP and current Mana are unaffected by level-up; only maximums change.

---

## Live Preview in Wizard Step 2

During the stat redistribution step of the character creation wizard, HP and Mana must update in real time as the player moves points between stats.

Implementation:
- Render HP and Mana as computed display fields below the stat grid, not as inputs.
- Recalculate on every `input` event on any stat field using the JavaScript equivalents of `calculate_hp` / `calculate_mana`.
- Display format: `HP: 11` / `Mana: 9` (plain numbers, no fraction — this is max, not current).
- Warrior: do not render the Mana field at all, or show "Mana: —".

---

## Test Checklist

- [x] Warrior level 1 default stats → HP = 11, Mana = 0
- [x] Scholar level 1 default stats → HP = 6, Mana = 9
- [x] Scholar with INT 8 at level 1 → Mana = max(1, 8 + (-1×1)) = 7
- [x] Scholar with CON 8 at level 1 → HP = max(1, 6 + (-1×1)) = 5
- [x] Level-up with negative CON_mod does not decrease max_hp below previous value
- [x] Wizard Step 2 live preview updates when CON or INT changes (`_wizardCalcHP`, `_wizardCalcMana`)
- [x] `stat_modifier(1)` = -5 (Python floor division: (1-10)//2 = -9//2 = -5)
- [x] `_default_playtest_sheet()` hardcoded HP=10 fixed — now uses `calculate_hp()`
- [x] 29 tests in `test_vitality_service.py`, all passing
