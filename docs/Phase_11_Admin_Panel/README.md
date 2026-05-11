# Phase 11 — Admin Panel 2.0

## Context

The current admin panel is a functional but aging 8-tab vanilla JS tool built incrementally across game phases. It has grown organically, leaving a single 225 KB `game_design.js` monster, mixed Polish/English UI, no dashboard, no analytics, and a Test Runner tab that only belongs in dev.

Admin Panel 2.0 is a **parallel deployment** — the old panel stays at `/admin/` and keeps working unchanged throughout development. The new panel lives at `/admin2/` and is developed phase by phase. Once all phases are complete and validated, the old panel can be retired (or kept forever as a fallback).

**Stack:** Vanilla HTML/CSS/JS (no build system), FastAPI + SQLite backend, Nginx, Docker on 192.168.1.61 (DEV).

---

## Parallel Deployment Architecture

```
Nginx (frontend container)
├── /admin/       → frontend/admin_panel/       ← OLD panel (untouched)
├── /panel/       → frontend/admin_panel/       ← OLD panel alias
└── /admin2/      → frontend/admin_panel_v2/    ← NEW panel (this phase)
```

### What changes to make this work
1. `frontend/nginx.conf` — add 2 location blocks for `/admin2/`
2. `frontend/admin_panel_v2/` — new folder, completely independent
3. Backend API — only **additive** new endpoints; nothing existing is changed or removed

### Shared utilities strategy
Copy `shared/` from v1 into `admin_panel_v2/shared/` in Phase 1. This gives v2 a clean, independent copy that can be upgraded (new palette, sort, etc.) without risking v1.

```
frontend/
├── admin_panel/           ← v1 (frozen, untouched)
│   ├── shared/
│   └── sections/
└── admin_panel_v2/        ← v2 (new)
    ├── shared/            ← copied from v1, then upgraded
    ├── sections/          ← all new files
    ├── index.html
    └── layout.css
```

---

## Workflow: Questions Before Each Phase

Before starting each phase, Claude will ask clarifying questions to confirm scope, design decisions, and any edge cases for that specific phase. **No phase starts without user confirmation.**

---

## New Section Map

Old 8 tabs → New 11 sections:

| # | Section | Sidebar Label (PL) | Contents | Replaces |
|---|---|---|---|---|
| 1 | Overview | Przegląd | Live stat cards, recent activity feed | — (new) |
| 2 | Mechanics | Mechaniki | Stats, Skills, DC Tiers, Conditions | game_design.js (partial) |
| 3 | Content | Zawartość | Weapons, Enemies, Items, Consumables, Loot Tables, Archetypes | game_design.js (partial) |
| 4 | World | Świat | Locations (tree), NPCs | game_design.js (partial) |
| 5 | Prompts | Narracja | Prompt Studio — System, History, Memory, Helpme | game_design.js (partial) |
| 6 | Players | Gracze | Users, roles, per-user LLM, campaign list, session timeline | accounts.js |
| 7 | Campaigns | Kampanie | Campaign Monitor: live state, GM plan, scene advancement | accounts.js (partial) |
| 8 | Campaign Designer | Kreator | AI agent for generating campaign hooks/snippets | — (new) |
| 9 | Analytics | Statystyki | Dice stats, combat outcomes, turn activity (native charts) | — (new) |
| 10 | Voice | Głos | Piper TTS/STT config | voice.js |
| 11 | System | System | DB, Migrations, Backup, Config export/import, LLM presets, Slash commands, Admin Cmd | technical.js + config.js + ui_settings.js + admin_commands.js |

**Removed from v2:** Test Runner (backend route stays for dev container use).

---

## Design System

**Style:** Dark SaaS Hybrid — charcoal base with amber gold accents and crimson for danger/crits.

```css
--bg-base:      #0f1117;   /* near-black base */
--bg-surface:   #1a1d27;   /* panels, cards */
--bg-elevated:  #252836;   /* raised elements */
--border:       #2e3244;
--accent-gold:  #c9a227;   /* primary accent, active sidebar, headings */
--accent-red:   #c0392b;   /* danger, crits, delete */
--accent-green: #27ae60;   /* success, connected */
--text-primary: #e8e6e1;
--text-muted:   #6b7280;
```

**i18n convention:** Every section file starts with a `const LABELS = { ... }` block. All user-visible game content strings (labels, descriptions, placeholders) are Polish. UI chrome (Save, Delete, Loading...) stays English.

