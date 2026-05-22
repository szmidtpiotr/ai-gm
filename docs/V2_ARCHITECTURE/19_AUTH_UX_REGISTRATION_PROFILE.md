# Auth UX — Registration, Onboarding, Profile & Invite System

> Planning document for Stage 11-C.
> Design session completed 2026-05-22. All screens decided. Ready for implementation.

---

## System overview

```
INVITE FLOW          REGISTRATION         VERIFICATION       ONBOARDING
────────────         ────────────         ────────────       ──────────
Admin creates   →   User opens link  →   Play session 1 →   2-step flow
  personalised        Social reg form      immediately        cinematic +
  or open link        email pre-filled     2nd login blocked  theme picker
                      shows inviter        until verified     writes onboarded_at
                                                                       ↓
EVERYDAY LOOP        PROFILE PAGE         FORGOT PASSWORD    INVITE SENDING
─────────────        ────────────         ───────────────    ─────────────
Login screen    →   Chronicle + Friends + Password reset     Profile modal +
subtle links        Invites + Security    2h link            heroes shortcut
                                          auto-login         email OR copy link
```

---

## Decisions log

| Screen | Decision |
|---|---|
| Login | Subtle footer links — "Nie pamiętasz hasła?" + "Masz zaproszenie?" |
| Registration layout | Social — inviter card (avatar letter + name) above form |
| Invite types | Personalised (player): email-locked, one person. Open (admin only): shareable, first-come |
| Email verification timing | Play immediately after registration. Block on 2nd login until verified |
| Onboarding Step 1 | Cinematic — dark art + inviter name + inviter personal message |
| Onboarding Step 2 | Theme picker → "Zaczynam przygodę" (no display name — hero IS the identity) |
| Password reset validity | 2h, single-use (expires on click), auto-login after |
| Profile page purpose | Chronicle stats + Friends (multiplayer foundation) + Invites + Security |
| Send invite UX | Profile page + heroes screen shortcut; modal has email form AND copyable link |
| Admin tree view | Interactive D3.js tree, collapsible, activity colour-coded |

---

## Screen specifications

### Screen 0 — Login (small addition to existing)

```
┌───────────────────────────────────┐
│          ⚔  AI-GM                 │
│                                   │
│  [ Nazwa użytkownika            ] │
│  [ Hasło                     👁 ] │
│                                   │
│  [ Zaloguj się                  ] │
│                                   │
│  Nie pamiętasz hasła? → Reset     │
│  Masz zaproszenie? → Zarejestruj  │
└───────────────────────────────────┘
```

- "Zarejestruj się" always visible — the invite code is the gate, not link visibility
- Both footer links are small, muted text — login is the primary action

---

### Screen 1 — Registration

Reached via: invite link (`/register?invite=TOKEN`) or "Zarejestruj się" on login.

**When arriving via valid invite link (personalised or open):**
```
┌───────────────────────────────────┐
│  ┌─────────────────────────────┐  │
│  │  [P]  Zaprosił cię:         │  │
│  │       Piotr                 │  │
│  │  "Hej! W końcu dołączasz.   │  │
│  │   Będziemy razem grać!"     │  │
│  └─────────────────────────────┘  │
│                                   │
│  Email                            │
│  [ piotrek@gmail.com   🔒 ]       │   ← pre-filled, locked (from invite)
│                                   │
│  Nazwa użytkownika                │
│  [                              ] │
│                                   │
│  Hasło           Powtórz hasło    │
│  [             ] [             ]  │
│                                   │
│  [ Dołącz do przygody ]           │
│                                   │
│  ◈ Zaproszenie ważne: 2d 14h      │
└───────────────────────────────────┘
```

**When arriving without invite link (bare /register page):**
```
┌───────────────────────────────────┐
│  Dołącz do AI-GM                 │
│                                   │
│  Wpisz kod zaproszenia            │
│  lub adres email zaproszenia      │
│  [                              ] │
│                                   │
│  [ Sprawdź zaproszenie ]          │
│                                   │
│  ───────────────────────────────  │
│  Nie masz zaproszenia?            │
│  Poproś kogoś kto już gra,        │
│  lub skontaktuj się z adminem.    │
└───────────────────────────────────┘
```

