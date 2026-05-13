# TASK 03 — World State Machine

**Status:** ✅ Done — commit `3ded667` (2026-05-13)
**Phase:** 01 — Foundation  
**Depends on:** TASK_01 (DB Schema), TASK_02 (Intent Parser — produces ACTION tags that WSM consumes)  
**Blocks:** TASK_04 (Context Injector receives mechanic results from resolvers WSM routes to)  
**New file:** `backend/app/services/world_state_machine.py`  
**Test file:** `backend/tests/test_world_state_machine.py` — 41 tests, all passing

**Notes:**
- Validators return `WSMResult(valid=True)` or `WSMResult.blocked(msg)` only — never route
- Routing is always done by the `_ROUTES` table in step 4
- Extra session_flags (e.g. REST needs `rest_type_in_progress`) returned via `_get_route_flags()`
- Resolver keys returned as strings — actual resolver implementations come in Phase 05+
- `game_engine.py` integration deferred to TASK_11 (Turn Pipeline)

---

## Overview

The World State Machine (WSM) is the gatekeeper between parsed player intent and mechanical resolution. Every ACTION tag produced by the Intent Parser passes through the WSM before anything happens. The WSM has two responsibilities:

1. **Validate** — is this action possible given the current game state?
2. **Route** — if valid, which resolver handles it?

The WSM never calls the LLM. All decisions are pure Python logic operating on DB-backed game state. If an action is blocked, the WSM returns a system message in Polish — no narrator involved.

---

## Why This Exists

### The V1 Problem

In V1, the LLM decided what was possible. If a player typed "I run away", the LLM might describe a successful escape even if no escape logic existed. If a player typed "I rest", the LLM might narrate a restful sleep in the middle of a dungeon with active enemies.

Mechanical validity was a suggestion, not an enforcement.

### The V2 Principle

> **Impossible actions are blocked before the LLM ever sees them.**

The WSM enforces game rules. The LLM only sees valid actions that have already been mechanically resolved. This makes world state consistent across sessions and removes the LLM as a decision-maker about possibility.

---

## Game States

The WSM recognizes the following game states. The active state is stored in `game_sessions.session_flags` as a JSON field:

```json
{
  "state": "NARRATIVE",
  "state_entered_at_turn": 14,
  "previous_state": "COMBAT"
}
```

| State | Description |
|---|---|
| `NARRATIVE` | Default exploration/roleplay state. No active combat or pending tests. |
| `COMBAT` | Active combat encounter. Turn order is tracked. Only combat-relevant actions allowed. |
| `SKILL_TEST_PENDING` | A skill roll has been triggered and awaits resolution (e.g., trap triggered). |
| `DEATH_SAVE_PENDING` | Character is at 0 HP and must make death saving throws. |
| `FEAR_TEST_PENDING` | A fear source has been revealed; character must make a WIS save before next action. |
| `SHOPPING` | Player is transacting with a merchant NPC. |
| `RESTING` | Active rest period in progress (short or long). |

Only one state is active at a time. Some states can be "interrupted" (e.g., RESTING can be interrupted by combat, which transitions to COMBAT and queues a rest-interrupted system message).

---

## State Transition Table

The full table of: `(current_state, action_type) → (new_state, resolver, or BLOCKED)`.

### From NARRATIVE

| Action | New State | Resolver | Notes |
|---|---|---|---|
| ATTACK | COMBAT | `combat_resolver` | Starts combat, rolls initiative |
| FLEE | BLOCKED | — | "Nie ma z czego uciekać." |
| STEALTH_ATTEMPT | NARRATIVE | `stealth_resolver` | No state change unless enemy patrol detected |
| DIALOGUE | NARRATIVE | `dialogue_resolver` | NPC must be present in location |
| MOVEMENT | NARRATIVE | `movement_resolver` | Target must be reachable |
| SEARCH | NARRATIVE | `search_resolver` | Rolls INT + Investigation |
| ITEM_USE | NARRATIVE | `item_resolver` | Consumable or usable item |
| ITEM_PICKUP | NARRATIVE | `item_resolver` | Item must be in location pool |
| REST | RESTING | `rest_resolver` | Location must have safe_for_rest > 0 |
| EXAMINE | NARRATIVE | `examine_resolver` | No roll required |
| SKILL_ATTEMPT | NARRATIVE | `skill_resolver` | May trigger SKILL_TEST_PENDING |
| SHOP | SHOPPING | `shop_resolver` | NPC must be merchant |

