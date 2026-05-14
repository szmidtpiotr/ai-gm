# TASK 12 — Skill Tests

**Phase:** 04 — Gameplay  
**Status:** ✅ Done

## Implementation Status

- `skill_counters` table created with seed data (all 13 skills, DC and opposed types)
- `skill_service.py` — tag interception, modifier calculation, resolution, narrator context
- `[SKILL_TEST:skill_key:DC:14]` and `[SKILL_TEST:skill_key:OPPOSED:perception]` tags intercepted from narrator prose; state set to `SKILL_TEST_PENDING`
- `[TRAP:skill_key:dc:damage_dice:condition]` tags intercepted; damage applied on failure
- Turn pipeline: `SKILL_ATTEMPT` actions now return `skill_test_pending` (no auto-roll); player must provide d20 via Roll Popup
- `POST /api/campaigns/{id}/skill-test/resolve` — accepts `{d20_roll, skill_test_id}`, resolves test, makes second narrator LLM call, returns prose
- Frontend Roll Popup: shows skill name, modifier breakdown, animated dice roll, nat20/nat1 highlights, sends d20 to resolve endpoint  
**Related tasks:** TASK 11 (turn pipeline), TASK 05 (character stats)

---

## Overview

Skill tests resolve all non-combat challenges: sneaking past guards, picking locks, persuading merchants, reading ancient runes. Two triggers exist — the narrator LLM may call for a test mid-prose, or the player may explicitly attempt a skilled action. Both paths converge on the same backend resolution logic.

**[TRAP] tag extension:** This task also handles the `[TRAP:skill_key:dc:damage_dice:condition]` tag — a minimal extension that reuses skill test resolution. When detected: surface a roll popup, apply damage + condition on fail. No new system needed. See `16_REMAINING_DECISIONS.md` for full spec.

Example: `[TRAP:perception:12:d6:leg_wound]` → Perception roll vs DC 12 → fail = 1d6 damage + LEG_WOUND condition.

---

## Trigger Paths

### Trigger A — Narrator-Initiated

During narration, the LLM embeds a skill test tag in its prose:

```
[SKILL_TEST:stealth:OPPOSED:perception]
[SKILL_TEST:lockpick:DC:14]
[SKILL_TEST:persuasion:OPPOSED:WIS]
[SKILL_TEST:athletics:DC:12]
```

Format: `[SKILL_TEST:skill_key:resolution_type:value]`

The backend intercepts this tag **before** the prose reaches the frontend. The tag is stripped from displayed text. The frontend receives the prose up to the tag point, then immediately renders the Roll Popup.

**Resolution types:**
- `DC` — compare against a static difficulty class number
- `OPPOSED` — compare against NPC/enemy stat modifier + d20 roll (server-side)

### Trigger B — Player-Initiated

Player types a free-text skill action (e.g., *"Próbuję przekraść się obok strażnika"*). The Intent Parser (TASK 11 Step 2) classifies this as:

```
ACTION:SKILL_ATTEMPT:stealth:guard_1
```

The turn pipeline reaches the Mechanic Resolver with this action tag. The Roll Popup is presented before the resolver finalizes the outcome, giving the player agency over the d20 result.

---

## Roll Formula

```
TOTAL = d20 (player-rolled) + skill_rank + stat_modifier + proficiency_bonus
```

- `skill_rank`: 0–5 integer from `character_skills` table
- `stat_modifier`: `floor((stat_score - 10) / 2)` for the skill's governing stat
- `proficiency_bonus`: +2 when `skill_rank ≥ 3`, else 0

**Nat 20:** auto-success regardless of DC or opponent roll. Adds bonus narrative flourish (exceptional success, unexpected windfall, reputation boost with witness NPCs).

**Nat 1:** auto-failure regardless of total. Adds complication (noise made, item dropped, NPC becomes suspicious, lock pick breaks).

---

## Skill-to-Stat Mapping

| Skill Key | Governing Stat |
|-----------|---------------|
| stealth | DEX |
| lockpick | DEX |
| perception | WIS |
| persuasion | CHA |
| deception | CHA |
| intimidation | CHA |
| insight | WIS |
| athletics | STR |
| acrobatics | DEX |
| arcana | INT |
| medicine | INT |
| survival | WIS |
| lore | INT |

---

## Opposed Test Resolution

When `resolution_type = OPPOSED`, the system performs a server-side opposing roll:

```
OPPONENT_TOTAL = d20 (server roll) + opponent_modifier
```

The `opponent_modifier` is resolved from the `skill_counters` table using the `counter_value` field:

- If `counter_type = 'stat'`: use NPC's stat modifier (e.g., WIS modifier for WIS insight)
- If `counter_type = 'skill'`: use NPC's skill rank + stat modifier
- If `counter_type = 'dc'`: treat as static DC (flat number), no NPC roll

Tie-breaking: player wins on a tie (defender advantage principle).

---

## Counter-Skill Matrix

Admin-configurable via `skill_counters` DB table. Default seed entries:

| Skill Key | Counter Type | Counter Value | Notes |
|-----------|-------------|---------------|-------|
| stealth | skill | perception | NPC active perception opposes |
| lockpick | dc | 14 | Default lock DC; can be overridden per lock item |
| persuasion | stat | WIS | NPC wisdom resists persuasion |
| deception | skill | insight | NPC insight sees through lies |
| athletics | dc | 12 | Default physical challenge DC |
| intimidation | stat | WIS | NPC wisdom resists fear |
| acrobatics | dc | 10 | Default agility challenge DC |
| arcana | dc | 14 | Magical knowledge difficulty |
| medicine | dc | 12 | Healing difficulty |

Admin panel path: `Admin → Skills → Counter Matrix`. Each row: skill_key, counter_type, counter_value (stat name or DC integer).

---

## Frontend Roll Popup

Displayed when a skill test is triggered (either path). The popup blocks further input until the player rolls.

**Popup contents:**

```
┌─────────────────────────────────┐
│  TEST SKRADANIA                 │
│                                 │
│  Skradanie  +2                  │
│  Bonus do Zr  +1                │
│  Biegłość  +0                   │
│  ─────────────────              │
│  Twój bonus:  +3                │
│                                 │
│  [Rzuć k20]                     │
│                                 │
│  vs. Percepcja strażnika        │
└─────────────────────────────────┘
```

**UI behavior:**
- Dice icon animates on [Rzuć k20] click (CSS animation, 1.2s)
- Player's d20 result displayed prominently after roll
- Total calculated and shown: `[roll] + [bonus] = [total]`
- Popup fades, narrative continues with result

**Player's roll is sent to backend**, not calculated client-side. Frontend sends:
```json
{ "d20_roll": 14, "skill_test_id": "abc123" }
```

The `skill_test_id` was issued by the backend when it intercepted the tag, locking in the context for resolution.

---

## Backend Resolution

On receiving the player's d20 result:

1. Retrieve stored skill test context by `skill_test_id`
2. Calculate `player_total = d20_roll + skill_rank + stat_mod + proficiency`
3. If opposed: server rolls `opponent_d20 + opponent_modifier = opponent_total`
4. If DC: `opponent_total = dc_value`
5. Compare totals, apply nat20/nat1 rules
6. Return `SkillTestResult`:

```json
{
  "skill_key": "stealth",
  "d20_roll": 14,
  "player_total": 17,
  "opponent_total": 9,
  "outcome": "SUCCESS",
  "nat20": false,
  "nat1": false,
  "bonus_narrative": false
}
```

---

## Second LLM Call — Narrator Outcome

After resolution, the system makes a **second narrator call** with the mechanical result injected into context. This call narrates the outcome specifically.

Context injected:

```
[SKILL TEST RESULT]
Skill: Skradanie
Player total: 17
Opponent: Percepcja strażnika 9
Outcome: SUCCESS
```

Narrator instruction: *"Narrate the skill test outcome in Polish. 60-90 words. Dark fantasy tone. Do not mention numbers or dice."*

If `nat20=true`: narrator receives additional instruction: *"This was an exceptional success — show something unexpected and favorable."*

If `nat1=true`: narrator receives: *"This was a fumble — introduce a complication that will create future tension."*

---

## Test Checklist

1. **Stealth vs perception (opposed, success):** Player rolls 15, stealth rank 2, DEX +1 = total 18. Server rolls perception for guard: d20=7, WIS +2 = 9. Outcome SUCCESS. Narrator called. Prose confirms silent passage.

2. **Lockpick vs DC 14 (failure):** Player rolls 6, lockpick rank 1, DEX +1 = total 8 vs DC 14. Outcome FAILURE. Narrator called. Complication: guards alerted flag set.

3. **Persuasion vs WIS (nat 20):** Player rolls 20. Auto-success regardless of NPC WIS. `nat20=true`. Narrator receives bonus instruction. Prose shows NPC unexpectedly cooperative.

4. **Deception vs insight (nat 1):** Player rolls 1. Auto-failure. `nat1=true`. Narrator introduces complication. NPC relationship `suspicious=true` set in DB.

5. **Athletics vs DC 12 (exact tie — player wins):** Player total = 12, DC = 12. Outcome SUCCESS (tie-breaker favors player).
