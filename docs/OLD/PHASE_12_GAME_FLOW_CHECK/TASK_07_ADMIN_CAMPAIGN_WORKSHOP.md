# TASK 07 — Admin Campaign Workshop + Ideas Bank

**Status:** ❌ Not Started
**Blocking:** None — spec complete
**Depends on:** Task 04 (campaign plan schema to view/edit)
**Unlocks:** Nothing directly — admin tooling

---

## Overview

Three connected features for the admin:
1. **Campaign Plan Viewer** — admin can read any live campaign's plan in a readable format
2. **Campaign Workshop** — admin has a conversational LLM agent to discuss, modify, and improve a campaign plan
3. **Ideas Bank** — a shared DB table where admins can save premises, plot twists, NPC concepts, and location sketches; future campaign generators draw from it

---

## Design Context

### Why should admin be able to see the plan?
Admins are the co-creators of the world. When a player's campaign goes sideways or the GM makes unexpected narrative choices, the admin needs visibility to understand what happened and whether to intervene. The plan viewer also serves as a QA tool — admins can verify that generated plans are coherent before the player encounters them.

### Why a conversational agent for editing, not a form?
Campaign plans have complex interdependencies. Changing an ending might require changing an NPC's role, which might require changing Act 3's summary. A form would require the admin to understand all these relationships. A conversational agent can handle the cascading changes — "I want ending B to involve a sacrifice instead of a negotiation" — and propose all the needed changes together before committing.

### Why an Ideas Bank?
Good campaign ideas are rare. When an admin or the LLM stumbles on a great plot twist, distinctive NPC concept, or evocative location, it should be saved for reuse. The Ideas Bank prevents this from being lost. More importantly, the campaign plan generator can query the Ideas Bank when creating new campaigns — "give me a campaign similar to the vampire mystery idea marked as 'great'" — producing campaigns that improve over time rather than starting from zero every time.

---

## Current State (Code)

- No campaign plan viewer in admin panel
- No LLM agent endpoint for admin campaign editing
- No Ideas Bank table or UI
- Admin panel has sections for stats, skills, weapons, enemies, accounts, etc. — campaign-related section is absent

---

## Full Specification

### Feature 1 — Campaign Plan Viewer

**Location:** New section in admin panel: "Campaigns" tab

**Display format:**
```
Campaign: Cień nad Graustein [ID: 42]
Player: Jan Kowalski | Character: Aldric (Warrior, Level 2)
Status: Active | Act: 2 of 3

PREMISE
Aldric przybywa do Graustein szukając spokojnej roboty...

ACTS
  Act 1: Martwe miasto [COMPLETED ✓]
    Beats visited: arrival ✓, tavern_job_offer ✓, first_clue_puncture_wounds ✓
  Act 2: Krew i złoto [ACTIVE]
    Beats visited: gambling_den_discovered ✓, vampire_thrall_encountered ✗, vampire_identity_hinted ✗
  Act 3: Rozliczenie [NOT YET]

KEY NPCs
  ● Nieznany (antagonist) [CRITICAL] — alive ✓
  ● Karczmar Heinz (ally) [SUPPORTING] — alive ✓

ENDINGS
  → Ending A: Rzeźnik z Graustein (primary)
  → Ending B: Pakt (alternate)

DEVIATIONS (1)
  Turn 14: Player attacked the town guard unprovoked [minor — steered back]

BRANCHES: none generated yet

ENGINE PRIVATE
  [🔒 Hidden from player — visible to admin only]
  Secret predisposition: Latent magical sensitivity
  Hidden twist: Vampire was once a local healer, cursed against will
```

**API:** `GET /api/admin/campaigns/{id}/plan` — returns full plan JSON

### Feature 2 — Campaign Workshop (LLM Agent)

**Location:** Within the campaign plan viewer — "Workshop" collapsible panel at the bottom

**Interface:** A chat-like input where admin types requests. Agent responds with proposed changes. Admin can Approve or Reject each change.

