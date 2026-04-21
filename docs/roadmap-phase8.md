# Phase 8 — Combat System

> Status: IN PROGRESS
> Split: 8A (Backend Combat Engine) | 8B (Frontend Combat UI)
> Last updated: 2026-04-20

---

## Pre-conditions (already completed ✅)

| Asset | Details |
|---|---|
| 25 enemies in DB | weak/standard/elite/boss — HP, DEF, attack_bonus, damage |
| 10 weapons in DB | melee/ranged/spell — damage_dice, stat |
| 7 conditions | poisoned, blinded, stunned, burning, frightened, bleeding, cursed |
| Loot tables | loot_table_key + drop_chance on enemies, resolve_enemy_loot() in game_engine.py |
| XP awards/costs | D-XP-01/02 imported |
| Phase 7.6 death save | logic in game_engine.py — DO NOT modify |

---

## Phase 8A — Backend Combat Engine

**Goal:** active_combat persistent state + resolution engine. No frontend changes.

### Step 1 — DB Migration: `014_active_combat.sql`

File: `backend/app/db/migrations/014_active_combat.sql`

```sql
CREATE TABLE IF NOT EXISTS active_combat (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  campaign_id INTEGER NOT NULL UNIQUE,
  character_id INTEGER NOT NULL,
  round INTEGER NOT NULL DEFAULT 1,
  turn_order TEXT NOT NULL,         -- JSON: ["player", "enemy_slug_1", "enemy_slug_2"]
  current_turn TEXT NOT NULL,       -- "player" or enemy key
  combatants TEXT NOT NULL,         -- JSON array (see schema below)
  status TEXT NOT NULL DEFAULT 'active',  -- active | ended
  ended_reason TEXT,                -- "victory" | "fled" | "player_dead"
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);
```

**Combatants JSON schema:**
```json
[
  {
    "id": "player",
    "type": "player",
    "name": "Aldric",
    "hp_current": 14,
    "hp_max": 14,
    "defense": 15,
    "initiative_roll": 17,
    "conditions": []
  },
  {
    "id": "bandit_01",
    "type": "enemy",
    "enemy_key": "bandit",
    "name": "Bandit",
    "hp_current": 12,
    "hp_max": 12,
    "defense": 13,
    "attack_bonus": 3,
    "damage_dice": "1d8",
    "damage_stat": "STR",
    "initiative_roll": 11,
    "conditions": [],
    "loot_table_key": "bandit_loot",
    "drop_chance": 0.75
  }
]
```

---

### Step 2 — CombatService: `backend/app/services/combat_service.py`

**Methods:**

| Method | Signature | Notes |
|---|---|---|
| `get_active_combat` | `(campaign_id) -> dict \| None` | Return None if no active combat |
| `initiate_combat` | `(campaign_id, character_id, enemy_keys: list[str]) -> dict` | Roll initiative d20+DEX, sort desc (ties: player first), insert row |
| `resolve_attack` | `(campaign_id, roll_result: int, attacker: str = "player") -> dict` | Hit = roll >= defense; apply damage; trigger loot on enemy death; trigger death save on player death |
| `advance_turn` | `(campaign_id) -> str` | Next living combatant; increment round on cycle; auto-end on all enemies dead |
| `end_combat` | `(campaign_id, reason: str)` | Set status="ended", update updated_at |
| `get_combat_context_for_prompt` | `(campaign_id) -> str \| None` | Returns compact text block for GM system prompt injection |

**Combat context block format (injected into GM prompt):**
```
== ACTIVE COMBAT (Round {n}) ==
Turn: {current_turn}
Combatants:
- Aldric: HP {x}/{max}, DEF {d}, Conditions: []
- Bandit: HP {x}/{max}, DEF {d}
Rules: player attacks first if it's their turn. Enemy attacks automatically after player turn.
DO NOT invent HP values. Read only from this block.
```