### From COMBAT

| Action | New State | Resolver | Notes |
|---|---|---|---|
| ATTACK | COMBAT | `combat_resolver` | Must have valid living target |
| FLEE | NARRATIVE (on success) / COMBAT (on fail) | `flee_resolver` | DEX contest; on fail, character takes opportunity attack |
| STEALTH_ATTEMPT | COMBAT | `combat_stealth_resolver` | High DC (enemy Perception +5); only hides, does not end combat |
| DIALOGUE | BLOCKED | — | "Nie możesz rozmawiać podczas walki." |
| MOVEMENT | BLOCKED | — | "Nie możesz się swobodnie poruszać podczas walki. Użyj Uciekaj." |
| SEARCH | BLOCKED | — | "Nie czas na przeszukiwanie podczas walki." |
| ITEM_USE | COMBAT | `item_resolver` | Consumables only; costs action for turn |
| ITEM_PICKUP | BLOCKED | — | "Nie możesz zbierać przedmiotów podczas walki." |
| REST | BLOCKED | — | "Nie możesz odpoczywać podczas walki." |
| EXAMINE | BLOCKED | — | "Nie czas na to podczas walki." |
| SKILL_ATTEMPT | COMBAT | `skill_resolver` | Only combat-applicable skills (Athletics, Acrobatics) |
| SHOP | BLOCKED | — | "Nie możesz handlować podczas walki." |

**Combat ends when:** all enemies are dead OR character has successfully fled. State transitions to NARRATIVE. Combat loot row is created in `combat_loot` table.

### From SKILL_TEST_PENDING

This state exists for exactly one turn. The pending test is resolved by the player's next action (usually a SKILL_ATTEMPT, but the WSM can auto-resolve it on any action).

| Action | New State | Resolver | Notes |
|---|---|---|---|
| Any | Previous state | `skill_resolver` (forced) | The pending test resolves first, then the action is queued for next turn |
| SKILL_ATTEMPT | Previous state | `skill_resolver` | Directly resolves the pending test |

The WSM stores the pending test in `session_flags`:
```json
{
  "state": "SKILL_TEST_PENDING",
  "pending_test": {
    "skill_key": "acrobatics",
    "dc": 14,
    "source": "unstable_floor",
    "failure_consequence": "fall_prone"
  }
}
```

### From DEATH_SAVE_PENDING

Character is at 0 HP. Only death saves are valid.

| Action | New State | Resolver | Notes |
|---|---|---|---|
| Any | DEATH_SAVE_PENDING | `death_save_resolver` | All input is treated as a death save attempt |

Three successes before three failures → character stabilizes at 1 HP, state → NARRATIVE.  
Three failures before three successes → character dies, state → DEAD (campaign-ending state).  
Natural 20 on death save → character regains 1 HP immediately, ends DEATH_SAVE_PENDING.  
Natural 1 counts as 2 failures.

### From FEAR_TEST_PENDING

A fear source (enemy `fear_aura`, horror event, etc.) has triggered. Character must make a WIS save before their next action.

| Action | New State | Resolver | Notes |
|---|---|---|---|
| Any | (resolved from fear test result) | `fear_resolver` | Fear test auto-resolves before action; action queued for next turn |

The fear test result determines whether the character gains a condition in `character_conditions`. After the test, state transitions back to the previous state (usually COMBAT or NARRATIVE).

### From SHOPPING

| Action | New State | Resolver | Notes |
|---|---|---|---|
| SHOP (leave intent) | NARRATIVE | `shop_resolver` | Player says "I leave" / "done" |
| Item buy/sell (handled by shop UI, not free text) | SHOPPING | `shop_resolver` | — |
| Any other | BLOCKED | — | "Jesteś w trakcie handlu. Zakończ lub kup/sprzedaj przedmiot." |

### From RESTING

| Action | New State | Resolver | Notes |
|---|---|---|---|
| ATTACK (enemy appears) | COMBAT | `combat_resolver` | Rest interrupted — partial recovery applied |
| Any other | RESTING | — | "Odpoczywasz. Poczekaj chwilę." (for short rest: 2 turns; long rest: 5 turns) |

