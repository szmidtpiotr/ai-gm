# TASK 19 — Command Palette (/help)

**Status:** ❌ Not Started
**Blocking:** None — spec complete
**Depends on:** Nothing
**Unlocks:** Nothing — standalone UX improvement

---

## Overview

Typing `/help` in the chat input opens a modal showing all available slash commands. Admin accounts see all commands. Regular players see only commands marked as player-visible. The admin panel has a per-command toggle: "visible to players: on/off." This replaces the current undiscoverable command system.

---

## Design Context

### Why a command palette, not an always-visible menu?
In a text-heavy narrative game, permanent UI chrome competes for attention with the story. A pop-up palette invoked on demand keeps the chat clean while still letting players discover what's possible. It's also the standard UX for slash commands (Slack, Discord, Notion all use this pattern).

### Why admin-controlled per-command visibility?
Some commands are useful during development/testing (`/debug`, `/atak`) but should never be player-accessible. Others might be available only in certain game modes. Admin toggling avoids a code change every time visibility needs to change. It also lets the admin gradually unlock features as they become stable.

---

## Current State (Code)

- `GET /api/mechanics/slash-commands` endpoint exists — returns list of commands
- `is_slash_command_enabled()` check exists in command handlers
- No frontend command palette UI exists
- No per-command "visible to players" field in DB

---

## Full Specification

### DB Change

Add `enabled_for_players` to the slash commands/mechanics table:

```sql
ALTER TABLE game_mechanics ADD COLUMN enabled_for_players INTEGER DEFAULT 0;
```

OR if commands are stored elsewhere, add the same field there.

Default: `0` (not visible to players) — must be explicitly enabled per command.

### /help Command

When player types `/help` (or presses a keyboard shortcut):
1. `GET /api/mechanics/slash-commands?player_view=true` (for normal players)
2. OR `GET /api/mechanics/slash-commands` (for admin — all commands)
3. Modal opens with categorized command list

### Command Palette Modal

**Design:**
- Searchable input at top (filter commands by name)
- Commands grouped by category: Navigation, Combat, Game, Admin (admin-only)
- Each command row shows: `/command_name`, short description, example usage
- Clicking a command inserts it into the chat input

**Example display:**
```
╔══════════════════════════════╗
║  /help — Available Commands  ║
╠══════════════════════════════╣
║ GAME                          ║
║  /mem <query>  — Search your  ║
║                  memory       ║
║  /help         — Show this    ║
║                                ║
║ COMBAT                        ║
║  [no player commands in v1]   ║
╚══════════════════════════════╝
```

### Admin Panel — Command Visibility Toggle

In admin panel "Mechanics" or "Settings" section:
- Table of all slash commands
- Toggle per row: "Visible to players: ON/OFF"
- Changes persist immediately

### Commands Visible to Players by Default (v1)

| Command | Description |
|---------|-------------|
| `/help` | Show command palette |
| `/mem <query>` | Search memory/past events |

Commands that remain admin-only by default:
- `/atak` — removed from player-facing entirely (Task 11)
- `/debug` — admin only
- `/test` — admin only
- All admin commands

---

## Edge Cases

- **Player types unknown command:** Return friendly error "Unknown command. Type /help to see available commands."
- **Admin disables a command mid-session:** Command disappears from palette on next /help invocation. If player tries it: "This command is currently unavailable."

---

## Test Plan

1. Type `/help` → verify modal opens with available commands
2. Admin command visible to admin, not visible to player
3. Admin enables a command in admin panel → verify it appears in player's /help next open
4. Click command in palette → verify it inserts into chat input
5. Type unknown `/xyz` → verify helpful error message

---

## Related Tasks
- Standalone — no hard dependencies
