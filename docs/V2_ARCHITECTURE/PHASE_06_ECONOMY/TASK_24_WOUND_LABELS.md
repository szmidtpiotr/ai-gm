# TASK 24 — Wound Labels

**Phase:** 06 — Economy  
**Status:** ✅ Done — commit `5fb1b9a` (2026-05-13)  
**Related tasks:** TASK 11 (turn pipeline / context injector), TASK 23 (healing system)

---

## Overview

Wound labels replace the raw HP number with narrative language, reinforcing the dark fantasy tone. A character at 18/24 HP is not "75% health" — they are "Ranny". The system maintains numeric precision under the hood while the frontend and narrator communicate in thresholds.

---

## HP Threshold Table

| HP % | Label (Polish) | HP Bar Color | Flavor Cue |
|------|---------------|--------------|------------|
| 76–100% | *(no label)* | Green `#4caf50` | Nothing displayed |
| 51–75% | Ranny | Yellow `#ffc107` | Shallow wounds, minor pain |
| 26–50% | Ciężko Ranny | Orange `#ff9800` | Significant blood loss, impaired movement |
| 11–25% | Poważnie Ranny | Red `#f44336` | Barely standing, desperate |
| 1–10% | Na Skraju Śmierci | Dark Red `#7f0000` | One blow from death |

At exactly 0 HP: trigger death/downed state (see combat rules, TASK 05). Wound label is not displayed at 0 HP — death state has its own UI.

---

## Implementation

### `get_wound_label(current_hp: int, max_hp: int) -> dict`

Helper function in `game_engine.py`:

```python
def get_wound_label(current_hp: int, max_hp: int) -> dict:
    """
    Returns wound status dict for context injection and frontend display.
    Returns None if HP is in Unharmed range (>= 76%).
    """
    if max_hp <= 0:
        return None
    
    pct = (current_hp / max_hp) * 100
    
    if pct > 75:
        return None  # Unharmed — no label
    elif pct > 50:
        return {
            "label": "Ranny",
            "pct_bucket": "51-75",
            "bar_color": "#ffc107",
            "flavor": "Ranny"
        }
    elif pct > 25:
        return {
            "label": "Ciężko Ranny",
            "pct_bucket": "26-50",
            "bar_color": "#ff9800",
            "flavor": "Ciężko Ranny"
        }
    elif pct > 10:
        return {
            "label": "Poważnie Ranny",
            "pct_bucket": "11-25",
            "bar_color": "#f44336",
            "flavor": "Poważnie Ranny"
        }
    else:
        return {
            "label": "Na Skraju Śmierci",
            "pct_bucket": "1-10",
            "bar_color": "#7f0000",
            "flavor": "Na Skraju Śmierci"
        }
```

### Context Injection

Called in the Context Injector (TASK 11 Step 7) when building the narrator prompt. If `get_wound_label()` returns a non-None value:

```
[CHARACTER CONDITION]
Wound Status: Ciężko Ranny (HP 10/24)
Narrator note: Mention the character's wounds approximately every 3-4 turns — not every turn.
Last wound mention: turn 14 (current: turn 17)
```

The `last_wound_mention_turn` is tracked in a session state variable (not DB — ephemeral per session). When `current_turn - last_wound_mention_turn >= 3`, the narrator is instructed to weave wound status into the narration. When < 3 turns since last mention, the wound note is omitted from the injected context.

This prevents the narrator from opening every paragraph with *"Twoje rany krwawią..."* — a pattern that quickly becomes tedious.

---

## Frontend UI

### HP Bar

The HP bar is a horizontal progress bar in the character panel (right sidebar).

```
HP  ████████░░░░  10 / 24
    [bar color changes with wound level]
Ciężko Ranny
```

- Bar fill percentage = `current_hp / max_hp`
- Bar color transitions: CSS `transition: background-color 0.5s ease`
- No animation jank — smooth color shift as HP changes
- Polish label below bar: appears at < 76% HP, disappears when healed above threshold

### Color Transitions

```css
.hp-bar-fill {
    transition: width 0.4s ease, background-color 0.5s ease;
}

.hp-bar-fill.unharmed  { background-color: #4caf50; }
.hp-bar-fill.hurt      { background-color: #ffc107; }
.hp-bar-fill.wounded   { background-color: #ff9800; }
.hp-bar-fill.severe    { background-color: #f44336; }
.hp-bar-fill.near-death { background-color: #7f0000; }
```

CSS class is set by the frontend based on the `wound_status.pct_bucket` field in the API response.

### Response Payload

The wound label is included in every turn response (TASK 11 Step 9):

```json
{
  "state": {
    "character_hp": 10,
    "character_max_hp": 24,
    "wound_label": "Ciężko Ranny",
    "wound_color": "#ff9800",
    "wound_pct_bucket": "26-50"
  }
}
```

If `wound_label` is null: frontend shows green bar, no label below it.

---

## Future Option B (Not V1 — Flag for V2)

At 50% HP (transitions to Ciężko Ranny) and at 25% HP (transitions to Poważnie Ranny), apply stat penalties:

- At 50% HP: `-1 DEX modifier` (movement impaired, reflexes dulled by pain)
- At 25% HP: `-1 STR modifier` (blood loss saps strength)

These modifiers would affect attack rolls, skill checks, and initiative. They are **not implemented in v1**. Leave the following comment in `get_wound_label()`:

```python
# FUTURE v2: consider applying DEX penalty at 50% HP and STR penalty at 25% HP
# See TASK_24_WOUND_LABELS.md Option B
```

Do not mention these penalties in any user-facing text in v1.
