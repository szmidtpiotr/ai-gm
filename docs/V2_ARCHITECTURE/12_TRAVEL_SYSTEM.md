# AI-GM V2 — Travel System

> Covers: macro-location travel, in-game time clock, random encounters, fast travel, rest on the road.
>
> **2026-05-18 status (post-audit):** Zegar gry (`ingame_hours`) **istnieje w bazie i narrator go czyta**, ale **nikt go nie zwiększa** — startuje o 9:00 i stoi. Stage 2A w ROADMAP.md (sub-itemy T1–T5) odblokowuje zegar:
>
> - **T1** `advance_clock(campaign_id, hours, reason)` — funkcja zwiększająca `ingame_hours` + audit log
> - **T2** Travel hook — przy każdym wpisie nowego hex'a/lokacji wywołać `advance_clock(travel_hours)`
> - **T3** Krótki odpoczynek hook — `advance_clock(1, "short_rest")`
> - **T4** Długi odpoczynek hook — `advance_clock(8, "long_rest")`
> - **T5** Nagłówek UI — pokazać "Dzień N, HH:MM Pora"
>
> Patrz: `DECISIONS_2026_05_18.md` [D13, D16].

---

## Overview

Moving between macro-locations (towns, dungeons, forests) takes in-game time and carries encounter risk. The system tracks a lightweight hour clock so the GM narrator always knows the time of day. Encounter chance is admin-configurable per route. Fast travel is available for known routes with a visual animation and GM narrative snippet.

---

## Decisions Made

| Decision | Answer |
|----------|--------|
| Travel experience | Narrative + random encounter based on danger_level |
| In-game time | Lightweight hour clock (`ingame_hours` in session) |
| Encounter timing | Pre-rolled, animation interrupts at 50% (mid-journey feel) |
| Fast travel | Available for known routes + world map animation + GM snippet |
| Fast travel card | GM narrates 1-2 sentences + random game tip |
| Rest on road | Yes — costs 1h, only on low/medium danger routes |
| Day/night effect | Narrative only in V2. Mechanical effects (stealth bonus, NPC hours) = TODO later |
| Encounter rates | Admin-configurable per route (`encounter_chance` column on `location_connections`) |

---

## In-Game Time Clock

### Storage

```sql
-- Add to game_sessions
ALTER TABLE game_sessions ADD COLUMN ingame_hours INTEGER NOT NULL DEFAULT 9;
-- Campaigns start at 09:00 (morning — hero is setting off for the day)
```

`ingame_hours` = total hours elapsed since campaign start. Never resets.

### Time of Day Calculation

```python
def get_time_period(ingame_hours: int) -> dict:
    hour = ingame_hours % 24
    if 6 <= hour < 12:
        return {"period": "morning",   "label": "Rano",      "hour": hour}
    elif 12 <= hour < 18:
        return {"period": "afternoon", "label": "Popołudnie","hour": hour}
    elif 18 <= hour < 22:
        return {"period": "evening",   "label": "Wieczór",   "hour": hour}
    else:
        return {"period": "night",     "label": "Noc",       "hour": hour}

# Example: ingame_hours = 33 → hour = 9 → morning → "09:00, Rano"
# Example: ingame_hours = 46 → hour = 22 → night → "22:00, Noc"
```

### When Hours Advance

| Event | Hours added |
|-------|------------|
| Travel between macro locations | `connection.travel_hours` |
| Short rest | 1 hour |
| Long rest | 8 hours |
| Rest on the road (during travel) | 1 hour extra |
| Combat | Does not advance time |
| Narrative turns | Does not advance time (conversations are fast) |

### Context Injection

Every turn, the GM narrator receives:

```
=== CZAS ===
Godzina: 14:30 | Popołudnie
Dzień kampanii: 3
============
```

This allows the GM to naturally reference time of day in narration without ever deciding it.

### Day/Night — V2 Narrative Only

In V2: time of day is flavour only. GM uses it for atmosphere ("ulice są puste o tej porze nocy").

**TODO (post-V2):**
- Night travel: +10% encounter chance on all routes
- Night in towns: merchants unavailable 22:00–08:00
- Night stealth: +1 to Stealth rolls (darkness helps)
- Dawn events: some NPCs only appear in morning

---

## Travel Flow

### Full Journey (first visit to a route, or player chooses full travel)