Rest completes after N turns (defined per rest type). On completion, state auto-transitions to NARRATIVE and recovery is applied.

---

## Validation Logic Per Action Type

Each validator runs sequentially. The first failing check causes the action to be blocked with a specific system message.

### ATTACK

```python
def validate_attack(session, params):
    # Check 1: Must be in COMBAT state
    if session.state != "COMBAT":
        return Blocked("Nie ma wrogów w pobliżu.")
    
    # Check 2: Target must be specified
    if "target" not in params:
        return Blocked("Musisz wskazać cel ataku.")
    
    # Check 3: Target must exist in combat roster
    target = get_combat_enemy(session, params["target"])
    if target is None:
        return Blocked(f"Cel '{params['target']}' nie istnieje w tej walce.")
    
    # Check 4: Target must be alive
    if target.hp <= 0:
        return Blocked(f"{target.name} jest już martwy/a.")
    
    # Check 5: Weapon must be in inventory if specified
    if "weapon" in params:
        if not character_has_item(session.character_id, params["weapon"]):
            return Blocked(f"Nie masz '{params['weapon']}' w ekwipunku.")
    
    # Check 6: Character must not be stunned
    if has_condition(session.character_id, "stunned"):
        return Blocked("Jesteś ogłuszony/a. Nie możesz atakować w tej turze.")
    
    return Valid(resolver="combat_resolver")
```

### FLEE

```python
def validate_flee(session, params):
    # Check 1: Must be in COMBAT state
    if session.state != "COMBAT":
        return Blocked("Nie ma z czego uciekać.")
    
    # Check 2: Must not be in TERROR condition (terror = must flee, bypass this block)
    # If character has terror condition, FLEE is automatically triggered by WSM
    # on any action — handled in fear_resolver
    
    # Check 3: There must be a reachable exit from current location
    exits = get_location_exits(session.location_key)
    if not exits:
        return Blocked("Nie ma drogi ucieczki z tego miejsca.")
    
    return Valid(resolver="flee_resolver")
```

### DIALOGUE

```python
def validate_dialogue(session, params):
    # Check 1: Must NOT be in COMBAT state
    if session.state == "COMBAT":
        return Blocked("Nie możesz rozmawiać podczas walki.")
    
    # Check 2: NPC key must be specified
    if "npc_key" not in params:
        return Blocked("Wskaż, z kim chcesz rozmawiać.")
    
    # Check 3: NPC must exist in DB
    npc = get_npc(params["npc_key"])
    if npc is None:
        return Blocked(f"NPC '{params['npc_key']}' nie istnieje.")
    
    # Check 4: NPC must be present in current location
    if not npc_in_location(params["npc_key"], session.location_key):
        return Blocked(f"{npc.name} nie jest tutaj.")
    
    # Check 5: NPC must be alive (not a corpse — corpses can be EXAMINE'd)
    if npc.is_dead:
        return Blocked(f"{npc.name} nie żyje. Możesz tylko zbadać ciało.")
    
    # Check 6: NPC must not be in hostile state that prevents dialogue
    if npc.attitude == "hostile" and not npc.accepts_dialogue_when_hostile:
        return Blocked(f"{npc.name} jest wrogi/a i nie chce rozmawiać.")
    
    return Valid(resolver="dialogue_resolver")
```

### MOVEMENT

```python
def validate_movement(session, params):
    # Check 1: Must be in NARRATIVE or RESTING state (RESTING interrupts)
    if session.state == "COMBAT":
        return Blocked("Nie możesz się swobodnie poruszać podczas walki.")
    
    # Check 2: Destination must be specified
    if "destination_key" not in params:
        return Blocked("Wskaż cel podróży.")
    
    # Check 3: Destination must exist in DB
    dest = get_location(params["destination_key"])
    if dest is None:
        return Blocked(f"Lokacja '{params['destination_key']}' nie istnieje.")
    
    # Check 4: Destination must be connected to current location
    if not locations_connected(session.location_key, params["destination_key"]):
        return Blocked(f"Nie można tam dotrzeć z tego miejsca.")
    
    # Check 5: Destination must not be locked (locked = requires key or quest flag)
    if dest.is_locked:
        key_item = dest.unlock_item_key
        if key_item and not character_has_item(session.character_id, key_item):
            return Blocked(f"Przejście jest zablokowane. Potrzebujesz: {key_item}.")
        elif dest.unlock_flag:
            if not session_has_flag(session, dest.unlock_flag):
                return Blocked("Droga jest zablokowana.")
    
    # Check 6: Character must not be prone or wounded_critical (movement penalty)
    # (prone allows movement at half speed — not blocked, but adds a note to narrator)
    if has_condition(session.character_id, "wound_critical"):
        return Blocked("Jesteś zbyt ciężko ranny/a, by się poruszać.")
    
    return Valid(resolver="movement_resolver")
```

