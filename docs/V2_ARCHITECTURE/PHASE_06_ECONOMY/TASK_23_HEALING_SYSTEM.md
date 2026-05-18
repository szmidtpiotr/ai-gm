# TASK 23 — Healing System

**Phase:** 06 — Economy
**Status:** ⚠ Items + Mend Wounds + rest counters działają, **endpointy `POST /rest` (krótki/długi) niezaimplementowane** — patrz `AUDIT_2026_05_18.md`.
**Related tasks:** TASK 20 (inventory/consumables), TASK 25V2 (XP loop), `12_TRAVEL_SYSTEM.md` (zegar), `DECISIONS_2026_05_18.md` [D13–D16]

> **2026-05-18 audit corrections** — odpoczynek to fundament XP loop. Stage 2C ROADMAP.md ma zaimplementować:
>
> **`POST /api/characters/{id}/rest?type=long`:**
> - Walidacja: bohater w lokacji z `safe_for_rest=1` LUB w `temp_camp` (po akcji "Rozbij obóz") LUB hex dziedziczy safe z lokacji
> - +8h zegara gry (`advance_clock(8, "long_rest")`)
> - Full HP + full mana
> - Reset `mend_wounds_used_this_rest`, krótkie odpoczynki counter, death save counter
> - **Flip pending XP → spendable** (kluczowe dla XP loop per [D7])
> - Out of combat only (409 jeśli `active_combat.status='active'`)
>
> **`POST /api/characters/{id}/rest?type=short`:**
> - Walidacja: max 2 krótkie między długimi
> - +1h zegara (`advance_clock(1, "short_rest")`)
> - Regen HP `1d6 + CON_mod`
> - Mend Wounds użyte w tej "rundzie odpoczynku" blokuje (`mend_wounds_used_this_rest=1`)
> - Out of combat only
>
> **Akcja "Rozbij obóz"** ([D15]):
> - Tworzy tymczasową sub-lokację `temp_camp` na bieżącym hex'ie z `safe_for_rest=1`
> - +1h zegara (sam akt rozbijania)
> - Encounter chance +20% podczas snu (ambush risk)
> - Niedozwolone na: ulicach miasta, środku lochu, terenach niesprzyjających (woda otwarta)

---

## Overview

Multiple healing vectors exist for different tactical contexts. Each has distinct costs (action, resource, gold, time) to prevent trivial HP recovery and preserve tension. The Scholar archetype has additional constraints to prevent double-dipping.

---

## Healing Vectors Summary

| Method | Amount | Combat? | Cost | Notes |
|--------|--------|---------|------|-------|
| Bandage | 1d6 HP | No | 5 sz | Cannot combine with Mend Wounds in same rest |
| Healing Potion | 1d8 + CON_mod HP | Yes | 30 sz | Costs player's combat action |
| Mend Wounds (Scholar) | 2d6 + INT_mod HP | Yes | 2 Mana | See Scholar restrictions |
| Short Rest | 1d6 + CON_mod HP + INT_mod Mana | No | Requires safe_for_rest | Max 2 per long rest |
| Long Rest | Full HP + Full Mana | No | Requires safe_for_rest | Resets all counters |

---

## Bandage

**Item key:** `bandage`  
**Item type:** `consumable`  
**Base price:** 5 sz

**Usage:** `POST /api/inventory/{character_id}/use` with `{ "item_key": "bandage" }`

**Rules:**
- Cannot be used during combat (`character.in_combat=true` → 400 error: *"Nie możesz opatrzyć ran podczas walki."*)
- Cannot be used in the same rest period as Scholar's Mend Wounds (`character.mend_wounds_used_this_rest=true` → 400 error)
- No maximum HP overheal (cannot exceed `max_hp`)
- Roll: `1d6` server-side. Return: HP gained, new HP total.
- Consumed on use (remove from inventory)

---

## Healing Potion

**Item key:** `health_potion`  
**Item type:** `consumable`  
**Base price:** 30 sz

**Usage:** `POST /api/inventory/{character_id}/use` with `{ "item_key": "health_potion", "combat": true/false }`

