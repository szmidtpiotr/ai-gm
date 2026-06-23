# Multiplayer Test Design — `/game-smoke-mp` + Playwright MP suite

> **BUILD STATUS (2026-06-23): BUILT + VERIFIED.**
> - Skill: `.claude/skills/game-smoke-mp/SKILL.md` + `scripts/` (`setup_mp_users.py`,
>   `setup_mp_lobby.py`, `play_mp_round.py`, `mp_sweep.py`, `snapshot_mp.py`) — all run green on DEV.
> - Playwright: `ai_test_agent/playwright/mp/` (`helpers/mp.js`, `mp_login_multicontext.spec.js`
>   **PASSING**, `mp_ingame.spec.js` `test.fixme`-gated).
> - Real endpoints confirmed (all under `/api`, identity via `?user_id=`); admin = `demo`/`demo`;
>   force-sweep = `svc.force_sweep(now=…)` via `docker exec`; DB reads via `docker exec sqlite3 -json`
>   (sshfs gives stale WAL reads — do NOT use it).
> - **Found on build (P0, [#959](https://github.com/szmidtpiotr/ai-gm/issues/959)):** MP is
>   unplayable past the opening round — backend never opens the next `collecting` round, and
>   frontend `enterMpGame` is undefined. The harness correctly detects + reports this. In-game
>   specs go live the moment #959 is fixed.

**Status:** design proposal (2026-06-23). MP is implemented behind the `multiplayer_enabled`
admin flag (G3–G31, ~45 backend pytest files already cover the unit/service layer). The gap this
doc fills is **end-to-end playability** (a smoke analogue to `/game-smoke`) and **real multi-client
UI verification** (Playwright with N browser contexts). Source of truth for behaviour:
`game_mechanics.md` CZĘŚĆ AC + the G-task issues (#784–#813, #787–#810, #937, #950).

---

## 0. Why MP needs its own harness (what is different from solo smoke)

| Aspect | Solo `/game-smoke` | MP `/game-smoke-mp` |
|---|---|---|
| Actors | 1 hero, 1 user (Demo, user_id=1) | **2–4 distinct user accounts**, members keyed on `campaign_members.user_id` |
| Turn unit | `POST /api/campaigns/{id}/turns` → immediate LLM reply | **Round**: every player `POST /campaigns/{id}/round/submit`; narration fires only when all submitted (collecting→narrating→done FSM) |
| Concurrency | none | SQLite single-writer; idempotency via `client_action_id`; round state machine must stay atomic (G30) |
| Timing | synchronous | **async deadline-driven** — sweep closes expired rounds; must use **admin force-sweep + injectable time** instead of waiting the real timer |
| Hero state | one sheet | **shared hero**: progression global (XP/gold/inventory), battle state per-campaign in `character_campaign_state` (G16) |
| Death | permadeath allowed | **downed-not-dead** (G17); full wipe = gold penalty + wake at 50% HP, never permakill |
| Privacy | n/a | whispers/spectator hints **must never reach the LLM prompt** (permanent rule) |
| Cost | 15 turns × 1 LLM | rounds × **2-pass narration** (planner→narrator). Budget: use `gpt-4.1-mini`, cap rounds. |

Conclusion: reuse the `/game-smoke` *shape* (checkpoint table + DB proof + P0/P1/P2 issues +
3 screenshots + verdict), but build new setup/orchestration plumbing.

---

## 1. `/game-smoke-mp` skill

### 1.1 Invocation

```
/game-smoke-mp 2          # 2-player party (default)
/game-smoke-mp 3
/game-smoke-mp 4
/game-smoke-mp 3 --spectator   # add 1 spectator to the party
```

### 1.2 Contract (same spirit as `/game-smoke`)

- Verify **only through real rounds** played with the real LLM. No service/SQL shortcuts to fake a round.
- Dedicated **test user accounts** `tester_mp1..tester_mp4` (NOT user_id=1013, NOT Piotr's heroes,
  NOT Mizel 999420). Demo user_id=1 may be host (`tester_mp1`).
- Campaigns/characters/users **never deleted** after the run.
- SQL **read-only**, via `ssh claude@192.168.1.61 'docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db "..."'`. Never sshfs for the DB.
- Round cap: **8 rounds** per run (covers the core checkpoint set; extended checkpoints across 2 runs).
- `multiplayer_enabled` flag must be ON for the test lobby (set/verify via admin first).

### 1.3 Setup plumbing (new scripts under `.claude/skills/game-smoke-mp/scripts/`)

| Script | Job |
|---|---|
| `setup_mp_users.py` | Idempotently ensure users `tester_mp1..N` exist (admin create-user or seed), each with a known password; log in each → return `{user_id, token}` map. One `[TEST-MP] <archetype>` hero per user (warrior/scholar/rogue/warrior), created via `POST /api/characters` if missing. |
| `setup_mp_lobby.py` | As host: `POST /multiplayer/campaigns` (mode=multiplayer, max_players=N, **round_timer_minutes=1** so sweep is cheap to trigger). Invite the others (`/invite/username` or `/invite-link`). Each invitee `POST /accept` selecting their hero. Optional spectator via `/accept` with `as_spectator=true`. Returns `{campaign_id, members:[{user_id,character_id,token,role}]}`. |
| `play_mp_round.py` | One round end-to-end: for each active member `POST /campaigns/{id}/round/submit` with `action_text` + unique `client_action_id`; poll `GET /round/status` until `done`; fetch `GET /round/narration` **per player token** (private notes are token-scoped). Returns narrative + per-player notes + roll_facts. Flags: `--absent user_id` (skip that player's submit), `--withdraw user_id` (submit then DELETE action). |
| `mp_sweep.py` | Trigger G30 admin force-sweep with injected time past the deadline (the hook `test_785`/`test_801` use) — closes a `collecting` round without waiting the wall-clock timer. |
| `snapshot_mp.py` | Read-only DB dump: campaign row, all `campaign_members`, latest `campaign_rounds` + `campaign_round_actions`, `character_campaign_state` per hero, `party_messages`, `campaign_kick_votes`, `campaign_round_summaries`. |

Auth detail: `POST /api/auth/login {username, password}` → `access_token`; every MP call carries that
player's bearer token (the backend derives the acting user from it — do **not** spoof user_id in body).

### 1.4 Scenario — core checkpoint table (one run, ≤8 rounds)

Order is flexible; narration leads, the checklist polices. Each ✅ needs **proof** = round# + narration
quote OR SQL result.

| # | Checkpoint | Mechanic (G-task) | DB / proof |
|---|---|---|---|
| 1 | Lobby created: mode, max_players, timer | base U3 | `campaigns.mode='multiplayer'`, `max_players=N`, `round_timer_minutes` set |
| 2 | All players join + pick hero; counts shown | base / #922/#925 | `campaign_members`: N rows `status='accepted'`, each `character_id` set, one `role='owner'` |
| 3 | (if `--spectator`) spectator joins without a hero | G19 #800 | member `role='spectator'`, `character_id IS NULL` |
| 4 | Host start → round 1 collecting + opening narration | base | `campaign_rounds` round 1 exists; narrative present after all submit |
| 5 | **Round sync**: all submit → collecting→narrating→done | G30 #801 | N rows in `campaign_round_actions`; round `status='done'`; `narrative_json` populated; single narrative for the party |
| 6 | Initiative order + conflict resolve ("Cel już martwy") | G5 #789 | actions carry `initiative_roll`; two players targeting one enemy → low-init gets dead-target note |
| 7 | Per-player private notes + own-character roll_facts only | G8 #792 | `GET /round/narration` with player A token shows A's `player_notes`/`roll_facts`, not B's |
| 8 | Shared-hero isolation: battle state per campaign, progression global | G16 #784 | HP/mana in `character_campaign_state` (per campaign_id); XP/gold/inventory on global `characters` sheet |
| 9 | MP combat: start, sequential turns, enemies auto-resolve | G7 #791 | `/combat/start` + `/combat/action`; turn order includes all players; enemy actions logged after players |
| 10 | Downed, not dead: HP 0 = unconscious, revivable | G17 #794 | member/hero state = unconscious (not `dead`); revive action restores ~25–50% HP |
| 11 | Party chat public + **whisper privacy** | G19 #800 / #950 | public msg seen by all in `party_messages`; whisper `whisper_to` set, visible only to target; whisper text **absent from the LLM prompt log** |
| 12 | Narrative coherence across the party | G28 | review N rounds: no contradiction vs `character_campaign_state` / world state; tone consistent |

Screenshots (via `/game-screen`, 2+ player contexts): after CP2 (lobby with N players), CP9 (combat
turn order), and CP11 (chat/whisper or final round). Minimum 3.

### 1.5 Scenario — extended checkpoints (second run / opt-in)

| # | Checkpoint | G-task | Proof |
|---|---|---|---|
| 13 | Absence ladder: missed round → `[BRAK AKCJI]`/`[AUTOPILOT]`, `absence_warnings++` | G22 #803 | run `play_mp_round.py --absent <u>` then `mp_sweep.py`; check `campaign_members.absence_warnings`, action text marker |
| 14 | Host auto-handoff after threshold absences | G22 #803 | host absent past threshold → `campaigns.host_user_id`/`role='owner'` moves to most-active player |
| 15 | Vote-kick: majority kicks (2-player = host unilateral); kicked hero → idle keeps XP/gold | G3 #787 / G13 #799 | `campaign_kick_votes` rows; target member `status='kicked'`; hero `status='idle'`, sheet XP/gold intact |
| 16 | Action withdraw while `collecting` | G24 #805 | `--withdraw <u>`: action row deleted, round stays `collecting` |
| 17 | Late-joiner: onboarding summary one-time + catch-up | G12/G25 #798/#806 | new member `pending_intro=1` then cleared; `GET /catchup` returns last-rounds context |
| 18 | Wipe penalty: all downed → gold loss % by level, wake 50% HP | G15 #813 | gold delta matches `mp_balance.WIPE_GOLD_PCT_BY_LEVEL` (10/20/30); `<50 gp` exempt; HP back to 50% max |
| 19 | Tiered summaries: layer-1 per round, layer-2 chapter ~10 | G18 #796 | `campaign_round_summaries` layer=1 rows; layer=2 after ≥10 |
| 20 | Quiet window: sweep won't close round at night | G27 #808 | inject time inside quiet window → `mp_sweep.py` no-ops |
| 21 | Idempotency: duplicate `client_action_id` → one action | G30 #801 | submit same id twice → single `campaign_round_actions` row |

### 1.6 Defects + report — identical to `/game-smoke`

Issues: `gh issue create --repo szmidtpiotr/ai-gm --title "[BUG] SMOKE-MP — <opis>" --label "bug,smoke-defect,needs-testing"`.
P0 = party can't progress a round (blocks the mode) · P1 = breaks experience (state↔narration
contradiction, privacy leak, dead mechanic) · P2 = cosmetic.

Report comment (on the MP tracker issue):

```
## 🎮 game-smoke-mp <N graczy> — <data>
Kampania: id | Gracze: u1,u2,… (+spectator) | Rund zagranych: N

### Werdykt: GRYWALNY / GRYWALNY Z ZASTRZEŻENIAMI / NIEGRYWALNY
(NIEGRYWALNY jeśli ≥1 P0; Z ZASTRZEŻENIAMI jeśli ≥1 P1)

### Checkpointy   (12 core + opcjonalnie 13–21)
| # | Checkpoint | Wynik | Dowód |   (✅ / ❌ #issue / N/D powód)

### Defekty: P0: n · P1: n · P2: n (linki)
### Screenshoty (3+, co widać, z którego kontekstu gracza)
```

### 1.7 Gotchas (MP-specific, in addition to solo ones)

- **Cost**: N players × rounds × 2-pass narration. Force `gpt-4.1-mini`, keep core run ≤8 rounds.
- **Don't wait the real timer** — always close rounds with `mp_sweep.py` (injected time). Set
  `round_timer_minutes=1` at lobby creation as a backstop.
- Private notes/roll_facts are **token-scoped** — fetch narration with each player's own token, never the host's for everyone.
- **Reassign / re-login** if the backend restarts mid-run (tokens survive, but verify each member still `accepted`).
- Whisper-privacy check is a **P1-or-worse gate**: grep the stored LLM prompt/round context for whisper text — any hit = leak.

---

## 2. Playwright MP suite (real multi-client UI)

### 2.1 Why Playwright on top of the smoke

The smoke proves the **engine** is playable via API. Playwright proves the **UI** wires N real
browsers together: lobby presence, live round status polling, the spectator read-only lock, chat
panel, kick modal, countdown timer. These are pure front-end behaviours (`frontend/front/js/multiplayer_ui.js`,
1163 lines) that the API smoke can't see.

### 2.2 Harness

- **N browser contexts in one test** (Playwright `browser.newContext()` per player → isolated
  cookies/localStorage), each logged in as a different `tester_mpX`. This is the core trick — one
  test file drives the whole party. (With the Playwright MCP, use separate tabs/contexts via
  `browser_tabs`; for committed specs, native `@playwright/test` multi-context is cleaner.)
- Specs land in `ai_test_agent/` so they auto-list in **admin → Narzędzia → Playwright** (same path
  the `tdd` skill uses). `BASE_URL=http://frontend:80` inside the test-agent container; external
  verify URL `https://aigm-dev.studio-colorbox.com/`.
- A `mp-fixtures.ts` helper: `loginAs(context, user)`, `createLobby(host, n)`, `acceptInvite(ctx, token, heroId)`,
  `submitRound(ctx, text)`, `forceSweep(campaignId)` (calls the admin endpoint), `dbAssert(sql)`
  (via the test-agent's DB read path).

### 2.3 Specs (one file per scenario)

| Spec | Steps | UI assertion |
|---|---|---|
| `mp_lobby_join.spec` | host creates lobby; P2/P3 open invite link; accept + pick hero | each context's lobby shows live member count = actual joined; host badge on host only |
| `mp_round_sync.spec` | all contexts type an action + send; | submit button disables after send; status bar shows `submitted k/N`; when last submits, all contexts poll → narration text appears in **every** context within timeout |
| `mp_private_notes.spec` | play a round with differing actions | player A's context shows A's green private note + 🎲 roll_facts; B's note **not** visible in A |
| `mp_spectator.spec` | spectator context joins (policy=watch) | action input **absent/disabled** for spectator; spectator sees narration; spectator cannot see whispers; with policy=none spectator sees nothing |
| `mp_chat_whisper.spec` | P1 public msg; P1 whisper→P2 | public msg appears in all player contexts; whisper appears only in P1+P2, **never** in P3 or spectator |
| `mp_spectator_mute.spec` | spectator (watch_hint) sends a hint; P2 mutes spectator | before mute P2 sees hint; after mute P2's context drops it; 403 path covered |
| `mp_absence_kick.spec` | P3 skips rounds; `forceSweep` ×N | P3's absence warning count renders; after threshold a **vote-kick / handoff modal** appears in other contexts; cast votes → P3 removed from member list |
| `mp_countdown.spec` | start a round with short timer | live countdown ticks down in all contexts; on `forceSweep` the round flips to narrating in the UI without reload |
| `mp_combat_initiative.spec` | start MP combat (3 players + 2 enemies) | initiative chips render in turn order; "Twoja kolej" highlight moves to the active player's context only; enemy turns shown after players |
| `mp_late_joiner.spec` | start a 2-player game, P3 joins mid-game | P3's first view shows the onboarding/"co się działo" summary once; it does not reappear next round |

### 2.4 Determinism rules for the specs

- Combat actions and skill outcomes go through the real engine → assert on **structure** (turn order
  exists, HP changed, note rendered), not on exact dice/damage numbers (those are starting/tunable values).
- LLM narration is non-deterministic → assert **presence + propagation** (narrative non-empty, same
  round id reaches all contexts), never exact prose.
- Always drive time with `forceSweep` / injected time — never `waitForTimeout(round_timer)`.
- Use `tester_mpX` accounts only; teardown leaves data intact (matches smoke contract).

---

## 3. Coverage map (what each layer owns)

| Layer | Owns | Already exists? |
|---|---|---|
| Backend pytest (`test_78x`–`test_81x`, #937/#950) | per-feature unit/service correctness (FSM, sweep, balance, injection, idempotency) | ✅ ~45 files |
| `/game-smoke-mp` | **is the mode playable end-to-end** with the real LLM across N real accounts | ✗ to build |
| Playwright MP suite | **multi-client UI** wiring: presence, sync, spectator lock, chat/whisper, kick modal, countdown | ✗ to build |

The smoke answers "can a party play this?"; Playwright answers "does the UI keep N browsers in
sync?"; pytest answers "is each rule correct in isolation". Build smoke first (catches the big
integration breaks cheaply), then Playwright for the UI-only behaviours.

---

## 4. Open items to confirm before building

1. **Test users**: which admin endpoint creates `tester_mp1..4` (or seed them) — registration needs an
   invite_code, so likely an admin create-user path. Confirm before `setup_mp_users.py`.
2. **Force-sweep endpoint**: exact route/signature of the G30 admin force-sweep + time injection
   (used by `test_785`/`test_801`) — read those tests to copy the call.
3. **MP tracker issue**: file one `[TASK] MP smoke + Playwright harness` issue (per the
   implementation-record convention) to host the smoke reports.
4. **Flag gate**: confirm `multiplayer_enabled` toggle path so the skill can ensure it's ON.
