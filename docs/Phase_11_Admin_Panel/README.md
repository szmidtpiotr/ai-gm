# Admin Panel 2.0 — Complete Implementation Summary

**Status: ✅ All 10 phases complete** | URL: `https://aigm-dev.studio-colorbox.com/admin2/`

---

## Architecture

Parallel deployment — old panel stays at `/panel/` untouched. New panel at `/admin2/` → `frontend/admin_panel_v2/`.

```
Nginx
├── /panel/   → frontend/admin_panel/        ← v1 (frozen)
└── /admin2/  → frontend/admin_panel_v2/     ← v2 (this)
```

**Stack:** Vanilla HTML/CSS/JS (no build system), FastAPI + SQLite, Docker on 192.168.1.61 (DEV).

---

## Design System

Dark SaaS Hybrid palette with amber gold accents:

```css
--bg-base:      #0f1117;
--bg-surface:   #1a1d27;
--bg-elevated:  #252836;
--accent-gold:  #c9a227;   /* primary accent */
--accent-red:   #c0392b;   /* danger / crits */
--accent-green: #27ae60;   /* success */
--text-primary: #e8e6e1;
--text-muted:   #6b7280;
```

**i18n:** Every section has `const LABELS = { ... }` at top. Game content labels are Polish; UI chrome stays English.

**Sidebar groups:** `── GAME ──` / `── LIVE ──` / `── SYSTEM ──`, collapsible, state persisted to localStorage.

---

## Sidebar Sections (final layout)

| # | Section | Label | Sub-tabs |
|---|---|---|---|
| 1 | Overview | Przegląd | — |
| 2 | Mechanics | Mechaniki | Stats · Skills · DC · Conditions · Archetypes |
| 3 | Content | Zawartość | Weapons · Armor · Items · Consumables · Loot Tables |
| 4 | World | Świat | Locations · NPCs · Enemies · Reguły |
| 5 | Prompts | Narracja | System · History Summary · Memory QA · Helpme |
| 6 | Players | Gracze | — |
| 7 | Campaigns | Kampanie | 🗺 Monitor · ✨ Kreator |
| 8 | Analytics | Statystyki | — |
| 9 | Voice | Głos | — |
| 10 | System | System | Database · Config · LLM · Slash Commands · Admin Cmd |

---

## Phase-by-Phase What Was Built

### Phase 1 — Foundation

- `frontend/admin_panel_v2/index.html` — full shell: sidebar with groups + dividers, topbar with LLM pill, login overlay (dev-login flow), activity log bar at bottom, section panels
- `frontend/admin_panel_v2/layout.css` (v28) — complete design system: CSS vars, sidebar, tables, modals, toasts, all section-specific CSS
- `frontend/admin_panel_v2/shared/` — api.js, auth.js, table.js (sort, filter, resize handles, popup tooltips), modal.js, toast.js

**UX extras added later:**
- Sidebar collapse (persistent)
- Section persistence on F5 (`aigm_admin2_section` localStorage)
- Activity log: sticky bottom, drag-to-resize, open/close persistent (`aigm_admin2_log_*`)
- AI chat bubble (floating ⚡ button, bottom-right, opens popup chat panel)
- Column resize drag handles on all tables (`tableId` → localStorage persistence)
- Cell popup tooltips for truncated long-text fields (`col.popup: true`)

---

### Phase 2 — Dashboard (Przegląd)

**Backend:** `GET /api/admin/overview` — aggregates users, active campaigns, turns today, active combats, DB size, LLM preset name, recent audit log, recent turns.

**Frontend:** `sections/dashboard.js`
- 6 stat cards (Active Combats highlighted red when > 0)
- Ostatnie zmiany (admin audit log feed)
- Ostatnie tury gry (last game turns feed)
- Auto-refresh every 30 s

---

### Phase 3 — Game Content Split

**`sections/mechanics.js`** — Stats · Skills · DC Tiers · Conditions · Archetypes
- Full CRUD on all tables via existing endpoints
- AI Assistant as floating bubble popup

**`sections/content.js`** — Weapons · Armor · Items · Consumables · Loot Tables
- Weapons: all columns including range_m, targeting, aoe, two_handed, finesse, magic_school, description, note
- **Armor**: separate tab (item_type=armor), `ac_bonus` column prominent
- Items: excludes armor entries
- AI Assistant as floating bubble popup

**`sections/world.js`** — Locations · NPCs · Enemies · Reguły

_Locations:_
- Columns: key, label, type, _parent_label (resolved from parent_id), _enemy_count, _rules_preview, description, is_active, locked_at
- Pending locations section (open by default, gold badge count, Zatwierdź/Odrzuć buttons → `/api/admin/locations/{id}/approve|reject`)
- Location modal: full rules editor (8 predefined checkboxes + value inputs + custom rules section + ✨ AI rule generator)

