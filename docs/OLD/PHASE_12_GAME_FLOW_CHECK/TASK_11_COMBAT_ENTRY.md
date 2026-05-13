# TASK 11 — Combat Entry Cleanup

**Status:** 🔶 Partially Built
**Blocking:** None — spec complete
**Depends on:** Nothing (cleanup of existing system)
**Unlocks:** Task 12 (Combat Round Flow builds on clean entry)

---

## Overview

Combat entry currently has two parallel paths:
1. GM emits `[COMBAT_START:enemy_keys]` tag in narrative (auto-detection)
2. Player uses `/atak <enemy>` command (manual)

Decision D21: **single path only** — the `[COMBAT_START]` tag. The `/atak` command is removed from player-facing UI. Additionally, enemy keys used in the tag must be validated against the DB — the GM cannot invent enemy keys that don't exist.

---

## Design Context

### Why remove `/atak`?
Having two paths for the same action creates inconsistency. Players figure out that `/atak` bypasses GM narrative, leading to people using it to skip ambushes or narrative build-up. It also means combat can start in a state that the GM didn't set up narratively — the combat panel appears without context.

With only the `[COMBAT_START]` path, every combat begins with GM narration that frames the fight. The player doesn't trigger combat directly — their narrative action (or GM event) triggers it, and the GM wraps it in story.

### Why validate enemy keys against DB?
If the LLM invents an enemy key not in `game_config_enemies`, the combat system will fail or create an empty combatant. Validation at the point of `[COMBAT_START]` tag detection means any unknown key either:
- Maps to an existing enemy (fuzzy match by name)
- Creates a pending_review enemy entry
- Falls back to a generic tier-appropriate enemy

This prevents silent failures mid-combat.

---

## Current State (Code)

**`[COMBAT_START]` path:**
- `COMBAT_START_RE = re.compile(r"\[COMBAT_START:([^\]]+)\]", re.IGNORECASE)` in turns.py
- `_maybe_start_combat_from_gm_tag()` — handles tag detection and calls `combat.init_combat()`
- Enemy keys available to LLM: `bandit, goblin, orc, skeleton, wolf, troll, guard, old_man, unknown_attacker, enemy` (hardcoded in system_prompt.txt line 56)

**`/atak` path:**
- Command handler in combat.py
- `is_slash_command_enabled("/atak")` gate exists
- Frontend "Atak" button triggers this path when player is not in combat

---

## Full Specification

### Change 1 — Remove /atak as Player Command

- Disable `/atak` in the slash command registry for non-admin players
- Admin may keep `/atak` as a debug/testing tool (admin-only)
- Remove the "Atak" button from the player frontend UI (or repurpose it as "Attack" during active combat — a different function)
- Remove `/atak` from the player-visible command palette

### Change 2 — Enemy Key Validation in Tag Handler

When `[COMBAT_START:enemy_key1,enemy_key2]` is detected:

```python
def resolve_enemy_keys(raw_keys: list[str]) -> list[dict]:
    resolved = []
    for key in raw_keys:
        # 1. Exact match in DB
        enemy = db.execute("SELECT * FROM game_config_enemies WHERE key = ? AND is_active = 1", [key]).fetchone()
        if enemy:
            resolved.append(enemy)
            continue
        
        # 2. Fuzzy name match (key contains enemy name or vice versa)
        fuzzy = db.execute(
            "SELECT * FROM game_config_enemies WHERE key LIKE ? AND is_active = 1",
            [f"%{key}%"]
        ).fetchone()
        if fuzzy:
            resolved.append(fuzzy)
            continue
        
        # 3. Not found — create pending_review entry or use generic fallback
        # For now: use "unknown_attacker" as fallback + log warning
        fallback = db.execute("SELECT * FROM game_config_enemies WHERE key = 'unknown_attacker'").fetchone()
        resolved.append(fallback)
        log.warning(f"Unknown enemy key '{key}' — using fallback")
    
    return resolved
```

### Change 3 — Enemy Keys in System Prompt

Replace the hardcoded list of valid enemy keys in `system_prompt.txt` with a dynamic injection.

Each turn, the system prompt context block includes:

```
Available enemies in this location (use these keys in [COMBAT_START]):
  goblin (weak), orc (standard), troll (elite), skeleton (standard), wolf (weak), ...
  [all active enemies from game_config_enemies, filtered by current location's enemy_keys]
```

This way:
- Enemy variety expands as admin adds more enemies
- Location-specific enemies are preferred (a dungeon suggests skeletons; a forest suggests wolves)
- LLM always has valid keys to use

### Change 4 — Combat Start Narration

When `[COMBAT_START]` is detected, the turn response flow:
1. Strip `[COMBAT_START:...]` tag from visible output
2. The GM text BEFORE the tag is shown as the combat setup narration (e.g., "The goblin lunges from behind the barrel!")
3. Combat panel opens with enemy lineup
4. Combat round begins (Task 12)

The GM text should DESCRIBE the combat starting — it should not say "combat begins." It should narrate: "Three goblins emerge from the shadows, blades drawn." The tag is the signal; the text is the story.

---

## Edge Cases

- **GM emits [COMBAT_START] while player is already in combat:** Ignored — can't start combat inside combat
- **GM emits [COMBAT_START] with empty key list:** Use "unknown_attacker" as single enemy
- **All enemy keys map to fallback:** Combat still starts — log admin alert "multiple unknown enemy keys in session {id}"
- **Admin uses /atak with invalid key:** Admin should see an error, not a silent failure

---

## Test Plan

1. GM response contains `[COMBAT_START:goblin]` → verify combat panel opens with goblin, tag stripped from visible text
2. Player types `/atak goblin` → verify command is rejected with "use narrative actions to engage enemies"
3. GM uses unknown key `[COMBAT_START:dragon_lord]` → verify fallback used, warning logged
4. Enemy keys in system prompt match what's in `game_config_enemies` active records
5. Starting combat in a forest location → verify forest-appropriate enemies suggested in system prompt

---

## Related Tasks
- Task 12 (Combat Round Flow) — combat entry feeds directly into this
- Task 10 (Data Tables) — enemy key lookup uses the source-of-truth pattern