**Invite fields:**
- `username` — unique login identifier (letters, numbers, underscore, 3-30 chars)
- `password` — min 8 chars
- `email` — pre-filled from invite record, locked (personalised) or editable (open invite)
- NO display name field — hero name is the player's identity in-game

**Inviter card:**
- Shows inviter's display name (or username)
- Shows optional personal message (entered when creating the invite)
- Avatar: letter chip with colour from username hash
- Hidden if admin created an open invite with no personal message

---

### Screen 2 — Email verification

**Immediately after registration:** play session normally. No gate. Onboarding fires.

**On second login (and every login while unverified):**
```
┌───────────────────────────────────┐
│                                   │
│               📬                  │
│                                   │
│  Potwierdź swój adres email       │
│                                   │
│  Wysłaliśmy link do:              │
│  piotrek@gmail.com                │
│                                   │
│  Konto jest aktywne, ale          │
│  aby kontynuować grę potrzebujemy │
│  potwierdzenia emaila.            │
│                                   │
│  Link ważny 72 godziny.           │
│                                   │
│  [ Wyślij ponownie ]              │   ← rate-limited: 1 per 2 minutes
│  (dostępne za 1:43)               │
│                                   │
│  Już weryfikowałeś? → Zaloguj się │
└───────────────────────────────────┘
```

- Backend checks `users.email_verified_at IS NULL` on login
- If unverified: return 403 with `{error: "email_unverified"}` → frontend shows this screen
- Resend rate-limited to 1 per 2 minutes per account

---

### Screen 3 — Onboarding (2 steps, fires when `onboarded_at IS NULL`)

**Step 1 — Cinematic welcome**

Full-screen, atmospheric. CSS animation: fade in background, then title, then inviter card, then "Dalej" button. Auto-advance after 6s or tap anywhere.

```
┌───────────────────────────────────┐
│  [dark atmospheric RPG art]       │
│                                   │
│  ┌─────────────────────────────┐  │
│  │  [P]  Piotr zaprasza Cię    │  │
│  │       do świata AI-GM       │  │  ← only if invite has personal message
│  │                             │  │
│  │  "Hej! W końcu dołączasz.   │  │
│  │   Będziemy razem grać!"     │  │
│  └─────────────────────────────┘  │
│                                   │
│              AI-GM                │
│                                   │
│     Twoja historia właśnie        │
│          się zaczyna...           │
│                                   │
│  ● ○                 [Dalej →]    │
└───────────────────────────────────┘
```

If no personal message from inviter: just the atmospheric art + title + tagline, no card.
If admin registered the account directly: no card at all.

**Step 2 — Theme + commit**

```
┌───────────────────────────────────┐
│                                   │
│  Wybierz swój styl               │
│                                   │
│  Kliknij aby podglądnąć — możesz  │
│  zmienić w ustawieniach.          │
│                                   │
│  ┌──────┐ ┌──────┐ ┌──────┐      │
│  │Ciemny│ │Ambr. │ │Sepia │      │   ← live preview on tap
│  └──────┘ └──────┘ └──────┘      │
│  ┌──────┐                         │
│  │Jasny │                         │
│  └──────┘                         │
│                                   │
│  ○ ●                              │
│                                   │
│  [ ⚔  Zaczynam przygodę ]        │
└───────────────────────────────────┘
```

On submit: write `users.onboarded_at = NOW()`, save theme to `localStorage` (same key as settings).

---

### Screen 4 — Forgot password (2 screens)

**4A — Enter email:**
```
┌───────────────────────────────────┐
│  Reset hasła                      │
│                                   │
│  Podaj email użyty podczas        │
│  rejestracji.                     │
│                                   │
│  [ twoj@email.com               ] │
│                                   │
│  [ Wyślij link resetujący ]       │
│                                   │
│  ← Wróć do logowania             │
└───────────────────────────────────┘
```

Always responds: "Jeśli ten adres istnieje w systemie, wyślemy link." Never confirm/deny (security).