**Rules:**
- Usable in combat: if `combat=true`, costs the player's action for the current combat round. The backend flags `character.action_used=true` for this round; the combat system checks this before allowing attack actions.
- No restriction on combining with other healing in same rest period (it's a magic potion, not mundane first aid)
- Roll: `1d8 + CON_mod` server-side. No overheal.
- Consumed on use.

---

## Scholar Mend Wounds

**Spell key:** `mend_wounds`  
**Archetype restriction:** Scholar only

**Usage:** `POST /api/characters/{character_id}/cast` with `{ "spell_key": "mend_wounds", "target_id": character_id }`  
(Self-cast; target is always self in v1)

**Rules:**
- Requires `character.archetype = 'scholar'`
- Requires `character.current_mana >= 2`
- Costs 2 Mana: `character.current_mana -= 2`
- Usable in combat (costs action, same as potion)
- After use: set `character.mend_wounds_used_this_rest = true`
- Cannot use bandage in same rest period after Mend Wounds (see Bandage restrictions)
- Roll: `2d6 + INT_mod` server-side. No overheal.

**Mana cost tuning note:** Starting value is 2 Mana. During playtesting, if Scholar feels unkillable (consistently surviving situations that should feel dangerous), raise cost to 3 Mana. The Scholar starts with `8 + INT_mod × level` max Mana, so at level 1 with INT +2: 10 Mana — this allows 5 casts at cost-2, or ~3 casts at cost-3. Monitor playtest feedback before changing.

---

## Short Rest

**Command:** `/rest` in text input, or [Odpoczynek] button in character panel  
**Intent Parser tag:** `ACTION:REST`

**Pre-conditions (all must be true):**
1. `location.safe_for_rest = true`
2. `character.short_rest_count < 2` (max 2 short rests per long rest)
3. NOT in combat

**Scholar restriction:** If `character.mend_wounds_used_this_rest = true` → short rest is unavailable for HP healing (no double-dip). Message: *"Twoje czary leczące wyczerpały zdolność odpoczynku. Konieczny jest długi odpoczynek."* Mana is still restored normally (no restriction on Mana recovery).

**On short rest:**
1. Roll: `1d6 + CON_mod` HP restored (Scholar restriction: 0 HP if `mend_wounds_used_this_rest`)
2. Scholar: restore `INT_mod` Mana (minimum 1, even if INT_mod <= 0)
3. Increment: `character.short_rest_count += 1`
4. Reset `mend_wounds_used_this_rest = false` (after this rest; they can cast again in next rest window)

**Narrator narrates the rest.** The system sends `ACTION:REST` outcome through the standard narrator pipeline (TASK 11). No special LLM call needed — the mechanic result includes HP/Mana gains and the narrator describes the reprieve.

---

## Long Rest

**Command:** `/rest long` or hold [Odpoczynek] button (long press), or explicit text *"Chcę spać do rana"*  
**Intent Parser tag:** `ACTION:REST_LONG`

**Pre-conditions:**
1. `location.safe_for_rest = true`
2. NOT in combat

**No maximum uses per session.** (Long rests represent sleeping; narratively bounded by story pacing.)

**On long rest:**
1. `character.current_hp = character.max_hp`
2. `character.current_mana = character.max_mana` (Scholar)
3. `character.short_rest_count = 0`
4. `character.mend_wounds_used_this_rest = false`
5. `character.death_save_count = 0` (from combat death saves, see TASK 05)
6. All `abandoned` loot for this character expires (see TASK 22)

**Narrator narrates the long rest** — passage of time, renewed strength, dreams perhaps touched with darkness (WFRP tone).

---

## Mana Restoration Wire-Up

The `POST /api/inventory/{character_id}/use` handler and rest handlers currently have a stub:

```python
# TODO: restore mana on rest
pass
```

Wire up:

**Short rest:** `character.current_mana = min(character.max_mana, character.current_mana + max(1, int_mod))`

**Long rest:** `character.current_mana = character.max_mana`

**Mana potions (future item type):** reserved `item_type='mana_potion'` for v2. Do not implement in this task.

---

## REST Handler Flow

```python
async def handle_rest(character_id: int, rest_type: str):
    # rest_type: 'short' or 'long'
    
    character = db.get_character(character_id)
    location = db.get_location(character.current_location_id)
    
    if not location.safe_for_rest:
        return SYSTEM_MESSAGE("To miejsce nie jest bezpieczne do odpoczynku.")
    
    if character.in_combat:
        return SYSTEM_MESSAGE("Nie możesz odpoczywać podczas walki.")
    
    if rest_type == 'short':
        if character.short_rest_count >= 2:
            return SYSTEM_MESSAGE("Możesz odpocząć krótko tylko dwa razy przed długim odpoczynkiem.")
        
        hp_gain = 0
        if not character.mend_wounds_used_this_rest:
            hp_gain = roll_dice('1d6') + character.con_mod
        
        mana_gain = max(1, character.int_mod) if character.archetype == 'scholar' else 0
        
        apply_short_rest(character, hp_gain, mana_gain)
        return mechanic_result(hp_gain=hp_gain, mana_gain=mana_gain, rest_type='short')
    
    elif rest_type == 'long':
        apply_long_rest(character)
        return mechanic_result(hp_gain=character.max_hp - character.current_hp, 
                               mana_gain=character.max_mana - character.current_mana,
                               rest_type='long')
```

---

## Test Checklist (8 Cases)

1. **Bandage — out of combat, success:** Use bandage. Verify 1d6 HP gained (within range 1–6). Bandage removed from inventory.

2. **Bandage — in combat, rejected:** Set `in_combat=true`. Use bandage. Verify 400 error, HP unchanged, bandage still in inventory.

3. **Healing potion — in combat, costs action:** Use potion in combat. Verify HP gained, `action_used=true` set, potion removed. Verify attack action blocked this round.

4. **Scholar Mend Wounds — mana deducted:** Scholar casts Mend Wounds. Verify `current_mana -= 2`, HP gained (2d6+INT_mod range). `mend_wounds_used_this_rest = true`.

5. **Scholar double-dip blocked:** Scholar casts Mend Wounds. Then attempts short rest for HP. Verify short rest returns 0 HP gain with message. Mana still restored normally.

6. **Short rest — max 2 enforced:** Take 2 short rests. Third attempt: verify rejection message *"Możesz odpocząć krótko tylko dwa razy..."*.

7. **Long rest — full reset:** Set HP to 5, Mana to 0, `short_rest_count=2`, `death_save_count=2`. Long rest. Verify all restored to max, counters reset.

8. **Scholar: Mend Wounds flag cleared after long rest:** Scholar casts Mend Wounds. `mend_wounds_used_this_rest=true`. Long rest. `mend_wounds_used_this_rest=false`. Short rest now available for HP again.