**Sidebar:** grouped with dividers — `── GAME ──`, `── LIVE ──`, `── SYSTEM ──`.

---

## Phase Progress

| Phase | Description | Status | Notes |
|---|---|---|---|
| **0** | Parallel deployment scaffold (Nginx + v2 folder + shared copy) | ✅ Done | `/admin2/` live, shared utilities copied |
| **1** | Foundation: Design system, shell, login | ✅ Done | Dark SaaS CSS, 11-section shell, username+password login, collapsible sidebar |
| **2** | Dashboard (Overview) | ✅ Done | `GET /api/admin/overview`, dashboard.js, 6 stat cards + 2 feeds, 30s refresh |
| **3** | Game Content Split (Mechanics + Content + World) | ✅ Done | mechanics.js (Stats/Skills/DC/Conditions), content.js (Weapons/Enemies/Items/Consumables/Loot/Archetypes + AI Assistant), world.js (Locations/NPCs) |
| **4** | Prompt Studio | ⬜ TODO | Dedicated editor with diff view |
| **5** | Players Section Overhaul | ⬜ TODO | Backend: user activity endpoint, players.js |
| **6** | Campaign Monitor | ⬜ TODO | Backend: live campaigns endpoint, campaigns_monitor.js |
| **7** | Analytics | ⬜ TODO | New router + service, canvas charts |
| **8** | Campaign Designer (AI Agent) | ⬜ TODO | New DB table, LLM endpoint, campaign_designer.js |
| **9** | System Consolidation | ⬜ TODO | Merge 4 logical groups into system.js |
| **10** | Voice Reskin | ⬜ TODO | Apply new CSS tokens to voice.js |
| **11** | Cutover (optional) | ⬜ TODO | Redirect /admin/ → /admin2/, retire v1 |

**Legend:** ⬜ TODO · 🔄 In Progress · ✅ Done · ❌ Blocked

---

## Phase 0 — Parallel Deployment Scaffold

**Goal:** `/admin2/` is live and reachable. Shows a placeholder. Old `/admin/` completely untouched.

### Files Changed

| File | Action | Notes |
|---|---|---|
| `frontend/nginx.conf` | Edit | Add `/admin2/` → `admin_panel_v2/` location blocks |
| `frontend/admin_panel_v2/index.html` | **New** | Placeholder "Admin 2.0 — coming soon" |
| `frontend/admin_panel_v2/shared/api.js` | **New** | Copy from v1 |
| `frontend/admin_panel_v2/shared/auth.js` | **New** | Copy from v1 |
| `frontend/admin_panel_v2/shared/table.js` | **New** | Copy from v1 |
| `frontend/admin_panel_v2/shared/modal.js` | **New** | Copy from v1 |
| `frontend/admin_panel_v2/shared/toast.js` | **New** | Copy from v1 |

Nginx blocks to add:
```nginx
location = /admin2 {
    return 301 /admin2/;
}

location /admin2/ {
    alias /usr/share/nginx/html/admin_panel_v2/;
    try_files $uri $uri/ /admin_panel_v2/index.html;
    add_header Cache-Control "no-store, must-revalidate" always;
}
```

### Requires
- Frontend container rebuild: `docker compose -f docker-compose.dev.yml up -d --build frontend`

### Verification
- `https://aigm-dev.studio-colorbox.com/admin/` still works (v1 intact).
- `https://aigm-dev.studio-colorbox.com/admin2/` shows placeholder.

---

## Phase 1 — Foundation: Design System & Shell

**Goal:** Full new visual shell with login overlay, sidebar with all 11 section placeholders.

### Files Changed

| File | Action | Notes |
|---|---|---|
| `frontend/admin_panel_v2/layout.css` | **New** | Full CSS vars, grouped sidebar, stat card components, table styles |
| `frontend/admin_panel_v2/index.html` | Rewrite | 11-section sidebar with group dividers, login overlay, activity log |
| `frontend/admin_panel_v2/shared/table.js` | Edit | Sort headers, sticky top, new palette classes |
| `frontend/admin_panel_v2/shared/modal.js` | Edit | Restyle to new palette |
| `frontend/admin_panel_v2/shared/toast.js` | Edit | Restyle to new palette |

### Verification
- `/admin2/` loads with dark design, login overlay appears.
- Dev login works, all 11 nav items are clickable (sections show "coming soon" state).
- No console errors.

---

## Phase 2 — Dashboard (Overview)