**4B — Set new password (after clicking email link):**
```
┌───────────────────────────────────┐
│  Nowe hasło                       │
│                                   │
│  [ Nowe hasło                   ] │
│  [ Powtórz hasło                ] │
│                                   │
│  [ Zapisz i zaloguj ]             │
└───────────────────────────────────┘
```

- Link valid 2h, single-use (invalidated immediately on click)
- On save: update password, delete reset token, log user in, redirect to heroes screen

---

### Screen 5 — Profile page

Entry point: Settings drawer → "Konto" link.

```
┌───────────────────────────────────┐
│  ← Ustawienia    Twoje konto     │
├───────────────────────────────────┤
│                                   │
│  ▣ TOŻSAMOŚĆ                     │
│  Użytkownik: @piotrek (read-only) │
│  Email: piotrek@gmail.com         │
│  Dołączył: 15 maja 2026           │
│  Motyw: [Ciemny ▼] (quick swap)   │
│                                   │
│  ▣ KRONIKA                       │
│  ⚔  Bohaterowie:         3       │
│  📖  Kampanie ukończone:  1       │
│  💀  Kampanie porzucone:  2       │
│  ✨  Łączne PD:       4 820       │
│  📜  Tur rozegranych:    127      │
│  🎲  Top próba:      Skradanie    │
│                                   │
│  ▣ ZNAJOMI                       │   ← foundation for multiplayer
│  [search: Dodaj gracza...]        │
│  Adam ● online                    │
│  Kasia ○ ostatnio 2h temu         │
│  [ + Dodaj znajomego ]            │
│                                   │
│  ▣ ZAPROSZENIA                   │
│  Zaproszony przez: @Piotr         │
│  Ten tydzień: ██░ 2/3             │
│  Reset za: 4d 12h                 │
│  [ + Wyślij zaproszenie ]         │
│                                   │
│  ▣ BEZPIECZEŃSTWO ▾ (collapsed)  │
│  [ Zmień hasło ]                  │
│  [ Usuń konto ] (soft-delete)     │
└───────────────────────────────────┘
```

Friends section placeholder — stores `user_friendships` table now, multiplayer campaign invite UI ships when F2 is implemented.

---

### Screen 6 — Send invite modal

Accessible from: Profile page "Zaproszenia" section + small "📨 Zaproś znajomego" chip on heroes screen.

```
┌───────────────────────────────────┐
│  Wyślij zaproszenie               │
│                                   │
│  Email znajomego                  │
│  [ adam@gmail.com               ] │
│  → Wyślemy zaproszenie na email   │
│                                   │
│  Opcjonalna wiadomość             │
│  [ Hej, dołącz do mojej gry!    ] │
│  (pojawi się w zaproszeniu)       │
│                                   │
│  [ Wyślij zaproszenie ]           │
│                                   │
│  ─── lub skopiuj link ───────── │
│                                   │
│  aigm.io/join?i=a3f9k2            │
│  [ 📋 Kopiuj link ]               │
│  Ważny 72h · 1 użycie             │
│                                   │
│  Pozostałe w tym tygodniu: 1/3   │
│  Reset za: 4d 12h                 │
│                                   │
│                    [ Zamknij ]    │
└───────────────────────────────────┘
```

- Both paths (email + link) consume 1 invite token from the weekly allowance
- Link is generated on modal open (or on demand via "Generuj link" if not pre-generated)
- Closing the modal without sending/copying does NOT consume a token

---

## Admin features

### SMTP configuration (System panel)

Stored in `app_config` table — all fields editable from admin panel, zero code changes on domain move:

| Key | Example |
|---|---|
| `smtp_host` | `smtp.gmail.com` |
| `smtp_port` | `587` |
| `smtp_username` | `yourgame@gmail.com` |
| `smtp_password` | `app-password-here` |
| `smtp_from_name` | `AI-GM` |
| `smtp_from_address` | `yourgame@gmail.com` |
| `smtp_use_tls` | `true` |

