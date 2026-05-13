# TASK 16: Fear & Terror System

**Status:** ✅ Done — commit `b22299d` (2026-05-13)

## Overview

The Fear & Terror system brings WFRP's psychological horror into combat. Encountering certain entities forces a WIS saving throw. Failure applies escalating conditions — FRIGHTENED, PANICKED, or BREAK — that constrain player choices and create genuine tension. The mechanics are resolved by the backend entirely; the LLM narrates the psychological moment after the outcome is determined.

**Design intent:** Fear should be consequential and atmospherically dark, not a combat-ender every fight. Most common enemies do not trigger fear checks. Fear-causing enemies are rare and dangerous encounters.

**CONDITIONS FULLY SPECIFIED:** Full lifecycle (duration, tick timing, stacking rules, clear conditions) documented in `11_CONDITIONS_SYSTEM.md`. This task covers the trigger mechanics; that doc covers the mechanical effects.

---

## 1. Fear Check Trigger

A Fear check is triggered when:

1. An enemy with `fear_aura = true` in their behavior profile is encountered (combat starts)
2. The player does **not** already have immunity to this entity type for this combat
3. The player does **not** currently have the FRIGHTENED, PANICKED, or BREAK condition from a previous check (escalation uses Terror path instead)

### Trigger Timing

Fear check fires at combat entry, during the INITIATIVE phase, before the first round begins. It fires once per entity type per combat (not per individual enemy).

If three goblins are present: no fear check (goblins have no fear_aura).
If a vampire thrall and two zombie guards are present: two fear checks (vampire thrall first, then zombie guards), each with their own DC.

---

## 2. FEAR Condition

### Saving Throw

```
Roll: d20 + WIS modifier
DC: enemy's fear_dc (from behavior profile)
```

### Success

Player passes the fear save. They are immune to Fear from this entity type for the remainder of this combat. No condition applied. No round lost.

The Narrator receives context: `"fear_save": "success"` → describes the player steeling their nerves.

### Failure — FRIGHTENED Condition

Player enters FRIGHTENED state.

**Mechanical restrictions while FRIGHTENED:**
- Player action choices reduced to [Attack] and [Flee] only
- [Use Item] button hidden/disabled
- Cannot attempt any non-combat action (resting, talking)
- Free-text input is still accepted but Intent Parser restricts valid intents to ATTACK and FLEE

**Duration:** 2 rounds. Tracked in `character_conditions` with `expires_at_round`.

**Recovery:** Condition clears automatically when `expires_at_round` is reached. No action required.

### Nat 1 on Fear Save — TERROR Escalation

If the player rolls a natural 1 on a Fear save, the condition does not stay at FRIGHTENED. The result immediately escalates to a Terror check (see Section 3). The player does not first receive FRIGHTENED — they go straight to the Terror save.

---

## 3. TERROR Condition

Terror is triggered by one of two paths:

1. Player rolls Nat 1 on a Fear save
2. Player is already FRIGHTENED and encounters the same (or another fear-causing) entity's attack/ability, and the GM narrative flags the entity as `terror_causing=true` in the enemy profile (reserved for truly horrific entities: demons, vampires themselves, not their thralls)

### Terror Saving Throw

```
Roll: d20 + WIS modifier
DC: enemy's fear_dc + 4
```

### Success

Player does not escalate further. They retain the FRIGHTENED condition (2 rounds) as if they had failed the original Fear save.

### Failure — PANICKED Condition

Player enters PANICKED state.

**Mechanical effects:**
- Player **loses their next full turn** (skip — no action, no movement)
- After the missed turn: automatically transitions to FRIGHTENED for 2 rounds

**Implementation:** Set `character_conditions` with `condition = "panicked"` and `expires_at_round = current_round + 1`. When round counter reaches that value, clear PANICKED and apply FRIGHTENED for 2 more rounds.

The Narrator receives: `"fear_save": "panicked"` → describes the player frozen in place, limbs refusing to move, a scream lodged in their throat.

### Nat 1 on Terror Save — BREAK Condition

BREAK is the worst outcome. Session-permanent for this encounter.

**Mechanical effects:**
- Player is forced to attempt Flee on their next available turn (this is resolved automatically by the backend — no player choice needed)
- If Flee succeeds: combat ends, player escapes to the parent location
- If Flee fails (enclosed location or DEX check failed): player remains but is still BREAK — they cannot re-enter aggressive stance. Each round they must attempt Flee
- Player **cannot re-enter combat with this specific encounter** for the remainder of the session (same `active_combat` session ID)