_NPCs:_
- Columns: id, key, label, npc_type, _location_keys_text (popup), is_shop, is_active, description (popup), personality_json (popup), shop_inventory_json (popup)
- Edit modal: location assignment via scrollable checkbox list (loaded from `/api/locations/admin/locations`)
- API field correction: personality_json/shop_inventory_json sent as strings (Pydantic `str` field)

_Enemies:_
- Columns: key, label, tier, hp_base, ac_base, attack_bonus, damage_die, damage_bonus, attacks_per_turn, damage_type, xp_award, loot_table_key, _drop_pct, _skills (popup), _ci (popup), note (popup), description (popup), is_active, locked_at
- Loot tables loaded in parallel for select dropdown
- _skills/_ci/_drop_pct mapped back to skills_json/conditions_immune/drop_chance on edit

_Reguły (Rules Library tab):_
- Predefined rules reference table (8 rules: no_combat, no_loot, teleport_blocked, stealth_check, rest_bonus, mana_regen, required_item, reason)
- Named rule preset creator: build a set of rules, save under a name, reuse across locations (stored in localStorage)
- AI bubble hidden on rules tab (uses its own AI button in preset editor)

_AI generation (✨ bubble):_
- Single floating bubble per tab, context-aware (generates location/npc/enemy based on active sub-tab)
- Each entity type has dedicated system prompt in `_WORLD_GEN_PROMPTS`
- Returns structured JSON pre-filled into the add/edit modal

---

### Phase 4 — Prompt Studio (Narracja)

**`sections/prompts.js`**
- Horizontal tab bar (matching Świat style): 🧠 System Prompt · 📖 History Summary · 🔍 Memory QA · 💡 Helpme
- Auto-loads first prompt on init
- Monospace textarea, char/line count bar
- Inline diff view (LCS-based line diff, add/delete/context highlighting) shown live while editing
- Save via `PUT /api/admin/prompts/{name}`, restore from backup
- Unsaved changes guard on tab switch

---

### Phase 5 — Players (Gracze)

**Backend:** `GET /api/admin/users/{user_id}/activity` — campaigns with character name/level/HP, turn count, last turn date.

**`sections/players.js`**
- User list table: id, username, display_name, is_admin, is_active, campaign_count
- Click row → slide-in drawer from right:
  - Role toggles (is_admin, is_active)
  - Password reset button
  - Per-user LLM settings (mode: default/custom, full provider config)
  - Campaign list with character HP bars, turn counts, last activity
  - Session sparkline (canvas turns-per-day chart)

---

### Phase 6 — Campaign Monitor

**Backend:** `GET /api/admin/campaigns/live` — joins campaigns + users + characters, returns HP/conditions/scene progress/last turn snippet.

**`sections/campaigns.js`** (accessed via Kampanie → 🗺 Monitor tab)
- Campaign cards grid: HP bar (green/amber/red), status badge, conditions, scene progress, last player message snippet
- Status filter + refresh + 60 s auto-refresh
- Detail modal with 3 inner tabs:
  - Przegląd — character sheet summary
  - Plan GM — arc/scene list with progress markers
  - Tury — last 15 turns (scrollable)
- Actions: Advance Scene, Regenerate GM Plan, Regenerate Summary

---

### Phase 7 — Analytics (Statystyki)

**Backend:**
- `backend/app/routers/admin_analytics.py` — 4 endpoints
- `backend/app/services/admin_analytics.py` — all DB query logic
- Registered in `main.py` at `/api/admin/analytics`

Endpoints: `overview`, `dice`, `combat`, `economy` (all `?days=7|30|90`)

**`sections/analytics.js`**
- Day range buttons (7/30/90), all 4 calls in parallel
- 6 stat cards
- Canvas line chart: turns/day (gold fill-under)
- Canvas bar chart: d20 distribution (player=gold/enemy=blue, crits=green, fumbles=red, dashed expected line)
- Combat stacked bar + top enemies table
- Economy items table

---

### Phase 8 — Campaign Designer / Hook Creator

**Backend:**
- `campaign_snippets` table in `migrations_admin.py`
- `POST /api/admin/campaign-designer/extract-pdf` — pypdf text extraction (max 25 000 chars)
- `POST /api/admin/campaign-designer/generate-hooks` — LLM returns array of `{title, content}` hooks
- `POST /api/admin/campaign-designer/generate-entity` — generates location/npc/enemy/rule JSON
- `GET/POST/DELETE /api/admin/campaign-designer/snippets`

**`sections/designer.js`** (accessed via Kampanie → ✨ Kreator tab)
- 3 input mode tabs: Prompt · Tekst/Historia · Plik PDF
- PDF mode: file pick → extract-pdf → shows text with page count + truncation warning
- Hook count selector (3/4/5/6)
- Generate → shows hook cards with editable titles + Save/Discard buttons per hook
- "Zapisz wszystkie" saves all unsaved hooks
- Library: only hook snippets, search, expandable cards, copy, delete
- LLM preset dropdown (overrides active preset)

