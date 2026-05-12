# TASK 25 — Auth & Onboarding

**Status:** ❓ Needs Design
**Blocking:** Design discussion needed (lowest priority)

---

## What Needs to Be Designed

1. **Registration** — Self-registration or admin-only? If self-registration: email confirmation? Invite code? If admin-only: how does the admin create accounts (currently exists in admin panel)?
2. **Guest/demo mode** — Can someone try the game without an account? Demo mode would need a sandboxed session that doesn't persist.
3. **Onboarding** — First-time player: explanation screen, interactive tutorial, or "learn by playing"? Given the game is narrative, an in-game tutorial GM scene might work well.
4. **Account recovery** — Password reset? Currently no reset flow exists.
5. **Multi-device** — localStorage token auto-login works on one device. If player logs in on another device: old session handling? (Currently: same campaign continues from DB, so multi-device should work — but localStorage state may be stale.)
6. **Session expiry** — How long does the localStorage token last? Is there any server-side session validation or is it purely client-stored?

## Current State

- Login: `POST /api/auth/login` → stores `user_id` + `is_admin` in localStorage
- Auto-login if localStorage token present on page load
- Admin creates users via admin panel Accounts section
- No self-registration, no password reset, no email
- Token: appears to be user_id stored client-side with no expiry — security concern to note

---

*Lowest priority. Design discussion after all gameplay systems are defined.*
