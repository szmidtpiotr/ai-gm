# TASK 08 — Skill Test System (Non-Combat)

**Status:** ❌ Not Started
**Blocking:** None — spec complete
**Depends on:** Nothing (new system)
**Unlocks:** Narrative gameplay becomes more interactive and mechanical

---

## Overview

Outside of combat, the player can attempt actions that require a skill test — picking a lock, sneaking past a guard, persuading a merchant. The system must:
1. Detect when a skill test is needed (GM-declared or player-declared)
2. Surface a Roll popup in the frontend
3. Resolve the roll mechanically (not by LLM)
4. Let the LLM narrate the outcome

Counter-skill tests add opposition — when the player tries to sneak, the guard also rolls Perception. These opposed rolls are resolved simultaneously on the backend, not by LLM description.

---

## Design Context

### Why mechanics for non-combat tests?
Without a roll system outside of combat, all skill resolution is LLM-decided. This means the LLM might auto-succeed a player's action because it "feels narratively right," or auto-fail because it wants tension. The player never knows if their stats matter. Having a mechanical roll for skill tests makes stats meaningful outside of combat and gives the player a tactile, legible resolution moment.

### Why two triggers (GM-declared and player-declared)?
GM-declared: "You attempt to cross the frozen river — roll DEX." This is the classic TTRPG flow where the GM sets up the challenge.
Player-declared: "I try to sneak past the guard." The player is initiating a skill action, and the GM must recognize it, name the skill, set the DC, and surface the roll. Both happen in real play and both need to work.

