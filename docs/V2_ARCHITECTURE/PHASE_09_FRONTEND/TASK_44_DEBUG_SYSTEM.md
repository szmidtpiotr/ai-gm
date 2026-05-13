# TASK 44 — Debug System

**Phase:** 09 — Frontend
**Status:** ❌ Not Started
**Depends on:** TASK 11 (Turn Pipeline — must expose debug data in response payload)

---

## Overview

The debug system gives admins and developers real-time visibility into system internals during a session: intent parsing, mechanic resolution, narrator prompts, LLM responses, and full game state. It is completely invisible to regular players — no UI element, no endpoint, no overhead — unless `debug_mode=true` is set for that user's session. Debug commands allow direct state manipulation for testing purposes.

---

## Debug Mode Toggle

### Setting Debug Mode

Three ways to enable or disable debug mode:

1. **Admin panel:** User Management → user record → "Debug Mode" toggle (checkbox). Writes to the user record; takes effect on next session start.
2. **Mid-session self-toggle (admin users only):** A [🐛] button visible only to admin-role users in the game UI toolbar. Clicking toggles debug mode immediately for the current session without reload.
3. **API (admin only):** `PATCH /api/admin/users/{user_id}/debug` with body `{ "debug_mode": true }`.

### Storage

```
game_sessions.session_flags.debug_mode  (boolean)
```

Set at session initialisation from the user's admin-configured default. Can be overridden mid-session by the self-toggle. The flag lives in `session_flags` so it is session-scoped — debug mode does not persist automatically to the next session unless the user record default is also set.

### Security

- The [🐛] button is only rendered for users with `role='admin'`.
- All `/api/debug/*` endpoints check `session.debug_mode == True` before executing. Return 403 if false.
- Debug data in turn response payloads is gated server-side: fields are only included when `debug_mode=True`. A player with `debug_mode=False` never receives debug data, even if they inspect network responses.

---

## Debug Panel

### Container

A collapsible drawer anchored to the right edge of the game screen. A narrow tab labelled `[🐛 Debug]` is visible only when `debug_mode=true`. Clicking the tab toggles the drawer open/closed.

- Width: 420px.
- Overlaps chat content (does not push layout).
- Has its own scroll — content sections scroll independently.
- Rendered only for debug sessions. For non-debug sessions, the tab and drawer DOM elements are not inserted at all.

### Sections

Each section is independently collapsible (click the section header to expand/collapse). Admin can configure in User Management which sections are visible by default; the frontend stores open/closed state in `localStorage` per section key.

| Section Key | Header Label | Content |
|---|---|---|
| `game_state` | Game State | Full `session_flags` JSON, WSM current state string |
| `last_intent` | Last Intent | Raw player text + parsed ACTION tag string |
| `mechanic_result` | Mechanic Result | Full Resolver JSON (roll values, modifiers, DC, outcome) |
| `llm_prompts` | LLM Prompts | Intent parser prompt (full text) + narrator prompt (full text) |
| `llm_response` | LLM Response | Raw narrator output before any post-processing |
| `campaign_plan` | Campaign Plan | Plan JSON (active act, beats, beats visited, deviations log) |
| `character` | Character | Full `sheet_json` raw, including `gm_only` fields |
| `location` | Location | Current location DB record + list of assigned NPC keys + enemy keys |
| `active_npc` | Active NPC | Last-interacted NPC — DB key, personality_prompt, keyword_triggers |
| `active_enemy` | Active Enemy | All current combat enemies with `behavior_profile` JSON |
| `performance` | Performance | `intent_parse_ms`, `narrator_ms`, `total_ms` for last turn |

### Anti-Hallucination Fields

The `location`, `active_npc`, and `active_enemy` sections exist specifically to confirm that the correct database records are being loaded — not hallucinated by the LLM. They show the raw DB key alongside the record contents. During testing, an admin can verify: if the LLM references "Merchant Brauer" but the `active_npc` section shows `key: 'bremer_innkeeper'`, that is a mismatch worth investigating.

### Data Flow

After each turn, the backend response payload includes a `debug` key when `debug_mode=True`:

```json
{
  "narration": "...",
  "state": { ... },
  "debug": {
    "game_state": { "wsm_state": "EXPLORATION", "session_flags": { ... } },
    "last_intent": {
      "raw_text": "Atakuję goblina",
      "parsed_tag": "[ACTION:ATTACK:target=goblin_1]"
    },
    "mechanic_result": {
      "roll": 14, "stat_mod": 2, "skill_rank": 1, "proficiency": 0,
      "total": 17, "dc": 12, "outcome": "SUCCESS"
    },
    "llm_prompts": {
      "intent_parser": "...",
      "narrator": "..."
    },
    "llm_response": { "raw": "..." },
    "campaign_plan": { ... },
    "character": { ... },
    "location": { "key": "graustein_tavern", "npcs": ["bremer_innkeeper"], "enemies": [] },
    "active_npc": { "key": "bremer_innkeeper", "personality_prompt": "...", "keyword_triggers": [...] },
    "active_enemy": null,
    "performance": { "intent_parse_ms": 340, "narrator_ms": 1820, "total_ms": 2200 }
  }
}
```

The frontend reads this payload on each turn response and updates each debug panel section with the latest data. Sections render JSON using a collapsible JSON viewer (e.g., `json-tree` or equivalent).

---

## Debug Commands

Debug commands are only parsed when `session.debug_mode = True`. They are typed by the player/admin in the normal chat input, prefixed with `/debug`. For non-debug sessions, `/debug` inputs are treated as plain text (or ignored with a silent error).

All debug commands bypass the intent parser and LLM. They go directly to the debug endpoint.

### Endpoint

```
POST /api/debug/command
Body: { "session_id": "...", "command": "set-hp 5", "args": "5" }
```

The endpoint checks `debug_mode=True` first, then routes to the appropriate handler.

### Command Reference

| Command | Effect |
|---|---|
| `/debug set-hp <n>` | Set `current_hp` to `n`. Clamps to `max_hp`. |
| `/debug set-state <STATE>` | Force WSM state (EXPLORATION, COMBAT, DIALOGUE, REST, etc.) |
| `/debug give-item <item_key>` | Add item to character inventory by key |
| `/debug trigger-fear` | Apply `frightened` condition to character |
| `/debug trigger-crit` | Force next attack roll to be treated as natural 20 |
| `/debug force-miscast` | Force next spell to trigger miscast table roll |
| `/debug skip-intent <ACTION_TAG>` | Bypass intent parser — inject raw action tag directly into resolver |
| `/debug show-context` | Dump the full narrator context to the debug panel (llm_prompts section) immediately, without waiting for a turn |
| `/debug set-xp <n>` | Set `xp_total` to `n`. Recomputes level. |
| `/debug add-condition <key>[:<duration>]` | Apply condition by key. Optional duration in turns (e.g., `stunned:3`). |
| `/debug clear-conditions` | Remove all active conditions from character |
| `/debug teleport <location_key>` | Move character to location by key, bypassing WSM connection validation |

### Output

Debug command responses are displayed in the chat as system messages styled distinctly (e.g., monospace, yellow border):

```
[DEBUG] HP set to 5 (max: 42)
[DEBUG] Condition 'stunned' applied — duration: 3 turns
[DEBUG] Teleported to 'goblin_warren'
```

---

## TASK 11 Integration Requirements

The turn pipeline (TASK 11) must collect and pass debug data at each stage when `debug_mode=True`. Key integration points:

1. **Intent Parser** — after parsing, store `{ raw_text, parsed_tag }` in the turn context.
2. **Mechanic Resolver** — after resolution, store full resolver output dict in turn context.
3. **LLM calls** — capture prompt sent and raw response received for both intent parse and narrator calls. Store in turn context.
4. **WSM** — store current state snapshot after processing.
5. **Turn response assembly** — if `debug_mode=True`, attach the `debug` key to the response.

Performance timing: use `time.perf_counter()` at the start of each LLM call and compute `_ms` values before response assembly.

---

## Test Checklist

1. **Toggle on/off:** Enable debug mode for a user, start session — verify [🐛] tab visible and debug data present in turn responses. Disable debug mode, restart session — verify tab absent, no `debug` key in response payloads.
2. **Panel sections:** Open debug panel, run a turn with a combat action — verify `mechanic_result` section contains correct roll values, `active_enemy` shows correct DB key.
3. **Commands rejected for non-debug users:** POST to `/api/debug/command` with a session where `debug_mode=False` — verify 403 response.
4. **`/debug teleport` bypasses WSM:** Use teleport to move to a disconnected location — verify character location updated, no WSM connection error, location added to visited keys.
5. **`/debug add-condition stunned:3`:** Verify condition applied with duration 3, decrements each turn, auto-removed at 0.