```
1. Player action:
   Map click OR free text "I travel to Thornwood Forest"
   → Intent Parser: [ACTION:MOVEMENT:destination=thornwood_forest]

2. WSM validates:
   - location_connections has edge from current → thornwood ✓
   - no active combat ✓
   - no BREAK condition (forced to flee, can't travel) ✓
   - connection.is_active = 1 ✓
   - connection.requires_item_key? → check inventory

3. Encounter pre-roll (server-side):
   has_encounter = random() < connection.encounter_chance
   if has_encounter:
     encounter_enemies = pick_enemies(connection, destination)

4. In-game time advances:
   session.ingame_hours += connection.travel_hours
   if rest_on_road: session.ingame_hours += 1

5. Travel card animates (frontend):
   - Hero icon moves along path on world map
   - If encounter: animation PAUSES at 50% of route
     → "Coś się porusza w krzakach..."
     → [COMBAT_START: encounter_enemies]
   - If no encounter: animation completes to destination

6. GM generates travel narrative (LLM call):
   Input: from, to, travel_hours, time_of_day, danger_level, encounter_happened
   Output: 1-2 sentences
   E.g.: "Droga przez las była spokojna, choć w koronach drzew słyszałeś
          coś dużego."

7. On arrival (if no encounter, or after combat):
   - current_location_id → thornwood_forest.id
   - Add to character.visited_location_keys
   - First visit: +15 XP (exploration)
   - Loot expiry check: different macro? → expire partial loots
   - Dungeon cooldown: hours advanced → re-check availability
```

### Fast Travel (known route, player opts to skip)

Available when route is in `character.visited_location_keys` path. Player sees option on world map:

```
[Full journey]  [Fast travel (10% encounter)]
```

Fast travel still:
- Advances in-game time normally
- Rolls for encounter (flat 10% regardless of danger_level)
- Shows travel animation card with GM snippet + game tip

---

## Encounter System

### Encounter Chance

`encounter_chance` stored directly on `location_connections` (admin-editable). No lookup table — admin sets exact probability per route.

```sql
ALTER TABLE location_connections ADD COLUMN encounter_chance REAL NOT NULL DEFAULT 0.1;
```

**Suggested starting values when admin creates a route:**

| `danger_level` | Suggested default `encounter_chance` |
|---|---|
| none | 0.00 |
| low | 0.10 |
| medium | 0.25 |
| high | 0.50 |
| extreme | 0.80 |

Admin can override freely. A "safe trade road" might be `danger_level=low` but `encounter_chance=0.02`. A notorious pass: `danger_level=high` and `encounter_chance=0.70`.

**Admin panel:** `location_connections` gets an editable `encounter_chance` field shown as a percentage slider (0–100%).

### Enemy Selection for Encounters

