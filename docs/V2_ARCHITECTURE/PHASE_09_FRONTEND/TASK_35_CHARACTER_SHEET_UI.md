# TASK 35 — Character Sheet UI

## Overview

The character sheet lives in the right sidebar and is the player's persistent reference for their character's state. It is visible during all non-combat states. During combat, it is replaced by the Combat UI (TASK_34) and returns when combat ends.

All sections are collapsible. The default expanded state on first load shows: Header, Resources, XP, Gold, Stats. Other sections default to collapsed.

---

## Section Breakdown

### 1. Header

```
┌─────────────────────────────────┐
│  Aldric z Middenheim             │
│  Wojownik  •  Poz. 3            │
│  📍 Karczma "Pod Czarnym Krukiem" │
└─────────────────────────────────┘
```

- Character name (large)
- Archetype + Level (smaller, muted)
- Location badge with 📍 icon — updates on every MOVEMENT action
- Location name is a link/tooltip showing the full location description on hover

---

### 2. Resources

```
HP  ████████████░░░░  28 / 40
         Ranny
```

- HP bar: full width, color-coded by wound label (see TASK_34 for color table)
- Numeric display: `{current} / {max}`
- Wound label text centered below bar, colored to match bar

Mana bar (Scholar archetype only):
```
Mana  ████████░░░░  8 / 12
```

- Blue bar
- Only rendered for Scholar archetype — completely absent for all other archetypes
- No "0 / 0" placeholder — if not Scholar, no mana row at all

---

### 3. XP Progress

```
XP  ██████████░░░░░  75 / 100
[!] POZIOM WYŻEJ!
```

- XP bar in a neutral color (gold/amber tone)
- Numeric: `{current_xp} / {xp_to_next_level}`
- Level-up badge `[!]` appears when level-up is available but not yet triggered
- Level-up banner (see Level-Up Notification section below)

---

### 4. Gold

```
🪙  47 sz
```

- Coin icon + amount + currency abbreviation ("sz" = sztuki złota)
- Always visible, never collapsed
- Updates immediately when gold changes (loot, purchase, etc.)
- Negative gold not possible — floor at 0

---

### 5. Stats

```
STR  14  (+2)    DEX  10  (±0)
CON  12  (+1)    INT   8  (-1)
WIS  11  (±0)    CHA   9  (-1)
LCK  13  (+1)
```

- All 7 stats displayed in a 2-column grid (LCK on its own in last row)
- Modifier in parentheses — positive prefixed with `+`, negative with `-`, zero shown as `±0`
- Tapping/clicking a stat shows a tooltip: stat name in full + brief description of what it affects
- Stats do not change during gameplay in V2 (level-up stat increases are a later feature)

---

### 6. Skills

```
Walka Bronią          ●●●○○  [STR]
Uniki                 ●●○○○  [DEX]
Spostrzegawczość      ●○○○○  [WIS]
Wiedza Tajemna        ●●●●○  [INT]
```

- Skill name + rank dots (filled ● = ranks owned, empty ○ = unowned)
- 5 dots maximum (ranks 0–5)
- Stat tag in brackets shows which stat this skill uses for rolls
- Rank 3+ shows proficiency bonus indicator (small `+2` tag)
- Skills sorted by rank descending, then alphabetically
- Collapsed by default

---

### 7. Equipment (Slot Diagram)

```
        [Głowa]
[L Ręka] [Tors] [P Ręka]
        [Nogi]
  [Stopy]  [Ręce]
```

- Visual slot grid — 6 slots: Head, Torso, Left Hand, Right Hand, Feet, Hands
- Each slot shows: item name if equipped, "—" if empty
- Click an equipped slot: opens item detail with [Zdejmij] button
- Click an empty slot: opens inventory filtered to equippable items for that slot
- Slot highlighting: if a wound affects a specific location (e.g., Rana Ręki), that slot has a red tint
- Collapsed by default

---

### 8. Inventory

