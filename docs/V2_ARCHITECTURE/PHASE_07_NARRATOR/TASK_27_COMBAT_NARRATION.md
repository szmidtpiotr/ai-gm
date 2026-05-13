# TASK 27 — Combat Narration

## Overview

Combat generates one short LLM narration call per action per round. These are the most performance-critical narrator calls in the system: they must be fast, vivid, and structurally consistent. Numbers are never mentioned — HP, damage values, and dice results are displayed in the UI, not read aloud.

---

## Input Schema (per action)

```python
class CombatNarrationRequest:
    actor:             str        # "Gracz" or NPC name from ŚWIAT block
    action_type:       str        # see action types below
    weapon:            str | None # weapon name from DB, or None for unarmed/magic
    damage_dealt:      int | None # used for constraint enforcement, NOT passed to LLM
    target_hp_after:   int | None # used for constraint enforcement, NOT passed to LLM
    hit_location:      str | None # "głowa" / "tors" / "prawa_ręka" / "lewa_ręka" / "prawa_noga" / "lewa_noga"
    nat_20:            bool
    nat_1:             bool
    condition_applied: str | None # e.g. "Przerażony", "Rana_Nogi", "Ogłuszony"
    target_name:       str        # NPC name or "Gracz"
    target_is_dead:    bool       # true if this action killed the target
```

Note: `damage_dealt` and `target_hp_after` are passed to the constraint validator, not to the LLM prompt. The LLM never sees raw numbers.

---

## Action Types

| action_type | Meaning |
|---|---|
| `ATTACK_HIT` | Standard hit, target survives |
| `ATTACK_MISS` | Attack roll missed |
| `ATTACK_CRIT` | Critical hit (nat 20 or double damage threshold) |
| `ATTACK_KILL` | Hit that kills the target |
| `FLEE_SUCCESS` | Actor successfully fled |
| `FLEE_FAIL` | Flee attempt failed |
| `ITEM_USE` | Consumable used in combat |
| `FEAR_TRIGGER` | Fear test is about to occur |
| `CONDITION_APPLIED` | A condition was just applied |
| `ENEMY_ACTION_HIT` | Enemy hit the player |
| `ENEMY_ACTION_MISS` | Enemy missed the player |
| `ENEMY_CRIT` | Enemy critical hit on player |

---

## LLM Prompt (per combat action)

```
Jesteś narratorem walki. Jedna akcja, 1-2 zdania, po polsku.
NIE wspominaj liczb (HP, obrażenia, wyniki kości).
NIE wymyślaj nowych postaci ani miejsc.

AKCJA:
  aktor: {actor}
  typ: {action_type}
  broń: {weapon or "gołe ręce"}
  cel: {target_name}
  trafienie_krytyczne: {nat_20}
  fumble: {nat_1}
  lokacja_trafienia: {hit_location or "—"}
  stan_zastosowany: {condition_applied or "—"}
  cel_martwy: {target_is_dead}

ŚWIAT:
  {ŚWIAT block with actor, target, location}

SPECJALNE INSTRUKCJE:
  {special_instructions — see below}

Opisz tę akcję w 1-2 zdaniach.
```

---

## Special Instructions by Action Type

### Nat 20 (Critical Hit)

```
To był spektakularny, druzgocący cios. Opisz go jako decydujący moment — precyzja, brutalna siła, lub szczęśliwy traf.
```

### Nat 1 (Fumble)

```
Coś poszło bardzo nie tak. Opisz śmieszne lub niebezpieczne potknięcie aktora — broń się ślizga, aktor się potyka, cel unika w zabawny sposób. Bez ofiar po stronie aktora.
```

### target_is_dead = true

```
Cel właśnie zginął. Opisz jego śmierć jako zapamiętały moment — specyficzny dla tej postaci, nie generyczny.
```

### hit_location present (crit)

Apply the hit location to the description:

| hit_location | Narrative instruction |
|---|---|
| `głowa` | Opisz ogłuszenie, zamazany wzrok, chwiejny krok |
| `tors` | Opisz głęboka rana, utrudniony oddech |
| `prawa_ręka` | Opisz osłabiony uścisk broni, drżące ramię |
| `lewa_ręka` | Opisz trudności z tarczą lub wolną ręką |
| `prawa_noga` | Opisz kulawienie, chwiejny krok, oparcie o ścianę |
| `lewa_noga` | Jak wyżej |