**Narrative framing (dark):** The player's character has psychologically shattered in the face of this horror. Even if they escape, they are haunted. The Narrator describes this vividly without being gratuitous.

**Storage:** `character_conditions` with `condition = "break"`, `encounter_id = active_combat.id`, no expiry (session-permanent for this encounter).

---

## 4. Fear Condition Summary Table

| Condition | Source | Action Restriction | Duration | Recovery |
|---|---|---|---|---|
| FRIGHTENED | Failed Fear save | No item use | 2 rounds | Auto-expires |
| PANICKED | Failed Terror save | Lose next turn, then FRIGHTENED | 1 turn + 2 rounds | Auto-expires |
| BREAK | Nat 1 on Terror save | Must flee each round | Session-permanent (this encounter) | None in combat |
| FEAR_IMMUNE | Passed Fear save | None | Rest of combat | N/A |

---

## 5. Fear-Causing Entities

### Entities WITH Fear Aura

| Enemy | fear_dc | Notes |
|---|---|---|
| Troll | 12 | Bestial horror; fear_dc is low — most prepared adventurers resist |
| Zombie | 12 | Shambling undead; visceral but not supernaturally terrifying |
| Skeleton Warrior | 12 | Animated bones; unnerving to the unprepared |
| Wraith | 16 | Incorporeal; hard to resist |
| Vampire Thrall | 16 | Supernatural presence emanating from master |
| Demon | 18 | Pure malevolence; even veterans may break |
| True Vampire | 18 | Apex predator; ancient and commanding |

### Entities WITHOUT Fear Aura

The following do NOT trigger fear checks:
- Goblin, Hobgoblin
- Bandit, Raider
- Wolf, Giant Wolf
- Orc, Orc Warrior
- Lizardman
- Giant Spider (fear optional — DM discretion, default off)
- Cultist, Dark Priest (humans)

**Rationale:** Fear should feel special and dread-inducing, not routine. Overusing it diminishes the horror.

---

## 6. Database Schema

### character_conditions table

```sql
CREATE TABLE IF NOT EXISTS character_conditions (
    id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    character_id    TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    condition_type  TEXT NOT NULL
        CHECK(condition_type IN (
            'frightened','panicked','break','fear_immune',
            'dazed','winded','arm_wound','leg_wound','bleeding','charmed','stunned'
        )),
    source_entity_type  TEXT,
        -- e.g. "vampire_thrall" — used for immunity tracking
    encounter_id    TEXT,
        -- active_combat.id — for BREAK's session scope
    expires_at_round    INTEGER,
        -- NULL for permanent-within-encounter conditions
    applied_at_round    INTEGER NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (character_id) REFERENCES characters(id)
);
```

### Reading conditions at turn start

```python
def get_active_conditions(character_id: str, session_id: str, current_round: int) -> list:
    return db.execute("""
        SELECT * FROM character_conditions
        WHERE character_id = ? AND session_id = ?
        AND (expires_at_round IS NULL OR expires_at_round >= ?)
    """, [character_id, session_id, current_round]).fetchall()
```

---

## 7. Fear Resolution Flow (Backend Pseudocode)

```python
def resolve_fear_check(enemy: Enemy, combat_state: CombatState) -> FearResult:
    profile = load_profile(enemy.behavior_profile_key)
    if not profile.fear_aura:
        return FearResult(triggered=False)

    # Check existing immunity
    if has_condition(combat_state.character_id, "fear_immune",
                     source=enemy.enemy_type, session=combat_state.session_id):
        return FearResult(triggered=False, reason="immune")

    # Fear save
    roll = roll_d20()
    total = roll + combat_state.player_wis_modifier
    dc = profile.fear_dc

    if roll == 20 or total >= dc:
        # Success — grant immunity
        apply_condition(combat_state.character_id, "fear_immune",
                        source_entity_type=enemy.enemy_type,
                        session_id=combat_state.session_id,
                        expires_at_round=None)
        return FearResult(triggered=True, outcome="success", roll=roll, total=total, dc=dc)

    if roll == 1:
        # Nat 1 — go straight to Terror
        return resolve_terror_check(enemy, combat_state, dc, reason="nat_1_fear_save")

    # Normal failure — FRIGHTENED
    apply_condition(combat_state.character_id, "frightened",
                    expires_at_round=combat_state.round_number + 2,
                    applied_at_round=combat_state.round_number)
    return FearResult(triggered=True, outcome="frightened", roll=roll, total=total, dc=dc)


def resolve_terror_check(enemy: Enemy, combat_state: CombatState,
                          fear_dc: int, reason: str) -> FearResult:
    terror_dc = fear_dc + 4
    roll = roll_d20()
    total = roll + combat_state.player_wis_modifier

    if roll == 20 or total >= terror_dc:
        # Terror save passed — still frightened
        apply_condition(combat_state.character_id, "frightened",
                        expires_at_round=combat_state.round_number + 2,
                        applied_at_round=combat_state.round_number)
        return FearResult(triggered=True, outcome="terror_saved_frightened",
                          roll=roll, total=total, dc=terror_dc)

    if roll == 1:
        # BREAK
        apply_condition(combat_state.character_id, "break",
                        encounter_id=combat_state.combat_id,
                        expires_at_round=None,
                        applied_at_round=combat_state.round_number)
        return FearResult(triggered=True, outcome="break", roll=roll, total=total, dc=terror_dc)

    # PANICKED
    apply_condition(combat_state.character_id, "panicked",
                    expires_at_round=combat_state.round_number + 1,
                    applied_at_round=combat_state.round_number)
    # Queue FRIGHTENED to apply when PANICKED expires
    apply_condition(combat_state.character_id, "frightened",
                    expires_at_round=combat_state.round_number + 3,
                    applied_at_round=combat_state.round_number + 1)
    return FearResult(triggered=True, outcome="panicked", roll=roll, total=total, dc=terror_dc)
```