### REST

```python
def validate_rest(session, params):
    # Check 1: Must be in NARRATIVE state
    if session.state != "NARRATIVE":
        return Blocked("Nie możesz teraz odpoczywać.")
    
    # Check 2: rest_type must be valid
    rest_type = params.get("rest_type", "short")
    if rest_type not in ("short", "long"):
        return Blocked("Typ odpoczynku musi być 'krótki' lub 'długi'.")
    
    # Check 3: Current location must support the requested rest type
    location = get_location(session.location_key)
    if location.safe_for_rest == 0:
        return Blocked("To miejsce nie jest bezpieczne na odpoczynek.")
    if rest_type == "long" and location.safe_for_rest < 2:
        return Blocked("To miejsce nadaje się tylko na krótki odpoczynek. Długi odpoczynek wymaga bezpiecznego schronienia.")
    
    # Check 4: No active combat (belt-and-suspenders check — state check handles this)
    if any_enemies_alive_in_location(session.location_key):
        return Blocked("W pobliżu są wrogowie. Nie możesz odpoczywać.")
    
    # Check 5: Character must not be in FEAR_TEST_PENDING state
    if session.state == "FEAR_TEST_PENDING":
        return Blocked("Musisz najpierw opanować strach.")
    
    return Valid(resolver="rest_resolver")
```

---

## SYSTEM_MESSAGE Format

When an action is blocked, the WSM returns a SYSTEM_MESSAGE. This is a plain text string — it is NOT processed by the LLM and NOT narrated. It is sent directly to the player as a UI system message, visually distinct from narrative text.

**Format rules:**
- Always in Polish
- Short — 1-2 sentences maximum
- States what is not possible and (if applicable) what is possible instead
- No flavor text, no adjectives about atmosphere

**Examples:**
```
Nie możesz rozmawiać podczas walki.
Nie ma z czego uciekać.
To miejsce nie jest bezpieczne na odpoczynek. Szukaj schronienia.
{NPC_NAME} nie żyje. Możesz tylko zbadać ciało.
Cel '{target_key}' nie istnieje w tej walce.
Jesteś ogłuszony/a. Nie możesz atakować w tej turze.
```

---

## State Storage in `session_flags`

The full state object stored in `game_sessions.session_flags` JSON:

```json
{
  "state": "COMBAT",
  "state_entered_at_turn": 22,
  "previous_state": "NARRATIVE",
  
  "combat_roster": [
    {"key": "goblin_1", "name": "Goblin Strażnik", "hp": 8, "hp_max": 20, "initiative": 14},
    {"key": "goblin_2", "name": "Goblin Szaman", "hp": 18, "hp_max": 18, "initiative": 9}
  ],
  "combat_turn_order": ["character", "goblin_1", "goblin_2"],
  "combat_current_turn_index": 0,
  
  "pending_test": null,
  
  "fear_test_pending": null,
  
  "death_save_successes": 0,
  "death_save_failures": 0,
  
  "rest_type_in_progress": null,
  "rest_turns_remaining": 0,
  
  "loot_available": true,
  "last_combat_loot_id": null
}
```

The WSM reads and writes this object on every turn. It is the authoritative source of combat state.

---

## Routing

After validation passes, the WSM returns a `RouteResult` with the correct resolver identifier. The game engine then calls the appropriate resolver service.

```python
@dataclass
class WSMResult:
    valid: bool
    blocked_message: str | None   # Polish system message if blocked
    resolver_key: str | None      # e.g. "combat_resolver", "dialogue_resolver"
    new_state: str | None         # state to transition to before calling resolver
    state_flags_update: dict      # partial update to apply to session_flags
```

