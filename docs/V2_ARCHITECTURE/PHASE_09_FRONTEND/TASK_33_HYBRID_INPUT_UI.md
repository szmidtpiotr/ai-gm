# TASK 33 — Hybrid Input UI

## Overview

Player input combines two modalities: context-sensitive action buttons (shortcuts for common actions in the current state) and a free-text input field (always present, always primary). Buttons are convenience — they bypass the Intent Parser and go directly to the World State Machine. Free text is expression — it goes through full Intent Parsing.

The design principle: **free text is the primary interface**. Buttons are subtle helpers. They should not feel like a menu system.

---

## Visual Hierarchy

```
[  Free text input — "Co robisz?"                    ] [Wyślij]
[ Porozmawiaj z Heinzem ] [ Przeszukaj salę ] [ Odpocznij ]
```

The free text input sits **above** the buttons and is visually dominant. Buttons are smaller, muted in color. They do not compete with the input field for attention.

---

## Context Button Generation

After every turn, the backend includes a `suggested_actions[]` array in the turn response. The frontend renders these as clickable buttons. Buttons are regenerated every turn.

### API Shape

```python
class SuggestedAction:
    label:   str          # Polish display text
    action:  str          # structured action string sent on click
    enabled: bool         # False = greyed out but visible
    reason:  str | None   # tooltip text when disabled, e.g. "Nie możesz tu odpoczywać"
    icon:    str | None   # optional emoji/icon prefix
```

```json
"suggested_actions": [
    {
        "label": "Porozmawiaj z Heinzem",
        "action": "DIALOGUE:heinz_karczmarz",
        "enabled": true
    },
    {
        "label": "Przeszukaj salę",
        "action": "SEARCH",
        "enabled": true
    },
    {
        "label": "Odpocznij",
        "action": "REST:long",
        "enabled": false,
        "reason": "Heinz twierdzi, że pokoje są zajęte"
    }
]
```

### State-Based Examples

**NARRATIVE state, tavern, NPC Heinz present:**
```json
[
    {"label": "Porozmawiaj z Heinzem", "action": "DIALOGUE:heinz_karczmarz", "enabled": true},
    {"label": "Przeszukaj salę", "action": "SEARCH", "enabled": true},
    {"label": "Odpocznij", "action": "REST:long", "enabled": false, "reason": "Lokacja nie jest bezpieczna do odpoczynku"}
]
```

**COMBAT state:**
```json
[
    {"label": "⚔ Atakuj", "action": "ATTACK", "enabled": true, "icon": "⚔"},
    {"label": "🏃 Uciekaj", "action": "FLEE", "enabled": false, "reason": "Zamknięte pomieszczenie — ucieczka niemożliwa"},
    {"label": "🧪 Użyj przedmiotu", "action": "ITEM_USE", "enabled": true}
]
```

**MOVEMENT available:**
```json
[
    {"label": "→ Idź do Piwnicy", "action": "MOVEMENT:piwnica", "enabled": true},
    {"label": "← Wróć do Karczmy", "action": "MOVEMENT:karczma", "enabled": true}
]
```

---

## Button Click Behavior

1. Player clicks a button
2. Frontend sends `action` string directly to `POST /api/campaigns/{id}/turns` with:
   ```json
   {"input": "DIALOGUE:heinz_karczmarz", "input_type": "structured"}
   ```
3. `input_type: "structured"` signals the backend to bypass Intent Parsing
4. World State Machine receives the action directly
5. Normal turn flow continues (narrator, state update, response)

Free text path:
```json
{"input": "Pytam Heinza, czy widział ostatnio kupca", "input_type": "free_text"}
```
This goes through full Intent Parser → World State Machine → narrator pipeline.

---

## Button States

### Greyed Out (disabled)

Disabled buttons are visible but not clickable. They always display a tooltip on hover explaining why. Examples:

- `REST` button when `location.safe_for_rest = false`: tooltip "Nie możesz tu bezpiecznie odpocząć"
- `FLEE` button when `location.enclosed = true`: tooltip "Brak drogi ucieczki"
- `ITEM_USE` button when inventory is empty: tooltip "Nie masz żadnych przedmiotów"
- `DIALOGUE:npc_id` button when NPC has left the scene: tooltip "[NPC name] już tu nie ma"

Disabled buttons use 40% opacity. No click handler attached. Cursor is `not-allowed`.

### Active / Enabled

Normal clickable state. Subtle hover effect (slight background highlight). No animation — they should not draw the eye away from the text input.

---

## Combat Buttons — Persistent State

During `COMBAT` state, the combat action buttons (Attack, Flee, Item) persist in the input area regardless of what `suggested_actions[]` returns. They are rendered from a separate `combat_actions` component, not from the `suggested_actions[]` array.

During the enemy's turn (`awaiting_player: false`), all combat buttons are disabled with a "Tura wroga..." indicator overlay. Player cannot submit free text during enemy turn either — the input field is also disabled.

During the player's turn (`awaiting_player: true`), buttons re-enable and input field unlocks.

---

## Suggested Actions API — Implementation Notes

Backend generates `suggested_actions[]` based on:

1. Current `game_state` (NARRATIVE / COMBAT / DIALOGUE)
2. Current location's `available_exits`, `safe_for_rest`, `enclosed` flags
3. NPCs present in the current location who are alive and have dialogue trees
4. Player inventory (ITEM_USE enabled only if inventory non-empty)
5. Campaign plan: if the next beat requires a specific action, that action is always surfaced as a button

The action generation logic lives in `WorldStateMachine.get_suggested_actions()`. It runs after state resolution, before the turn response is assembled.

---

## Free Text Input — Always Available

The free text input is never fully hidden. During combat, it accepts text but submits as a free-form action that goes through Intent Parser first (the player might type "I want to use the healing potion" rather than clicking the button).

Placeholder text changes by state:
- NARRATIVE: "Co robisz? Możesz pisać swobodnie..."
- COMBAT: "Twoja akcja... (lub użyj przycisków powyżej)"
- DIALOGUE: "Co mówisz?"
- DEAD/ENDED: input disabled, "Kampania zakończona"

Max input length: 500 characters. Show character counter when over 400.

---

## Testing Requirements

1. **Button render**: After a turn in a tavern with NPC present, verify buttons appear with correct labels and action strings.
2. **Disabled state**: Verify disabled button has `disabled` attribute, tooltip text is present, cursor is `not-allowed`.
3. **Button click bypass**: Click a button, verify `input_type: "structured"` in the request payload.
4. **Free text path**: Submit free text, verify `input_type: "free_text"` in the request payload.
5. **Combat persistent buttons**: Enter COMBAT state, verify attack/flee/item buttons are present and independent of `suggested_actions[]`.
6. **Enemy turn lockout**: Simulate enemy turn (`awaiting_player: false`), verify all buttons disabled and input field disabled.
7. **Placeholder text**: Verify placeholder changes correctly between NARRATIVE and COMBAT states.
