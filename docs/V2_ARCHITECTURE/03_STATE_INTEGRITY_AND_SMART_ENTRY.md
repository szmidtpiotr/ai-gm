# AI-GM V2 — State Integrity, Extensible States & Smart Entry Pattern

> Two related systems:
> 1. How game states work and how new ones are created (DB-driven, no code changes)
> 2. How admin creates any DB record via AI conversation (universal Smart Entry pattern)

---

## Part 1 — Game State System

### Core Principle

Game state is stored in `game_sessions.session_flags.game_state` as a string key (e.g. `"NARRATIVE"`, `"COMBAT"`). Every possible state is defined in the `game_state_definitions` table. The World State Machine reads this table at runtime — **adding a new state requires only a DB record, not a code change.**

### `game_state_definitions` Table

```sql
CREATE TABLE game_state_definitions (
    id                INTEGER PRIMARY KEY,
    key               TEXT UNIQUE NOT NULL,  -- "NEGOTIATION", "CHASE", "PUZZLE"
    label             TEXT NOT NULL,         -- human-readable, shown in admin/UI
    description       TEXT,

    -- What player can/can't do while in this state
    valid_actions     TEXT DEFAULT '[]',     -- JSON array of ACTION_TYPE strings
                                             -- empty = ALL actions allowed
    blocked_actions   TEXT DEFAULT '[]',     -- JSON array — overrides valid_actions

    -- Transitions
    entry_trigger     TEXT DEFAULT '{}',     -- JSON: what event/action causes entry
    exit_to           TEXT DEFAULT 'NARRATIVE', -- default state on clean exit

    -- Frontend
    ui_buttons        TEXT DEFAULT '[]',     -- JSON: context buttons to render
    ui_indicator      TEXT,                  -- badge shown in UI: "⚔ Walka"

    -- Time limit
    max_turns         INTEGER DEFAULT NULL,  -- NULL = no limit
    on_timeout_action TEXT DEFAULT NULL,     -- action string when time expires

    -- System hooks (run by Mechanic Resolver, not LLM)
    on_enter_hook     TEXT DEFAULT NULL,     -- e.g. "roll_initiative"
    on_exit_hook      TEXT DEFAULT NULL,     -- e.g. "grant_xp:negotiation_success"

    is_active         INTEGER DEFAULT 1
);
```

### Built-In States (Seeded on Install)

| Key | Label | Entry | Exit | Notes |
|-----|-------|-------|------|-------|
| `NARRATIVE` | Narracja | Default / any clean exit | — | Base state |
| `COMBAT` | Walka | `[COMBAT_START]` tag | All enemies dead / flee | Core state |
| `SKILL_TEST_PENDING` | Test umiejętności | `[SKILL_TEST]` tag | Player rolls | Waiting for d20 |
| `FEAR_TEST_PENDING` | Test strachu | Fear-causing entity encountered | Player rolls WIS | WFRP Fear mechanic |
| `DEATH_SAVE_PENDING` | Rzut na śmierć | Player HP ≤ 0 | Player rolls / all enemies dead | Escalating DC |
| `SHOPPING` | Handel | DIALOGUE with merchant NPC | Exit shop | Shop panel open |
| `RESTING` | Odpoczynek | REST action in safe location | Rest complete | Short/long rest |

### Example Extended States

**NEGOTIATION:**
```json
{
  "key": "NEGOTIATION",
  "label": "Negocjacje",
  "valid_actions": ["DIALOGUE", "SKILL_ATTEMPT", "ATTACK", "FLEE"],
  "blocked_actions": ["REST", "SHOP", "ITEM_USE"],
  "entry_trigger": {"action": "DIALOGUE", "target_condition": "npc.is_hostile == true"},
  "exit_to": "NARRATIVE",
  "ui_buttons": [
    {"label": "🗣 Przekonaj",   "action": "SKILL_ATTEMPT:persuasion"},
    {"label": "😨 Zastrasz",    "action": "SKILL_ATTEMPT:intimidation"},
    {"label": "💰 Zaproponuj",  "action": "DIALOGUE:topic=offer"},
    {"label": "🚪 Porzuć",      "action": "FLEE"}
  ],
  "ui_indicator": "🗣 Negocjacje",
  "max_turns": 6,
  "on_timeout_action": "exit_negotiation_failed"
}
```

