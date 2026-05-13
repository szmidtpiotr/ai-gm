# TASK 17 — Wound Narrative Labels

**Status:** ❌ Not Started
**Blocking:** None (but needs Task 01 HP formula to work correctly at scale)
**Depends on:** Task 01 (HP formula — needs correct max_hp for percentage calculation)
**Unlocks:** Nothing — aesthetic layer on top of existing HP system

---

## Overview

When a player is below full HP, the GM should describe their physical state in narration — not via a UI stat, but woven into the story text. "Aldric squares up to the goblin, blood dripping from his forearm" tells the player their character is Hurt without breaking immersion. These labels are Option C from the design review: narrative flavor only, no mechanical penalties.

Option B (actual stat penalties from wounds) is marked as a future extension.

---

## Design Context

### Why not just show HP numbers in the GM text?
"You have 5 HP remaining" is meta. It breaks the fourth wall and reminds the player they're in a game system. "You're barely standing, vision swimming" communicates the same information but keeps the player in the world. Both are valid — this game leans narrative, so immersive labels are preferred.

### Why 5 thresholds instead of just "hurt/not hurt"?
Fine gradations let the GM calibrate urgency. "Hurt" and "Near Death" should feel very different in narration. 5 levels give enough granularity to meaningfully distinguish early danger (51-75%) from desperate situations (1-10%), while not being so complex that the GM struggles to apply them.

### Why only narrative — why no mechanical effect in v1?
Mechanical wound effects (e.g., DEX -2 below 50% HP) require balancing and can feel punishing. Narrative labels are the safe first step: they communicate the same information without changing the math. Once the core systems work, Option B can be layered on top.

**Option B (future):** At 50% HP: DEX -1 (you're slowed by pain). At 25% HP: DEX -2, STR -1 (significant wound). These are post-v1.

---

## Full Specification

### Threshold Table

| HP % | Label | Example GM Flavor |
|------|-------|-------------------|
| 76-100% | Unharmed | No mention — character is fine |
| 51-75% | Hurt | "krew sączy się z cięcia na ramieniu" (blood seeping from cut) |
| 26-50% | Wounded | "kuleje, każdy krok kosztuje" (limping, every step costs) |
| 11-25% | Severely Wounded | "ledwo stoi, oddycha urywanie" (barely standing, breathing ragged) |
| 1-10% | Near Death | "jeden cios i to koniec" (one hit and it's over) |

HP % = `current_hp / max_hp * 100`

### Where Labels Appear

**Option 1 — GM narration injection (Recommended)**

On every GM narrative turn, if player HP < 76%, inject the wound label into the GM's context block:

```
=== CHARACTER STATE ===
{character_name} — WOUNDED (HP: {current}/{max})
Physical state for GM flavor: "limping, every step costs pain"
Note: Reference this state occasionally in narration, not every sentence.
=========================
```

The GM receives this context and naturally weaves it into descriptions when relevant. The label doesn't force the GM to mention it every turn — it's a reminder, not a mandate.

**Option 2 — UI indicator (Supporting)**

In the character sheet panel (right sidebar), below the HP bar:
- HP bar color changes with threshold: green → yellow → orange → red → dark red
- Small text label below bar: "Hurt" / "Wounded" / "Severely Wounded" / "Near Death"
- Label is in Polish: "Ranny" / "Poważnie Ranny" / "Bliski śmierci"
- No label when Unharmed

Both options should be implemented — GM narration injection is the core, UI label is a supportive visual.

### How Often GM Should Mention Wounds

Instruction in GM context: "Reference the character's physical state approximately once every 3-4 turns when wounded. Do not repeat the same description. Vary the phrasing."

Too frequent: breaks flow, becomes annoying
Too rare: player forgets they're injured, HP feels meaningless
Every 3-4 turns: subtle, immersive, reminds without nagging

---

## Implementation Details

### Backend — Context Injection

In `game_engine.py`, where the GM context block is assembled per turn:

```python
def get_wound_label(current_hp: int, max_hp: int) -> dict | None:
    if max_hp == 0:
        return None
    pct = (current_hp / max_hp) * 100
    if pct > 75:
        return None  # Unharmed — no label needed
    elif pct > 50:
        return {"label": "Hurt", "label_pl": "Ranny", "flavor": "krew sączy się z cięcia"}
    elif pct > 25:
        return {"label": "Wounded", "label_pl": "Ranny", "flavor": "kuleje, każdy krok kosztuje"}
    elif pct > 10:
        return {"label": "Severely Wounded", "label_pl": "Poważnie Ranny", "flavor": "ledwo stoi, oddycha urywanie"}
    else:
        return {"label": "Near Death", "label_pl": "Bliski śmierci", "flavor": "jeden cios i to koniec"}
```

Injected into system prompt context block when not None.

### Frontend — HP Bar Color

Existing HP bar in character sheet panel. Modify CSS class based on percentage:
- >75%: green (`#4CAF50`)
- 51-75%: yellow-green (`#8BC34A`)
- 26-50%: orange (`#FF9800`)
- 11-25%: red-orange (`#FF5722`)
- 1-10%: dark red (`#B71C1C`) + pulse animation

---

## Future Extension — Option B (Wound Effects)

**Not for v1 — document here for later reference:**

At 50% HP: -1 DEX modifier (pain slowing movement)
At 25% HP: -2 DEX, -1 STR (severe wound affecting combat)

Implementation would require:
- New field: `wound_modifier_dex`, `wound_modifier_str` on character runtime
- Applied to all relevant rolls (attacks, skills, flee) when HP crosses threshold
- Cleared on long rest
- GM narration adjusted to explain the mechanical effect ("your sword arm trembles")

---

## Test Plan

1. Create Warrior (11 HP), deal 4 damage → HP 7/11 = 64% → verify "Hurt" label in GM context
2. Deal 4 more damage → HP 3/11 = 27% → verify "Severely Wounded"
3. Restore to full HP → verify label disappears from GM context
4. HP bar changes color at each threshold
5. GM turn at "Wounded" → verify GM text references wound state at least once per 3 turns over 9 turns

---

## Related Tasks
- Task 01 (HP Formula) — max_hp needed for percentage
- Task 16 (Healing System) — healing changes HP, which changes label
- Task 14 (Death Saves) — at "Near Death" label, death save is imminent
