# TASK 37 — Command Palette

**Status:** ❌ Not Started

## Overview

`/help` opens a modal showing all player-visible commands. Admins see all commands. Each command can be toggled per-visibility in the admin panel. Unknown commands return a friendly error message.

---

## `/help` Modal

Triggered by typing `/help` in the input or by a "?" help icon in the UI.

```
┌─────────────────────────────────────────────────┐
│  Dostępne komendy                         [✕]   │
│  ┌─────────────────────────────────────────┐    │
│  │ 🔍 Szukaj komend...                     │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  /mem <zapytanie>                                │
│  Przeszukaj historię kampanii                    │
│                                                  │
│  /helpme                                         │
│  Wskazówka — co zrobić dalej                     │
│                                                  │
│  /status                                         │
│  Pokaż aktualny stan postaci                     │
│                                                  │
│  /historia                                       │
│  Podsumowanie kampanii                           │
│                                                  │
│  [kliknij komendę aby wstawić do pola tekstowego]│
└─────────────────────────────────────────────────┘
```

---

## Command Structure

Each command has:

```python
class Command:
    name:                str          # "/mem"
    usage:               str          # "/mem <zapytanie>"
    description:         str          # Polish description shown in help modal
    enabled_for_players: bool         # admin-configurable toggle
    admin_only:          bool         # if true, only admins see it (regardless of toggle)
    requires_args:       bool         # if true, click-to-insert adds cursor after command name
```

---

## Command List

| Command | Usage | Description | Admin Only |
|---|---|---|---|
| `/mem` | `/mem <zapytanie>` | Przeszukaj historię kampanii | No |
| `/helpme` | `/helpme` | Wskazówka — co dalej | No |
| `/historia` | `/historia` | Podsumowanie kampanii | No |
| `/status` | `/status` | Aktualny stan postaci i lokacji | No |
| `/inv` | `/inv` | Szybki podgląd ekwipunku | No |
| `/help` | `/help` | Lista komend | No |
| `/reset` | `/reset` | Resetuj kampanię (tylko admin) | Yes |
| `/debug` | `/debug <subcommand>` | Narzędzia diagnostyczne | Yes |
| `/setstate` | `/setstate <state>` | Ustaw stan gry | Yes |
| `/additem` | `/additem <item_id>` | Dodaj przedmiot do ekwipunku | Yes |
| `/settp` | `/settp <hp>` | Ustaw HP postaci | Yes |
| `/skipbeat` | `/skipbeat` | Pomiń aktualny beat kampanii | Yes |

---

## Per-Command Admin Toggle

In the Admin Panel → Settings → Komendy:

```
┌───────────────────────────────────────┐
│  Komendy gracza                       │
│                                       │
│  /mem          [✓ Włączona]           │
│  /helpme       [✓ Włączona]           │
│  /historia     [✓ Włączona]           │
│  /status       [✓ Włączona]           │
│  /inv          [✓ Włączona]           │
└───────────────────────────────────────┘
```

Toggle stored in `command_config` table (or as a JSON blob in `admin_settings`):
```json
{
    "commands": {
        "mem": {"enabled_for_players": true},
        "helpme": {"enabled_for_players": true},
        "historia": {"enabled_for_players": true},
        "status": {"enabled_for_players": true},
        "inv": {"enabled_for_players": true}
    }
}
```

When a command is disabled for players (`enabled_for_players: false`):
- It does not appear in the player's `/help` modal
- If player types it anyway: treated as unknown command (same error as unknown)
- Admin always sees and can use it regardless of toggle

---

## Search and Filter

The `/help` modal includes a text search field. Filtering:
- Matches against command name and description
- Case-insensitive, Polish diacritics-aware
- Real-time filter as player types (no submit button)
- Empty state: "Nie znaleziono komendy '{query}'"

---

## Click to Insert

Clicking any command in the modal:
1. Closes the modal
2. Inserts the command into the text input field
3. If `requires_args: true`: cursor is placed after the command name with a space ready for arguments
4. If `requires_args: false`: full command inserted, ready to submit

Example: clicking `/mem` inserts `/mem ` (with trailing space) and focuses the input.

---

## Unknown Command Error

When a player submits input that starts with `/` but doesn't match any known command:

The response is displayed in the narrative panel as a system message (not a turn — no GM narration, no state change):

```
Nieznana komenda: /foobar
Wpisz /help aby zobaczyć dostępne komendy.
```

Styling: muted, system-message style (different from narrator prose — grey, italic, smaller font).

This applies even if the command exists but is disabled for players — it appears unknown to them.

---

## Command Processing Order

Commands are processed before the Intent Parser and World State Machine. When a turn input starts with `/`:

1. Strip leading `/`
2. Split into `name` and `args`
3. Look up in command registry
4. If not found or not enabled for this user's role: return unknown command error
5. If found: dispatch to command handler, return result as system message
6. Do NOT pass command turns through narrator or state machine

Exception: `/debug` subcommands may interact with state machine directly (admin only).

---

## Testing Requirements

1. **Modal appears**: Type `/help`, verify modal opens with command list.
2. **Player list**: Log in as player, verify admin-only commands not in list.
3. **Toggle effect**: Disable `/historia` in admin panel. Log in as player. Verify `/historia` not in `/help` modal.
4. **Disabled command typed directly**: Disable `/historia`. Player types `/historia`. Verify "unknown command" error is shown.
5. **Click to insert with args**: Click `/mem` in modal. Verify input field contains `/mem ` with cursor at end.
6. **Click to insert no args**: Click `/helpme`. Verify input field contains `/helpme` ready to submit.
7. **Search filter**: Open `/help`, type "hist". Verify only commands matching "hist" remain.
8. **Unknown command**: Submit `/xyznotacommand`. Verify error message appears in narrative panel without triggering a game turn.
