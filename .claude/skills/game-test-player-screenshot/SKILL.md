---
name: game-test-player-screenshot
description: >-
  Same as /game-test-player — plays 8-12 turns as a real player, runs DB checks,
  posts a report to GitHub — PLUS takes screenshots at key moments and embeds them
  in the GitHub comment. Use when visual evidence of the UI state is needed alongside
  the text report. Use /game-test-player when screenshots are not required.
  Use when: the user types /game-test-player-screenshot #NNN [optional hint].
---

# game-test-player-screenshot

Identical to `/game-test-player` in every way, with one addition: **after the turns
are played, takes a screenshot of the campaign from the DEV frontend, uploads it to
GitHub, and embeds it in the report comment.**

Follow every step below exactly — steps 1–6 are identical to `/game-test-player`;
step 7 is extended with screenshot capture and upload.

## ⛔ VERIFICATION CONTRACT (same as /game-test-player)

Verification happens through **real gameplay turns only**. No Python scripts, no direct service calls, no DB writes as a substitute for turns. See game-test-player SKILL.md for full contract.

## 📸 SCREENSHOT RULES

**Screenshots must show EVIDENCE of the mechanic, not just the game running.**

### What makes a valid evidence screenshot:

| Feature type | What to screenshot |
|---|---|
| Gold mechanic (SPEND_GOLD, shop) | The turn card where the transaction appeared — narrative visible showing cost/refusal text |
| HP / combat | TWO screenshots: HP badge BEFORE combat, HP badge AFTER combat. Shows the change. |
| Shop prices (price_gp) | The shop UI or turn card showing the item price — must display the actual number |
| Death / resurrection | The death screen itself showing the resurrection button + cost |
| Admin UI | The specific feature being USED (form filled, not just tab visible) |
| Anti-farm | Turn card showing sell transaction with reduced price vs first sell |

### Opening-turn screenshot = NO EVIDENCE

A screenshot of the opening narrative (tura 1) proves nothing about the tested feature. **Always take the screenshot AFTER the turn that triggered the tested mechanic.**

### Multi-screenshot strategy:

For mechanics with before/after states (HP, gold, inventory), take **two screenshots**:
1. Screenshot A — before the mechanic fires (shows starting state)
2. Screenshot B — after the mechanic fires (shows resulting state)

Both upload to GitHub and both embed in the comment with clear labels ("Przed" / "Po").

## Invocation

```
/game-test-player-screenshot #378
/game-test-player-screenshot #378 "szukaj kowala i pomóż mu"
```

Args:
- `#NNN` — GitHub issue number (required)
- `"hint"` — optional player strategy hint

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

**If hint given**: use it as the starting point for your strategy.
**If no hint**: derive strategy entirely from the issue description.

---

## Step 3 — Setup Hero Pool (once, idempotent)

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

---

## Step 5 — Play Turns

```bash
cd /home/claude/projects/DEV_AIGM/.claude/skills/game-test-player
python3 ../game-test/scripts/play_turn.py \
  --campaign CAMPAIGN_ID \
  --character CHARACTER_ID \
  --message "player text here" \
  --narr-chars 500
```

**After each turn**: read narrative, adapt next message. If `route=skill_test` → resolve before continuing.

**Skill test handling**: send `"Staram się jak mogę."` or fitting action.

**Combat handling**: when combat starts, use combat API:
```bash
curl -X POST http://192.168.1.61:8100/api/campaigns/CAMP_ID/combat/resolve-attack \
  -H "Content-Type: application/json" -d '{"roll_result": 16, "attacker": "player", "raw_d20": 15}'
curl -X POST http://192.168.1.61:8100/api/campaigns/CAMP_ID/combat/enemy-turn \
  -H "Content-Type: application/json" -d '{}'
```

---

## Step 6 — Issue-Specific DB Check

