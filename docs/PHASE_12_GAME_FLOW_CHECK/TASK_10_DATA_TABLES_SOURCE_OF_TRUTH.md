# TASK 10 — Data Tables as Source of Truth

**Status:** ❌ Not Started
**Blocking:** None — spec complete
**Depends on:** Nothing (cross-cutting pattern, but can be implemented independently)
**Unlocks:** All world-content tasks benefit from this once established

---

## Overview

The GM/LLM must never invent game world content (locations, NPCs, enemies, items) from scratch when a database table already has relevant records. This task establishes a "lookup-before-create" pattern across all world content services and adds a `pending_review` status so that newly GM-invented content flows through an admin approval queue before becoming permanent.

This is a cross-cutting architectural pattern, not a single feature.

---

## Design Context

### Why enforce DB-first for world content?
Without this, every campaign has a completely fresh set of NPCs, enemies, and locations invented by the LLM. Two problems:
1. **Inconsistency:** The "goblin" in one campaign has different stats, abilities, and personality than in another — the world has no coherent identity
2. **LLM drift:** The LLM might invent enemies with wildly different power levels, items with contradictory prices, or locations that don't match the established world tone

With DB-first, the admin curates a consistent library of world content. The LLM builds stories FROM that library, not beside it.

### Why pending_review instead of immediate permanent?
The LLM should be allowed to create new content when it doesn't find a match — this prevents the game from being unable to introduce a new character or location. But the admin should decide which new creations become permanently part of the world. A clever NPC invented by the GM for one campaign might deserve to become a recurring character; a generic "unnamed guard #4" probably doesn't. The review queue gives the admin that curation power.

### How does this NOT break immersion?
From the player's perspective, nothing changes. The GM invents "Viktor, a scarred blacksmith with a secret" and the player meets Viktor. Whether Viktor is from the permanent database or a pending_review entry makes no difference to the narrative. The difference is only in admin visibility and world-building consistency over time.

---

## Current State (Code)

**What exists:**
- `game_locations` table — `is_active` flag, no `status`/`review_status`
- `npc_definitions` table — `is_active`, `npc_type`, `is_shop` flags
- `game_config_enemies` table — `is_active`, `tier` flags
- `game_config_items` table — `is_active`, `approved`, `ai_generated` flags (items are partially covered!)
- Items already have `ai_generated` (0/1) and `approved` (0/1) — closest to what we need

**What is missing:**
- `review_status` TEXT field on: `game_locations`, `npc_definitions`, `game_config_enemies`
- Items need `ai_generated` to map to the same `pending_review` concept
- Lookup-before-create logic in game_engine.py / location service / NPC service
- GM prompt instruction: "check DB first"
- Admin review queue UI

---

## Full Specification

### New DB Field: review_status

Add to `game_locations`, `npc_definitions`, `game_config_enemies`:

```sql
ALTER TABLE game_locations ADD COLUMN review_status TEXT DEFAULT 'permanent'
  CHECK(review_status IN ('permanent', 'pending_review', 'discarded'));

ALTER TABLE npc_definitions ADD COLUMN review_status TEXT DEFAULT 'permanent'
  CHECK(review_status IN ('permanent', 'pending_review', 'discarded'));

ALTER TABLE game_config_enemies ADD COLUMN review_status TEXT DEFAULT 'permanent'
  CHECK(review_status IN ('permanent', 'pending_review', 'discarded'));
```

For `game_config_items`: repurpose existing fields:
- `approved = 1` AND `ai_generated = 0` → equivalent to `permanent`
- `approved = 0` AND `ai_generated = 1` → equivalent to `pending_review`
- `approved = 0` AND `ai_generated = 0` → discarded/inactive

### Status Meanings

| Status | Meaning |
|--------|---------|
| `permanent` | Admin-approved, part of the canonical world, used freely |
| `pending_review` | GM-created during a session, currently in use, awaiting admin decision |
| `discarded` | Admin rejected, should not be used in future sessions |

Records with `pending_review` are FULLY FUNCTIONAL during the current session. The status only affects:
- Whether they appear in admin-curated "permanent" lookups for future campaigns
- Whether admin sees them in the review queue

### Lookup-Before-Create Pattern

