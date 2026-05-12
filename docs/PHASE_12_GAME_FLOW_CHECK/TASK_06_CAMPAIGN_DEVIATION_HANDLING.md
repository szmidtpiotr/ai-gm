# TASK 06 — Campaign Deviation Handling

**Status:** ❌ Not Started
**Blocking:** N7 (confirm [BRANCH_REQUIRED] tag system vs pure LLM judgment) — recommendation: use tag system
**Depends on:** Task 04 (campaign plan schema with deviation_consequence flags)
**Unlocks:** Nothing directly — this runs during live gameplay

---

## Overview

During play, the player will inevitably do things the GM didn't plan for. This system handles two cases:
1. **Minor deviation** — player ignores a clue, takes a detour, delays the plot. GM steers them back gently over the next 1-2 turns.
2. **Major deviation** — player kills a critical NPC, makes a key arc path impossible. GM generates a new branch that reconnects to a valid ending.

The distinction between minor and major must be made by the SYSTEM (via NPC importance flags and key beat tracking), not by the LLM on its own. The LLM alone will either over-react to minor deviations (constant railroading) or under-react to major ones (ignoring broken plot logic).

---

## Design Context

### Why not let the LLM handle all deviation?
LLMs are very good at improvisation but very bad at maintaining structural coherence over long sessions. Without external tracking, the LLM will:
- Forget that a key NPC was killed three sessions ago and have them appear again
- Generate new plot threads that never connect to the established ending
- Lose track of whether the player is progressing toward any ending at all

The deviation handler gives the LLM a READ of the current structural state with each turn — "here's where you are in the story, here's what's broken, here's what you must do about it."

### Why a [BRANCH_REQUIRED] tag?
If we rely on the LLM to recognize "I need to generate a new branch," it might do so silently without the backend ever knowing. The backend cannot track deviation state or notify the admin if the LLM just improvises. The tag makes the structural decision EXPLICIT — the LLM says "I cannot continue this arc, I need a new branch" and the backend handles it.

### Minor vs major — what's the difference in practice?

| Player action | Classification | GM response |
|---------------|----------------|-------------|
| Ignores a clue NPC | Minor | Re-introduce clue through different NPC |
| Leaves town for a day | Minor | NPC sends a message, event escalates |
| Kills a REPLACEABLE NPC | Minor | Steer — different NPC takes their role |
| Kills a SUPPORTING NPC | Minor/Major | Steer if alternate path exists; Branch if not |
| Kills a CRITICAL NPC before reveal | Major → Branch | Generate new mini-arc |
| Burns down the tavern before getting the job offer | Major | Branch — new meeting point found |
| Kills every NPC in the starting location | Catastrophic | New ending generated |

---

## Current State (Code)

- No deviation tracking exists
- `gm_plan_json` has no key beats tracking or NPC alive flags
- LLM gets the plan as context but has no explicit instructions about deviation handling
- No `[BRANCH_REQUIRED]` tag support in `game_engine.py`

---

## Full Specification

### Deviation Detection Flow

On every player turn, before calling the LLM:

1. **Load current plan state** from `gm_plan_json`
2. **Check NPC alive flags** — any CRITICAL NPCs now `alive = false`?
3. **Check key beat progress** — active act's key beats: how many visited? How many skipped?
4. **Classify current situation:**
   - All CRITICAL NPCs alive AND reasonable beat progress → No deviation — normal turn
   - Non-critical NPC dead OR minor beat skip → Minor deviation — inject steering hint into GM context
   - CRITICAL NPC dead OR multiple beats skipped → Major deviation — inject branch instruction into GM context
5. **Build deviation context block** injected into the system prompt

### GM Context Injection (per turn)

```
=== DEVIATION STATUS ===
[NORMAL] All key NPCs alive. Story on track.
Next required beat: tavern_job_offer
=========================
```

OR when a critical NPC is dead:

```
=== DEVIATION STATUS ===
[BRANCH REQUIRED] Critical NPC "vampire_hunter" was killed before vampire_identity_known.
The main arc cannot proceed. You MUST:
  1. Emit [BRANCH_REQUIRED: reason] in your response
  2. Generate a new path to one of the valid endings: ending_a, ending_b
  3. Introduce new elements that replace the critical NPC's role
=========================
```

### [BRANCH_REQUIRED] Tag Processing

When GM response contains `[BRANCH_REQUIRED: {reason}]`:

1. Backend intercepts tag (regex, similar to COMBAT_START)
2. Strip tag from player-visible output
3. Call `generate_branch(campaign_id, reason)` asynchronously
4. Branch generation:
   - LLM receives: current plan state, what was lost, valid endings, current player location and resources
   - LLM generates: new mini-arc (2-3 plot beats) that reconnects to an existing ending
   - New branch saved as `Branch` object in plan's `branches` list
   - New NPC keys and locations created as `pending_review` entries if new ones are needed
5. Updated plan saved to DB
6. Admin notification (if admin notification system exists) — "Branch generated in campaign {id}"

### NPC Death Tracking

When an NPC is killed during gameplay (combat or narrative):
- Backend detects NPC key in the kill event (GM emits `[NPC_KILLED: npc_key]` tag)
- Find NPC in plan's `key_npcs` list
- Set `alive = false`
- If `deviation_consequence = "branch"` → trigger deviation check on NEXT turn
- If `deviation_consequence = "steer"` → inject minor deviation hint on next turn
- Save updated plan to DB

### Key Beat Tracking

Key beats are narrative milestones like `"tavern_job_offer"` or `"vampire_identity_revealed"`.

When a beat is completed:
- GM emits `[BEAT_COMPLETE: beat_key]` tag
- Backend marks beat as visited in plan
- If all beats in current act are visited: consider advancing to next act

Beat skipping detection:
- If player is in Act 2 but Act 1 has unvisited beats: minor deviation, steer back
- If Act 2 beats are being skipped and Act 3 is attempted: major deviation, branch or steer

---

## Deviation Severity Rules

```python
def classify_deviation(plan: CampaignPlan) -> str:
    dead_critical = [npc for npc in plan.key_npcs 
                     if not npc.alive and npc.importance == "critical"]
    dead_supporting = [npc for npc in plan.key_npcs 
                       if not npc.alive and npc.importance == "supporting"]
    
    if len(dead_critical) >= 2:
        return "catastrophic"
    elif len(dead_critical) == 1:
        return "major"
    elif dead_supporting or skipped_beats > 2:
        return "minor"
    else:
        return "normal"
```

---

## Edge Cases

- **Player kills CRITICAL NPC but plan has a BRANCH pre-written in `engine_private.contingency`:** Use the contingency branch instead of generating a new one
- **Branch generation fails (LLM error):** GM continues with steering mode; admin alerted; plan still functional
- **Player somehow reaches ending requirements without visiting all beats:** Allow it — the player found their own path. Mark as "speedrun" deviation in scene_log.
- **Player creates completely new characters / NPCs through roleplay:** These exist in the narrative but don't affect the structural plan unless GM tags them with [NPC_KILLED] or [BEAT_COMPLETE]

---

## Test Plan

1. Create a campaign, kill a SUPPORTING NPC → verify `alive = false` in plan, minor deviation hint injected next turn
2. Kill a CRITICAL NPC → verify `[BRANCH_REQUIRED]` emitted by GM, branch saved to plan
3. Complete all Act 1 beats → verify `act 1.completed = true`, Act 2 injected as new context
4. Admin views campaign plan → sees deviation history and branches clearly
5. Player reaches ending_a requirements without visiting Act 2 beats → verify they can reach the ending (non-blocking) and deviation is logged

---

## Related Tasks
- Task 04 (Campaign Plan v2 Schema) — NPC importance flags, key beats, Branch objects
- Task 07 (Admin Workshop) — admin views deviation history and branches
- Task 10 (Data Tables) — new NPCs from branch generation saved as pending_review