**resolve_attack — player attacker:**
- Target = first living enemy in turn_order
- hit = roll_result >= enemy.defense
- if hit: roll damage_dice + STR/DEX mod from sheet_json
- Apply to enemy hp_current
- If enemy hp_current <= 0: mark dead, call resolve_enemy_loot()
- Return: `{ hit, damage, target_name, target_hp_remaining, enemy_dead, loot }`

**resolve_attack — enemy attacker:**
- Roll d20 + enemy.attack_bonus
- hit = attack_roll >= player.defense
- if hit: roll enemy damage_dice (no stat mod — keep simple)
- Apply to player hp_current in combat state AND in sheet_json
- If player hp_current <= 0: trigger Phase 7.6 death save
- Return: `{ hit, damage, attack_roll, player_hp_remaining, player_incapacitated }`

---

### Step 3 — Inject combat context into GM prompt

In `backend/app/services/game_engine.py`, where system prompt/context is assembled:
- Call `CombatService.get_combat_context_for_prompt(campaign_id)`
- If not None, append combat block to system prompt **BEFORE** game state injection

---

### Step 4 — Combat initiation hook

In turn processing flow, after parsing roll cues:
- Check if GM response contains `"Roll Initiative d20"`
- If yes AND no active_combat for campaign:
  - Extract enemy_keys via manual match against enemies table (NO free-text guessing)
  - Call `CombatService.initiate_combat()`
  - Append to turn response: `{ ..., "combat_initiated": true, "combat_state": { ... } }`

---

### Step 5 — New API endpoints: `backend/app/routes/combat.py`

| Method | Endpoint | Body | Action |
|---|---|---|---|
| POST | `/api/campaigns/{id}/combat/start` | `{ "enemy_keys": [...] }` | initiate_combat() — manual start |
| GET | `/api/campaigns/{id}/combat` | — | active combat state or 404 |
| POST | `/api/campaigns/{id}/combat/resolve-attack` | `{ "roll_result": 14, "attacker": "player" }` | resolve_attack() |
| POST | `/api/campaigns/{id}/combat/enemy-turn` | — | resolve_attack(enemy) + advance_turn() |
| POST | `/api/campaigns/{id}/combat/flee` | — | end_combat("fled") |

---

### Step 6 — Wire loot on enemy death

In `resolve_attack()`, when enemy hp_current <= 0:
- Call `resolve_enemy_loot(enemy)` from `game_engine.py`
- Include loot result in return payload

---

### Step 7 — Tests: `backend/tests/test_phase8_combat.py`

| Test | Expected |
|---|---|
| initiate_combat | combatants created, initiative sorted, turn_order correct |
| resolve_attack hit | damage applied, enemy hp reduced |
| resolve_attack miss | enemy hp unchanged |
| enemy death | combat status="ended", ended_reason="victory", loot rolled |
| player hit | sheet_json hp_current updated |
| advance_turn | cycles correctly, round incremented |
| flee | status="ended", reason="fled" |
| get_combat_context_for_prompt | returns non-empty string |

**All tests must pass before Phase 8B.**

---

## Phase 8B — Frontend Combat UI

High-level scope (implemented/planned from Roadmap 8.6–8.10):
- Combat panel component: HP bars (player + enemies), round/turn indicator
- Action buttons: Atak / Ucieczka / Przedmiot
- Roll dice trigger → send roll_result to `/combat/resolve-attack`
- Enemy turn auto-trigger after player resolves
- Victory / defeat screen with loot display
- Conditions display (poisoned, stunned, etc.)
- Auto-load active combat on page refresh with `GET /combat`

---

## Phase 8 Manual Test Checklist

> Intended for playtesting in Notion or roadmap docs. Mark each item with: `Not tested` / `Tested` / `Pass` / `Fail`.

### S1 — Combat Start