### Why an admin-configurable counter-skill matrix?
Which skill opposes which is a design decision that might change. Stealth vs Perception makes sense. But does Persuasion oppose Wisdom (the target's judgment) or CHA (their own force of personality)? Making this admin-configurable means the answer can be adjusted without code changes, and game masters can tune the feel of the system.

### Why is counter-skill rolled on the BACKEND?
The player rolls by clicking the Roll button in the frontend. The enemy/NPC counter-roll should not be a visible button for the player — it happens "off-screen." Backend resolves both, returns the final outcome. Player sees: their roll, the result, and the narrated consequence.

---

## Current State (Code)

- `D8` decision: roll popup appears for non-combat skill tests
- `D9` decision: counter-skill matrix needed
- `D10` decision: skill activation detection via `[SKILL_TEST:skill_key:dc_or_opponent]` tag
- No skill test system exists in code
- The roll popup button is disabled/hidden in the current frontend
- `app/api/mechanics.py` and `slash-commands` endpoint exist but don't handle skill tests

---

## Full Specification

### Tag Detection

The GM (LLM) emits a special tag when a skill test is needed:

```
[SKILL_TEST:skill_key:resolution_type:value]
```

Examples:
```
[SKILL_TEST:stealth:opposed:perception]
[SKILL_TEST:lockpick:dc:14]
[SKILL_TEST:persuasion:opposed:wisdom]
[SKILL_TEST:athletics:dc:12]
```

- `skill_key` — key from the `skills` admin table (e.g., "stealth", "lockpick", "persuasion")
- `resolution_type` — either `"dc"` (roll vs static number) or `"opposed"` (roll vs NPC counter-roll)
- `value` — DC number (for "dc") or counter-skill key (for "opposed")

### GM Behavior

The GM receives instruction (in system prompt): "When a player attempts a skill action, emit `[SKILL_TEST:...]` in your response BEFORE narrating the attempt. Do not resolve the outcome — wait for the mechanical result."

Two triggers:
1. **GM-declared:** GM describes a situation requiring a roll ("You try to cross the ice — roll DEX Athletics")
2. **Player-declared:** Player types "I try to sneak past the guard" → GM recognizes skill action → emits tag + "Roll Stealth against the guard's Perception"

### Frontend Roll Popup

When `[SKILL_TEST]` tag is detected in GM stream:
1. Strip tag from visible output
2. Pause the GM message after the setup sentence (before resolution narrative)
3. Show Roll popup modal:
   - Title: "Skill Test — {skill_name}"
   - Shows: character's skill rank + relevant stat modifier + total bonus
   - Example: "Stealth: Rank 3 + DEX mod +2 = +5 to d20"
   - Big "Roll" button with dice animation
4. Player clicks Roll → d20 animation → result displayed
5. Result sent to backend: `POST /api/campaigns/{id}/skill-test/resolve`
6. Backend resolves and returns outcome
7. GM narrates outcome (second LLM call with result as input)

### Backend Resolution — `POST /api/campaigns/{id}/skill-test/resolve`

Request:
```json
{
  "skill_key": "stealth",
  "resolution_type": "opposed",
  "opponent_skill_key": "perception",
  "opponent_context": "town_guard",
  "player_roll": 15
}
```

Backend process:
1. Load character sheet → get skill rank for `skill_key` → get relevant stat modifier
2. Calculate player total: `player_roll + skill_rank + stat_modifier + proficiency_bonus`
   - Proficiency bonus: +2 if skill_rank ≥ 3 (per locked game mechanics)
3. If `resolution_type = "opposed"`:
   - Look up opponent in `npc_definitions` or `enemies` table → get counter-skill value
   - Roll `d20` for opponent + counter-skill modifier
   - Compare totals: player > opponent = SUCCESS
4. If `resolution_type = "dc"`:
   - Compare player total to DC value
   - Player total ≥ DC = SUCCESS
5. Special cases:
   - Player rolls natural 20: auto-success + bonus narrative flag
   - Player rolls natural 1: auto-failure + complication flag
6. Return outcome JSON

Response:
```json
{
  "outcome": "success",
  "player_total": 20,
  "opponent_total": 13,
  "nat_20": false,
  "nat_1": false,
  "margin": 7,
  "narration_hint": "The guard's attention wanders just as you slip past."
}
```

### GM Outcome Narration (second LLM call)

The backend calls the LLM again with:
- Original GM setup sentence
- Mechanical outcome (success/failure, margin)
- Nat 20 or Nat 1 flag
- Counter-roll result (if opposed)

The LLM narrates ONLY the outcome — it does not re-decide what happened.

### Counter-Skill Matrix (Admin-Configurable)

**New DB table:** `skill_counters`

```sql
CREATE TABLE skill_counters (
    id INTEGER PRIMARY KEY,
    player_skill_key TEXT NOT NULL,
    counter_type TEXT NOT NULL CHECK(counter_type IN ('opposed_skill', 'opposed_stat', 'static_dc')),
    counter_key TEXT,           -- skill key or stat key for opposed; NULL for static_dc
    default_dc INTEGER,         -- for static_dc type
    description TEXT            -- "Why does this counter make sense"
)
```

**Default entries:**

| Player Skill | Counter Type | Counter |
|---|---|---|
| stealth | opposed_skill | perception |
| lockpick | static_dc | 14 |
| persuasion | opposed_stat | WIS |
| deception | opposed_skill | insight |
| athletics | static_dc | 12 |
| acrobatics | opposed_stat | DEX |
| intimidation | opposed_stat | WIS |

Admin can add/edit/remove entries in admin panel ("Skill Counters" section).

---

## Skill Resolution Formula (Full)

```
Total = d20_roll + skill_rank + stat_modifier + proficiency_bonus

Where:
  skill_rank = character's rank in the skill (0-5)
  stat_modifier = (relevant_stat_value - 10) // 2
  proficiency_bonus = +2 if skill_rank >= 3, else 0

Example:
  Player attempts Stealth. Skill rank: 3, DEX: 14 (mod +2), proficiency: +2
  Roll: 11
  Total: 11 + 3 + 2 + 2 = 18

  Guard Perception: counter-skill modifier 1 (guard has Perception 1), WIS 12 (mod +1)
  Guard roll: 9
  Guard total: 9 + 1 + 1 = 11

  18 > 11 → SUCCESS
```

---

## Edge Cases

- **Skill key not in character sheet:** Default to `rank = 0` (untrained — no proficiency bonus)
- **NPC has no counter-skill in DB:** Use flat stat DC from enemy tier (weak: 8, standard: 12, elite: 16)
- **Player rolls mid-combat:** Skill tests can occur in narrative turns only. During combat, the [Use Item] / attack / flee are the only actions.
- **GM emits [SKILL_TEST] but player ignores popup:** Frontend should time out after 60 seconds and auto-submit a roll (random d20) to prevent game state lock

---

## Test Plan

1. GM narrates "You try to pick the lock — roll DEX" → verify [SKILL_TEST:lockpick:dc:14] tag detected → Roll popup appears
2. Player clicks Roll, rolls 18 → verify backend resolves vs DC 14 → returns success
3. Opposed test: player types "I try to sneak past the guard" → verify tag emitted → both rolls resolved → correct winner
4. Nat 20: verify "auto-success" in response with bonus narrative flag
5. Nat 1: verify "auto-failure + complication" flag
6. Admin adds new skill counter → verify it's used in next opposed test
7. Skill rank ≥ 3: verify +2 proficiency bonus applied

---

## Related Tasks
- Task 08 is standalone but depends on skills data being in the admin `skills` table (already exists)
- Task 19 (Command Palette) — /help should list available skill commands or interactions