**Kampanie hub (`sections/campaigns_hub.js`):** lazy-loads Monitor + Kreator as inner tabs.

---

### Phase 9 — System Consolidation

**`sections/system.js`** — 5 inner sub-tabs:

| Sub-tab | What it does |
|---|---|
| **LLM** | Preset management (create/edit/activate/delete), model fetcher (↻), Loki URL override |
| **Database** | DB info, table list with row counts, migrations runner, backup download, restore with confirm |
| **Config** | Export JSON, import with dry-run preview + commit, summary rollup settings |
| **Slash Commands** | Enable/disable per command, description editor, save to DB |
| **Admin Cmd** | Character cheat terminal: +GP, Full Heal, set level, clear inventory, end combat; quick action buttons; character state viewer |

---

### Phase 10 — Voice (Głos)

**`sections/voice.js`** — same logic as v1, new design tokens:
- Status badge (online/warn/offline) with TTS/STT loaded indicators
- Toggle switches (not plain checkboxes) for global TTS/STT
- Client TTS pref rows per bubble type (localStorage)
- Two-column: TTS config + test | STT config + silence params
- 30 s health poll, audio state cleanup on re-init

---

## Extra Features (Beyond Original Plan)

| Feature | Where |
|---|---|
| Enemies moved to Świat | World tab, not Content |
| Armor as separate tab | Content → Zbroja |
| Kampanie + Kreator merged | Single sidebar entry, inner tabs |
| Location rules editor | Location modal + Reguły sub-tab |
| Pending location approve/reject | Locations tab, auto-badge count |
| NPC location multi-select | NPC modal, checkbox list |
| Rules library + presets | Świat → Reguły |
| AI rule generator | Reguły preset editor + location modal |
| Column resize (persistent) | All tables with tableId |
| Cell popup tooltips | All long-text fields |
| Activity log drag-resize | Bottom log bar |
| Section persistence F5 | localStorage `aigm_admin2_section` |
| Narracja horizontal tabs | Matching Świat layout |
| demo/demo login fixed | DB password reset |

---

## File Map

```
frontend/admin_panel_v2/
├── index.html                    (shell, sidebar, login, moduleMap)
├── layout.css                    (v28 — complete design system)
├── shared/
│   ├── api.js                    (adminFetch + event dispatch)
│   ├── auth.js                   (connect/disconnect/baseUrl)
│   ├── table.js                  (renderTable: sort, filter, resize, popup)
│   ├── modal.js                  (openModal, showConfirm)
│   └── toast.js                  (showToast)
└── sections/
    ├── dashboard.js              (Overview)
    ├── mechanics.js              (Stats/Skills/DC/Conditions/Archetypes)
    ├── content.js                (Weapons/Armor/Items/Consumables/Loot)
    ├── world.js                  (Locations/NPCs/Enemies/Reguły)
    ├── prompts.js                (Narracja — 4 prompt editors)
    ├── players.js                (Users + detail drawer)
    ├── campaigns.js              (Campaign Monitor cards + modal)
    ├── campaigns_hub.js          (Wrapper: Monitor + Kreator tabs)
    ├── designer.js               (Hook Creator: PDF/Text/Prompt)
    ├── analytics.js              (Charts: dice/turns/combat/economy)
    ├── voice.js                  (TTS/STT config)
    └── system.js                 (DB/Config/LLM/Slash/AdminCmd)

backend/app/routers/
├── admin.py                      (all admin endpoints — additive only)
└── admin_analytics.py            (analytics router)

backend/app/services/
└── admin_analytics.py            (analytics DB queries)
```

---

## Backend Endpoints Added (new, all in admin.py unless noted)

| Endpoint | Phase | Purpose |
|---|---|---|
| `GET /api/admin/overview` | 2 | Dashboard aggregate stats |
| `GET /api/admin/users/{id}/activity` | 5 | User campaign/turn history |
| `GET /api/admin/campaigns/live` | 6 | Live campaign state for monitor |
| `GET /api/admin/analytics/*` | 7 | admin_analytics.py router |
| `POST /api/admin/campaign-designer/extract-pdf` | 8 | PDF → text (pypdf) |
| `POST /api/admin/campaign-designer/generate-hooks` | 8 | Multi-hook LLM generation |
| `POST /api/admin/campaign-designer/generate-entity` | 8 | Single entity JSON (location/npc/enemy/rule) |
| `GET/POST/DELETE /api/admin/campaign-designer/snippets` | 8 | Snippet CRUD |
| `GET /api/admin/campaigns/{id}/turns` | 6 | Last N turns for modal |

---

## Next: Phase 12 — Campaign Plot Creator

See `docs/Phase_11_Campaign_Plot_Creator/README.md` for full spec.

**TL;DR:** Admin selects hooks + locations + NPCs + enemies from DB, writes a tone brief, and the LLM generates a full `gm_plan_json` campaign skeleton (arcs + scene goals). Preview + inline edit + save to campaign.

Estimated effort: ~1 focused session.