**Resolver registry** (in `world_state_machine.py`):

```python
RESOLVER_REGISTRY = {
    "combat_resolver":         "backend.app.services.combat_service.CombatResolver",
    "flee_resolver":           "backend.app.services.combat_service.FleeResolver",
    "combat_stealth_resolver": "backend.app.services.combat_service.CombatStealthResolver",
    "dialogue_resolver":       "backend.app.services.npc_service.DialogueResolver",
    "movement_resolver":       "backend.app.services.location_service.MovementResolver",
    "search_resolver":         "backend.app.services.location_service.SearchResolver",
    "examine_resolver":        "backend.app.services.location_service.ExamineResolver",
    "item_resolver":           "backend.app.services.inventory_service.ItemResolver",
    "skill_resolver":          "backend.app.services.mechanics_service.SkillResolver",
    "shop_resolver":           "backend.app.services.shop_service.ShopResolver",
    "rest_resolver":           "backend.app.services.mechanics_service.RestResolver",
    "death_save_resolver":     "backend.app.services.mechanics_service.DeathSaveResolver",
    "fear_resolver":           "backend.app.services.mechanics_service.FearResolver",
}
```

---

## Example End-to-End Flow

**Input:** Player types "I attack the goblin"

1. Intent Parser produces: `[ACTION:ATTACK:target=goblin_1:weapon=sword_iron]`

2. WSM receives: `action_type=ATTACK`, `params={"target": "goblin_1", "weapon": "sword_iron"}`

3. WSM reads `session_flags.state = "COMBAT"` → passes Check 1

4. WSM reads combat_roster → finds `goblin_1` with `hp=8` → passes Checks 2, 3, 4

5. WSM checks inventory → character has `sword_iron` → passes Check 5

6. WSM checks conditions → no `stunned` condition → passes Check 6

7. WSM returns:
```python
WSMResult(
    valid=True,
    blocked_message=None,
    resolver_key="combat_resolver",
    new_state="COMBAT",  # no state change
    state_flags_update={}
)
```

8. Game engine calls `combat_resolver.resolve(session, parsed_intent)`

9. Combat resolver rolls dice, applies damage, checks for enemy death

10. If goblin dies → WSM called again internally to check if all enemies dead → if yes, transitions state to NARRATIVE

---

**Input:** Player types "I want to sleep" in the dungeon (location `safe_for_rest=0`)

1. Intent Parser produces: `[ACTION:REST:rest_type=long]`

2. WSM reads `session_flags.state = "NARRATIVE"` → passes Check 1

3. WSM reads location DB → `safe_for_rest = 0` → BLOCKED

4. WSM returns:
```python
WSMResult(
    valid=False,
    blocked_message="To miejsce nie jest bezpieczne na odpoczynek. Szukaj schronienia.",
    resolver_key=None,
    new_state=None,
    state_flags_update={}
)
```

5. Game engine sends system message directly to player. No LLM call.

---

**Input:** Player types "I talk to the blacksmith" but the blacksmith is in a different location

1. Intent Parser produces: `[ACTION:DIALOGUE:npc_key=blacksmith_aldric]`

2. WSM checks `session_flags.state = "NARRATIVE"` → passes Check 1

3. WSM looks up `blacksmith_aldric` in DB → found → passes Check 3

4. WSM checks `npc_in_location("blacksmith_aldric", "loc_forest_clearing")` → NOT in this location → BLOCKED

5. WSM returns blocked message: `"Aldric Kowal nie jest tutaj."`

---

## Service Structure (`world_state_machine.py`)