---

## 8. Frontend: Fear Test Popup

When a Fear check is triggered during combat entry (INITIATIVE phase), the frontend displays a **Fear Test modal** before rendering the initiative results.

### Modal Content

```
┌─────────────────────────────────────────┐
│           *** FEAR TEST ***             │
│                                         │
│  You behold the Vampire Thrall —        │
│  an unnatural, hollow-eyed creature     │
│  that should not walk among the living. │
│                                         │
│  WIS Saving Throw — DC 16               │
│                                         │
│  WIS Modifier: +1                       │
│                                         │
│         [ Roll d20 ]                    │
└─────────────────────────────────────────┘
```

After the roll button is pressed, the roll is sent to the backend. The backend resolves the outcome and returns the result (success/frightened/panicked/break) alongside the fear narrative from the Narrator.

The outcome is then displayed:
- Success: brief green banner "Nerves held."
- Frightened: amber warning "FRIGHTENED — cannot use items. 2 rounds."
- Panicked: red warning "PANICKED — you freeze in terror. Your next turn is lost."
- Break: dark red overlay "BROKEN — your mind cannot face this. You must flee."

### Condition Indicator in Combat HUD

Active conditions are displayed as small icons below the player HP bar during combat:

```
HP: [████████░░] 14/20    [FRIGHTENED: 1 round]
```

---

## 9. Narrator Integration

Fear events are passed to the Narrator as part of the combat round context:

```python
fear_events = [
    {
        "entity_name": "Vampire Thrall",
        "save_type": "fear",
        "outcome": "frightened",
        "roll": 7,
        "total": 8,
        "dc": 16,
        "player_wis_mod": 1
    }
]
```

The Narrator prompt instructs: "When fear_events are present, describe the psychological impact of the encounter in dark, visceral terms. For BREAK, make the horror palpable — the player character's mind truly cannot handle what stands before them. Do not trivialize."

---

## 10. Implementation Notes

### Files to Create/Modify

| File | Change |
|---|---|
| `backend/app/services/fear_service.py` | New file — all fear/terror resolution logic |
| `backend/app/services/combat_service.py` | Call fear_service at combat entry; check conditions each turn |
| `backend/app/db/migrations/0012_character_conditions.sql` | character_conditions table |
| `frontend/js/combat_fear.js` | Fear Test modal, condition HUD display |
| `frontend/js/combat_ui.js` | Disable [Use Item] when FRIGHTENED, auto-flee when BREAK |

### Testing

```bash
docker exec ai-gm-dev-backend-1 pytest backend/tests/test_fear_system.py -v
```

Key test cases:
- WIS +3 vs DC 12: confirm passes at roll 9 (total 12)
- Nat 1 on fear save → goes to terror check, not FRIGHTENED
- Nat 1 on terror save → BREAK applied
- FRIGHTENED expires correctly at round N+2
- PANICKED creates FRIGHTENED starting at round N+1 (chained conditions)
- FEAR_IMMUNE prevents second fear check from same entity type
- Skeleton (fear_aura=true) triggers check; goblin (fear_aura=false) does not
- BREAK auto-flee fires: confirm flee action generated without player input
