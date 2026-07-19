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
| Effect | **-1 HP** at start of each turn (flat, not a dice roll) |
| Cleared by | Bandage (out of combat), Mend Wounds (in combat), 3 rounds expire |
| Stacking | If stacking enabled: each additional bleed adds +1 dmg/round, max 3 stacks |

*(#1465 — seed `bleeding` normalised to flat `dot value:1` to match this spec. It previously carried a malformed `{"damage":"1d3"}` whose key the DoT loop ignored → it silently rolled the 1d4 default. Now it deals exactly 1/round.)*

#### POISONED
Applied by: `poison_vial` item applied to weapon before attack, or specific enemy abilities.

| Property | Value |
|----------|-------|
| Duration | Max 3 rounds (or until saved/cleared) |
| Effect | **STR −2** AND **1d4 poison damage** at start of each turn (DoT). *(#1465 — value is a STARTING value, Sandbox-tunable.)* |
| Cleared by | Antidote item (immediate), 3 rounds expire |

The DoT models the venom eating away at the victim while the STR penalty saps their strikes; tough characters simply outlast the 3 rounds. *(Implemented as seed `poisoned`: `static_stat_modifier STR −2` + `dot 1d4 poison`. The earlier CON-save-early-out from the draft spec is not wired — kept simple per #1465.)*

#### FROZEN
Applied by: frost spells / ice effects.

| Property | Value |
|----------|-------|
| Duration | Until a successful CON save |
| Effect | **Odbiera akcje** (`block_action` — traci turę) AND **DEX −4** |
| Save | CON save DC 14 at start of each turn — success shatters the ice and frees the actor (that turn is NOT lost); failure = frozen solid, turn skipped |
| Cleared by | Passing CON save, or contact with heat/fire (narrative remove) |

#### SLOWED
Applied by: frost_grip and similar control effects, or a critical-fumble/wrestling result.

| Property | Value |
|----------|-------|
| Duration | 2 rounds |
| Effect | **50% chance to skip the turn** each round AND **−2 to defense** (`ac`, folds into the #826 defense_stat) |
| Cleared by | 2 rounds expire |

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

Stat penalties from conditions are applied **at the point of every roll** via `_combatant_stat_modifier()` in `combat_service.py`. When the function computes a stat modifier it first reads the raw stat value, then iterates over all active conditions and sums any `stat_mods` deltas from their `effect_json`.

```python
# Simplified view of _combatant_stat_modifier() after Task 1a fix:
def _combatant_stat_modifier(combatant, *, sheet, stat):
    stat_key = stat.upper()
    base = (raw_stat - 10) // 2          # from sheet.stats or combatant.stats

    conditions = active_conditions(sheet or combatant)
    for cond in conditions:
        parsed = parse_effect_json(cond["effect_json"])
        sm = parsed.get("stat_mods", {})  # e.g. {"STR": -2}
        base += sm.get(stat_key, 0)       # fold penalty in

    return base
```

**What this affects:**
- Player attack rolls (STR/DEX modifier contribution)
- Player saving throws (stat modifier contribution)
- Enemy attack rolls (any stat they roll with)
- Enemy saving throws triggered by `on_hit_save` weapon effects
- Periodic save rolls inside `evaluate_current_turn_conditions()`

**Example:** A player with STR 14 (+2) who is Frightened (`{"stat_mods":{"STR":-2,"INT":-1}}`) will attack at +0, not +2. An enemy with DEX 14 (+2) who is Blinded (`{"stat_mods":{"DEX":-4}}`) uses DEX -2 for saves.

Multiple conditions **stack additively** — no cap in the current implementation.

---

## Admin Panel — Conditions Table

The `game_config_conditions` table in admin lets admins view/edit condition definitions. Admin can:
- Edit `label` (display name)
- Edit `description` (shown to player)
- Toggle `is_active` (disable a condition from being applied)
- Edit `effect_json` — **this is now partially live**

**`effect_json` execution model (as of Task 1a):**

| Field in `effect_json` | Executed? | Notes |
|---|---|---|
| `stat_mods` | ✅ **Yes** | Applied to every roll via `_combatant_stat_modifier()` |
| `damage_per_turn` | ✅ Yes | Periodic HP loss evaluated in `evaluate_current_turn_conditions()` |
| `skip_turn` | ✅ Yes | Block action evaluated per turn |
| `effects[].type = "periodic_save"` | ✅ Yes | Structured save loop |
| `effects[].type = "block_action"` | ✅ Yes | Structured action block |
| `attack_penalty` | ❌ Not yet | Stored as metadata only |
| `duration` (string like "2 turns") | ❌ Not yet | Duration countdown uses `duration_rounds` (int) on the live condition instance |

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
