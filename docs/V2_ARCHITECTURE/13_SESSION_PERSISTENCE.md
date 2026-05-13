# AI-GM V2 — Session Persistence

> What happens when a player disconnects and reconnects.
> Core principle: the game state is a DB snapshot that waits. Real-world time is irrelevant.

---

## Decisions Made

| Situation | Behaviour |
|-----------|-----------|
| HP on reconnect | Exactly as left — no automatic recovery |
| Combat on reconnect | Resume exactly at same initiative slot, enemies at same HP |
| Conditions on reconnect | Exactly as left — rounds only tick during combat turns, not real time |
| In-game time offline | Does NOT advance — time only moves on explicit actions |
| Rest prompt on reconnect | Soft prompt if: HP < 75% AND in safe_for_rest location AND no combat |
| Time display on reconnect | Show last in-game time unchanged |

---

## Design Rationale

In-game time and real-world time are completely disconnected by design.

A player might:
- Write 2-3 narrative turns, then go make dinner and come back
- Leave mid-combat to take a phone call
- Go to sleep after exploring a dungeon corridor
- Play for 5 minutes or 3 hours in one sitting

In all cases: the game state is exactly as they left it. Nothing happens "while they were away." The game world is paused, not simulated.

This means:
- Bleeding doesn't tick down in real time
- FRIGHTENED doesn't expire while you're away
- Enemies don't move or act
- In-game time doesn't advance
- Dungeon cooldowns only count in-game hours (earned through play, not waiting)

---

## Reconnect Flow

### 1. Load State

On page load / reconnect, the frontend fetches current state:

```
GET /api/campaigns/{id}/session-state

Returns:
  character: { hp, max_hp, mana, conditions, location }
  combat: { active: bool, round, current_actor, enemies[] }
  ingame_time: { hours, period }
  pending_xp: int
```

### 2. Determine Reconnect Banner

```python
def get_reconnect_context(character, combat, location):
    if combat.active:
        return {
            "type": "combat_resume",
            "message": f"Byłeś w trakcie walki! Runda {combat.round}.",
            "action": "resume_combat"
        }
    
    if character.hp < (character.max_hp * 0.75) and location.safe_for_rest:
        return {
            "type": "rest_suggestion",
            "message": f"{character.name} jest ranny. {location.label} jest bezpieczna.",
            "options": ["rest", "continue"]
        }
    
    return {"type": "normal", "message": None}
```

### 3. Show Reconnect UI

**If mid-combat:**
```
⚔️ 'Byłeś w trakcie walki!'
   Runda 2 | Twoja tura
   Goblin: 6/12 HP

   [Kontynuuj walkę]
```
Banner auto-dismisses after 3 seconds. Combat panel shows automatically.

**If injured in safe location:**
```
💤 'Aldric jest ranny.
    Karczma jest bezpieczna.'

   [Odpocznij]  [Kontynuuj]
```
Stays until player chooses. Clicking [Odpocznij] triggers a long rest if conditions allow.

**Normal reconnect (full HP or no safe location):**
No banner. Game resumes exactly as left. In-game time shown in header as normal.

---

## State That IS Preserved (DB-backed)

Everything in the DB is fully preserved across sessions:

| State | Where stored |
|-------|-------------|
| HP / Mana | `characters.sheet_json` |
| Active conditions | `character_conditions` table |
| Current location | `game_sessions.current_location_id` |
| Active combat | `active_combat` table |
| Combat turn order | `active_combat.combatants` JSON |
| In-game time | `game_sessions.ingame_hours` |
| Inventory | `character_inventory` table |
| Campaign plan progress | `campaigns.gm_plan_json` |
| Pending XP | `character_xp_grants` (pending flag) |
| Loot availability | `combat_loot` table |
| Visited locations | `characters.visited_location_keys` |
| Short rest counter | `game_sessions.session_flags.short_rest_count` |
| Death save counter | `game_sessions.session_flags.death_save_state` |

---

## State That Is NOT Preserved (frontend-only)

| State | Behaviour on reconnect |
|-------|----------------------|
| Chat scroll position | Resets to bottom (latest message) |
| Open/closed panels | Resets to default layout |
| Pending text in input | Cleared (not saved) |
| Active animations | Not restored (static state shown instead) |
| Debug panel state | Resets to closed |

---

## Conditions Offline — No Tick

Condition duration is measured in **combat rounds**, not real time.

```
Log off state:
  BLEEDING: 2 rounds remaining
  FRIGHTENED: 1 round remaining

After 3 real-world hours offline:

Reconnect state:
  BLEEDING: 2 rounds remaining  ← unchanged
  FRIGHTENED: 1 round remaining ← unchanged
```

Rounds only tick when a combatant actually takes their turn. No ticking happens in the DB automatically. The `character_conditions` table is updated only by the Mechanic Resolver during turn processing.

---

## Mid-Combat Reconnect Detail

Combat is fully deterministic from DB state. The `active_combat` record contains:
- All combatant HP values
- Initiative order (locked at combat start)
- Current actor slot
- Round number
- Death save state (if applicable)
- Pending enemy turns

On reconnect mid-combat:
- Load `active_combat` record
- Show combat panel with current state
- If `current_actor = player` → show action buttons
- If `current_actor = enemy` → auto-fire enemy turns (they were waiting)

The only special case: if the player disconnected during an **enemy auto-turn** (backend was processing), the enemy turn may or may not have completed. The backend should:
1. Check if `current_actor = enemy` on reconnect
2. If yes: complete the pending enemy turns, then hand control to player
3. Return complete round result to frontend

---

## In-Game Time

```
Time at log-off: 14:30 (Afternoon)
Real time elapsed: 3 hours
Time on reconnect: 14:30 (Afternoon) ← unchanged
```

Time advances ONLY through explicit actions:
- Travel: `+connection.travel_hours`
- Short rest: `+1 hour`
- Long rest: `+8 hours`
- Rest on road: `+1 hour extra during travel`

The GM narrator always receives the current in-game time. After a long rest, the header shows the updated time ("08:00, Rano").

---

## Test Checklist

- [ ] Log off at 3/12 HP → reconnect → still 3/12 HP
- [ ] Log off with BLEEDING (2 rounds) → reconnect → still BLEEDING (2 rounds)
- [ ] Log off mid-combat → reconnect → combat panel shows, same round/turn
- [ ] Log off (injured, in tavern) → reconnect → soft prompt appears
- [ ] Log off (full HP) → reconnect → no prompt
- [ ] Log off (injured, in dungeon) → reconnect → no prompt (not safe_for_rest)
- [ ] [Odpocznij] on reconnect prompt → long rest executes normally
- [ ] In-game time unchanged after 8 real hours offline
- [ ] Pending XP preserved across reconnect
- [ ] Loot availability preserved (partial loot still claimable if location unchanged)