When an encounter triggers, enemies are pulled from:
1. `location_enemy_assignments` for the DESTINATION location (you're approaching their territory)
2. Filtered by `spawn_chance` (each enemy type has its own spawn chance)
3. Count: 1-3 enemies, scaled to hero level/XP

If destination has no enemy assignments: use enemies from the nearest macro location that does.

### Mid-Journey Animation Effect

Even though the encounter is pre-rolled, the animation makes it feel mid-journey:

```
[Travel animation starts]
  Hero moves along path...
  Route: ──────────────────
          ^ 50% point
  
  If encounter triggered:
    Animation freezes at 50%
    GM text appears: "Coś porusza się w zaroślach..."
    Short delay (1.5s)
    [COMBAT_START: ...]

  If no encounter:
    Animation completes to destination
    Arrival narrative shown
```

---

## Rest on the Road

Player can declare a short rest during a journey. Only allowed on routes with `danger_level ∈ {none, low, medium}`.

**How to trigger:**
- Free text: "I rest by the road" / "Odpoczywam"
- Intent Parser: [ACTION:REST:type=short:context=traveling]

**Effect:**
- +1h to in-game time (already being added by the travel time anyway, so effectively the journey takes 1h longer)
- Short rest mechanics: heal 1d6 + CON modifier HP
- Short rest counter increments (max 2 per long rest)
- Cannot rest if `danger_level ∈ {high, extreme}` — too dangerous to stop

**GM narrates:** "Siadasz na omszałym głazie przy drodze. Las szumi spokojnie..."

---

## Travel Card (Frontend)

Shown during both full journeys and fast travel. Displays while the animation plays.

```
┌────────────────────────────────────────────────────────┐
│  🗺 Podróż do Thornwood Forest              3h 25min   │
│                                                        │
│  [Graustein] ══════════════════════ [Thornwood]        │
│                    📍 ────────►                         │
│                                                        │
│  "Droga przez pola była pusta o tej porze. Gdzieś     │
│   z oddali dochodził dźwięk dzwonu kościelnego."       │
│                                                        │
│  ─────────────────────────────────────────────────    │
│  💡 Wskazówka: Trafienie krytyczne wymaga przekroczenia│
│     AC o 5 lub więcej. Nat 20 zawsze krytyk!          │
└────────────────────────────────────────────────────────┘
```

**Components:**
- Route path with animated hero icon
- GM travel narrative (1-2 sentences, Polish, LLM-generated)
- Random game tip (shuffled from `game_tips` list — see below)
- Dismisses automatically on arrival OR when encounter triggers

### Game Tips List

Static list in frontend (no DB needed). Random selection each travel. Examples:
- "Trafienie krytyczne wymaga przekroczenia AC o 5 lub więcej. Nat 20 zawsze krytyk!"
- "Rzut Strachu przed walką z Wampirem — WIS vs DC 16. Porażka = FRIGHTENED na 2 rundy."
- "Mikstura Leczenia leczy 1k8+KON podczas walki. Bandaż jest tylko na poza walką."
- "Uciekanie z walki to rzut ZRE vs najszybszego wroga. Porażka traci tylko turę."
- "Bronie Finezja używają ZRE zamiast SIŁ. Rapier i nóż do rzucania."
- "Złoto z lochu przepada jeśli zmienisz makrolokację przed zebraniem go."
- "Każda nowa lokacja odkryta po raz pierwszy daje +15 PD."
- "Uczony zaczyna walkę w strefie DYSTANS — bezpieczniej dla zaklęć."

---

## DB Changes Summary

```sql
-- In-game clock
ALTER TABLE game_sessions ADD COLUMN ingame_hours INTEGER NOT NULL DEFAULT 9;

-- Admin-configurable encounter chance per route
ALTER TABLE location_connections ADD COLUMN encounter_chance REAL NOT NULL DEFAULT 0.1;
```

---

## World State Machine Integration

Travel action validation:

```python
def validate_movement(character_id, destination_key):
    current = get_current_location(character_id)
    conn = db.get_connection(current.key, destination_key)
    
    if not conn or not conn.is_active:
        return BLOCKED, "Nie ma drogi do tego miejsca."
    
    if conn.requires_item_key:
        if not character_has_item(character_id, conn.requires_item_key):
            item = get_item(conn.requires_item_key)
            return BLOCKED, f"Potrzebujesz {item.label}, aby tędy przejść."
    
    return VALID, conn
```

After validation, `process_travel(character_id, conn)`:

```python
def process_travel(character_id, conn):
    # Advance time
    session.ingame_hours += conn.travel_hours
    
    # Encounter roll
    encounter = random() < conn.encounter_chance
    
    # Update location (even if encounter — player was heading there)
    update_location(character_id, conn.to_location_key)
    add_visited(character_id, conn.to_location_key)
    
    # Loot expiry
    expire_loot_if_macro_changed(character_id, conn)
    
    # Return result
    return {
        "new_location": conn.to_location_key,
        "ingame_hours": session.ingame_hours,
        "time_of_day": get_time_period(session.ingame_hours),
        "encounter": encounter,
        "encounter_enemies": pick_enemies(conn) if encounter else None,
        "travel_hours": conn.travel_hours
    }
```

---

## Test Checklist

- [ ] Player travels to new location → arrives, ingame_hours incremented correctly
- [ ] Time of day updates after travel (09:00 + 3h = 12:00, afternoon)
- [ ] GM narrator receives time of day in context → references it in output
- [ ] High danger route → ~50% encounter chance over 10 test trips
- [ ] Encounter triggers → animation pauses, combat starts, player at road enemies
- [ ] After combat → player continues to destination
- [ ] Fast travel: available only for previously visited routes
- [ ] Fast travel: 10% encounter chance regardless of route danger
- [ ] Travel card: GM narrative shows, game tip shown
- [ ] Rest on road: +1h, short rest heals, only on low/medium danger routes
- [ ] Rest on road blocked on high/extreme danger routes
- [ ] `encounter_chance` editable in admin panel per route
- [ ] Loot expiry: moving to different macro expires partial loot
- [ ] Dungeon cooldown: ingame_hours advance enables cooldown expiry check

---

## Related Tasks

- Task 08 (Location System) — `location_connections` table, WSM movement validation
- Task 22 (Loot System) — loot expiry on macro change
- Task 40 (World Builder) — admin sets encounter_chance per connection
- Task 43 (Player World Map) — travel animation, route display
- Task 11 (Turn Pipeline) — travel is processed through the main pipeline