Admin panel: System → Email → form + "Wyślij testowy email" button (sends to admin's own email).

**Gmail setup:** requires Google App Password (Account → Security → App passwords). Takes 2 minutes. Works for up to ~500 emails/day.

### Invite tree view (Players → Drzewo zaproszeń)

Interactive D3.js (or vis.js) tree:
- Expandable/collapsible nodes
- Each node: username + turns-played badge
- Activity colour: 🟢 active (>10 turns/30d) · 🟡 low (<10 turns/30d) · ⚪ cold (>30d inactive)
- Click node → flyout with: email, joined date, last active, campaigns count, who they've invited
- "Eksportuj CSV" button → `username, email, invited_by, joined_at, last_active, turns_total, depth, branch_size`

---

## Database schema additions

```sql
-- Invite records
CREATE TABLE user_invites (
    id          INTEGER PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,           -- random token in URL
    created_by  INTEGER REFERENCES users(id),   -- who created it
    email       TEXT,                            -- NULL = open invite
    message     TEXT,                            -- optional personal message
    accepted_by INTEGER REFERENCES users(id),   -- NULL until used
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,                  -- 72h from creation
    used_at     TEXT                            -- NULL until claimed
);

-- Track who invited whom (for tree)
ALTER TABLE users ADD COLUMN invited_by_user_id INTEGER REFERENCES users(id);
ALTER TABLE users ADD COLUMN email_verified_at TEXT;     -- NULL = unverified
ALTER TABLE users ADD COLUMN onboarded_at TEXT;          -- NULL = first session

-- Weekly invite quota (denormalised for fast check)
ALTER TABLE users ADD COLUMN invite_weekly_limit INTEGER DEFAULT 3;

-- Friends (foundation for multiplayer)
CREATE TABLE user_friendships (
    id           INTEGER PRIMARY KEY,
    user_a_id    INTEGER REFERENCES users(id),
    user_b_id    INTEGER REFERENCES users(id),
    status       TEXT DEFAULT 'pending',  -- pending / accepted / blocked
    created_at   TEXT NOT NULL,
    UNIQUE(user_a_id, user_b_id)
);

-- Email verification tokens
CREATE TABLE email_verification_tokens (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id),
    token      TEXT UNIQUE NOT NULL,
    expires_at TEXT NOT NULL,
    used_at    TEXT
);

-- Password reset tokens
CREATE TABLE password_reset_tokens (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id),
    token      TEXT UNIQUE NOT NULL,
    expires_at TEXT NOT NULL,            -- 2h from creation
    used_at    TEXT
);

-- SMTP and app config (already exists as app_config key-value)
-- Keys to add: smtp_host, smtp_port, smtp_username, smtp_password,
--              smtp_from_name, smtp_from_address, smtp_use_tls,
--              registration_open (bool)
```

---

## Implementation order

```
1. DB migration (all new tables + columns)
2. Email service (SMTP via app_config, send_email() helper)
3. Backend: invite CRUD + validation
4. Backend: registration endpoint (POST /auth/register)
5. Backend: email verification flow (send + confirm endpoints)
6. Backend: password reset flow (request + confirm endpoints)
7. Frontend: Screen 0 — login footer links
8. Frontend: Screen 1 — registration form
9. Frontend: Screen 2 — email verification gate on login
10. Frontend: Screen 3 — onboarding cinematic + theme picker
11. Frontend: Screen 4 — forgot password flow
12. Frontend: Screen 5 — profile page
13. Frontend: Screen 6 — send invite modal
14. Admin: SMTP config panel
15. Admin: invite tree (D3.js)
```

---

## Open questions (deferred, not blocking)

1. **Email change** — can users change their email after registration? Requires re-verification. Deferred — not on profile MVP.
2. **Invite visibility in profile** — "Zaproszony przez: @Piotr" — should this be hideable by the user?
3. **Friend request UX** — pending/accept/decline notifications. Deferred to when multiplayer ships (F2).
4. **Invite quota override** — admin boosts a specific user's weekly limit. Simple: edit `invite_weekly_limit` column directly from user detail in admin panel.
</content>
</invoke>