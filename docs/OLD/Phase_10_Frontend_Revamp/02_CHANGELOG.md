# Phase 10: Frontend Revamp — Changelog

Track implementation progress for the mobile-first frontend.

---

## 2026-05-08

### T28.5 — Initial Mobile-First Frontend (DONE)

**Scope:** Core application shell based on Figma v18-20 designs

**Implemented:**
- Login screen with dark theme styling
- Campaigns list screen with empty state
- New campaign creation form with suggestions
- 4-step character wizard (name → race → class → backstory)
- Game screen with chat messaging
- Character sheet slide-up panel with tabs (stats/skills/inventory)
- Settings panel with font customization
- Toast notifications
- API integration for auth, campaigns, characters, turns
- Chat history loading and GM response parsing
- Mobile viewport meta tags, touch-friendly controls

**Files created:**
- `frontend/front/index.html` — HTML structure
- `frontend/front/css/styles.css` — Design system (~800 lines)
- `frontend/front/js/app.js` — Application logic (~850 lines)
- `frontend/front/img/` — 14 Figma reference screens

**Config:**
- `frontend/nginx.conf` — Added `/front/` location

**Design tokens:**
- Background: `#1a1a2e`, `#252542`
- Accent: `#c9a54a` (gold)
- Text: `#e0e0e0`, `#a0a0a0`
- Borders: `#3a3a5c`
- Chat bubbles: GM green `#2d4a3e`, User blue `#2a3f5f`

---

## 2026-05-08

### C04-C06 — Campaign Actions (DONE)

**Scope:** Campaign deletion on list screen, reset actions in settings (admin)

**Implemented:**
- **Delete campaign on list screen:**
  - Mobile: swipe left to reveal red delete button
  - Desktop: trash icon appears on card hover
- **Admin settings (in-game cog menu):**
  - Reset Campaign — clears chat history, keeps campaign/character
  - Reset Character — restores sheet to post-wizard state

**Files modified:**
- `frontend/front/index.html` — Admin section (reset only, delete moved)
- `frontend/front/css/styles.css` — Swipe wrapper, delete action, hover trash
- `frontend/front/js/app.js` — `renderCampaigns` with swipe, `initSwipeGesture`, `handleDeleteCampaignFromList`

---

## 2026-05-08

### Y01-Y02 — History Summary: Dziennik podróżnika (DONE)

**Scope:** Campaign narrative summary as slide-up "Traveler's Journal" panel

**Implemented:**
- Book icon button in game header (between character and settings buttons)
- Slide-up panel matching settings/sheet panel pattern
- Loads saved summary via `GET /api/campaigns/{id}/history/summary?audience=player`
- "Odśwież podsumowanie" button regenerates via `POST` (calls LLM, overwrites saved)
- Loading dots animation while fetching
- Empty state with icon when no summary exists yet
- Error banner when regen fails (falls back to showing last saved summary)
- Summary text displayed in parchment-styled box using current chat font/size
- Swipe-down-to-close + overlay click to close
- Opens: closes any other open panel first

**Files modified:**
- `frontend/front/index.html` — journal button in header, journal panel HTML
- `frontend/front/css/styles.css` — journal panel styles, loading dots, parchment body
- `frontend/front/js/app.js` — `toggleJournal`, `closeJournal`, `loadJournalContent`, `fetchSavedJournal`, `showJournalText`, `showJournalEmpty`, `showJournalBanner`

---

## 2026-05-09

### B01-B04 — Combat System (DONE)

**Scope:** Mobile-first combat UI with attack/flee actions and live state sync

**Implemented:**
- **Combat banner** at top of game screen (slides in when active)
  - Round indicator + whose turn (player/enemy with color/animation)
  - Enemy list with name, HP `current/max`, color-tiered HP bar (green/yellow/red)
  - Death state: dim, strikethrough, skull icon
  - Status message line (success/error)
- **Combat composer** replaces normal input during combat
  - Big "Atak" (red gradient) and "Ucieczka" (dark) buttons
  - Disabled during enemy turn or while busy
- **Polling** every 3.5s while game screen active
  - Auto-shows banner when GM initiates combat (also re-polls after sendMessage)
  - Auto-hides when combat ends
- **Attack flow**: roll d20 (`/api/gm/dice`) → POST `resolve-attack` → system bubble with result → hidden combat narration message → GM responds
- **Flee flow**: confirm → POST `/combat/flee` → system bubble → hidden narration → GM responds
- Polling stopped when leaving game screen

**Files modified:**
- `frontend/front/index.html` — combat banner, combat composer
- `frontend/front/css/styles.css` — banner, enemy rows, HP bars, attack/flee buttons
- `frontend/front/js/app.js` — `pollCombatState`, `renderCombatUI`, `handleCombatAttack`, `handleCombatFlee`, `sendCombatNarration`

---

---

## 2026-05-09

### W03-W05 — Character Creation Wizard Rewrite (DONE)

**Scope:** Complete wizard rewrite to use the real backend character creation flow

**Problem:** Previous wizard had fake race/class selection (Człowiek/Elf/Krasnolud) — no such thing exists in the backend. The real flow uses archetypes (warrior/scholar) and calls 3 endpoints.

