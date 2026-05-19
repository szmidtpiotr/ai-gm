# TASK 10 — Data Tables as Source of Truth

**Status:** ✅ Done — commit `cd4c2d1` (2026-05-13)
**Phase:** 03 — World

---

## Overview

The LLM narrator does not invent world content from scratch. Locations, NPCs, and enemies must resolve to a DB record before they can be used. If a record does not exist, the LLM signals the need to create one via a structured tag. The system creates a `pending_review` record, uses it immediately, and queues it for admin review.

This pattern prevents world inconsistency: every named place, person, and creature in the game has a single authoritative record.

---

## Priority Order for World Content

For any named entity the LLM needs to reference:

```
1. DB lookup by key
   └── Found → use existing record (permanent or pending_review)
   └── Not found →

2. DB candidate lookup by attributes (locations only — Stage 2B-Schema)
   └── Query canonical/non-discarded records matching biome + subtype + tier
   └── Inject best candidates into LLM prompt as "[AVAILABLE CONTENT]"
   └── Narrator should pick one of these keys instead of minting new

3. LLM emits [CREATE_*] tag in its narrative output (fallback only)
   └── System parses tag, creates record with review_status='pending_review'
   └── For locations: created_by='gm_runtime', canonical=0, source_campaign_id=current
   └── Record is used immediately in the current session

4. Admin reviews the new record
   └── Approve → review_status='permanent'
   └── Promote to canonical → also canonical=1 (enters preferred-reuse pool)
   └── Edit + Approve → fix then permanent
   └── Discard → review_status='discarded'
```

Records with `review_status = 'discarded'` are not injected into future sessions. Sessions where a discarded record was already used retain it (no retroactive changes).

**Target ratio:** ~60-70% of locations referenced per campaign come from `created_by IN ('seed','admin_manual','admin_kreator')` (the curated set). The remaining ~30-40% may be `gm_runtime`. The candidate-injection step at priority (2) is the mechanism that pushes the ratio in this direction.

---

## `review_status` Field

Added to three tables:

```sql
ALTER TABLE game_locations ADD COLUMN review_status TEXT DEFAULT 'permanent';
ALTER TABLE npc_definitions ADD COLUMN review_status TEXT DEFAULT 'permanent';
ALTER TABLE game_config_enemies ADD COLUMN review_status TEXT DEFAULT 'permanent';
```

Valid values: `permanent` / `pending_review` / `discarded`

All existing records default to `permanent` (migration sets this via the DEFAULT clause).

---

## CREATE Tags

The LLM may emit the following tags inline in its narrative response. Tags must appear on their own line. The game engine parses them after receiving the LLM output and strips them before displaying the narrative to the player.

### `[CREATE_LOCATION]`

```
[CREATE_LOCATION: key=x, label=x, type=macro|sub, parent_key=x, atmosphere=x, description=x]
```

| Field       | Required | Notes                                                  |
|-------------|----------|--------------------------------------------------------|
| key         | Yes      | Snake_case identifier. Must be unique.                 |
| label       | Yes      | Display name shown to player.                          |
| type        | Yes      | `macro` or `sub`.                                      |
| parent_key  | No       | Required if type=sub. Key of the parent macro location.|
| atmosphere  | No       | Short mood descriptor (e.g. "oppressive, rain-soaked").|
| description | No       | 1–3 sentences.                                         |

### `[CREATE_NPC]`

```
[CREATE_NPC: key=x, name=x, role=x, personality=x, location_key=x]
```

| Field        | Required | Notes                                                    |
|--------------|----------|----------------------------------------------------------|
| key          | Yes      | Snake_case identifier. Must be unique.                   |
| name         | Yes      | Display name.                                            |
| role         | Yes      | Narrative role (e.g. "innkeeper", "informant", "thug").  |
| personality  | Yes      | Short raw description used to generate `personality_prompt`. Max 200 chars. |
| location_key | No       | Key of the location where this NPC is currently present. |

