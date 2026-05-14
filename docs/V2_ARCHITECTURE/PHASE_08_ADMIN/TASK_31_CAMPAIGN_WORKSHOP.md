# TASK 31 — Campaign Workshop (Admin Live Campaign Editor)

**Status:** ✅ Done
**Phase:** 08 — Admin Tools
**Depends on:** Task 13 (Campaign Plan v2 schema)

---

## Implementation Status

- Moved inside the campaign detail modal as a 4th tab "🔧 Warsztat" (not a separate panel as originally specced)
- Campaign ID auto-loaded from context — no dropdown needed
- `POST /api/admin/campaigns/{id}/workshop/message` endpoint implemented and working
- `POST /api/admin/campaigns/{id}/workshop/apply` endpoint for applying approved changes
- Right panel shows "PROPONOWANE ZMIANY" cards with per-change ✓ Zatwierdź / ✗ Odrzuć buttons
- Raw JSON stripped from chat display — only human-readable text shown to admin
- Frontend: `renderWorkshopTab()` in `campaigns.js`

---

## Overview

The Campaign Workshop lets admins view and edit ANY live campaign's plan through a conversational AI agent. Different from the Ideas Workshop (which builds new ideas for the bank) — this tool works on a RUNNING campaign. Admin can see exactly where the story is, what's gone wrong, and ask the agent to propose changes.

---

## Features

### Campaign Plan Viewer
`GET /api/admin/campaigns/{id}/plan` → readable outline of the full plan.

Shows: current act, visited beats, alive/dead NPCs, deviations logged, branches generated, player's current location.

### Conversational Editor
Agent receives: full campaign plan + character sheet + last 10 scene_log entries.

Admin can ask:
- "Add a new subplot where the vampire has a human lover who doesn't know what he is"
- "Make ending B involve a sacrifice instead of negotiation"  
- "The player killed the vampire hunter — what branch should the GM generate?"
- "Does this plan have any plot holes?"

Agent returns: proposed JSON diff (what changes). Admin sees Approve/Reject buttons per change.

On Approve: `PATCH /api/admin/campaigns/{id}/plan` with updated plan JSON.

### New endpoint
`POST /api/admin/campaigns/{id}/workshop` — sends message + receives proposed changes.

---

## Related Tasks
- Task 13 (Campaign Plan v2) — the schema being edited
- Task 30 (Ideas Workshop) — different tool, creates new Ideas Bank entries