```python
class WorldStateMachine:
    def validate_and_route(
        self,
        session: GameSession,
        parsed_intent: ParsedIntent
    ) -> WSMResult:
        """Main entry point. Validates action against current state, routes to resolver."""
        
        # 1. Get current state
        state = self._get_state(session)
        
        # 2. Check if action is valid in this state at all (state-level check)
        state_check = self._check_state_allows_action(state, parsed_intent.action_type)
        if not state_check.valid:
            return WSMResult(valid=False, blocked_message=state_check.message, ...)
        
        # 3. Run action-specific validator
        validator = self._get_validator(parsed_intent.action_type)
        validation_result = validator(session, parsed_intent.params)
        if not validation_result.valid:
            return WSMResult(valid=False, blocked_message=validation_result.message, ...)
        
        # 4. Determine resolver and state transition
        resolver_key, new_state, flags_update = self._route(state, parsed_intent.action_type, parsed_intent.params)
        
        return WSMResult(
            valid=True,
            blocked_message=None,
            resolver_key=resolver_key,
            new_state=new_state,
            state_flags_update=flags_update
        )
    
    def transition_state(self, session: GameSession, new_state: str, flags_update: dict) -> None:
        """Apply a state transition to session_flags. Called by game_engine after resolve."""
        ...
    
    def handle_enemy_turn(self, session: GameSession) -> EnemyTurnResult:
        """Process enemy actions in combat. Reads enemy_behavior_profiles."""
        ...
```

---

## Enemy Turn Resolution

After the player's action resolves in COMBAT state, the WSM handles enemy turns automatically. This is a WSM responsibility because enemy behavior is rule-based, not LLM-generated.

```python
def handle_enemy_turn(self, session: GameSession) -> EnemyTurnResult:
    results = []
    for enemy in session.combat_roster:
        if enemy.hp <= 0:
            continue
        
        profile = get_behavior_profile(enemy.key)
        if profile is None:
            # Default behavior: attack character
            action = "attack"
        else:
            # Check flee threshold
            if profile.hp_threshold_flee > 0:
                hp_pct = (enemy.hp / enemy.hp_max) * 100
                if hp_pct <= profile.hp_threshold_flee:
                    action = "flee"
                else:
                    action = profile.default_action
            else:
                action = profile.default_action
            
            # Check special ability cooldown
            if action == "use_special":
                if enemy.special_ability_cooldown_remaining > 0:
                    action = "attack"  # fall back
        
        result = self._resolve_enemy_action(session, enemy, action, profile)
        results.append(result)
    
    return EnemyTurnResult(actions=results)
```

Enemy turn results are included in the `mechanic_result` that gets passed to the Context Injector — they appear in the narrator's MECHANICAL RESULT BLOCK so the narrator describes what the enemies did.

---

## Edge Cases

1. **State desync:** `session_flags.state = "COMBAT"` but `combat_roster` is empty (e.g., crash during combat cleanup). WSM must detect this and auto-heal: if state is COMBAT but roster has no living enemies, force-transition to NARRATIVE and log a warning. Do not surface this as an error to the player.

2. **Multiple pending states:** Can a character be in `FEAR_TEST_PENDING` and `SKILL_TEST_PENDING` simultaneously? No — only one special pending state is allowed. If a second pending state is triggered while one is active, queue it in `session_flags.pending_queue` and resolve them in FIFO order.

3. **NPC becomes dead mid-dialogue:** If an NPC is killed during a scene (e.g., enemy NPC in combat), and the player had been in dialogue with them, the dialogue state must be cleared on death. The combat resolver must call `wsm.clear_dialogue_state(npc_key)` on NPC death.

4. **Location locked with no key item defined:** `dest.is_locked = True` but `dest.unlock_item_key = None` and `dest.unlock_flag = None`. This is a data integrity error. WSM returns a generic "Droga jest zablokowana." and logs a data error — do not crash.

5. **FLEE with no exits:** The validator checks for exits before allowing FLEE. But the flee_resolver should also handle the edge case of all exits becoming blocked mid-resolution (rare race condition). If flee_resolver finds no exit, it falls back to: character hides in current location (STEALTH_ATTEMPT, DC 18) as a last resort.

6. **Enemy behavior profile references missing special_ability_key:** If `profile.special_ability_key` is set but the key doesn't exist in `game_config_skills`, log an error and fall back to `attack`. Do not crash the turn.

7. **DEATH_SAVE_PENDING — any action triggers auto-death-save:** If the player types "I attack" while in DEATH_SAVE_PENDING, the WSM ignores the ATTACK and auto-resolves a death save. The player's intended action is lost. This must be communicated clearly: "Jesteś nieprzytomny/a. Musisz wykonać rzut na śmierć." The action is not queued.

8. **Condition check for ATTACK (stunned):** The `stunned` condition expires after 1 turn. The WSM must check whether the condition has expired (compare `expires_at` turn number vs current turn) before blocking. If it expired this turn, allow the attack and mark the condition inactive.

