# AI-GM V2 — Conditions System

> Complete specification for all game conditions: application, effects, duration, removal.
> Source of truth for Phase 05 combat implementation.

---

## Foundation Rules

| Rule | Decision |
|------|---------|
| Duration unit | **Combat rounds** (all combatants acting once = 1 round) |
| Damage tick timing | **End of each round** (after all combatants have acted) |
| Stacking | **Admin-configurable global switch** — off by default (same condition refreshes duration), can be enabled to stack up to intensity 3 |
| Clear on long rest | All conditions cleared on long rest |
| Clear on combat end | Wound conditions (Arm/Leg/Winded/Dazed) persist after combat — require healing. Fear conditions clear after combat ends. |

---

## Conditions Reference Table

### Fear-Based (from WFRP Fear/Terror system)

| Condition | Source | Duration | Effect | Cleared by |
|-----------|--------|---------|--------|-----------|
| **FRIGHTENED** | Failed Fear save | 2 rounds | Can only Attack or Flee. Cannot use Items, Spells, or Move zones. | Rounds expire |
| **PANICKED** | Failed Terror save | 1 turn skip + 2 rounds Frightened | Skip next turn completely, then Frightened for 2 rounds | Rounds expire |
| **BREAK** | Nat 1 on Terror save | Session-permanent for this encounter | Must flee immediately. Cannot re-enter this combat for remainder of session. | Cannot be cleared mid-combat |

---

### Wound Conditions — Player Receives (from enemy critical hits)

Applied when enemy attack exceeds player AC by ≥5, or on Nat 20.

| Condition | Hit Location | Duration | Mechanical Effect | Cleared by |
|-----------|-------------|---------|------------------|-----------|
| **DAZED** | Head (d6=1) | Skip next action | Player loses their next combat action entirely | Action skipped → auto-clears |
| **WINDED** | Torso (d6=2) | 2 rounds | -2 to all STR-based rolls (attack, athletics, intimidation) | Rounds expire |
| **ARM WOUND** | Arm (d6=3 or 4) | 3 rounds | -1 to all ATK rolls | Bandage / Mend Wounds / Rounds expire |
| **LEG WOUND** | Leg (d6=5 or 6) | 3 rounds | -2 to DEX flee roll | Bandage / Mend Wounds / Rounds expire |

**Character sheet wound tracking:** Active wound conditions display on the character sheet as body location markers:
```
     [HEAD: 💀 DAZED]
     [TORSO: 🌀 WINDED]
  [L.ARM]    [R.ARM: 🩹 -1 ATK]
  [L.LEG]    [R.LEG: 🦿 -2 FLEE]
```
Body part silhouette in the Overview tab. Markers disappear when condition expires.

---

### Enemy Conditions (player crits on enemies)

Applied when player attack exceeds enemy AC by ≥5, or on Nat 20.