After parsing, the system generates a full `personality_prompt` via a secondary LLM call (see TASK_09).

### `[CREATE_ENEMY]`

```
[CREATE_ENEMY: key=x, name=x, based_on=existing_key, tier=weak|standard|elite|boss]
```

| Field      | Required | Notes                                                         |
|------------|----------|---------------------------------------------------------------|
| key        | Yes      | Snake_case identifier. Must be unique.                        |
| name       | Yes      | Display name (e.g. "Bog Wraith", "Corrupted Militiaman").     |
| based_on   | No       | Key of an existing enemy. New enemy inherits base stats, then tier scaling is applied. If omitted, use tier defaults. |
| tier       | Yes      | `weak` / `standard` / `elite` / `boss`. Applies stat multipliers from a tier table. |

### Items — No Auto-Creation

Items are **not** auto-created via tags. If the LLM references an unknown item key, the system logs a warning and substitutes a generic fallback appropriate to the context (e.g. "a worn blade" for a weapon reference). Only admin creates items via the admin panel.

---

## Per-Turn Context: Available Content Index

Before each turn, the context injector builds a summary index of usable content for the player's current location. This index is injected into the LLM prompt so the narrator uses real keys rather than invented ones.

Format injected:

```
[AVAILABLE CONTENT — use these keys, do not invent new ones unless unavoidable]
Location: {current_location.key} — {current_location.label}

Nearby NPCs:
- {key}: {name} ({npc_type})
- ...

Possible enemies:
- {key}: {name} (tier: {tier})
- ...

Reusable nearby locations (prefer these before [CREATE_LOCATION]):
- {key}: {label} ({subtype}, {biome}, tier {tier})  ★ canonical
- ...
```

If a needed entity is not in this list, the LLM should emit a `[CREATE_*]` tag to register it, not simply invent a key.

### Reusable-locations query (Stage 2B-Schema Phase 2)

When the player is on hex `(q, r)` with `hex_type = X` and hero level `L`, the injector runs:

```sql
SELECT key, label, location_subtype, biome, tier, canonical
FROM game_locations
WHERE review_status != 'discarded'
  AND is_active = 1
  AND (biome = ? OR biome IS NULL)        -- biome bound to hex_type
  AND tier <= ?                            -- ceil(L/2) + 1
ORDER BY
  canonical DESC,                          -- canonical first
  CASE WHEN created_by IN ('seed','admin_manual','admin_kreator') THEN 0 ELSE 1 END,
  usage_count DESC                         -- popular content first within same tier
LIMIT 5;
```

If `location_subtype` is contextually narrow (e.g., narrative beat calls for a tavern), filter by it. Otherwise return the diversified top-5 so the narrator can pick what fits.

---

## Admin Review Queue

New section in the admin panel: **Review Queue**.

Three tabs: **Locations** | **NPCs** | **Enemies**

Each tab shows all records with `review_status = 'pending_review'` for that entity type.

### Review Table Columns

| Column        | Notes                                                      |
|---------------|------------------------------------------------------------|
| Name / Label  | Display name of the entity.                                |
| Description   | Short description or personality summary.                  |
| Source campaign | Name of the campaign that triggered creation.            |
| Times used    | How many turns have referenced this record since creation. |
| Actions       | [Approve] [Edit + Approve] [Discard]                       |

### Actions

- **Approve**: sets `review_status = 'permanent'`. No edits.
- **Edit + Approve**: opens an inline edit form pre-populated with current values. On save, sets `review_status = 'permanent'`.
- **Discard**: sets `review_status = 'discarded'`. Confirm dialog: "This entity will not appear in future sessions. Current sessions are unaffected."

### Badge Count

The admin sidebar entry for "Review Queue" shows a badge with the total count of `pending_review` records across all three tables. Badge disappears when count reaches zero.

---

## Tag Parsing Implementation

Tag parsing runs in a post-processing step after receiving the full LLM response string:

1. Scan response for lines matching `[CREATE_*: ...]` pattern.
2. For each match: parse key=value pairs, call the appropriate create function.
3. Create function inserts the record with `review_status = 'pending_review'`, returns the new record's DB ID.
4. Replace the tag line in the response with an empty string (strip from player-visible output).
5. If tag parsing fails (malformed key=value): log the error, skip creation, leave the tag stripped (do not show raw tag to player).

Tag parsing is idempotent: if a key already exists (race condition or retry), the create function performs an upsert or returns the existing record.

---

## DB Migration Summary

Single migration covers all three tables:

```sql
-- game_locations
ALTER TABLE game_locations ADD COLUMN review_status TEXT DEFAULT 'permanent';
ALTER TABLE game_locations ADD COLUMN safe_for_rest INTEGER DEFAULT 0;  -- TASK_08

-- npc_definitions
ALTER TABLE npc_definitions ADD COLUMN review_status TEXT DEFAULT 'permanent';
ALTER TABLE npc_definitions ADD COLUMN personality_prompt TEXT DEFAULT '';  -- TASK_09
ALTER TABLE npc_definitions ADD COLUMN keyword_triggers TEXT DEFAULT '[]';  -- TASK_09
ALTER TABLE npc_definitions ADD COLUMN npc_type TEXT DEFAULT 'neutral';     -- TASK_09

-- game_config_enemies
ALTER TABLE game_config_enemies ADD COLUMN review_status TEXT DEFAULT 'permanent';
```

All new columns have safe defaults and will not break existing records.

### Stage 2B-Schema additional columns (locations only)

```sql
-- game_locations — provenance & reuse fields
ALTER TABLE game_locations ADD COLUMN created_by         TEXT    NOT NULL DEFAULT 'admin_manual';
ALTER TABLE game_locations ADD COLUMN location_subtype   TEXT    DEFAULT NULL;
ALTER TABLE game_locations ADD COLUMN biome              TEXT    DEFAULT NULL;
ALTER TABLE game_locations ADD COLUMN tier               INTEGER NOT NULL DEFAULT 1;
ALTER TABLE game_locations ADD COLUMN canonical          INTEGER NOT NULL DEFAULT 0;
ALTER TABLE game_locations ADD COLUMN usage_count        INTEGER NOT NULL DEFAULT 0;
ALTER TABLE game_locations ADD COLUMN source_campaign_id INTEGER NULL REFERENCES campaigns(id);

-- backfill from legacy ai_generated boolean
UPDATE game_locations SET
  created_by = CASE WHEN ai_generated = 1 THEN 'gm_runtime' ELSE 'admin_manual' END,
  canonical  = CASE WHEN review_status = 'permanent' AND ai_generated = 0 THEN 1 ELSE 0 END;

-- indexes for the candidate query
CREATE INDEX IF NOT EXISTS idx_game_locations_biome_subtype ON game_locations(biome, location_subtype);
CREATE INDEX IF NOT EXISTS idx_game_locations_canonical     ON game_locations(canonical);
```

See `TASK_08_LOCATION_SYSTEM.md` § "Provenance & Reuse" for the full field rationale.

---

## Implementation Notes
- `review_status` columns on game_locations, npcs, game_config_enemies already in DB from TASK_01 migrations
- `process_create_tags()` in `world_service.py`: regex-based tag parsing, idempotent (existing key = return existing record)
- [CREATE_ENEMY] inherits stats from `based_on` key if provided; otherwise uses tier defaults
- Items: no [CREATE_ITEM] tag — items are admin-only, consistent with spec
- Admin review queue: 5 endpoints at `/api/admin/world/...` (counts, list per type, approve/discard)
- `build_available_content_index()` injects [AVAILABLE CONTENT] block with real DB keys
- Tags processed AFTER turn saves to DB (in DONE event handler) — prevents blocking the stream
- Turn pipeline (TASK_11) will need to call `build_available_content_index()` + `build_v2_npc_context_block()` before each LLM call