```
[ Eliksir Leczenia x2  ]  [Użyj] [Ekwipuj] [Porzuć]
[ Stara Mapa           ]  [Użyj] [Zbadaj]  [Porzuć]
[ Lina (10m)           ]  [Użyj] [Ekwipuj] [Porzuć]
```

- List view (grid available as toggle for large inventories)
- Per-item action buttons: always [Porzuć], plus contextual buttons based on item type
  - Consumable: [Użyj]
  - Equipment: [Ekwipuj]
  - Quest item: [Zbadaj] (read description), no drop allowed (drop button hidden)
  - Generic item: [Zbadaj]
- Item count shown for stackable items
- Collapsed by default
- Empty state: "Twój ekwipunek jest pusty."

---

### 9. Conditions

```
[⚠ Przerażony     2 rundy ]
[🩸 Rana Nogi     trwała  ]
```

- Active conditions only — not shown if no conditions
- Duration: rounds remaining, or "trwała" for permanent conditions
- Red/warning styling
- Clicking a condition shows a tooltip: what it does mechanically (e.g., "Przerażony: -2 do wszystkich rzutów")
- Collapsed by default; if conditions present, auto-expands on load

---

### 10. Identity

```
Wygląd:       Wysoki, blizna przez lewe oko, szare włosy
Osobowość:    Małomówny, nieufny wobec obcych, lojalny
Więzi:        Siostra w Altdorfie, winna długi lichwiarzowi
Słabości:     Panikuje w zamkniętych przestrzeniach
```

- Static text from character creation — not gameplay-modifiable in V2
- Collapsed by default
- Used as RP reference for player and as context for GM personality injection

---

## Level-Up Notification

When `level_up: true` is received in a turn response:

1. A full-width animated banner appears at the top of the character sheet:
   ```
   ★ POZIOM WYŻEJ! Jesteś teraz poziomem {new_level} ★
   ```
2. Animation: slide down from top (300ms), gold/amber color, subtle glow
3. Auto-dismisses after 5 seconds or on player click/tap
4. After dismiss: XP bar resets to new base, max HP updates immediately

If the level-up triggers a stat increase (future feature), the relevant stat value flashes briefly.

---

## Mobile Behavior

On screens narrower than 768px:

- Character sheet is not always-visible
- Accessed via a "Postać" tab at the bottom of the screen (tab bar: "Gra" | "Postać" | "Ekwipunek")
- Default tab on mobile: "Gra" (narrative + input)
- "Postać" tab shows the sheet
- "Ekwipunek" tab shows inventory + equipment slots (sections 7+8 only, for quick access)
- Combat UI on mobile replaces the right panel with the combat panel, accessible via the "Gra" tab

---

## Real-Time Updates

The character sheet updates incrementally on each turn response — only changed fields are updated, not the full sheet. Animation for changed values:

- HP decrease: red flash on the HP bar and number
- HP increase: green pulse
- Gold change: brief coin animation
- XP increase: bar animates forward to new value
- New condition: badge fades in with orange highlight
- Condition removed: badge fades out

---

## Testing Requirements

1. **Mana bar visibility**: Verify mana bar appears for Scholar archetype and is absent for Wojownik/Łotr.
2. **Wound label color**: Set HP to 20/40 (50%). Verify wound label is "Ranny" and color is orange.
3. **Level-up banner**: Trigger a turn response with `level_up: true`. Verify banner appears and auto-dismisses after 5s.
4. **Condition auto-expand**: Load character with conditions. Verify Conditions section is expanded on load.
5. **Quest item drop**: Verify quest items have no [Porzuć] button.
6. **Slot wound tint**: Apply Rana Ręki condition. Verify Right Hand slot has red tint.
7. **Mobile tabs**: At viewport width 375px, verify bottom tab bar appears and "Gra" is default active tab.
8. **HP flash**: Receive a turn with reduced HP. Verify red flash animation on HP bar.
9. **Gold update**: Receive a turn response with changed gold. Verify gold display updates immediately.
