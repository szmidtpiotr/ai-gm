---
name: game-test
description: Impersonate a player against the DEV AI-GM stack to verify a bug fix end-to-end. The user invokes this when they want you to play 3-6 turns as if you were a real human, then diff DB state and report whether the just-shipped fix actually held. The skill provides the mechanics (POST a turn, snapshot DB state, reset to a clean test campaign); you provide the judgement (what player messages to send and what to check for, based on the fix at hand).
---

# game-test

## When the user invokes this

The user has just implemented a fix or a feature and wants you to verify it from a player's perspective — by actually talking to the live DEV LLM, not by running unit tests. The triggering context is in conversation history: which bug, which files changed, what symptom should have gone away.

**Read the conversation context first** to understand *what* you're testing. Without that, you have no basis to pick player messages or decide what state to assert against.

## Architecture (one-time read)

- DEV backend API: `http://192.168.1.61:8100`
- Endpoint used: `POST /api/campaigns/{campaign_id}/turns` with body `{"character_id": int, "text": "player message"}`
- No auth required on this endpoint.
- DB lives on `192.168.1.61` inside container `ai-gm-dev-backend-1` at `/data/ai_gm.db`, bind-mounted to host at `~/ai-gm/data-dev/ai_gm.db`, visible from this Claude VM via sshfs at `/home/claude/projects/DEV_AIGM/data-dev/ai_gm.db`.
- All DB reads in helpers open it locally read-only. Writes (reset) happen via SQL directly.
- Test campaign is hard-pinned: a campaign whose `title` starts with `[TEST]` and a character whose `name` starts with `[TEST]`. The reset script bootstraps both if missing (prints instructions; campaign creation through the API is too involved to automate here).

## Workflow you follow

1. **Reset.** `python3 scripts/reset_test_campaign.py` — finds or instructs to create the `[TEST]` campaign + character, soft-deletes any locations created during prior runs, repoints the session to the starting location. Returns JSON with `campaign_id`, `character_id`, `starting_location_id`, `starting_location_key`. If the script reports `bootstrap_required: true`, surface its instructions to the user and stop.

2. **Baseline snapshot.** `python3 scripts/snapshot.py --campaign <id>` — returns compact JSON: location count, current session location, last turn id, character HP/mana, active combat id (if any). Stash this. Default snapshot is intentionally small; use `--full` only if the fix touches inventory/combat/spells.

3. **Drive turns.** For each of 3-6 turns, call `python3 scripts/play_turn.py --campaign <id> --character <id> --message "..."` — POSTs the turn, waits up to 90s, returns JSON:
   - `turn_id`, `turn_number`, `route`
   - `narrative` (first 250 chars)
   - `location_blocked_tags` (list of reasons stripped from narrative — empty when OK)
   - `location_intent` (action / target_key / target_label / parent_key)
   - `new_locations` (list of locations created during this turn — should be empty unless the fix expected creation)
   - `session_location_change` (from→to with keys)
   - `error` (HTTP error or timeout, if any)

   Improvise the player messages to exercise the fix. If you don't know what to send, look at the conversation: which input previously triggered the bug, what edge cases would re-trigger it after the fix.

4. **Post snapshot + diff.** Re-run `snapshot.py` and compare against baseline. The interesting deltas live in: new locations, session location, integrity log entries, turn count.

5. **Report.** One short paragraph: PASS/FAIL, what symptom you tried to reproduce, what actually happened, with turn numbers as evidence. If FAIL, write a structured note the user can paste into a follow-up issue.

## Table cheatsheet (which tables matter for which bug)

| Bug area | Tables to check |
|---|---|
| Location integrity / movement | `game_locations` (orphans, dupes), `game_sessions.current_location_id`, `location_integrity_log` |
| Combat | `combat_state`, `combat_events`, `combat_turns`, `characters.sheet_json` (HP/conditions) |
| Inventory / loot | `character_inventory`, `loot_*` |
| Spells / Scholar | `character_spells`, `characters.sheet_json` (current_mana) |
| NPCs | `game_npcs`, `npc_locations` |
| Skill checks / dice | `campaign_turns.route='skill_test'`, the roll result string |
| GM plan / story | `campaigns.gm_plan_json`, `campaign_turns.assistant_text` (scene transitions) |

When you don't know what's relevant, default to the locations + turns columns — they cover the majority of fixes.

## What this skill does NOT do

- It does not write the fix. It does not run the unit tests (`pytest` lives elsewhere). It does not deploy to prod. It plays the game.
- It does not enforce a fixed pass/fail rubric — you decide what counts based on the fix being verified.
- It does not clean up turns; only locations get soft-deleted on reset. Turns accumulate in the test campaign — useful for inspecting LLM behavior across runs.

## Pitfalls

- The LLM is non-deterministic. A single PASS run is weak evidence. If a fix is critical, run the scenario twice with different phrasings.
- `location_blocked_tags` includes legitimate blocks. If the user's fix is *about* blocking properly, an empty tag list is FAIL, not PASS. Read the goal.
- Turn POSTs can hang up to 90s on slow LLM responses. Don't retry blindly — check whether a row actually landed in `campaign_turns` before re-sending.
- The reset script intentionally does not delete turns. To clear test history, drop the campaign via Admin UI and re-bootstrap.