9. **REST interrupted by combat (RESTING → COMBAT):** When an enemy attacks during rest, the WSM must:
   - Apply partial rest recovery (50% of full rest benefits if >50% of rest duration completed, 0% otherwise)
   - Clear `rest_type_in_progress` from session_flags
   - Transition to COMBAT state
   - Add the enemy to combat_roster
   - Return a system message: "Odpoczynek przerwany! Wrogowie atakują."

10. **SHOPPING state with ATTACK:** If the player is in SHOPPING state and types "attack the shopkeeper", the WSM blocks with "Jesteś w trakcie handlu. Najpierw zakończ transakcję." The shopkeeper cannot be attacked from within the shopping state — this prevents game-breaking exploits. The player must leave shopping state first, then attempt ATTACK.

---

## Test Checklist

For each test, define the initial `session_flags` state, the input ACTION tag, and the expected WSM output (Valid+resolver or Blocked+message).

### State Enforcement Tests

- [ ] ATTACK in NARRATIVE state → Blocked "Nie ma wrogów w pobliżu."
- [ ] FLEE in NARRATIVE state → Blocked "Nie ma z czego uciekać."
- [ ] DIALOGUE in COMBAT state → Blocked "Nie możesz rozmawiać podczas walki."
- [ ] MOVEMENT in COMBAT state → Blocked "Nie możesz się swobodnie poruszać podczas walki."
- [ ] REST in COMBAT state → Blocked "Nie możesz odpoczywać podczas walki."
- [ ] SHOP in COMBAT state → Blocked "Nie możesz handlować podczas walki."

### Validation Tests

- [ ] ATTACK target=dead_enemy → Blocked "{enemy.name} jest już martwy/a."
- [ ] ATTACK target=nonexistent_key → Blocked "Cel '{key}' nie istnieje w tej walce."
- [ ] ATTACK with stunned condition (active) → Blocked "Jesteś ogłuszony/a."
- [ ] ATTACK with stunned condition (expired this turn) → Valid → combat_resolver
- [ ] DIALOGUE with NPC not in current location → Blocked "{name} nie jest tutaj."
- [ ] DIALOGUE with dead NPC → Blocked "{name} nie żyje."
- [ ] MOVEMENT to unreachable destination → Blocked "Nie można tam dotrzeć z tego miejsca."
- [ ] MOVEMENT to locked location without key → Blocked "Przejście jest zablokowane."
- [ ] REST in unsafe location (safe_for_rest=0) → Blocked "To miejsce nie jest bezpieczne."
- [ ] REST (long) in short-rest-only location (safe_for_rest=1) → Blocked "To miejsce nadaje się tylko na krótki odpoczynek."
- [ ] REST with enemies alive in location → Blocked "W pobliżu są wrogowie."

### Routing Tests

- [ ] ATTACK valid in COMBAT → resolver=combat_resolver, state unchanged
- [ ] FLEE valid in COMBAT → resolver=flee_resolver
- [ ] DIALOGUE valid in NARRATIVE → resolver=dialogue_resolver
- [ ] REST valid (short) in safe location → resolver=rest_resolver, new_state=RESTING
- [ ] SHOP valid with merchant NPC present → resolver=shop_resolver, new_state=SHOPPING

### State Transition Tests

- [ ] All enemies die in COMBAT → state auto-transitions to NARRATIVE
- [ ] FLEE success → state transitions to NARRATIVE
- [ ] FLEE failure → state remains COMBAT, character takes opportunity attack
- [ ] REST (short) completes (2 turns elapsed) → state auto-transitions to NARRATIVE
- [ ] DEATH_SAVE 3 successes → state transitions to NARRATIVE, character at 1 HP
- [ ] DEATH_SAVE 3 failures → character DEAD

### Enemy Turn Tests

- [ ] Enemy with `hp_threshold_flee=25` at 20% HP → action=flee
- [ ] Enemy with `default_action=use_special` at 60% HP, cooldown=0 → action=use_special
- [ ] Enemy with `default_action=use_special` at 60% HP, cooldown=2 remaining → action=attack (fallback)
- [ ] Enemy with `fear_aura=1` → character WIS save triggered at combat start
- [ ] Enemy with no behavior profile → default action=attack character
