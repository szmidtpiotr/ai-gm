# TASK 34 — Combat UI

## Overview

When the game enters COMBAT state, the right panel transforms into a dedicated combat view. The main narrative panel continues to show narration. The right panel shows the tactical situation: who is fighting, whose turn it is, HP bars, conditions, and round status.

Combat UI must communicate urgency without chaos. The player should always know: whose turn it is, what their HP is, and what options they have.

---

## Right Panel Layout (COMBAT state)

```
┌─────────────────────────────────┐
│  Runda 3                        │
├─────────────────────────────────┤
│  KOLEJNOŚĆ INICJATYWY           │
│  ► Gracz          [██████ ] 28HP │
│    Goblin Wartownik [████  ] 12HP │
│    Goblin Łucznik   [██    ] 4HP  │
├─────────────────────────────────┤
│  STAN GRACZA                    │
│  HP ████████████░░ 28/40        │
│  Ranny (Wound Label)            │
│  [⚠ Przerażony]                  │
├─────────────────────────────────┤
│  LOG AKCJI                      │
│  Goblin Wartownik atakuje!      │
│  Trafienie — 5 dmg              │
│  Goblin Łucznik strzela...      │
├─────────────────────────────────┤
│  [⚔ Atakuj] [🏃 Uciekaj] [🧪]    │
└─────────────────────────────────┘
```

---

## Initiative Order List