```bash
# Turn count + last routes
ssh claude@192.168.1.61 "docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  'SELECT turn_number, route, substr(assistant_text,1,120) FROM campaign_turns WHERE campaign_id=CAMPAIGN_ID ORDER BY turn_number DESC LIMIT 10;'"

# Combat state / HP
ssh claude@192.168.1.61 "docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  'SELECT json_extract(sheet_json,\"$.hp\") hp, json_extract(sheet_json,\"$.max_hp\") max_hp FROM characters WHERE id=CHARACTER_ID;'"

# NPC memory
ssh claude@192.168.1.61 "docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  'SELECT npc_name, notes FROM campaign_known_npcs WHERE campaign_id=CAMPAIGN_ID AND notes IS NOT NULL;'"
```

Derive the exact query from the issue's acceptance criteria.

---

## Step 7 — Screenshot + Report + GitHub

### 7a — Take screenshot (ADDITIONAL step vs /game-test-player)

**WHEN to take screenshots:**
- Take screenshot AFTER the turn that triggered the tested mechanic (not at end of session)
- For before/after mechanics: take screenshot before turn N, then again after turn N
- Label each screenshot with what it shows: `TS_before`, `TS_after`, `TS_death`, `TS_shop`, etc.

```bash
# Copy script into container (once per session)
scp /home/claude/projects/DEV_AIGM/.claude/skills/game-screen/scripts/screenshot.js \
    claude@192.168.1.61:/tmp/gs_screenshot.js
ssh claude@192.168.1.61 \
    'docker cp /tmp/gs_screenshot.js ai-gm-dev-test-agent-1:/app/gs_screenshot.js'

# Run AFTER the mechanic-triggering turn — use campaign_id from Step 4
ssh claude@192.168.1.61 \
    'docker exec -w /app ai-gm-dev-test-agent-1 node gs_screenshot.js campaign CAMPAIGN_ID'

# Copy result back (MUST go via sudo on .61 — sshfs temp-img is not writable from .19)
TIMESTAMP=$(date +%s)
LABEL="mechanic_name"   # e.g. "spend_gold_after", "hp_before_combat", "death_screen"
ssh claude@192.168.1.61 \
    "sudo docker cp ai-gm-dev-test-agent-1:/tmp/game_screen_out.png /tmp/gs_${TIMESTAMP}.png && \
     sudo cp /tmp/gs_${TIMESTAMP}.png /home/piotrszmidt/ai-gm/temp-img/${TIMESTAMP}_${LABEL}.png && \
     sudo chmod 664 /home/piotrszmidt/ai-gm/temp-img/${TIMESTAMP}_${LABEL}.png"
```

**Read the screenshot inline** (REQUIRED — always look before writing the description):
```bash
# Local path via sshfs mount:
# /home/claude/projects/DEV_AIGM/temp-img/${TIMESTAMP}_${LABEL}.png
```
Use the Read tool on that path — Claude Code renders PNG inline. Look at it.

**If the screenshot shows only the opening narrative and no mechanic evidence → it is NOT valid evidence. Take another screenshot after the relevant turn.**

### 7b — Upload to GitHub release assets (ADDITIONAL step)

```bash
TAG=$(gh release list --repo szmidtpiotr/ai-gm --limit 1 --json tagName --jq '.[0].tagName')
FNAME="${TIMESTAMP}_game_screen.png"

gh release upload $TAG \
  /home/claude/projects/DEV_AIGM/temp-img/$FNAME \
  --repo szmidtpiotr/ai-gm --clobber

IMAGE_URL=$(gh release view $TAG --repo szmidtpiotr/ai-gm --json assets \
  --jq ".assets[] | select(.name == \"$FNAME\") | .url")
```

### 7c — Post report comment with embedded screenshot