**CHASE:**
```json
{
  "key": "CHASE",
  "label": "Pościg",
  "valid_actions": ["FLEE", "SKILL_ATTEMPT", "ITEM_USE"],
  "blocked_actions": ["REST", "SHOP", "DIALOGUE", "EXAMINE"],
  "entry_trigger": {"event": "chase_initiated"},
  "exit_to": "NARRATIVE",
  "ui_buttons": [
    {"label": "🏃 Biegnij",    "action": "FLEE"},
    {"label": "🙈 Ukryj się",  "action": "SKILL_ATTEMPT:stealth"},
    {"label": "🧪 Użyj",       "action": "ITEM_USE"}
  ],
  "ui_indicator": "🏃 Pościg",
  "max_turns": 5,
  "on_timeout_action": "exit_to_COMBAT:caught",
  "on_enter_hook": "roll_initiative_chase"
}
```

**DRUNK:**
```json
{
  "key": "DRUNK",
  "label": "Pijany",
  "valid_actions": [],
  "blocked_actions": [],
  "entry_trigger": {"event": "item_use:alcohol_heavy"},
  "exit_to": "NARRATIVE",
  "ui_indicator": "🍺 Pijany",
  "on_enter_hook": "apply_condition:drunk:dex-2:wis-1",
  "on_exit_hook": "remove_condition:drunk"
}
```

### How World State Machine Uses the Table

```python
def validate_action(action_type: str, character_id: int) -> tuple[bool, str]:
    state_key = get_session_state(character_id)
    state_def = db.get_one("game_state_definitions", key=state_key)

    # Explicit block wins over everything
    if action_type in json.loads(state_def.blocked_actions):
        return False, f"Nie możesz tego teraz ({state_def.label})."

    valid = json.loads(state_def.valid_actions)
    if valid and action_type not in valid:
        return False, f"Działanie niedostępne w stanie: {state_def.label}."

    return True, ""


def transition_to_state(character_id: int, new_state_key: str, context: dict = {}):
    state_def = db.get_one("game_state_definitions", key=new_state_key)

    if state_def.on_enter_hook:
        mechanic_resolver.run_hook(state_def.on_enter_hook, character_id, context)

    db.update("game_sessions",
        where={"character_id": character_id},
        values={"session_flags": patch_flags(character_id, {"game_state": new_state_key})}
    )

    return {
        "new_state": new_state_key,
        "ui_indicator": state_def.ui_indicator,
        "ui_buttons": json.loads(state_def.ui_buttons),
        "max_turns": state_def.max_turns
    }
```

### Turn Timeout Tracking

When `max_turns` is set, track in `session_flags`:
```json
{
  "game_state": "NEGOTIATION",
  "state_entered_turn": 14,
  "state_max_turns": 6
}
```

After each turn in this state:
```python
if current_turn - flags["state_entered_turn"] >= flags["state_max_turns"]:
    run_timeout_action(state_def.on_timeout_action)
    transition_to_state(character_id, state_def.exit_to)
```

---

## Part 2 — Smart Entry Pattern (Universal Admin AI Agent)

### The Problem With Forms

Admin panel forms require the admin to:
- Know every field name and what it means
- Understand all valid values
- Fill in 15+ fields for a complex enemy or state
- Risk producing invalid JSON manually

### The Solution: Conversational Record Creation

Every admin table gets an **AI Assistant** button alongside the classic form. Admin describes what they want; the agent asks targeted questions and builds a valid DB record.

### Universal Endpoint

```
POST /api/admin/smart-entry/{table_name}
Body: { "message": "...", "session_id": "..." }
Response: { "reply": "...", "draft": {...} | null, "ready_to_save": bool }
```

One endpoint, works for any table. Behavior is driven by **schema descriptors** — one JSON config per table.

### Schema Descriptor Structure

```json
{
  "table": "game_state_definitions",
  "friendly_name": "Stan gry",
  "agent_opening": "Opisz nowy stan gry — co gracz może w nim robić i co go wywołuje?",
  "required_fields": ["key", "label", "valid_actions", "entry_trigger"],
  "optional_fields": ["blocked_actions", "max_turns", "on_timeout_action", "ui_buttons"],
  "field_hints": {
    "key": "Krótki klucz wielkimi literami (np. NEGOTIATION, CHASE)",
    "valid_actions": "Lista z: ATTACK, FLEE, DIALOGUE, SKILL_ATTEMPT, MOVEMENT, EXAMINE, REST, SHOP, ITEM_USE",
    "max_turns": "Liczba tur lub null (brak limitu)"
  },
  "validation_rules": {
    "key": "UPPERCASE_UNDERSCORE only",
    "valid_actions": "values must be from ACTION_TYPES enum"
  },
  "questions": [
    {"field": "valid_actions",   "ask": "Jakie akcje gracz może wykonywać w tym stanie?"},
    {"field": "blocked_actions", "ask": "Czy jakieś akcje są całkowicie zablokowane?"},
    {"field": "max_turns",       "ask": "Czy jest limit tur? Ile?"},
    {"field": "ui_buttons",      "ask": "Jakie przyciski pokazać graczowi? (nazwy i akcje)"},
    {"field": "entry_trigger",   "ask": "Co wywołuje wejście w ten stan?"}
  ]
}
```

