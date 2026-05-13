# Phase 11 — Campaign Plot Creator

## Goal

Admin uses an LLM agent to generate a full campaign plot plan — a structured `gm_plan_json` draft — built from saved assets already in the database: hooks (from the Hook Creator), locations, NPCs, and enemies. The result is a ready-to-use campaign skeleton that the GM LLM can execute in-game.

---

## Context

By Phase 10, the admin has a growing library of reusable game assets:

| Asset | Where stored | How created |
|---|---|---|
| Hooks | `campaign_snippets` (snippet_type=hook) | Kreator tab (PDF/text/prompt input) |
| Locations | `game_locations` | Świat → Lokacje |
| NPCs | `npcs` + `npc_locations` | Świat → NPC |
| Enemies | `game_config_enemies` | Świat → Wrogowie |
| Rule presets | localStorage | Świat → Reguły |

Phase 11 connects these assets into a coherent campaign narrative.

---

## Feature Design

### 1. Asset Selector

The admin selects which assets to include:

- **Hooks** — multi-select from `campaign_snippets` (hook type), filtered by search
- **Locations** — multi-select from `game_locations`
- **NPCs** — multi-select from `npcs`
- **Enemies** — multi-select from `game_config_enemies`
- **Tone / Brief** — free text describing the overall campaign mood and direction (e.g. "mroczna intryga polityczna, zdradziecka gildia kupców")
- **Arc count** — how many major story arcs (1–5)
- **Scenes per arc** — how many scenes per arc (2–6)

### 2. LLM Generation

The admin clicks **"Generuj plan kampanii"**. The backend:

1. Loads full text of all selected assets from DB
2. Builds a structured system prompt instructing the LLM to produce a `gm_plan_json`
3. Calls the LLM (respects active preset or chosen preset)
4. Parses and validates the returned JSON
5. Returns the draft plan to the frontend

The generated `gm_plan_json` follows the existing game engine structure:

```json
{
  "arcs": {
    "arc_1": {
      "title": "Cień Gildiil",
      "status": "pending",
      "hooks": ["hook text..."],
      "scene_goals": [
        "Gracz odkrywa korupcję w tawernie",
        "Konfrontacja z mistrzem gildii",
        "Ucieczka z podziemi"
      ]
    }
  },
  "active_arc_id": "arc_1"
}
```

### 3. Plan Preview & Edit

- The generated plan renders as an interactive arc/scene tree (same component as the Campaign Monitor GM Plan viewer)
- Admin can **edit scene goals inline** before saving
- Admin can **regenerate a single arc** without regenerating the whole plan
- Shows which input assets were "used" (highlighted)

### 4. Save to Campaign

The admin selects a target campaign (or creates a new one) and saves the plan:

- `PUT /api/admin/campaigns/{id}/gm-plan` — saves `gm_plan_json`
- Optionally also assigns selected locations, NPCs, enemies to the campaign

---

## Backend Changes

### New endpoint: `POST /api/admin/campaign-designer/generate-plot`

**Request body:**
```json
{
  "hook_ids": [1, 2, 3],
  "location_keys": ["tavern_main", "guild_hall"],
  "npc_keys": ["merchant_aldric", "guildmaster_vorn"],
  "enemy_keys": ["bandit_thug", "guild_enforcer"],
  "brief": "Mroczna intryga polityczna, zdradziecka gildia kupców",
  "arc_count": 3,
  "scenes_per_arc": 4,
  "preset_id": null
}
```

**Response:**
```json
{
  "gm_plan_json": { ... },
  "used_assets": { "hooks": [...], "npcs": [...], ... },
  "model_used": "gpt-4.1"
}
```

### System prompt strategy

The LLM receives:
- The game's tone and mechanics (dark fantasy, d20, Polish language)
- All selected hooks as narrative seeds
- Location descriptions to ground scenes geographically
- NPC personality summaries to drive character-driven plot
- Enemy names/tiers to place in encounter scenes
- Admin's brief as the overarching direction
- Strict JSON schema for `gm_plan_json` output

---

## Frontend Changes

### New sub-tab inside Kampanie → Kreator: "Plan Fabuły"

OR a standalone new section. TBD with user.

**UI layout:**
```
┌─────────────────────────────────────────────────────┐
│  ASSET SELECTOR          │  GENERATED PLAN           │
│                          │                           │
│  Haki (3 selected)  ▼   │  Arc 1: Cień Gildii       │
│  Lokacje (2) ▼           │    Scene 1: ...           │
│  NPC (2) ▼               │    Scene 2: ...           │
│  Wrogowie (1) ▼          │  Arc 2: Zdrada Mistrza    │
│                          │    Scene 1: ...           │
│  Brief:                  │                           │
│  [textarea]              │  [Edytuj] [Zapisz do      │
│                          │   kampanii ▼]             │
│  Arki: [3] Sceny: [4]   │                           │
│                          │                           │
│  [Generuj plan kampanii] │                           │
└─────────────────────────────────────────────────────┘
```

---

## Dependencies

- Phase 8 (Hook Creator) must be complete — provides `campaign_snippets` ✅
- Phase 3 (World — Locations, NPCs, Enemies) must be complete ✅
- Phase 6 (Campaign Monitor — `gm_plan_json` structure known) ✅

---

## Out of Scope for Phase 11

- The campaign flag on locations/NPCs/enemies (discussed, deferred — easy to add later)
- Automatic NPC/enemy assignment to campaigns (can be manual for now)
- Streaming LLM output (generate-plot returns full JSON, not a stream)

---

## Open Questions

1. **Where does "Plan Fabuły" live in the UI?** — inside Kampanie → Kreator as a third tab, or a separate top-level section?
2. **Should the plan be editable arc-by-arc inline, or only after full generation?**
3. **Should saving the plan also start a new campaign, or only update an existing one?**
4. **Polish or English for generated scene titles?** (Game narration is Polish — likely Polish output)

---

## Estimated Work

| Area | Effort |
|---|---|
| Backend endpoint + LLM prompt engineering | Medium (1 session) |
| Asset selector UI (multi-selects from DB) | Small |
| Plan preview + inline edit | Medium (reuses Campaign Monitor components) |
| Save to campaign flow | Small |
| **Total** | **~1 focused session** |
