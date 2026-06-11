---
name: game-test-player
description: >-
  Claude impersonates a player to reproduce or verify an issue end-to-end.
  Creates a dedicated campaign named "#NNN" on the Demo account (user_id=1),
  plays 8-12 turns guided by the issue's acceptance criteria, posts a text
  report + DB check as a GitHub comment, then leaves the session intact.
  Text-only report — no screenshots. Use /game-test-player-screenshot for the
  same test with screenshots embedded in the GitHub comment.
  Use when: the user types /game-test-player #NNN [optional hint].
---

# game-test-player

## ⛔ VERIFICATION CONTRACT — READ BEFORE ANYTHING ELSE

**This skill tests from the player's perspective. The player has NO access to:**
- Python scripts / direct service calls
- SQLite / DB writes
- Internal API calls that bypass the game flow

**What counts as valid verification:**
- The LLM narrative text contains the expected output (e.g., "Zapłaciłeś 5 złota", refusal message, HP changed)
- The route or game state changed as seen through the turn response
- The feature visibly triggered during a real turn (the turn's `narrative` field contains evidence)

**What does NOT count as verification:**
- Calling the service function directly in Python → does NOT prove the LLM flow works
- Writing rows to `character_gold_log` manually → does NOT prove `shop/sell` endpoint works
- Querying `resurrect-preview` API directly → does NOT prove the death screen shows the button
- Checking DB columns exist → does NOT prove they are used correctly end-to-end

**DB checks (Step 6) are SUPPLEMENTARY** — they confirm DB state AFTER real gameplay triggered the mechanic. They never substitute for actual turns.

**If you cannot trigger the scenario through turns in 15 turns → verdict is NIEKONKLUZYWNY. Never fake it.**

---

## Purpose

Different from `/game-test` (which resets a scratch campaign to verify a *fix*).
This skill creates a **permanent, human-viewable session** where Claude plays
a real game attempting to **reproduce** the scenario described in the issue.
The user watches from the frontend and judges whether the bug still exists.

## Invocation

```
/game-test-player #378
/game-test-player #378 "szukaj kowala i pomóż mu"
```

Args:
- `#NNN` — GitHub issue number (required)
- `"hint"` — optional player strategy hint (overrides Claude's default strategy)

---

## Step 1 — Read the Issue

```bash
gh issue view NNN --repo szmidtpiotr/ai-gm
```

Read: title, body, acceptance criteria, comments. Understand:
- What scenario triggers the bug/feature?
- What outcome proves it works (or is broken)?
- Any manual testing instructions already written?

---

## Step 2 — Select Archetype and Form Strategy

**Archetype selection** (pick ONE):

| Archetype | Use when issue involves… |
|-----------|--------------------------|
| `warrior` | combat, melee, HP, physical stats, NPCs, narrative (default) |
| `scholar` | mana, spells, magic_bolt, arcane, INT-based mechanics |
| `rogue`   | stealth, DEX, pickpocket, traps, evasion |

**Strategy**: Write out 8–12 player messages BEFORE playing.
Think: "What would a real player say to organically reach the scenario?"

**Map each acceptance criterion to a specific turn:**
For every checkbox in the issue's acceptance criteria, identify which turn will trigger it and what the LLM response must contain to prove it works. Example:

```
Issue: SPEND_GOLD tag deducts gold from character
Acceptance: "Wystarczające złoto → tag usunięty, złoto odliczone"

Turn 1: __AI_GM_OPEN (auto)
Turn 2: "Wchodzę do wioski i szukam gospody"
Turn 3: "Pytam karczmarza o nocleg i cenę"   ← LLM should mention cost / [SPEND_GOLD:inn_night]
Turn 4: "Płacę za nocleg i kładę się spać"   ← trigger: LLM response must NOT show the tag; gold must decrease
Turn 5: DB check gold_gp → confirm decreased by expected amount
```

Example strategy for #378 (NPC memory):
```
Turn 1: "__AI_GM_OPEN"               ← always first, auto-sent by setup script
Turn 2: Enter a settlement, find a named NPC
Turn 3: Help the NPC with something memorable (repair, rescue, gift)
Turn 4: Do something unrelated (explore, fight, move)
Turn 5: Return to same settlement, seek same NPC
Turn 6–7: Reference earlier event — see if NPC remembers
Turn 8: DB check + conclude
```

**If hint given**: use it as the starting point for your strategy.
**If no hint**: derive strategy entirely from the issue description.

---

## Step 3 — Setup Hero Pool (once, idempotent)

Run from skill directory:

```bash
cd /home/claude/projects/DEV_AIGM/.claude/skills/game-test-player
python3 scripts/setup_hero_pool.py
```

Creates (if missing) for user_id=1:
- `[TEST] Wojownik` (warrior)
- `[TEST] Uczony` (scholar)
- `[TEST] Łotrzyk` (rogue)

Returns JSON with `warrior_id`, `scholar_id`, `rogue_id`. Save these.

---

## Step 4 — Setup Campaign

```bash
python3 scripts/setup_campaign.py --issue NNN --archetype warrior
```

This script:
1. Checks if campaign `#NNN` already exists for user_id=1
2. Creates it if not (title `"#NNN"`, system_id `"fantasy"`, model_id `"default"`)
3. Assigns the chosen archetype hero from the pool
4. Sends `__AI_GM_OPEN` if campaign has no turns yet
5. Returns: `campaign_id`, `character_id`, `opening_narrative`, `existed`

**If campaign already existed**: new turns are appended — good for multiple test runs.

---

## Step 5 — Play Turns

Use the shared play_turn script:

```bash
cd /home/claude/projects/DEV_AIGM/.claude/skills/game-test-player
python3 ../game-test/scripts/play_turn.py \
  --campaign CAMPAIGN_ID \
  --character CHARACTER_ID \
  --message "player text here" \
  --narr-chars 500
```

**After each turn**:
1. Read `narrative` in the result
2. **Check: did this turn contain evidence of the tested mechanic?**
   - Quote the exact fragment from narrative that proves/disproves the feature
   - E.g. SPEND_GOLD: does narrative show cost/refusal? Does `gold_gp` in DB decrease?
   - E.g. HP/combat: does HP badge in response change? Screenshot before vs after.
   - E.g. shop price: does the listed price match `price_gp × multiplier`?
3. Adapt the next turn message based on what the LLM responded
4. If `route` is `skill_test` → send the skill test result text to resolve it before continuing
5. If `error` is set → check if the turn landed (`campaign_turns` count via DB check below) before retrying

**Pacing**: LLM calls take 15–90s. Do not send next turn until previous returns.

**Skill test handling**: if the LLM triggers a skill test (`route=skill_test`), send a descriptive action to resolve it: `"Staram się jak mogę"` or something fitting the context.

---

## Step 6 — Issue-Specific DB Check

After all turns, run an SSH+sqlite check to verify the DB state.
Derive the exact query from the issue's acceptance criteria.

**Common patterns:**

```bash
# NPC memory (#378)
ssh claude@192.168.1.61 "docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  'SELECT npc_name, notes FROM campaign_known_npcs WHERE campaign_id=CAMPAIGN_ID AND notes IS NOT NULL;'"

# Location creation
ssh claude@192.168.1.61 "docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  'SELECT id, key, label FROM game_locations WHERE source_campaign_id=CAMPAIGN_ID ORDER BY id DESC LIMIT 10;'"

# Combat state / HP
ssh claude@192.168.1.61 "docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  'SELECT json_extract(sheet_json,\"$.hp\") hp, json_extract(sheet_json,\"$.max_hp\") max_hp FROM characters WHERE id=CHARACTER_ID;'"

# Session flags (dungeon, pending skill test, etc.)
ssh claude@192.168.1.61 "docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  'SELECT session_flags FROM game_sessions WHERE campaign_id=CAMPAIGN_ID ORDER BY id DESC LIMIT 1;'"

# Turn count + last routes
ssh claude@192.168.1.61 "docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  'SELECT turn_number, route, substr(assistant_text,1,120) FROM campaign_turns WHERE campaign_id=CAMPAIGN_ID ORDER BY turn_number DESC LIMIT 10;'"

# World state / NPC memory table
ssh claude@192.168.1.61 "docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  'SELECT * FROM campaign_known_npcs WHERE campaign_id=CAMPAIGN_ID;'"
```

---

## Step 7 — Report + GitHub

### 7a — Print structured report to user

Print a structured report. **Do NOT delete the campaign.**

```
## game-test-player report — issue #NNN

**Campaign**: #NNN (id: CAMPAIGN_ID) — https://aigm-dev.studio-colorbox.com/admin/#campaigns
**Hero**: [TEST] Wojownik (id: CHARACTER_ID)
**Turns played**: X (total in campaign: Y)

### Strategy
[1-sentence description of what you tried to do]

### Turn Log
| # | Player input | LLM response (first 150 chars) |
|---|---|---|
| 1 | __AI_GM_OPEN | [opening scene] |
| 2 | ... | ... |
...

### DB Check Results
[paste the SQL output]

### Verdict
**BUG WIDOCZNY** / **BUG NIE WIDOCZNY** / **NIEKONKLUZYWNY**

**Evidence from turns** (quote narrative fragment or show before/after state):
> [paste exact text from LLM response that proves the mechanic fired — or did not fire]

[1-2 sentences of interpretation: e.g. "Tura 4: karczmarz zażądał 5 gp, gold_gp w DB 8→3. Tag nie widoczny w narracji → SPEND_GOLD działa."]

⚠️ If verdict is based only on DB/API checks without actual turns triggering the scenario → change to **NIEKONKLUZYWNY** and explain what turns were missing.

### Next steps
[If NIEKONKLUZYWNY: what additional turns or different approach would help]
[If BUG WIDOCZNY: paste the specific turn/narrative fragment as reproduction evidence]

### Side Bugs (niezwiązane z #NNN)
Każdy błąd napotkany podczas testu, który NIE jest testowanym issue:

| # | Opis | Endpoint/lokalizacja | Jak odtworzyć |
|---|------|---------------------|---------------|
| SB-1 | opis błędu | gdzie | kroki |

**Polityka:** nie naprawiaj side bugs podczas testu. Zapisz tutaj, podaj userowi w raporcie.
Naprawa w trakcie zmienia środowisko testowe.
Workflow: test → raport → dyskusja → naprawa → retest.
```

### 7b — Post comment to original issue #NNN

Always comment on the **original issue** being tested with the test results:

```bash
gh issue comment NNN --repo szmidtpiotr/ai-gm --body "$(cat <<'COMMENT'
## 🎮 game-test-player run — [date]

**Campaign**: #NNN (id: CAMPAIGN_ID)
**Hero**: [archetype hero name] (id: CHARACTER_ID)
**Turns played**: X

### Verdict
**BUG WIDOCZNY** / **BUG NIE WIDOCZNY** / **NIEKONKLUZYWNY**

[evidence summary — 2-3 sentences]

### Turn log (skrócony)
[paste turn log table]

### DB check
```
[paste SQL output]
```

Campaign visible at: https://aigm-dev.studio-colorbox.com/admin/#campaigns
COMMENT
)"
```

### 7c — File new issues for side bugs only

For each side bug that is **not** related to #NNN:

```bash
gh issue create \
  --repo szmidtpiotr/ai-gm \
  --title "[BUG] SB-N — short description" \
  --label "bug,needs-testing" \
  --body "..."
```

**Never** create a new issue for the main tested scenario — that goes as a comment on #NNN.

---

## Constraints

- **Never delete** the campaign or characters after the run
- **Only Demo account** (user_id=1) — never touch user_id=1013 (piotrszmidt)
- **Max 15 turns per run** — stop and report even if inconclusive
- **Campaign title exactly `#NNN`** — so user can find it in admin panel filter
- The `play_turn.py` opens the local sshfs DB **read-only** — this is allowed. Never open it for writes.
- If `__AI_GM_OPEN` was already sent (campaign existed), start from turn 2 of your strategy

---

## Quick reference

| Script | What it does |
|--------|-------------|
| `scripts/setup_hero_pool.py` | Create [TEST] Wojownik/Uczony/Łotrzyk on user_id=1 |
| `scripts/setup_campaign.py --issue N --archetype X` | Create #N campaign, assign hero, open scene |
| `../game-test/scripts/play_turn.py --campaign C --character H --message "..."` | POST one turn, return narrative |

---

## Known Issues & Gotchas (from first run)

**1. Reassign before EVERY session (not just first):**
The DEV backend (gpt-4.1 on OpenAI) restarts occasionally (clean exit, Docker restart policy).
After each restart, character loses in-campaign status. Always run assign-campaign before playing:
```bash
curl -s -X POST http://192.168.1.61:8100/api/characters/CHAR_ID/assign-campaign \
  -H "Content-Type: application/json" -d '{"campaign_id": CAMP_ID, "user_id": 1}'
```

**2. Rate limit (TPM 30k/min) → 502 errors:**
gpt-4.1 at 30k TPM limit. Each turn uses ~8-12k tokens (context grows with turns).
After ~3 narrative turns, hit rate limit → 502. Wait 60s between 502 retries.
Alternative: use `model_id: "gpt-4.1-mini"` in setup_campaign.py for lower token cost.

**3. skill_test_keyword route:**
When route=skill_test_keyword, send a follow-up: `"Staram się jak mogę."` or similar brief action.
The next turn will resolve the skill test and return the actual narrative.

**4. SKILL_TEST_PENDING stuck state:**
If `session_flags.state == "SKILL_TEST_PENDING"` without `pending_skill_test` data,
subsequent turns may return empty narratives. Check:
```bash
ssh claude@192.168.1.61 "docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  'SELECT session_flags FROM game_sessions WHERE campaign_id=CAMP_ID ORDER BY id DESC LIMIT 1;'"
```
If stuck, clear with: continue sending turns — the backend usually self-recovers in 1-2 turns.

**5. Combat handling:**
When combat starts (turn says "Walka trwa!"), narrative turns won't work. Use:
```bash
# Player attack (roll d20 + STR mod = roll_result)
curl -X POST http://192.168.1.61:8100/api/campaigns/CAMP_ID/combat/resolve-attack \
  -H "Content-Type: application/json" -d '{"roll_result": 16, "attacker": "player", "raw_d20": 15}'
# Enemy turn + advance
curl -X POST http://192.168.1.61:8100/api/campaigns/CAMP_ID/combat/enemy-turn \
  -H "Content-Type: application/json" -d '{}'
# After combat ends, narrative turns work again
```

**6. NPC_MEMORY is LLM-optional:**
The `[NPC_MEMORY: Name | fact]` tag is OPTIONAL per system prompt — LLM uses it when it
decides the fact is "narratively significant for future meetings". In 15+ turns of meaningful
NPC interaction (meeting, helping, giving gold), gpt-4.1 did NOT generate any NPC_MEMORY tags.
This makes testing #378 end-to-end difficult via organic play.
Better approach: craft a test turn where the narrative explicitly includes the tag format,
or use the `create_turn_log` admin approach from the issue's own test plan.
