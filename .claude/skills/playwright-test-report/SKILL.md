---
name: playwright-test-report
description: >-
  Drive the AI-GM DEV frontend through a requested test scenario using the
  Playwright MCP browser, screenshot each verified step, file full TDD-style
  GitHub issues for bugs found, and produce a step-by-step session report in
  plain (non-technical) Polish — screenshots in test order, each with a
  human-readable description and a PASS/PROBLEM verdict, ending with a
  prioritized fix list linking every filed issue. Updates notes.md (test
  status) and game_mechanics.md (only on spec↔game divergence). Use when the
  user types /playwright-test-report <co przetestować> [#NNN].
---

# playwright-test-report

Live, browser-driven test of the AI-GM DEV frontend that produces a **report a
non-technical person can read**: ordered screenshots, plain-language "co
testowano / co widać / czy działa", filed bug tickets, and a prioritized
summary.

Runs the browser through **Playwright MCP** (`mcp__playwright__*` tools) — the
`.19` browser hits `https://aigm-dev.studio-colorbox.com/` directly. No docker
test-agent needed.

## Invocation

```
/playwright-test-report przetestuj run w lochu krypta_probna
/playwright-test-report sprawdź czy drzwi-zaślepki działają #697
/playwright-test-report przejdź walkę w lochu i sprawdź skrzynię #696
```

Args (natural language):
- **Task description** (required) — what to test, in plain words
- **`#NNN`** (optional) — GitHub issue this test relates to. If given, the final
  report goes as a **comment on #NNN**. If absent, a **new `[TEST-REPORT]` issue**
  is created.

## ⛔ Core contract

- **Real browser turns only.** Verify through the actual UI via Playwright MCP —
  no Python service calls or DB writes as a substitute for what a player sees.
- **Demo account only** (`user_id=1`, login `demo`/`demo`). NEVER touch
  `piotrszmidt` (`user_id=1013`).
- **Never delete** campaigns/heroes after the run.
- **Every screenshot must show EVIDENCE** of the thing tested — not just "game is
  open". Capture AFTER the action that triggers the mechanic.
- **Screenshots saved to `temp-img/<run>/NN-label.png`**, NEVER `/tmp/` (not
  visible to the user via sshfs). Always `Read` each PNG inline before describing
  it — describe only what you actually see.

---

## Step 1 — Parse request & plan the test

1. Extract task description + optional `#NNN`.
2. If `#NNN` given: `gh issue view NNN --repo szmidtpiotr/ai-gm` — read acceptance
   criteria so the test targets what matters.
3. Write an ordered **test plan**: list the discrete steps you'll verify, each
   with the screenshot you intend to capture and what would count as PASS vs
   PROBLEM. This list becomes the report's spine — keep it in order.
4. Create the run dir:
   ```bash
   RUN="$(date +%Y%m%d_%H%M%S)_<short-slug>"
   mkdir -p /home/claude/projects/DEV_AIGM/temp-img/$RUN
   ```
   Use a fixed `RUN` slug for the whole session so screenshots sort in order.

---

## Step 2 — Open & log in via Playwright MCP

```
mcp__playwright__browser_navigate  → https://aigm-dev.studio-colorbox.com/
mcp__playwright__browser_snapshot   (to get element refs)
mcp__playwright__browser_type       #login-username = "demo"
mcp__playwright__browser_type       #login-password = "demo"
mcp__playwright__browser_click      #login-form button
mcp__playwright__browser_wait_for   (heroes screen / "Moi Bohaterowie")
```

Selectors (player UI): `#login-username`, `#login-password`, `#login-form button`.
Use `browser_snapshot` whenever you need fresh element refs; use
`browser_evaluate` for state checks the UI doesn't show directly.

---

## Step 3 — Execute the test, screenshot each step IN ORDER

For **each** step in the plan:

1. Drive the UI to the state under test (navigate, click, enter campaign/dungeon,
   take a turn, resolve combat, open chest, move through a door…).
2. **Capture evidence** right after the trigger:
   ```
   mcp__playwright__browser_take_screenshot
     filename = temp-img/<RUN>/NN-<label>.png   (NN = zero-padded order: 01,02,…)
   ```
3. `Read` the PNG inline. **Look at it.** Confirm it actually shows the mechanic.
   If it only shows an opening/neutral screen → redo after the right action.
4. Record, for the report (plain Polish, no jargon):
   - **Co testowano** — one sentence a non-dev understands
   - **Co widać** — quote concrete visible elements (exact text, HP values, gold
     amounts, button labels, door glyphs, tile image)
   - **Werdykt** — ✅ DZIAŁA / ❌ PROBLEM / ⚠️ NIEPEWNE
   - If PROBLEM: what's wrong, in plain words ("Gracz kliknął drzwi na północ, ale
     nic się nie wydarzyło — postać została w tej samej komnacie").

For before/after mechanics (HP, gold, mana, inventory) take **two** screenshots
(`NN-...-przed`, `NN+1-...-po`) and describe the difference.

Combat / dungeon helpers: prefer the UI buttons. If a flow needs a backend nudge,
the dungeon/combat endpoints on `http://192.168.1.61:8100` are available (see
`game-test-player` skill), but the player-visible result must still be
screenshotted from the browser.

---

## Step 4 — File a full TDD-style issue for each bug

The moment a step is ❌ PROBLEM, file a GitHub issue **before** continuing (so the
report can link it). Match issue template #18 exactly
(https://github.com/szmidtpiotr/ai-gm/issues/18):

```bash
gh issue create --repo szmidtpiotr/ai-gm \
  --title "[BUG] <task-code if any> — <short description>" \
  --label "bug,needs-testing" \
  --body "$(cat <<'BODY'
## Task
<what was being tested + link to #NNN if related>

## What was observed
<plain description of the broken behavior + which step in the test>

## Expected
<what should have happened per acceptance criteria / spec>

## Repro (browser, demo account)
1. <exact UI steps to reproduce>

## Evidence
![<alt: co widać na zrzucie dowodzącym buga>](SCREENSHOT_URL)   ← fill after Step 5 upload

## Files (suspected)
- <best guess at code path, or "TBD">

## Acceptance
- [ ] <observable condition that proves the fix>
BODY
)"
```

Capture the new issue number — it goes in the report's fix list. Screenshot URL
is filled after Step 5 (upload), then `gh issue edit NNN --body` to patch it in,
or include the URL inline if upload is done first.

---

## Step 5 — Upload screenshots to GitHub (for embedding)

GitHub issues can't render `temp-img/` paths — upload to release assets and use
the returned URLs:

```bash
TAG=$(gh release list --repo szmidtpiotr/ai-gm --limit 1 --json tagName --jq '.[0].tagName')
for f in /home/claude/projects/DEV_AIGM/temp-img/$RUN/*.png; do
  gh release upload "$TAG" "$f" --repo szmidtpiotr/ai-gm --clobber
done
# URL for each: gh release view "$TAG" --repo szmidtpiotr/ai-gm --json assets \
#   --jq '.assets[] | select(.name=="<basename>") | .url'
```

Keep a label→URL map in screenshot order.

---

## Step 6 — Build the session report (plain Polish, in test order)

The report is for a **non-technical reader**.

**🖼 Hard rule — zdjęcia INLINE w sekcjach, nie zbiorczo.** Każdy screenshot
osadzony jest BEZPOŚREDNIO pod nagłówkiem swojego kroku, tuż przed opisem "Co
widać", tak by czytelnik widział obraz dokładnie tam, gdzie czyta o nim. NIGDY
nie zbieraj wszystkich zdjęć w jedną galerię na końcu wpisu. Jedna sekcja `####`
= jeden (lub para przed/po) obraz + jego opis, w kolejności wykonania. Każdy
obraz dostaje też tekst `alt` opisujący co przedstawia (`![walka: HP wroga
spadło do 8](URL)`), nie generyczne `![krok 2]`.

Structure:

```markdown
## 🧪 Raport testu — <data> — <task w jednym zdaniu>

**Co testowano:** <2-3 zdania prostym językiem>
**Środowisko:** DEV (demo), kampania/loch: <nazwa/id>
**Werdykt ogólny:** ✅ Wszystko działa / ⚠️ Działa z zastrzeżeniami / ❌ Są blokery

---

### Przebieg krok po kroku

#### 1. <co testowano w tym kroku>
![<alt: co dokładnie widać na tym zdjęciu>](URL_01)
- **Co widać:** <konkret z ekranu>
- **Werdykt:** ✅ DZIAŁA  (albo ❌ PROBLEM → opis + link do #issue)

#### 2. <…>
![<alt opisujący ten ekran>](URL_02)
- **Co widać:** …
- **Werdykt:** …

(…wszystkie kroki w kolejności wykonania — KAŻDY ze swoim zdjęciem inline pod
nagłówkiem; przed/po jako dwa obrazy w tej samej sekcji…)

---

### Podsumowanie — co poprawić i w jakiej kolejności

1. 🔴 **<najpilniejsze>** — <prosty opis problemu> → #<issue>
2. 🟠 **<średnie>** — … → #<issue>
3. 🟡 **<drobne>** — … → #<issue>

✅ Działa poprawnie: <lista przetestowanych rzeczy bez problemów>
```

Rules:
- Screenshots appear in **the exact order they were taken** during the test.
- **Inline, never grouped:** every screenshot sits inside its own `####` step,
  directly above that step's "Co widać". No end-of-report gallery, no block of
  images detached from their descriptions.
- Each gets a plain-language "co widać" quoting real visible content, and an
  `alt` text that describes the image (helps the reader scan + a11y).
- Confirmations matter too: when a previously-broken thing now works, say so
  explicitly ("Poprawka zadziałała — skrzynia daje teraz przedmioty do plecaka,
  widać 'Zdobyto: Mikstura leczenia'").
- The closing summary orders fixes by priority (🔴 bloker → 🟡 kosmetyka) and links
  every filed issue.

Post it:
- **If `#NNN` given** → `gh issue comment NNN --repo szmidtpiotr/ai-gm --body "..."`
- **Else** → `gh issue create --repo szmidtpiotr/ai-gm --title "[TEST-REPORT] <data> — <task>" --label "test-report" --body "..."`
  (create the `test-report` label first if missing:
  `gh label create test-report --repo szmidtpiotr/ai-gm --color BFD4F2 2>/dev/null || true`)

---

## Step 7 — Update notes.md & game_mechanics.md

**notes.md (always):** record test status against the relevant task(s). If a
task's checklist item was verified, note it (e.g. under the FAZA L debt block:
"L-doors #697 — przetestowane /playwright-test-report <data>, raport: <link>,
werdykt ✅/❌"). Keep it one or two lines; link the report.

**game_mechanics.md (ONLY on spec↔game divergence):** if the test proves the game
behaves differently from what the spec says, add a short dated note in the
relevant CZĘŚĆ describing the divergence + report link. Do NOT append routine
test logs here — the file is the locked spec, not a test journal. If no
divergence, leave it untouched.

---

## Step 8 — Commit & report back

Commit `notes.md` (+ `game_mechanics.md` if changed) on `develop` via
`sudo -u piotrszmidt git` on `.61` (per repo git topology), referencing any filed
issue numbers. Push. Then tell the user, in one short message: verdict, how many
problems found, and the report link.

---

## Constraints

- Demo account (`user_id=1`) only — never `piotrszmidt` (`1013`).
- Never delete campaigns/heroes.
- Screenshots → `temp-img/<RUN>/`, never `/tmp/`; `Read` each before describing.
- Cap the run at a sensible length (~15 turns / steps); stop and report even if
  inconclusive, noting what wasn't reached.
- Close the browser at the end (`mcp__playwright__browser_close`).
