# TASK 39 — Auth and Onboarding

## Overview

This is a private, closed game. Players cannot self-register. Admins create accounts. Authentication uses proper tokens stored in localStorage. The first-time experience is minimal — a brief overlay and then directly into play. There is no tutorial level; the opening scene is the tutorial.

---

## Authentication

### Registration Policy

**CONFIRMED:** Admin creates accounts by default (closed system). Admin panel has a toggle to enable self-registration when needed. Optional: self-registration with invite codes (admin generates codes). See `10_ALL_OPEN_DECISIONS_RESOLVED.md`.

Self-registration is **disabled**. There is no public registration form or endpoint. Player accounts are created exclusively by admins via the Admin Panel → Accounts section.

This is intentional: AI-GM is a private game run for a specific group. Open registration is not a use case.

The `POST /api/auth/register` endpoint (if it exists) must be admin-token protected. Any unauthenticated POST to register returns `403 Forbidden` with no information about whether the endpoint exists.

### Token Security

Authentication tokens must be proper JWT or signed session tokens. They must NOT be raw `user_id` values or plain UUIDs stored as-is.

Requirements:
- Token contains: `user_id`, `role` (player/admin), `issued_at`, `expires_at`
- Token is signed with a server-side secret (`JWT_SECRET` env var)
- Token expiry: 7 days (configurable via `TOKEN_EXPIRY_DAYS` env var)
- On expiry: 401 response → frontend clears localStorage → redirects to login

Token storage: `localStorage.setItem("aigm_token", token)`. Not in cookies (no cross-domain issues needed). Token is sent as `Authorization: Bearer {token}` header on all API calls.

### Auto-Login

On page load:
1. Check `localStorage` for `aigm_token`
2. If present: verify token validity via `GET /api/auth/me` (lightweight endpoint, no DB hit — just validates the JWT signature and expiry)
3. If valid: proceed directly to player's active campaign (or campaign selection if multiple)
4. If missing or invalid: show login form

### Login Form

Minimal: username field + password field + "Zaloguj" button. No registration link. No "Forgot password" link (see Password Reset below).

On failed login: "Nieprawidłowy login lub hasło." Generic — no information about which field is wrong.

Brute force protection: lock account after 10 failed attempts within 15 minutes. Unlock via admin panel.

---

## Password Reset

No self-service password reset in V2.

If a player loses their password:
1. Player contacts the game admin (out-of-band — Discord, email, etc.)
2. Admin goes to Admin Panel → Accounts → finds the user → clicks "Resetuj hasło"
3. Admin sets a new temporary password
4. Admin tells the player the new password out-of-band
5. Player logs in and changes their password in account settings (if that feature exists)

No email infrastructure needed. No reset tokens. No "forgot password" flow.

---

## First-Time Experience

### Definition

"First time" = player has a valid account but no campaigns yet (or has never completed the onboarding overlay).

Tracked via: `user.onboarding_completed` boolean in DB.

### Onboarding Overlay

Shown once, on first login for new players. Full-screen modal with a dark background.

```
┌─────────────────────────────────────────────────┐
│                                                  │
│          Witaj w AI-GM                           │
│                                                  │
│  Grasz w mroczną fantasy napędzaną sztuczną      │
│  inteligencją. Mistrz Gry reaguje na każde       │
│  twoje działanie.                                │
│                                                  │
│  ─────────────────────────────────────────────  │
│  ✏  Pisz swobodnie — lub użyj przycisków         │
│  ⚔  Mistrz Gry poprowadzi twoją historię        │
│  💀  Twoje wybory mają znaczenie                 │
│  ─────────────────────────────────────────────  │
│                                                  │
│  Nie ma właściwych ani błędnych odpowiedzi.      │
│  Graj jak chcesz.                                │
│                                                  │
│          [Zaczynam przygodę]                     │
│                                                  │
└─────────────────────────────────────────────────┘
```

- Single button: "Zaczynam przygodę"
- No "skip" — it's short enough that skipping is unnecessary
- On button click: `user.onboarding_completed = true` (PATCH to `/api/users/me`)
- Transition: fade out overlay → campaign creation flow begins

### No Tutorial Combat

There is no dedicated tutorial combat encounter. The opening scene of the first campaign serves as the de facto tutorial — the player learns by doing. The context buttons (TASK_33) ensure even new players can find actions without knowing any commands.

If a player seems stuck (no input for > 5 minutes — future feature), a subtle hint could be triggered. Not in V2.

---

## Campaign Creation Flow (First Campaign)

After onboarding overlay dismisses, the player goes to campaign creation:

1. **Choose campaign type**: Select from available campaign templates (admin-created) or "Custom" if enabled
2. **Name your character**: Text input for character name
3. **Choose archetype**: Wojownik / Łotr / Uczony (each with brief description)
4. **Appearance** (optional): brief text field — "Jak wygląda twoja postać?"
5. **Personality** (optional): brief text field — "Jaka jest osobowość twojej postaci?"
6. → Campaign starts. First turn is triggered automatically with a "start" action.

The first GM narration sets the scene. No tutorial text. No UI tooltips. The world begins.

---

## Multi-Device Access

The same campaign is accessible from any device. Data is DB-backed, not localStorage-backed (except the token).

Flow on second device:
1. Player opens the game on a new device
2. Log in with credentials
3. `GET /api/users/me/campaigns` returns active campaigns
4. Player selects the campaign
5. Campaign state loads from DB — full history, current location, character state

`localStorage` only caches the auth token. All game state is server-side.

Edge case: two devices playing the same campaign simultaneously. Not explicitly prevented in V2. The DB is the source of truth — last write wins. If this causes issues (rare — solo game), a session lock warning can be added later.

---

## Account Settings (Player-Accessible)

Accessible via a "Konto" link in the sidebar or header.

Available in V2:
- Change display name (cosmetic — not login username)
- Change password (current password required)

Not available in V2:
- Change login username
- Delete account (admin-only)
- Export data

---

## Testing Requirements

1. **No self-registration**: Attempt `POST /api/auth/register` without admin token. Verify 403.
2. **Token is JWT**: Inspect token in localStorage after login. Verify it's a valid JWT with expected claims.
3. **Token expiry**: Set a token with past `expires_at`. Attempt authenticated request. Verify 401.
4. **Auto-login**: Store a valid token in localStorage. Reload page. Verify login form does not appear and campaign loads directly.
5. **Onboarding once**: Complete onboarding. Reload page. Verify onboarding overlay does not appear again.
6. **Multi-device**: Log in on device A (mock), start a turn. Log in on device B (mock same user). Verify campaign state matches.
7. **Brute force lock**: Simulate 10 failed logins in 15 minutes. Verify 11th returns a locked error.
8. **Password change**: Change password successfully. Attempt login with old password. Verify 401. Attempt login with new password. Verify 200.