| ID | Scenario | Trigger / Action | Expected | Status |
|---|---|---|---|---|
| **S1-01** | Start combat vs 2 bandits | `POST /combat/start {"enemy_keys": ["bandit", "bandit"]}` | Combat starts, 3 combatants exist, panel appears, turn order valid | Not tested |
| **S1-02** | Start combat again in same campaign | Call `/combat/start` again during/after previous combat | Old combat row replaced, no SQL UNIQUE error | Not tested |
| **S1-03** | Start combat with invalid enemy | `POST /combat/start {"enemy_keys": ["dragon_ancient"]}` | API returns 400 `unknown enemy key` | Not tested |
| **S1-04** | Reload page during active combat | Refresh browser during active fight | Combat panel reloads from `GET /combat` and keeps state | Not tested |

### S2 — Player Turn

| ID | Scenario | Trigger / Action | Expected | Status |
|---|---|---|---|---|
| **S2-01** | Player attack hits | Click **Atak**, roll high enough to beat enemy DEF | Message `Trafienie!`, enemy HP decreases | Not tested |
| **S2-02** | Player attack misses | Click **Atak**, low roll | Message `Pudło!`, enemy HP unchanged | Not tested |
| **S2-03** | Attack button locked on enemy turn | Wait until `current_turn != "player"` | **Atak** and **Ucieczka** buttons disabled, ENEMY TURN overlay visible | Not tested |
| **S2-04** | Player kills first of two enemies | Start 2-enemy fight, kill one enemy | Loot popup for first enemy, second enemy remains active | Not tested |

### S3 — Enemy Turn

| ID | Scenario | Trigger / Action | Expected | Status |
|---|---|---|---|---|
| **S3-01** | Enemy attack hits player | Let enemy turn resolve | Message `Cios!`, player HP decreases in UI and sheet | Not tested |
| **S3-02** | Enemy attack misses player | Let enemy turn resolve with miss | Message `Atak chybił!`, player HP unchanged | Not tested |
| **S3-03** | Multiple enemy turns chain correctly | Fight against 2 enemies | All enemy turns resolve in correct order before player turn returns | Not tested |
| **S3-04** | Enemy-turn called on wrong turn | Trigger `/combat/enemy-turn` while `current_turn == "player"` | No HP change, guard behavior handled safely | Not tested |

### S4 — Loot and Victory

| ID | Scenario | Trigger / Action | Expected | Status |
|---|---|---|---|---|
| **S4-01** | Kill final enemy | Defeat last living enemy | Combat ends with `victory`, victory screen appears | Not tested |
| **S4-02** | Loot popup shows loot | Kill enemy with drops | Popup lists item(s), dismiss works | Not tested |
| **S4-03** | Loot popup shows empty state | Kill enemy with no loot | Popup shows `Wróg nie miał łupów.` | Not tested |
| **S4-04** | Victory screen accumulates all loot | Kill multiple enemies with drops | Victory screen lists combined loot from the fight | Not tested |

### S5 — Defeat and Death Save

| ID | Scenario | Trigger / Action | Expected | Status |
|---|---|---|---|---|
| **S5-01** | Player reduced to 0 HP | Lower player HP, then let enemy hit | `player_dead` state, defeat overlay visible | Not tested |
| **S5-02** | Death save prompt triggers | Reach `player_dead` state | Existing Phase 7.6 death save UI/button appears | Not tested |
| **S5-03** | HP bar color thresholds | Damage player above 50%, then 25–50%, then below 25% | HP bar changes green → yellow → red | Not tested |

### S6 — Flee

| ID | Scenario | Trigger / Action | Expected | Status |
|---|---|---|---|---|
| **S6-01** | Flee from active combat | Click **Ucieczka** | Panel hides, message `Udało ci się uciec!`, combat ends with `fled` | Not tested |
| **S6-02** | Flee without active combat | `POST /combat/flee` when no combat exists | API returns 404 | Not tested |

### S7 — Prompt / Persistence / Safety

| ID | Scenario | Trigger / Action | Expected | Status |
|---|---|---|---|---|
| **S7-01** | Combat context in GM prompt | Send a normal turn during active combat | Prompt contains `ACTIVE COMBAT` block with current HP data | Not tested |
| **S7-02** | No combat context after end | End combat, then send next narrative turn | No combat block injected into prompt | Not tested |
| **S7-03** | Missing `active_combat` table fallback | Use DB/environment without migration | Narrative works, no crash, no combat state returned | Not tested |