**Real backend flow implemented:**
1. `POST /campaigns/{id}/characters` — rolls stats + skills, returns character
2. `POST /characters/{id}/generate-identity` — LLM generates appearance/personality preview
3. `POST /characters/{id}/finalize-sheet` — persists all edits (stat overrides, skill swaps, name, backstory)

**Step 1 — Name, background, archetype:**
- Text input for name + backstory textarea
- Archetype radio: Wojownik (STR+2/CON+1) vs Uczony (INT+2/WIS+1)
- Calls `POST /campaigns/{id}/characters` on submit
- Loading dots animation on "Dalej" button while API is in flight

**Step 2 — Stats (pool model):**
- Displays rolled stat values with archetype bonus applied
- Decrease stat → adds to unassigned pool; increase stat → spends pool
- `wizardStatBases` tracks editable values; `wizardStatOriginal` allows reset
- Layout: stat name | modifier | `−` value `+` controls tight/inline

**Step 3 — Skills (swap model):**
- 16 skill rows showing all rolled skills with rank (1 or 2 dots)
- Up to 4 free name-swaps from unrolled pool (free, costs no budget)
- Level change (▲/▼ rank) costs skill budget points
- `wizardSkillSwapMap` tracks swapped names; `wizardSkillLevels` tracks rank overrides

**Step 4 — Identity (LLM preview):**
- Calls `POST /characters/{id}/generate-identity` while showing spinner
- Displays LLM-generated appearance and personality
- "Stwórz postać" button calls `_wizardFinalizeAndEnter()` with full payload

**Files modified:**
- `frontend/front/js/app.js` — full wizard rewrite (`_renderStep1-4`, `_wizardStep1Submit`, `_wizardStep3Submit`, `_wizardFinalizeAndEnter`, helpers)
- `frontend/front/css/styles.css` — stat controls layout, skill rows, swap-mode, loading dots

---

### M05 — GM Narrative Parsing Fix (DONE)

**Scope:** Raw JSON was showing in GM chat bubbles

**Problem:** `parseGmResponse` failed to extract narrative from some LLM responses (especially when JSON was nested or had code fences).

**Fix:**
- Rewrote `parseGmResponse` to match old frontend's robust extraction: strip `__AI_GM` prefix lines, strip code fences, try full JSON.parse, fall back to character-by-character JSON extraction
- Added `parseGmFull(text)` → `{narrative, locationIntent, raw}` for structured responses
- Strips `[LOCATION_BLOCKED:...]` tags from narrative text

**Files modified:**
- `frontend/front/js/app.js` — `parseGmResponse`, `parseGmFull`

---

### Backend Fix — LLM model "default" not resolving to Global LLM (DONE)

**Scope:** HTTP 404 "model 'default' does not exist" when campaign model was set to "default"

**Problem:** `_resolve_model("default", effective)` treated `"default"` as a non-empty string (truthy) and returned it literally instead of falling back to the Global LLM setting.

**Fix (backend — required SSH rebuild):**
- `backend/app/services/llm_service.py`: `_resolve_model` now treats `"default"` same as `None`
- `backend/app/api/turns.py`: `resolve_model_name` + `_clean_model_hint` helper strips "default" → None

---

### Admin Panel — Background Upload Fix (DONE)

**Scope:** "Missing or invalid authorization header" error on background image upload

**Problem:** `ui_settings.js` read `localStorage.getItem("adminToken")` but admin panel stores token under `"aigm_admin_token"`.

**Fix + improvements:**
- Fixed key to `"aigm_admin_token"`
- Added `desc` field to all `BG_SCREENS` entries with human-readable descriptions
- Added `.ui-bg-card__desc` CSS for description display

**Files modified:**
- `frontend/admin_panel/sections/ui_settings.js`
- `frontend/admin_panel/layout.css`

---

### G06 — Debug Panel (DONE / location tracking pending)

**Scope:** Per-GM-bubble debug panel showing COMBAT state and LOCATION intent

**Implemented:**
- Debug toggle in Settings panel (Settings → Debug section) — persists to `localStorage['aigm_debug']`
- Every GM message gets a `div.debug-block` appended below the bubble
- Shows live-refreshed COMBAT state (updated AFTER `pollCombatState()` resolves)
- Shows `location_intent` from `parseGmFull` when the LLM includes it in JSON response
- Blocks hidden/shown via `el.style.display` (avoids `<details>` + `overflow:hidden` Chrome bug)

**Pending:**
- Task #1: Track `lastKnownLocation` on frontend across turns so LOCATION always shows, not just when LLM includes it in the current response

**Files modified:**
- `frontend/front/index.html` — debug toggle in settings HTML
- `frontend/front/js/app.js` — `debugMode`, `parseGmFull`, `appendMessage` debug block, `_renderDebugCombatLine`, `_refreshDebugBlocks`
- `frontend/front/css/styles.css` — `.debug-block`, `.debug-block__pre`, `.debug-block__loc`

---

## Backlog

### Next up
- [ ] Task #1: Location tracking in debug panel (G06 partial)
- [ ] Shop modal (H01-H04)
- [ ] Archive toggle (M06)
- [ ] XP spending UI (S09)

### Later
- [ ] Voice features (V01-V04)
