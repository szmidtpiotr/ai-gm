# Auth UX — Registration, Onboarding & Profile Page

> Planning document for Stage 11-C (A8 + Registration + Profile).
> Game-design analysis completed 2026-05-22. Ready for implementation discussion.

---

## Context

Three related player moments that currently have gaps:

| Moment | Current state | Problem |
|---|---|---|
| **Registration** | Admin-only account creation | New players can't self-register |
| **Onboarding (A8)** | Planned but not built (`users.onboarded_at`) | First login drops straight into heroes screen — no orientation |
| **Profile page** | Deferred to Stage 17 (F1) | No way for players to change password or see their stats |

These three ship best as a single coherent auth-UX stage because they share the same DB columns (`display_name`, `onboarded_at`, `theme`) and the same entry migration.

---

## 5-Component Evaluation

### Registration

| Component | Rating | Notes |
|---|---|---|
| **Clarity** | ✅ | Username/password is globally understood |
| **Motivation** | ⚠ | Player has zero investment yet — keep friction minimal |
| **Response** | ✅ | Instant field validation, clear errors |
| **Satisfaction** | ⚠ | Completing a form feels like nothing |
| **Fit** | ❌ | Generic auth forms break world immersion |

**Fix:** Frame it as enlisting, not form-filling. CTA = "Rozpocznij przygodę", not "Create account".

### Onboarding Overlay (A8)

| Component | Rating | Notes |
|---|---|---|
| **Clarity** | ✅ | Player knows exactly where they are |
| **Motivation** | ✅ | Investment is fresh right after registration |
| **Response** | ⚠ | Most onboardings are passive — player just clicks Next |
| **Satisfaction** | ⚠ | Theme picker is the only moment of expression |
| **Fit** | ⚠ | Must match dark RPG tone or it breaks immersion |

**Fix:** One data-entry moment (display name) + one expressive choice (theme) = player owns something before seeing the hero screen.

### Profile Page (F1 promoted from Stage 17)

| Component | Rating | Notes |
|---|---|---|
| **Clarity** | ✅ | Utility page — labels explain everything |
| **Motivation** | ⚠ | Only relevant when player needs to change something |
| **Satisfaction** | ❌ | Pure settings with zero reflection of progress |
| **Fit** | ❌ | Settings drawer in an RPG breaks immersion |

**Fix:** Merge utility (password, name) with identity (XP, campaigns, heroes). Make it a dossier, not a settings page.

---

## Designs

### 1 — Registration Modal

**Admin-gated:** only visible when `app_config.registration_open = true` (default: false). Admin enables via System panel toggle. This prevents open signups on private servers.

**Fields (3 max):**
- Username — unique, used for login, shown in admin panel
- Display name — shown in-game to player (pre-filled = username, editable)
- Password + confirm

No email required. No verification flow. Admin can still create accounts manually.

**Entry point:** `"Nie masz konta? Zarejestruj się"` link on login screen, hidden when `registration_open = false`.

**Backend:**
- `GET /api/auth/registration-status` — returns `{open: bool}` (no auth)
- `POST /api/auth/register` — creates user with `role='player'`, `is_admin=0`
- New `app_config` key: `registration_open` (boolean, default 0)

---

### 2 — Onboarding Overlay (A8)

Three screens, one modal, one commit. Fire when `users.onboarded_at IS NULL`.

**Screen 1 — The World (5 s, no input)**
Full-screen atmospheric art (existing background), game title, tagline in Cinzel font.
Auto-advances after 5 s or tap. Sets tone — this is not a form, it's an arrival.

**Screen 2 — Your Identity (1 field)**
- Display name input, pre-filled with username
- "Jak mają cię nazywać?" label
- Minimum 2 characters, max 30

**Screen 3 — Your Style**
- Theme chips (same as existing settings: Dark / Light / Sepia / Amber)
- Instant live preview via `data-theme` attribute on `<body>`
- CTA: `"Zaczynam przygodę"` button

**On submit:**
```sql
UPDATE users SET display_name=?, onboarded_at=NOW() WHERE id=?
```
Store theme in `localStorage` (same key as current settings toggle). Never show again — checked on every login via `users.onboarded_at`.

**What NOT to include:** tutorial tips, rules text walls, terms of service. If legal needed: one checkbox on screen 3.

---

### 3 — Profile Page (F1 promoted)

**Entry point:** Long-press or secondary tap on the hero avatar button in game header → Profile. Also accessible from settings drawer.

**Two-panel layout:**

**Left — Identity card** (dossier aesthetic, RPG feel):
- Display name (editable inline, save on blur or Enter)
- Username (read-only, grey)
- Member since date
- Active theme with quick-change chips

**Right — Chronicle** (progress reflection — read-only stats):
- Heroes created / currently active count
- Campaigns completed vs abandoned
- Lifetime XP across all heroes (from `character_xp_grants` — already journaled)
- Total narrative turns played (from `campaign_turns` count)
- Most-rolled skill (from `character_xp_grants` where category = 'skills')

**Bottom — Settings** (collapsed by default, expand on tap):
- Change password: current → new → confirm
- Account deletion: soft-delete, requires typing username to confirm, grace period

**Backend endpoints needed:**
- `GET /api/me` — already exists (from Stage 10-B JWT)
- `PATCH /api/me` — update display_name
- `POST /api/me/change-password`
- `DELETE /api/me` — soft-delete
- `GET /api/me/stats` — aggregate from existing tables

---

## Implementation Order

```
1. Migration: users.display_name, app_config.registration_open
2. Backend: POST /auth/register + GET /auth/registration-status
3. Frontend: Registration modal on login screen (admin-gated)
        ↓
4. Backend: PATCH /api/me (display_name)
5. Frontend: A8 Onboarding overlay (3 screens)
        ↓
6. Backend: GET /api/me/stats + POST /me/change-password
7. Frontend: Profile page (identity card + chronicle + settings)
```

Profile page is cheap right after A8 because the migration (`display_name`, `onboarded_at`) lands in A8's step — profile just reads and edits the same columns.

---

## Risks

| Risk | Mitigation |
|---|---|
| Registration spam | `registration_open` defaults false; admin-controlled toggle |
| Onboarding bypassed via localStorage clear | Detect `onboarded_at IS NULL` server-side on every login, not in localStorage |
| Profile stats getting stale | Pull from already-journaled tables (`character_xp_grants`, `campaign_turns`) — no new write paths needed |
| Soft-delete complexity | Phase 1: just set `users.deleted_at`; hide from login; admin can restore. Phase 2: data purge after 30 days (separate task) |

---

## Open Questions (for discussion)

1. **Registration default:** Should `registration_open` default to `true` on fresh installs (easy onboarding) or `false` (secure by default)? Leaning `false` — admin can flip it.
2. **Display name uniqueness:** Enforce uniqueness or allow duplicates? Duplicates are fine since `username` is the login key. Display names are cosmetic.
3. **Profile page location:** Avatar button long-press is subtle. Should there be an explicit "Konto" entry in the settings drawer instead?
4. **Password recovery:** Email-based reset is out of scope here. Admin can reset via the admin panel. Is that sufficient for now?
</content>
</invoke>