---
name: game-screen
description: >-
  Take a screenshot of the AI-GM DEV frontend and display it inline in Claude Code.
  Logs in as demo user, optionally navigates to a specific campaign or screen, saves
  the PNG to temp-img/ and reads it back so it appears inline in the conversation.
  Use when the user wants to visually verify frontend state.
---

# game-screen

## Purpose

Capture a live screenshot of https://aigm-dev.studio-colorbox.com/ using
Playwright in the test-agent container on .61, save to `temp-img/`, and
display inline in Claude Code via the Read tool.

## Invocation

```
/game-screen
/game-screen campaign 999435
/game-screen death 999435
/game-screen heroes
/game-screen login
/game-screen wygeneruj death screen
/game-screen pokaż ekran śmierci kampanii 999435
```

Args (all optional, natural language OK — infer intent):
- `campaign <id>` — enter campaign with that id (uses [TEST] Wojownik, user_id=1)
- `death <id>` / "death screen" / "ekran śmierci" — show death screen; if no id given, use most recently ended campaign for user_id=1
- `heroes` / "bohaterowie" — show heroes screen after login
- `login` — show login screen only (no login)
- no args — heroes screen (default)

**Natural language parsing:** if args contain "death", "śmierć", "poległ", "ekran śmierci" → mode=death; if "heroes", "bohater" → mode=heroes; if a number is present → campaignId. When mode=death and no id given, query DB for most recent ended campaign.

## Steps

1. Build Playwright script based on args
2. Run via `docker exec -w /app ai-gm-dev-test-agent-1 node ...` on .61
3. Copy PNG back to `temp-img/<timestamp>_game_screen.png` on .19
4. Read the file to display inline

## Script location

`scripts/screenshot.js` — generated dynamically; template in this dir.

## Output

```
Screenshot: temp-img/1234567890_game_screen.png
[inline image displayed by Read tool]
```

## Execution (follow exactly)

```bash
# 1. Copy script into container
scp /home/claude/projects/DEV_AIGM/.claude/skills/game-screen/scripts/screenshot.js \
    claude@192.168.1.61:/tmp/gs_screenshot.js
ssh claude@192.168.1.61 \
    'docker cp /tmp/gs_screenshot.js ai-gm-dev-test-agent-1:/app/gs_screenshot.js'

# 2. Run (adjust mode and campaignId per args)
ssh claude@192.168.1.61 \
    'docker exec -w /app ai-gm-dev-test-agent-1 node gs_screenshot.js <mode> [campaignId]'

# 3. Copy result back
ssh claude@192.168.1.61 \
    'docker cp ai-gm-dev-test-agent-1:/tmp/game_screen_out.png /tmp/gs_out.png'
scp claude@192.168.1.61:/tmp/gs_out.png \
    /home/claude/projects/DEV_AIGM/temp-img/<TIMESTAMP>_game_screen.png
```

# 4. Use Read tool on the saved path — Claude Code renders it inline.

## Notes

- Always uses `demo` / `demo` credentials (user_id=1)
- Playwright is in `/app/node_modules` inside test-agent container
- temp-img dir: `/home/claude/projects/DEV_AIGM/temp-img/`
- Image displayed inline: Claude Code reads PNG path and renders it
- TIMESTAMP = `date +%s` value, makes filenames unique