**In every service that creates world content (location, NPC, enemy), implement:**

```python
async def get_or_create_location(key: str, description: str, atmosphere: str) -> dict:
    # Step 1: DB lookup
    existing = db.execute(
        "SELECT * FROM game_locations WHERE key = ? AND review_status != 'discarded'",
        [key]
    ).fetchone()
    
    if existing:
        return existing  # Use existing record — consistency maintained
    
    # Step 2: Not found — create new entry
    new_location = {
        "key": key,
        "label": generate_label(key),
        "description": description,
        "atmosphere": atmosphere,
        "review_status": "pending_review",
        "is_active": 1,
        "ai_generated": 1  # flag for admin visibility
    }
    db.execute("INSERT INTO game_locations ...", new_location)
    return new_location
```

Same pattern for NPCs and enemies. Items are only created by admin (players can't invent items), but the LLM can reference item keys — if key not found, use a generic fallback.

### GM Prompt Instruction

Add to system prompt (or per-turn context injection):

```
WORLD CONTENT PROTOCOL:
When introducing a Location, NPC, or Enemy:
1. Use an existing key from the provided world content list when possible
2. Only create new content if no suitable match exists
3. New content you create will be reviewed by the admin — use consistent naming conventions
4. Never contradict established properties of existing records
```

The per-turn context injection includes the relevant DB records for the current location's linked NPCs and enemies.

### Admin Review Queue UI

**New section in admin panel:** "Pending World Entries"

**Display:**
- Tab bar: Locations | NPCs | Enemies
- Table per tab showing all `review_status = 'pending_review'` entries
- Each row: name, description, when created, which campaign created it, times used
- Actions per row: **Approve** (→ permanent) | **Edit + Approve** | **Discard**
- Batch select + bulk approve/discard

**New endpoints:**
- `GET /api/admin/world/pending` — all pending entries across types
- `PATCH /api/admin/world/locations/{id}/review` — `{action: "approve"|"discard"}`
- `PATCH /api/admin/world/npcs/{id}/review`
- `PATCH /api/admin/world/enemies/{id}/review`

---

## Example Flow

1. GM generates opening scene for a campaign set in a small town called "Graustein"
2. Backend calls `get_or_create_location("graustein_town", ...)`
3. No existing record → creates new location with `review_status = "pending_review"`
4. Game session proceeds — Graustein is used normally
5. GM introduces a vampire suspect NPC named "Viktor the Healer"
6. Backend calls `get_or_create_npc("viktor_healer", ...)`
7. No existing record → creates NPC with `review_status = "pending_review"`
8. Admin opens review queue → sees Graustein and Viktor as pending
9. Admin approves Graustein (good location, worth keeping) → `review_status = "permanent"`
10. Admin discards Viktor (too specific to one campaign) → `review_status = "discarded"`
11. Next campaign that needs a Graustein location finds the permanent record and uses its established description

---

## Edge Cases

- **Two simultaneous sessions create the same location key:** UNIQUE constraint on `key` — second creation fails gracefully, uses the first-created pending record
- **Admin discards a pending NPC that's currently active in a campaign:** NPC is still visible in the current campaign (session uses their own copy), but won't be found in future campaigns' lookups
- **GM invents an item** (not in `game_config_items`): Do not create items automatically — instead GM uses a "generic item" placeholder and admin adds the item manually through the normal item creation flow
- **Review queue grows too large:** Add admin setting: "Auto-discard pending entries older than {N} days with 0 times_used"

---

## Test Plan

1. Start a new campaign in a fresh setting → verify starting location created with `review_status = pending_review`
2. Continue campaign, GM introduces new NPC → verify NPC created with `pending_review`
3. Start SECOND campaign with same setting key → verify second campaign reuses the FIRST campaign's location record (lookup succeeds)
4. Admin approves a pending location → verify `review_status = permanent`
5. Admin discards a pending NPC → verify it's not returned in future DB lookups
6. Review queue UI shows correct counts per tab

---

## Related Tasks
- Task 09 (Location System) — locations created via this pattern
- Task 06 (Deviation Handling) — new branch NPCs/locations created via this pattern
- Task 05 (Campaign Plan Generation) — starting location created via this pattern