### Tables That Get Smart Entry

| Table | Admin describes... |
|---|---|
| `game_state_definitions` | A new game situation, what player can do, when it ends |
| `game_config_enemies` | An enemy's appearance, power level, abilities, how it fights |
| `npc_definitions` | An NPC's personality, secrets, role in the world |
| `game_locations` | A place's atmosphere, who lives there, what can happen |
| `game_config_items` | An item's purpose, who uses it, what it does mechanically |
| `enemy_behavior_profiles` | How an enemy decides what to do each turn |
| `skill_counters` | Which skill opposes which in tests |
| `campaign_ideas` | A scenario concept (already in Ideas Workshop — same pattern) |

### Example: Admin Creates New Enemy

```
Admin: "Chcę dodać zarażonego chłopa — ofiarę plagi która atakuje z 
        powodu gorączki. Słaby, ale ich jest dużo."

Agent: "Kilka pytań:
  1. Jak silny powinien być? (słaby/standardowy)
  2. Czy powinien wywoływać strach u gracza?
  3. Czy ma jakąś specjalną zdolność — np. zarażenie?"

Admin: "Słaby. Nie wywołuje strachu — to tylko chory człowiek.
        Tak, małe szanse na zarażenie przy uderzeniu."

Agent: "Gotowy szkic:
  Klucz: plague_peasant
  Tier: weak | HP: 6 | AC: 8
  ATK: +1 | DMG: 1d4 (gołe ręce)
  Zachowanie: atakuje najbliższego, ucieka przy < 25% HP
  Specjalne: Zaraza (15% szans przy trafieniu → CON save DC 11)
  Loot: brak / złom
  Strach: NIE
  [Podgląd JSON]
  Zapisać?"

Admin: "Zmień HP na 8"

Agent: "Zaktualizowano HP: 8. Zapisać?"

Admin: "Tak" → saved to game_config_enemies + enemy_behavior_profiles
```

### Adding a New Table to Smart Entry

1. Create the DB table (migration)
2. Write a `schema_descriptor` JSON (add to `admin_schema_descriptors` table or config file)
3. Smart Entry agent automatically works for that table — no new code

This means the admin panel is **self-extending**: every new table admin creates can immediately have AI-assisted record creation.

---

## How States + Smart Entry Work Together

```
Admin wants NEGOTIATION state:
  1. Opens "Stany Gry" in admin panel
  2. Clicks [🤖 Asystent AI]
  3. Describes the state in plain Polish
  4. Agent fills in all fields via conversation
  5. Saves to game_state_definitions

Next player session:
  1. Player initiates DIALOGUE with hostile NPC
  2. World State Machine reads game_state_definitions table
  3. Finds NEGOTIATION entry_trigger matches → transitions to NEGOTIATION
  4. Returns ui_buttons from DB to frontend
  5. Player sees [Przekonaj] [Zastrasz] [Zaproponuj] [Porzuć] buttons
  6. 6-turn countdown begins
  7. If timeout → NPC leaves, back to NARRATIVE
```

Zero code changes. Admin defined the whole behavior through conversation.

---

## State Integrity: What the System Enforces

See also: `02_DATA_FLOW_EXAMPLE.md` for full traces.

| Concern | How enforced |
|---|---|
| Player can't do blocked actions | WSM reads `blocked_actions` from DB, rejects |
| Player can't stay in timed state forever | Turn counter in session_flags vs max_turns |
| Player can't "declare" a different state | Only system transitions update session_flags.game_state |
| LLM can't change game state directly | LLM emits tags (e.g. `[COMBAT_START]`), WSM decides the actual transition |
| New states don't break old code | WSM reads all rules from DB — no hardcoded state logic except core hooks |
| Invalid state key in DB | WSM falls back to NARRATIVE with admin alert |

---

## Implementation Notes

- `game_state_definitions` seeds go in `backend/app/migrations_admin.py`
- Built-in states (`NARRATIVE`, `COMBAT`, `SKILL_TEST_PENDING`, `FEAR_TEST_PENDING`, `DEATH_SAVE_PENDING`, `SHOPPING`, `RESTING`) seeded on first migration
- `on_enter_hook` / `on_exit_hook` values are string keys that map to functions in `mechanic_resolver.py`
- Schema descriptors stored in: `backend/app/admin_schema_descriptors/` as JSON files (one per table), loaded at startup
- Smart Entry endpoint: `POST /api/admin/smart-entry/{table_name}` — single handler, reads descriptor for table
- Session state for Smart Entry conversations: lightweight in-memory dict keyed by `admin_user_id + table_name` (cleared after save or 30min inactivity)
