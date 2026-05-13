# TASK 25 — XP and Progression

**Phase:** 06 — Economy  
**Status:** Pending  
**Related tasks:** TASK 11 (turn pipeline), TASK 13 (campaign plan), TASK 05 (combat)

---

## Overview

XP represents character growth through experience — combat, story milestones, and demonstrated skill. It is granted by the system automatically, never by LLM decision. Level-up is immediate on threshold crossing, with point spending deferred to the player's convenience.

---

## XP Sources

All XP grants are system-determined, not narrator-determined. The narrator never decides XP values.

### Combat Victory

XP awarded per enemy defeated, based on enemy tier (defined in `enemy_definitions.tier`):

| Enemy Tier | XP per Kill |
|-----------|-------------|
| `weak` (minions, animals) | 10 |
| `standard` (common enemies) | 25 |
| `elite` (named enemies, champions) | 50 |
| `boss` (act bosses, major antagonists) | 150 |

XP is granted immediately when enemy HP reaches 0 and `VICTORY` is recorded. For group combat (multiple enemies), XP is summed across all defeated enemies in that combat.

### Narrative Milestones

| Event | XP |
|-------|----|
| Key beat completed (`BEAT_COMPLETE` tag processed) | 30 |
| Campaign ending reached (`CAMPAIGN_END` tag processed) | 200 |

XP is granted in the World State Updater (TASK 11 Step 6) immediately when the tag is processed.

### Skill Tests vs High DC

| Condition | XP |
|-----------|----|
| Skill test SUCCESS vs DC ≥ 16 | 5 |

Low-DC successes do not award XP — this incentivizes players to attempt hard things. XP is granted in the Mechanic Resolver outcome processing. Opposed tests where the opponent's resolved value was effectively ≥ 16 also qualify.

---

## Level Thresholds

Starting threshold (Level 1 → 2): 100 XP.  
Each subsequent threshold: `previous_threshold × 1.5`, rounded to nearest 50.

| Level | XP to Next Level |
|-------|-----------------|
| 1 | 100 |
| 2 | 150 |
| 3 | 225 → rounds to 250 |
| 4 | 375 → rounds to 400 |
| 5 | 600 → rounds to 600 |
| 6 | 900 → rounds to 900 |
| 7 | 1350 → rounds to 1350 |
| 8 | 2025 → rounds to 2050 |
| 9 | 3075 → rounds to 3100 |
| 10 | Level cap — no further advancement |

Store precomputed thresholds as a constant list in `game_engine.py`:

```python
XP_THRESHOLDS = [0, 100, 250, 500, 900, 1500, 2400, 3750, 5800, 8900]
# Index = level required to reach this threshold
# XP_THRESHOLDS[2] = 250 means you need 250 total XP to reach level 3
```

---

## Level-Up Resolution

Level-up is detected in the World State Updater after any XP grant:

```python
def grant_xp(character_id: int, amount: int, source: str):
    character.xp_total += amount
    log_xp_event(character_id, amount, source)
    
    new_level = compute_level(character.xp_total)
    if new_level > character.level:
        apply_level_up(character, new_level)
```

### `apply_level_up(character, new_level)`

1. `character.level = new_level`
2. **Max HP increase:**
   - Warrior: `character.max_hp += character.con_mod` (minimum +1)
   - Scholar: `character.max_hp += character.con_mod` (minimum +1)
   - (Both archetypes get the same HP formula — archetype difference is in starting HP base)
3. **Max Mana increase (Scholar only):** `character.max_mana += character.int_mod` (minimum +1)
4. **Skill point awarded:** `character.unspent_skill_points += 1`
5. **Stat point awarded:** `character.unspent_stat_points += 1`
6. Set `character.level_up_pending_notification = true`

---

## Level-Up Notification

On the next turn response after a level-up, include in the response payload:

```json
{
  "level_up": {
    "new_level": 3,
    "hp_gain": 2,
    "mana_gain": 1,
    "skill_points_available": 1,
    "stat_points_available": 1
  }
}
```

Frontend shows a notification banner (non-blocking, slides in from top):

```
┌─────────────────────────────────────┐
│  AWANS! Osiągnąłeś poziom 3         │
│  +2 HP | +1 Mana | +1 pkt umiejęt.  │
│  [Rozdaj punkty]                    │
└─────────────────────────────────────┘
```

[Rozdaj punkty] button opens the character sheet panel with skill/stat spending UI highlighted. This button is optional — the notification auto-dismisses after 8 seconds if not clicked. Points can be spent at any time outside combat.

Clear `level_up_pending_notification` after the notification is delivered.

---

## Spending Points

### Skill Points

Spending UI: character panel → Skills section. Each skill shows current rank (0–5) with a [+] button when `unspent_skill_points > 0`. Confirm button. No undo.

`POST /api/characters/{character_id}/spend-skill-point`
```json
{ "skill_key": "stealth" }
```

Backend: `skill_rank += 1` (max 5), `unspent_skill_points -= 1`.

### Stat Points

Spending UI: character panel → Stats section. Each stat shows current value with a [+] button when `unspent_stat_points > 0`.

`POST /api/characters/{character_id}/spend-stat-point`
```json
{ "stat_key": "DEX" }
```

Backend: `character.dex += 1`, recalculate `dex_mod = floor((dex - 10) / 2)`, `unspent_stat_points -= 1`. Recalculate AC immediately if DEX changed (see TASK 20).

**Out-of-combat only:** Both endpoints return 400 if `character.in_combat=true`. Message: *"Nie możesz zmieniać postaci podczas walki."*

---

## No XP Loss on Death

If the character enters a death save state (TASK 05) or is resurrected, XP is never deducted. The character's earned experience persists. Death in this system represents a near-miss or a setback in narrative terms, not a mechanical punishment that compounds failure.

Comment in code: `# XP is permanent — no deduction on death by design`

---

## XP UI

### Progress Bar

Location: character panel (right sidebar), below HP/Mana bars.

```
XP  ████████████░░░  75 / 100  (Poz. 2)
```

On hover: tooltip shows exact values: *"75 / 100 XP do poziomu 3"*

### Implementation

Frontend receives in every turn response:

```json
{
  "state": {
    "xp_total": 75,
    "xp_next_level": 100,
    "level": 2,
    "xp_delta": 25
  }
}
```

`xp_delta` is the XP gained this turn (may be 0). If > 0, briefly flash the XP bar yellow (+25 XP indicator appears for 2 seconds, then fades).

---

## Level Cap

Maximum level is 10. When `character.level = 10`:
- No further XP is tracked (or tracked but does nothing — implementation choice)
- Progress bar shows "Maks. poziom osiągnięty"
- No level-up notifications
- Skill/stat points from future level-ups are silently not issued (already at cap)

Recommended: continue tracking XP total for stats/display, but do not process level-up logic. Add a check: `if character.level >= 10: return` at the start of `apply_level_up`.
