# TASK 32 — World Review Queue

**Status:** ✅ Done
**Phase:** 08 — Admin Tools
**Depends on:** Task 10 (Data Tables Source of Truth — creates pending_review entries)

---

## Implementation Status

- "Oczekujące" sub-tab implemented inside the Świat section in admin_panel_v2 (`world.js _renderPendingReview`)
- Three entity types supported: Lokacje, NPC, Przeciwnicy
- Per-row Zatwierdź / Odrzuć buttons working
- `GET /api/admin/world/pending/{type}` — fetch pending by entity type
- `POST /api/admin/world/review/{type}/{key}` with `{action: "approve"|"discard"}` — review action endpoint (note: POST not PATCH as originally specced)
- Badge count on nav tab showing total pending items across all types
- "Edytuj i Zatwierdź" inline edit and batch bulk-approve are not implemented

---

## Overview

Whenever the GM creates a new Location, NPC, or Enemy mid-session (via CREATE tag), it gets stored with `review_status = 'pending_review'`. This admin panel section shows all pending entries. Admin reviews, approves (→ permanent, available to all future campaigns), or discards (→ removed from future use, but stays in the current session).

---

## Admin Panel UI

**Location:** Admin panel → "Świat" tab → "Oczekujące" sub-tab

Three tabs: Lokacje | Postacie NPC | Przeciwnicy

Each row shows:
- Name, description preview, source campaign, times used this session
- **[Zatwierdź]** → review_status = 'permanent'
- **[Edytuj i Zatwierdź]** → inline edit form, then save as permanent
- **[Odrzuć]** → review_status = 'discarded'

Batch select + bulk approve for rapid review.

Badge count in admin nav showing total pending.

---

## API Endpoints

- `GET /api/admin/world/pending` — all pending across types
- `PATCH /api/admin/world/locations/{id}/review` — `{action: "approve"|"discard"}`
- `PATCH /api/admin/world/npcs/{id}/review`
- `PATCH /api/admin/world/enemies/{id}/review`

---

## Rules

- **Discard doesn't break running campaigns** — the entity is still usable in the session it was created in. Discard only prevents future campaigns from finding it in DB lookup.
- **Approve makes it available globally** — any future campaign can now find this location/NPC/enemy in their DB lookup.
- **Auto-discard** (optional, configurable): pending entries older than 30 days with 0 times_used → auto-discarded on next admin login.

---

## Related Tasks
- Task 10 (Data Tables) — creates the pending_review entries this tool reviews