- All combatants displayed in initiative order (highest to lowest)
- Current actor (whose turn it is) has `►` indicator and highlighted row
- Dead combatants are struck through and dimmed, remain in list until round ends
- HP bars per enemy: color-coded (green → yellow → red based on % remaining)
- Player HP shown as bar + number
- Enemy HP shown as bar only (no exact number — players don't know enemy max HP)
- Enemy HP bar: green → yellow → red as they take damage

### HP Bar Colors

| % HP remaining | Color |
|---|---|
| > 60% | Green `#4a7c59` |
| 30–60% | Yellow `#b8860b` |
| < 30% | Red `#8b2020` |
| 0% (dead) | Grey, struck through |

---

## Round Counter

Simple integer displayed at top of combat panel. Increments after all combatants have acted.

```
Runda {n}
```

---

## Fear and Condition Indicators

Active conditions on the player are shown as small icon badges below the HP bar:

| Condition | Icon | Color |
|---|---|---|
| Przerażony | ⚠ | Dark red |
| Spanikowany | ⚠⚠ | Red, pulsing |
| Rana Ręki | 🩸 | Red |
| Rana Nogi | 🩸 | Red |
| Ogłuszony | 💫 | Yellow |
| Zatruty | ☠ | Green |

Condition badges show remaining duration on hover (e.g., "2 rundy").

---

## Critical Hit Notification

When a critical hit occurs (player or enemy), a brief flash notification appears centered over the combat panel:

```
╔══════════════════╗
║  KRYTYK!         ║
║  Noga            ║
╚══════════════════╝
```

- Duration: 1500ms
- Animation: fade in (200ms) → hold (1100ms) → fade out (200ms)
- Styling: dark red border, dark background
- Hit location displayed on second line
- Appears regardless of whose crit it was — combat is violent for everyone

If the player is the one critting: positive styling (gold accent).
If the player is being critted: negative styling (red/dark).

---

## Player HP (Wound Label Color)

The player's HP display uses wound label coloring from the game system:

| Wound Label | HP % range | Color |
|---|---|---|
| Nieuszkodzony | > 75% | Normal text |
| Draśnięty | 50–75% | Yellow |
| Ranny | 25–50% | Orange |
| Ciężko Ranny | 10–25% | Red |
| Umierający | < 10% | Red, pulsing |

The wound label text is displayed below the HP bar.

---

## Action Buttons

Three buttons, always present during player's turn in combat:

```
[⚔ Atakuj]  [🏃 Uciekaj]  [🧪 Przedmiot]
```

State rules:
- Player's turn (`awaiting_player: true`): all enabled (subject to action availability)
- Enemy's turn (`awaiting_player: false`): all disabled, overlay reads "Tura wroga..."
- FLEE disabled if `location.enclosed = true`: tooltip "Zamknięte pomieszczenie"
- ITEM_USE disabled if inventory empty: tooltip "Brak przedmiotów"

"Tura wroga..." overlay: semi-transparent grey covers the button area. Text centered. No spinner — the enemy action log below already shows what's happening.

---

## Roll Popups

### Player Attack Roll

Triggered when player clicks [⚔ Atakuj].

```
┌─────────────────────────────────┐
│  Atak — Krótki Miecz            │
│  Modyfikator: STR +2, Skill +1  │
│  Suma: +3                       │
│                                 │
│  [🎲 Rzuć k20]                  │
└─────────────────────────────────┘
```

After [Rzuć k20] clicked:
- Dice animation plays (spinning d20, 800ms)
- Result number revealed with animation
- Hit/miss result displayed ("TRAFIENIE!" / "PUDŁO!")
- Popup closes after 2000ms, turn continues

### Fear Test Popup

Triggered when `FEAR_TRIGGER` action occurs.

```
┌─────────────────────────────────┐
│  ⚠ TEST STRACHU                 │
│  Coś przeszywa cię na wskroś.   │
│                                 │
│  DC: 12  |  WIS: -1  |  +0     │
│                                 │
│  [💀 Rzuć k20]                  │
└─────────────────────────────────┘
```

Styling differences from attack roll popup:
- Darker background (near-black)
- Red/dark red accent colors
- "Horror" typography feel — slightly different font weight
- Brief atmospheric sentence from the narration above the roll button
- On fail: animate in the condition badge ("Przerażony" appears with red flash)

### Death Save Popup

Triggered when player HP reaches 0 (Umierający state) and must make death saves.

```
┌─────────────────────────────────┐
│  ☠ WALKA O ŻYCIE                │
│                                 │
│  DC: {current_dc}               │
│  CON: {con_modifier}            │
│                                 │
│  Sukces: {successes}/3          │
│  Porażka: {failures}/3          │
│                                 │
│  [❤ Rzuć k20 — walcz o życie]  │
└─────────────────────────────────┘
```

Most dramatic styling:
- Near-black background
- Deep red accents
- Success counter increments green, failure counter increments red
- On 3 failures: screen transition to death screen (TASK_38)
- On 3 successes: player stabilizes, combat continues with 1 HP

---

## Enemy Action Log

Below the initiative list, a brief text feed shows enemy actions as they resolve:

```
Goblin Wartownik atakuje! (trafienie, 5 dmg)
Goblin Łucznik strzela... (pudło)
```

Log format: `{enemy_name} {action_description} ({outcome})`

This is separate from the main narrative panel. It is mechanical, not atmospheric. The atmospheric narration is in the main panel (from TASK_27).

After a full round resolves, each enemy action log entry appears sequentially with ~800ms delay between entries. Player action results appear immediately when submitted.

Log shows last 5 entries. Older entries scroll up and fade out.

---

## Exiting Combat UI

When `game_state` returns to `NARRATIVE`, the right panel transitions back to the character sheet view (TASK_35). Transition: cross-fade 400ms. The combat panel does not persist after combat ends.

---

## Testing Requirements

1. **Panel transformation**: Verify right panel switches to combat layout when `game_state = "COMBAT"` is received.
2. **Initiative order**: Verify combatants appear in correct order, current actor has `►` indicator.
3. **HP bar colors**: Verify color changes at the correct thresholds (test with 70%, 40%, 20% HP values).
4. **Crit flash**: Trigger a crit, verify the notification appears for ~1500ms then disappears.
5. **Fear popup styling**: Verify fear popup has distinct styling from attack roll popup (darker, different accent color).
6. **Death save counters**: Simulate 2 successes, 1 failure. Verify counters show correctly.
7. **Enemy turn lockout**: Set `awaiting_player: false`. Verify all buttons disabled and overlay appears.
8. **Action log sequencing**: Verify log entries appear with ~800ms delay between each.
9. **Return to character sheet**: Set `game_state = "NARRATIVE"`. Verify right panel transitions back.