**Goal:** First screen shows live game state.

### Backend
| File | Action | Detail |
|---|---|---|
| `backend/app/routers/admin.py` | ✅ Added endpoint | `GET /api/admin/overview` |

Response:
```json
{
  "users_total": 7,
  "campaigns_active": 4,
  "turns_today": 3,
  "active_combats": 1,
  "db_size_mb": 3.15,
  "llm_preset_name": "—",
  "recent_audit": [...],
  "recent_turns": [...]
}
```

### Frontend
| File | Action | Detail |
|---|---|---|
| `frontend/admin_panel_v2/sections/dashboard.js` | ✅ Created | 6 stat cards + 2 feed panels, 30 s auto-refresh |
| `frontend/admin_panel_v2/layout.css` | ✅ Updated | Dashboard CSS: `.stat-cards`, `.dash-feeds`, `.feed-row`, badge variants |
| `frontend/admin_panel_v2/index.html` | ✅ Updated | `moduleMap` wired — `"overview"` → `dashboard.js?v=2` |

**6 stat cards:** Users · Active Campaigns · Turns Today · Active Combats (red highlight when > 0) · DB Size · LLM Model

**Two side-by-side feeds:**
- **Ostatnie zmiany (admin)** — last 10 audit log rows: CREATE/UPDATE/DELETE badge · table · row key · relative timestamp
- **Ostatnie tury gry** — last 10 game turns: campaign title · player text snippet · relative timestamp

**Auto-refresh:** silent 30 s `setInterval`; timer cleared on section deactivate.

### Verification
- ✅ Dashboard loads immediately after login, showing real DEV DB numbers.
- ✅ Active combat card gets red border (1 combat active in DEV).
- ✅ Both feeds scroll independently; content confirmed against DB.
- ✅ No console errors.
- ✅ Backend required `--no-cache` rebuild (code is baked into image, not bind-mounted).

---

## Phase 3 — Game Content Split (Mechanics + Content + World)

**Goal:** 3 focused sections replacing the monolithic game_design.js logic.

### Frontend (v2 only — v1 game_design.js is untouched)

| File | Action | Sub-tabs |
|---|---|---|
| `frontend/admin_panel_v2/sections/mechanics.js` | **New** | Stats · Skills · DC Tiers · Conditions |
| `frontend/admin_panel_v2/sections/content.js` | **New** | Weapons · Enemies · Items · Consumables · Loot Tables · Archetypes |
| `frontend/admin_panel_v2/sections/world.js` | **New** | Locations (tree) · NPCs |

All existing API endpoints unchanged. AI Assistant lives in `content.js`.

### Verification
- Each tab loads sub-tabs, CRUD works, lock guard shows warning on locked rows.

---

## Phase 4 — Prompt Studio

### Frontend
| File | Action | Detail |
|---|---|---|
| `frontend/admin_panel_v2/sections/prompts.js` | **New** | Prompt list + monospace editor + inline diff |

Features: prompt picker (System / History / Memory / Helpme), character count, last-modified, diff view before save.

### Verification
- Edit prompt → diff shows. Save persists. Reload confirms.

---

## Phase 5 — Players Section Overhaul

### Backend
| File | Action | Detail |
|---|---|---|
| `backend/app/routers/admin.py` | Add endpoint | `GET /api/admin/users/{user_id}/activity` |

### Frontend
| File | Action | Detail |
|---|---|---|
| `frontend/admin_panel_v2/sections/players.js` | **New** | User list + slide-in detail drawer |

Drawer contents: role toggles, password reset, per-user LLM, campaign list with HP, session timeline sparkline.

### Verification
- User list loads. Drawer opens with real data. LLM override saves.

---

## Phase 6 — Campaign Monitor

### Backend
| File | Action | Detail |
|---|---|---|
| `backend/app/routers/admin.py` | Add endpoint | `GET /api/admin/campaigns/live` |

### Frontend
| File | Action | Detail |
|---|---|---|
| `frontend/admin_panel_v2/sections/campaigns_monitor.js` | **New** | Campaign cards + detail modal |

Modal: character sheet, GM plan arcs/scenes, last 10 turns, action buttons (Advance Scene, Regenerate, End).

### Verification
- Campaign appears with HP bar. Modal opens with GM plan and turns.

---

## Phase 7 — Analytics