**Agent capabilities:**
- Explain any part of the plan ("Why did you make the vampire a healer?")
- Propose changes to endings, acts, NPCs ("Change ending B to involve the player helping the vampire find a cure")
- Generate alternative plot twists
- Add new NPCs or locations with appropriate importance flags
- Review and critique the current plan ("Does this plan have any plot holes?")
- Generate a new branch manually (without player having triggered [BRANCH_REQUIRED])

**Agent context:** Receives the full campaign plan + character sheet + scene log

**Commit flow:**
1. Admin sends message: "Make the alternate ending involve finding a cure for the vampire"
2. Agent responds with proposed JSON diff of the plan
3. Admin sees: "This will change: endings[1].description, endings[1].requirements. Approve?"
4. Admin clicks Approve → `PATCH /api/admin/campaigns/{id}/plan` with updated plan
5. OR admin clicks Reject → no changes, agent awaits next message

**New endpoint:** `POST /api/admin/campaigns/{id}/workshop` — sends message to agent, returns proposed changes

### Feature 3 — Ideas Bank

**New DB table:** `campaign_ideas`

```sql
CREATE TABLE campaign_ideas (
    id INTEGER PRIMARY KEY,
    category TEXT NOT NULL CHECK(category IN (
        'premise', 'plot_twist', 'npc_concept', 'location', 'encounter', 'ending', 'other'
    )),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    tags TEXT DEFAULT '[]',       -- JSON array of tag strings
    quality_rating INTEGER DEFAULT 0,  -- 0-5, admin-rated
    times_used INTEGER DEFAULT 0,
    source TEXT,                  -- "admin_manual", "campaign_{id}_generated", "llm_workshop"
    created_at TEXT DEFAULT (datetime('now')),
    created_by INTEGER REFERENCES users(id),
    is_active INTEGER DEFAULT 1
)
```

**Admin UI — Ideas Bank panel:**
- List all ideas with filter by category + tags
- Create new idea (manual entry)
- Rate quality (0-5 stars)
- Tag with searchable keywords
- "Save to Ideas Bank" button available from Workshop chat — saves any LLM-generated idea to the bank

**Campaign generation integration:**
When generating a new campaign plan (Task 05), the LLM receives:
- Top 3 rated ideas in the "premise" category (if any exist)
- Top 2 rated ideas in categories matching the requested setting/tone
- Instruction: "You may draw inspiration from these ideas, but the campaign must still be personalized to the character"

**New endpoints:**
- `GET /api/admin/ideas` — list with filters
- `POST /api/admin/ideas` — create
- `PATCH /api/admin/ideas/{id}` — update rating/tags
- `DELETE /api/admin/ideas/{id}` — soft delete (is_active = 0)

---

## Edge Cases

- **Admin edits plan while player is mid-turn:** Plan update must be atomic (transaction). If a turn is processing during plan edit, either queue the plan update or reject it with "turn in progress"
- **Approved plan change invalidates ongoing deviation:** If admin resolves a deviation by editing the plan directly, the deviation tracker should be marked "resolved by admin"
- **Ideas Bank grows very large:** Quality rating allows filtering to best ideas. Auto-archive ideas with rating 0 after 6 months of no use.

---

## Test Plan

1. Navigate to admin panel → verify "Campaigns" section exists
2. Select an active campaign → verify plan renders in readable format with all fields
3. Open Workshop → send "Add a new ending where the player becomes the vampire's thrall" → verify proposed change shown with Approve/Reject
4. Approve the change → verify campaign plan updated in DB
5. Create a new idea in Ideas Bank → verify it appears in list
6. Rate an idea → verify rating saved
7. Create a new campaign → verify Ideas Bank ideas appear in generation prompt

---

## Related Tasks
- Task 04 (Campaign Plan v2 Schema) — defines what the viewer displays
- Task 05 (Campaign Plan Generation) — queries Ideas Bank as input
- Task 06 (Deviation Handling) — deviations visible in plan viewer