---

## Notion Paste Template

Copy this block into Notion and convert to a table if needed:

```text
ID | Scenario | Trigger / Action | Expected | Status | Notes
S1-01 | Start combat vs 2 bandits | POST /combat/start {"enemy_keys": ["bandit", "bandit"]} | Combat starts, 3 combatants exist, panel appears, turn order valid | Not tested |
S1-02 | Start combat again in same campaign | Call /combat/start again during/after previous combat | Old combat row replaced, no SQL UNIQUE error | Not tested |
S1-03 | Start combat with invalid enemy | POST /combat/start {"enemy_keys": ["dragon_ancient"]} | API returns 400 unknown enemy key | Not tested |
S1-04 | Reload page during active combat | Refresh browser during active fight | Combat panel reloads from GET /combat and keeps state | Not tested |
S2-01 | Player attack hits | Click Atak, roll high enough to beat enemy DEF | Message Trafienie!, enemy HP decreases | Not tested |
S2-02 | Player attack misses | Click Atak, low roll | Message Pudło!, enemy HP unchanged | Not tested |
S2-03 | Attack button locked on enemy turn | Wait until current_turn != player | Atak and Ucieczka disabled, ENEMY TURN overlay visible | Not tested |
S2-04 | Player kills first of two enemies | Start 2-enemy fight, kill one enemy | Loot popup for first enemy, second enemy remains active | Not tested |
S3-01 | Enemy attack hits player | Let enemy turn resolve | Message Cios!, player HP decreases in UI and sheet | Not tested |
S3-02 | Enemy attack misses player | Let enemy turn resolve with miss | Message Atak chybił!, player HP unchanged | Not tested |
S3-03 | Multiple enemy turns chain correctly | Fight against 2 enemies | All enemy turns resolve in correct order before player turn returns | Not tested |
S3-04 | Enemy-turn called on wrong turn | Trigger /combat/enemy-turn while current_turn == player | No HP change, guard behavior handled safely | Not tested |
S4-01 | Kill final enemy | Defeat last living enemy | Combat ends with victory, victory screen appears | Not tested |
S4-02 | Loot popup shows loot | Kill enemy with drops | Popup lists item(s), dismiss works | Not tested |
S4-03 | Loot popup shows empty state | Kill enemy with no loot | Popup shows Wróg nie miał łupów. | Not tested |
S4-04 | Victory screen accumulates all loot | Kill multiple enemies with drops | Victory screen lists combined loot from the fight | Not tested |
S5-01 | Player reduced to 0 HP | Lower player HP, then let enemy hit | player_dead state, defeat overlay visible | Not tested |
S5-02 | Death save prompt triggers | Reach player_dead state | Existing Phase 7.6 death save UI/button appears | Not tested |
S5-03 | HP bar color thresholds | Damage player above 50%, then 25–50%, then below 25% | HP bar changes green → yellow → red | Not tested |
S6-01 | Flee from active combat | Click Ucieczka | Panel hides, message Udało ci się uciec!, combat ends with fled | Not tested |
S6-02 | Flee without active combat | POST /combat/flee when no combat exists | API returns 404 | Not tested |
S7-01 | Combat context in GM prompt | Send a normal turn during active combat | Prompt contains ACTIVE COMBAT block with current HP data | Not tested |
S7-02 | No combat context after end | End combat, then send next narrative turn | No combat block injected into prompt | Not tested |
S7-03 | Missing active_combat table fallback | Use DB/environment without migration | Narrative works, no crash, no combat state returned | Not tested |
```

---

## Constraints (both phases)

- ❌ DO NOT break existing turn flow, dice routes, or death save logic (Phase 7.6)
- ❌ DO NOT add multiplayer combat (solo only)
- ❌ DO NOT auto-detect enemy names from GM free text
- ❌ DO NOT implement frontend in Phase 8A