### Backend
| File | Action | Detail |
|---|---|---|
| `backend/app/routers/admin_analytics.py` | **New** | Analytics router |
| `backend/app/services/admin_analytics.py` | **New** | DB query logic |
| `backend/app/main.py` | Edit | Register at `/api/admin/analytics` |

Endpoints: `overview`, `dice`, `combat`, `economy` — all with `?days=` param.

### Frontend
| File | Action | Detail |
|---|---|---|
| `frontend/admin_panel_v2/sections/analytics.js` | **New** | Day selector + canvas charts (no external libs) |

Charts: d20 distribution bar, turns/day line, top enemies table, top items table.

### Verification
- Charts render with real data. Day range selector updates them.

---

## Phase 8 — Campaign Designer (AI Agent)

### Backend
| File | Action | Detail |
|---|---|---|
| `backend/app/services/admin_campaign_designer.py` | **New** | LLM generation service |
| `backend/app/migrations_admin.py` | Edit | Add `campaign_snippets` table |
| `backend/app/routers/admin.py` | Add endpoints | generate (streaming) + snippets CRUD |

```sql
CREATE TABLE IF NOT EXISTS campaign_snippets (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  snippet_type TEXT NOT NULL,   -- hook / location / npc / encounter
  title        TEXT NOT NULL,
  content      TEXT NOT NULL,
  tags         TEXT,
  created_at   TEXT DEFAULT (datetime('now')),
  is_active    INTEGER DEFAULT 1
);
```

### Frontend
| File | Action | Detail |
|---|---|---|
| `frontend/admin_panel_v2/sections/campaign_designer.js` | **New** | 2-column: generator (left) + library (right) |

### Verification
- Generate → streams. Save → in library. Delete → removed.

---

## Phase 9 — System Consolidation

### Frontend
| File | Action | Sub-tab |
|---|---|---|
| `frontend/admin_panel_v2/sections/system.js` | **New** | Database · Config · LLM · Slash Commands · Admin Cmd |

(v1 technical.js / config.js / ui_settings.js / admin_commands.js untouched)

### Verification
- All 5 sub-tabs load. Backup, export, import, migrate work.

---

## Phase 10 — Voice Reskin

### Frontend
| File | Action | Detail |
|---|---|---|
| `frontend/admin_panel_v2/sections/voice.js` | **New** | Copy v1 logic, new CSS tokens + LABELS const |

### Verification
- Voice tab loads. Piper model management works.

---

## Phase 11 — Cutover (Optional)

When v2 is fully validated, redirect old paths to new panel:

```nginx
# In nginx.conf — replace /admin/ block with redirect
location = /admin { return 301 /admin2/; }
location /admin/ { return 301 /admin2/; }
location = /panel { return 301 /admin2/; }
location /panel/ { return 301 /admin2/; }
```

Or keep both running indefinitely — v1 as fallback, v2 as primary.

---

## Files Summary

### New files (v2 only)
```
frontend/admin_panel_v2/
├── index.html
├── layout.css
├── shared/
│   ├── api.js      (copy of v1, then upgraded)
│   ├── auth.js     (copy of v1)
│   ├── table.js    (copy of v1, then upgraded)
│   ├── modal.js    (copy of v1, then upgraded)
│   └── toast.js    (copy of v1, then upgraded)
└── sections/
    ├── dashboard.js
    ├── mechanics.js
    ├── content.js
    ├── world.js
    ├── prompts.js
    ├── players.js
    ├── campaigns_monitor.js
    ├── analytics.js
    ├── campaign_designer.js
    ├── system.js
    └── voice.js

backend/app/routers/admin_analytics.py
backend/app/services/admin_analytics.py
backend/app/services/admin_campaign_designer.py
```

### Modified files
```
frontend/nginx.conf                   (Phase 0 — add /admin2/ location)
backend/app/routers/admin.py          (Phases 2,5,6,8 — additive endpoints only)
backend/app/migrations_admin.py       (Phase 8 — campaign_snippets table)
backend/app/main.py                   (Phase 7 — register analytics router)
```

### v1 files — NOT touched
```
frontend/admin_panel/   ← entire folder left completely alone
```

---

## Docker Notes

**Phase 0** (Nginx change) requires frontend container rebuild:
```bash
# Run on 192.168.1.61
docker compose -f docker-compose.dev.yml up -d --build frontend
```

All subsequent frontend phases: static files only — no rebuild, just bump `?v=` cache params in `index.html`.

Backend changes (new endpoints, new table) require:
```bash
docker compose -f docker-compose.dev.yml up -d --build backend
```