Example for `prawa_noga`: "Opisz że cel kuleje lub opiera się o coś."

### FEAR_TRIGGER

```
Zanim test strachu — chwilowy opis grozy. "Terror przeszył cię na wskroś" lub podobnie. Jedno zdanie, potem test.
```

### CONDITION_APPLIED

If a condition was just applied to the target, the narration should briefly acknowledge it (one clause, not a full sentence). The condition name is in Polish already in the input.

---

## Length Enforcement

All combat narrations: **maximum 2 sentences**. Enforced by the post-processor (sentence split, keep first 2).

Never mention:
- Specific HP values
- Specific damage numbers
- Dice roll results
- Turn order or round numbers

---

## Enemy Death — Not Generic

Enemy death narrations should reflect the NPC's personality/type when possible. The `ŚWIAT` block will include a brief archetype tag for each enemy (e.g., `goblin`, `bandit`, `undead`, `beast`). Use it:

| archetype | Death flavor |
|---|---|
| `goblin` | Pathetic, squealing, crumples in a heap |
| `bandit` | Curses under breath, grabs at the wound |
| `undead` | Silent, finally still, collapses without sound |
| `beast` | Thrashing, a last snarl, then nothing |
| `soldier` | Falls in formation, still grasping weapon |
| `boss` | Always memorable — warrants full 2 sentences |

---

## Parallelism — Multiple Enemies Per Round

When multiple enemies act in one round, combat narrations are generated in parallel async calls and assembled in declaration order.

```python
async def narrate_round(actions: list[CombatNarrationRequest]) -> list[str]:
    tasks = [narrate_action(a) for a in actions]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Replace exceptions with fallback templates
    return [
        r if isinstance(r, str) else FALLBACK_TEMPLATES[actions[i].action_type]
        for i, r in enumerate(results)
    ]
```

Display: narrations are shown sequentially with ~800ms delay between each (frontend handles timing).

---

## Fallback Templates (12 templates covering all action types)

```python
COMBAT_FALLBACK_TEMPLATES = {
    "ATTACK_HIT":          "Cios dosięga celu. Wróg się chwieje.",
    "ATTACK_MISS":         "Atak rozmija się w ostatniej chwili.",
    "ATTACK_CRIT":         "Druzgocący cios trafia w słaby punkt.",
    "ATTACK_KILL":         "Wróg pada, pokonany.",
    "FLEE_SUCCESS":        "Udaje ci się wyrwać z walki i zniknąć w ciemnościach.",
    "FLEE_FAIL":           "Droga ucieczki jest zablokowana.",
    "ITEM_USE":            "Używasz przedmiotu w wirze walki.",
    "FEAR_TRIGGER":        "Coś w tej chwili przeszywa cię zimnym dreszczem.",
    "CONDITION_APPLIED":   "Nowy stan wpływa na przebieg walki.",
    "ENEMY_ACTION_HIT":    "Wróg trafia. Poczułeś ból.",
    "ENEMY_ACTION_MISS":   "Atak wroga chybia o włos.",
    "ENEMY_CRIT":          "Wróg zadaje okrutny cios.",
}
```

---

## Testing Requirements

1. **No numbers in output**: Verify regex finds no digits in narrator output for combat narrations.
2. **Length**: All responses <= 2 sentences.
3. **Nat 20 path**: Input `nat_20=true`, verify output is more dramatic than standard hit (qualitative check — flag for human review if CI can't assert).
4. **Death narration**: Input `target_is_dead=true`, verify output is different from `ATTACK_HIT` fallback.
5. **Hit location usage**: Input `hit_location="prawa_noga"`, verify output contains a reference to limping/leg (keyword list: "kuleje", "noga", "krok", "chwieje").
6. **Parallelism**: Simulate 3 enemy actions simultaneously, verify all 3 narrations return and are assembled in order.
7. **Partial failure**: Simulate one of 3 parallel calls failing, verify the other 2 succeed and the failed one uses fallback.