| Condition | Hit Location | Duration | Mechanical Effect | Cleared by |
|-----------|-------------|---------|------------------|-----------|
| **STUNNED** | Head (d6=1) | 1 round | Enemy skips their next turn | Round expires |
| **BLEEDING** | Torso (d6=2) | 3 rounds | -1 HP end of each round | Rounds expire (enemies don't have bandages) |
| **DISARMED** | Arm (d6=3 or 4) | 3 rounds | -2 to all damage rolls | Rounds expire |
| **HOBBLED** | Leg (d6=5 or 6) | 3 rounds | Cannot use flee action | Rounds expire |

---

### Status Conditions (from items, spells, environment)

#### BLEEDING (standalone — not from crits)
Applied by: poison_vial with `apply_to_weapon: true` on hit, or narrative wounds, or some enemy special abilities.

| Property | Value |
|----------|-------|
| Duration | 3 rounds (or until cleared) |
| Effect | -1 HP at end of each round |
| Cleared by | Bandage (out of combat), Mend Wounds (in combat), 3 rounds expire |
| Stacking | If stacking enabled: each additional bleed adds +1 dmg/round, max 3 stacks |

#### POISONED
Applied by: `poison_vial` item applied to weapon before attack, or specific enemy abilities.

| Property | Value |
|----------|-------|
| Duration | Max 3 rounds (or until saved/cleared) |
| Effect | -2 HP at end of each round |
| Save | CON save DC 13 at end of each round — pass = poison ends early |
| Cleared by | Antidote item (immediate), 3 rounds, or passing CON save |

The CON save creates meaningful tension: tough characters (high CON) can fight through poison; fragile Scholars may need to use their antidote.

#### BLINDED
Applied by: smoke_bomb area effect (3m radius), magical effects, or darkness (future).

| Property | Value |
|----------|-------|
| Duration | 3 rounds (smoke disperses) or until leaving area |
| Effect | -4 to all ATK rolls for blinded combatant |
| Counter-effect | Enemies also -2 ATK against a blinded target (harder to find) |
| Cleared by | Rounds expire, move out of smoke area |

Note: Smoke bomb creates a zone — all combatants in ENGAGED with the bomb's location are blinded. Enemy archers targeting into smoke also take -2 ATK.

---

### Miscast Conditions (Scholar — from Nat 1 on spell)

| Scholar Level | Condition Applied | Duration |
|---|---|---|
| 1–2 | STUNNED (skip next action) | 1 action skipped |
| 3–4 | STUNNED + 1d4 self-damage | 1 action skipped |
| 5+ | STUNNED + 1d6 self-damage | 1 round |

---

## Condition Lifecycle (implementation guide)

### Application
```python
def apply_condition(target_id, condition_type, source, duration_rounds):
    # Check if condition already active
    existing = db.get_condition(target_id, condition_type)
    
    if existing and not STACKING_ENABLED:
        # Refresh duration (no stack)
        db.update_condition_duration(existing.id, duration_rounds)
        return existing
    
    if existing and STACKING_ENABLED:
        # Add intensity (max 3)
        new_intensity = min(existing.intensity + 1, 3)
        db.update_condition_intensity(existing.id, new_intensity)
        return existing
    
    # Apply new condition
    db.insert("character_conditions", {
        "character_id": target_id,  # or enemy slot id
        "condition_type": condition_type,
        "intensity": 1,
        "rounds_remaining": duration_rounds,
        "source": source  # "crit_head", "fear_save", "poison_vial", etc.
    })
```

### End of Round Tick
```python
def tick_round_conditions(combatants):
    for combatant in combatants:
        conditions = db.get_active_conditions(combatant.id)
        for cond in conditions:
            # Apply ongoing damage
            if cond.condition_type == "BLEEDING":
                combatant.hp -= 1 * cond.intensity
            elif cond.condition_type == "POISONED":
                combatant.hp -= 2
                # Roll CON save
                if roll_d20() + combatant.con_modifier >= 13:
                    db.remove_condition(cond.id)
                    continue
            
            # Decrement duration
            cond.rounds_remaining -= 1
            if cond.rounds_remaining <= 0:
                db.remove_condition(cond.id)
            else:
                db.update(cond)
```

### Mechanical Effect Application
```python
def get_attack_modifier(character_id) -> int:
    modifier = 0
    conditions = db.get_active_conditions(character_id)
    for cond in conditions:
        if cond.condition_type == "ARM_WOUND":
            modifier -= 1
        elif cond.condition_type == "WINDED":
            modifier -= 2  # only for STR-based attacks
        elif cond.condition_type == "BLINDED":
            modifier -= 4
    return modifier
```

---

## Admin Panel — Conditions Table

The `game_config_conditions` table in admin lets admins view/edit condition definitions. Each condition in this table maps to the hardcoded logic above. Admin can:
- Edit `label` (display name)
- Edit `description` (shown to player)
- Toggle `is_active` (disable a condition from being applied)
- Edit `effect_json` (reference only — actual logic is in code)

**The effect_json on conditions is documentation, not execution.** The actual mechanical effects are coded in the Mechanic Resolver. This ensures no hallucination risk.

---

## Full Condition ID List (for DB seeding)

```
fear:       frightened, panicked, break
wound:      dazed, winded, arm_wound, leg_wound
enemy:      stunned, bleeding, disarmed, hobbled  
status:     bleeding, poisoned, blinded
miscast:    stunned (reuses wound version)
```

Note: `stunned` is used for both enemy head crits AND Scholar miscast. Same mechanics, different source.