```bash
gh issue comment NNN --repo szmidtpiotr/ai-gm --body "$(cat <<'COMMENT'
## 🎮 game-test-player run — [date]

**Campaign**: #NNN (id: CAMPAIGN_ID)
**Hero**: [archetype hero name] (id: CHARACTER_ID)
**Turns played**: X

### Verdict
**BUG WIDOCZNY** / **BUG NIE WIDOCZNY** / **NIEKONKLUZYWNY**

[evidence summary — 2-3 sentences]

### Turn log
| # | Player input | LLM response (first 150 chars) |
|---|---|---|
| 1 | __AI_GM_OPEN | ... |

### DB check
[paste SQL output]

---

## 📸 Screenshot — [short description of what was captured]

![campaign #NNN — feature name](IMAGE_URL)

**Co widać:**
- [specific UI elements visible — character name, HP badges, turn cards, combat log]
- [exact values/states shown]

**Co sprawdzić:**
- [what a human reviewer should look for to confirm the feature works]
- [expected numbers, state badges, turn outcomes]

Campaign visible at: https://aigm-dev.studio-colorbox.com/admin/#campaigns
COMMENT
)"
```

**Screenshot description rules:**
- Look at the actual screenshot before writing — no generic text
- The screenshot must show the MOMENT the mechanic fired or its result — not just the game open
- Name specific elements visible: exact text in narrative, HP values, gold amounts, price numbers, button labels
- "Co widać" must quote what's visible: "Narracja w turze 4 zawiera tekst: 'Zapłaciłeś 5 złota za nocleg'" not "pokazuje narrację"
- "Co sprawdzić" must be actionable with exact expected values: "HP badge shows 8/24 (hurt after combat)" not "verify the HP"
- For before/after: explicitly label Zrzut A (PRZED) i Zrzut B (PO) i wskaż różnicę

**If you only have an opening-turn screenshot → add a note: "Brak screenshotu z momentu mechaniki — wymagany retest z turą triggering."**

### 7d — File new issues for side bugs

```bash
gh issue create --repo szmidtpiotr/ai-gm \
  --title "[BUG] SB-N — short description" \
  --label "bug,needs-testing" --body "..."
```

---

## Constraints

- **Never delete** the campaign or characters after the run
- **Only Demo account** (user_id=1) — never touch user_id=1013 (piotrszmidt)
- **Max 15 turns per run** — stop and report even if inconclusive
- **Campaign title exactly `#NNN`**
- `play_turn.py` opens the local sshfs DB **read-only** — allowed. Never write.
- If `__AI_GM_OPEN` was already sent (campaign existed), start from turn 2

---

## Known Issues & Gotchas

**1. Reassign before EVERY session:**
```bash
curl -s -X POST http://192.168.1.61:8100/api/characters/CHAR_ID/assign-campaign \
  -H "Content-Type: application/json" -d '{"campaign_id": CAMP_ID, "user_id": 1}'
```

**2. Rate limit (TPM 30k/min) → 502 errors:**
Wait 60s between 502 retries. Use `model_id: "gpt-4.1-mini"` to reduce token cost.

**3. skill_test_keyword route:**
Send `"Staram się jak mogę."` to resolve, then continue.

**4. temp-img write restriction:**
Cannot write directly from .19 to sshfs-mounted temp-img. Always use `sudo cp` on .61 as shown in Step 7a.

**5. gate_blocked: no_enemies:**
Narrative turns trying to "attack X" are blocked if no enemy pool is set. Start combat directly:
```bash
curl -s -X POST http://192.168.1.61:8100/api/campaigns/CAMP_ID/combat/start \
  -H "Content-Type: application/json" \
  -d '{"enemy_keys": ["thug"], "character_id": CHAR_ID}'
```
Get admin token first: `curl -s -X POST http://192.168.1.61:8100/api/admin/dev-login -H "Content-Type: application/json" -d '{"username":"demo","password":"demo"}'`

**6. Screenshot 502 errors in console:**
PAGE error 502 in screenshot output is normal (voice service, other optional services). The game UI still loads — screenshot is valid.
