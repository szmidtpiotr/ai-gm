# AI-GM V2 — World Builder, Hero Persistence & Dungeon Runs

> Covers: visual world map editor, NPC/enemy assignment, persistent hero across campaigns, dungeon runs as standalone content, and debug system.

---

## 1. Visual World Builder (Admin Panel)

### Overview

A node-edge graph editor in the admin panel. Locations are interactive bubbles, travel routes are connecting lines. The world is built by admin and grows organically as campaigns are played — new GM-created locations appear as pending bubbles waiting for approval.

### Technology

**Cytoscape.js** — lightweight graph visualization library, works with vanilla JS.
- Drag-and-drop nodes built in
- Interactive edge creation (click-drag between nodes)
- Custom node styling per state
- No framework dependency

### DB Schema

```sql
-- Positions and display
ALTER TABLE game_locations ADD COLUMN map_x REAL DEFAULT NULL;
ALTER TABLE game_locations ADD COLUMN map_y REAL DEFAULT NULL;
ALTER TABLE game_locations ADD COLUMN map_icon TEXT DEFAULT 'town';
  -- values: town / dungeon / forest / ruin / castle / cave / road / camp

-- Player visibility
ALTER TABLE game_locations ADD COLUMN visible_before_visit INTEGER DEFAULT 0;
  -- 0 = fog of war until visited
  -- 1 = always visible on player map (famous city, known landmark)

-- Travel connections
CREATE TABLE IF NOT EXISTS location_connections (
    id                  INTEGER PRIMARY KEY,
    from_location_key   TEXT NOT NULL,
    to_location_key     TEXT NOT NULL,
    travel_hours        REAL DEFAULT 1.0,
    travel_description  TEXT,            -- "Forest road, moderately dangerous"
    is_dangerous        INTEGER DEFAULT 0,
    requires_item_key   TEXT DEFAULT NULL, -- locked gate, need a boat, etc.
    is_bidirectional    INTEGER DEFAULT 1, -- 0 = one-way only
    is_active           INTEGER DEFAULT 1
);
```

### Node Visual States

| State | Visual |
|---|---|
| `permanent` | Solid bubble, full colour |
| `pending_review` | Dashed border, faded + 🟡 NEW badge |
| Player's current location | Pulsing glow animation |
| Player visited | Small ✓ indicator |
| Undiscovered (player map) | Grey silhouette / fog |

### Node Icon Types

| Icon | Type | Colour hint |
|---|---|---|
| 🏘️ | Town | Warm brown |
| ⚔️ | Dungeon | Dark red |
| 🌲 | Forest | Green |
| 🏚️ | Ruin | Grey |
| 🏰 | Castle | Blue-grey |
| 🏕️ | Camp | Orange |
| 🗺️ | Road/Crossroads | Yellow |

### Admin World Builder UI

```
┌──────────────────┬──────────────────────────────────────────┐
│  LIBRARY         │   [+ Location]   [+ Connection]   [Save] │
│ ─────────────    │                                          │
│ NPCs             │        ╭──────────╮                      │
│  👤 Wotan        │        │ Graustein│──── 2h ─────╮        │
│  👤 Bremer       │        │  🏘️ town │              │        │
│  [+ New NPC]     │        ╰──────────╯         ╭───────╮   │
│                  │              │               │  Mill │   │
│ Enemies          │             3h               │  🏚️  │   │
│  👹 Goblin       │              │               ╰───────╯   │
│  🐺 Wolf         │        ╭──────────╮                      │
│  [+ New Enemy]   │        │Thornwood │  🟡 NEW              │
│                  │        │  🌲 wood │ ╭──────────╮         │
│ FILTER           │        ╰────┬─────╯ │ Old Mill │         │
│  ○ All           │            1h       │  🏚️  ?  │         │
│  ● Pending (2)   │        ╭──────────╮ ╰──────────╯         │
│  ○ Visited       │        │  Dungeon │                      │
└──────────────────┴────────┴──────────┴──────────────────────┘
```

### Node Detail Panel (on click)

```
┌──────────────────────────────────────┐
│ 📍 Graustein                 [Edit]  │
│ Type: 🏘️ Town  Status: ✅ Permanent  │
│ Safe to rest: ✅  Visible: always    │
├──────────────────────────────────────┤
│ NPCs PRESENT                  [+ Add]│
│  👤 Wotan — Karczmiarz               │
│  👤 Hans Bremer — Kupiec             │
├──────────────────────────────────────┤
│ ENEMIES POSSIBLE              [+ Add]│
│  👹 Bandit (standard)                │
├──────────────────────────────────────┤
│ SUB-LOCATIONS            [+ Add sub] │
│  🏠 Karczma Pod Krzyżem [safe ✅]   │
│  🏪 Rynek                            │
│  🏰 Brama Zamkowa                    │
├──────────────────────────────────────┤
│ CONNECTIONS                          │
│  → Thornwood Forest    3h ⚠️ danger  │
│  → Old Mill            1h ✅ safe    │
│  [Draw new connection]               │
├──────────────────────────────────────┤
│ [🤖 AI Assistant] [❌ Reject] [✅ Approve] │
└──────────────────────────────────────┘
```

**🤖 AI Assistant** opens Smart Entry agent inline — admin describes the location in chat, agent fills in fields. Same pattern as universal Smart Entry.

### NPC/Enemy Assignment Methods

1. **Drag from library** — drag NPC/Enemy bubble onto a location node → assigned
2. **From detail panel** — `[+ Add]` → search list → select
3. **From record** — NPC creation has `home_location_key` field

**Visual on node:** Small avatar row beneath the bubble:
```
╭──────────╮
│ Graustein│
│  🏘️ town │
│  👤👤 👹  │  ← 2 NPCs, 1 enemy type
╰──────────╯
```

### Pending Review Flow on Map

When GM creates `[CREATE_LOCATION: key=old_mill_ruins, ...]` mid-campaign:

1. Bubble appears on world map with dashed border + 🟡 NEW badge
2. Auto-positioned near the campaign's starting location
3. Admin sees it in "Pending" filter in library panel
4. Admin clicks → repositions by dragging → approves or rejects

**Approve** → solid bubble, permanent part of world, available to all future campaigns.
**Reject** → fades away. Stays usable in the current active campaign session, not made permanent.

### Player-Facing Map (Read-Only Mode)

Same graph data, different render mode. Player sees only discovered locations:

```
╭──────────────────────────────────────────╮
│  📍 Twoja lokacja: Graustein             │
│                                          │
│     [Graustein] ──── 2h ──── [???]      │
│          │                               │
│         3h                               │
│          │                               │
│     [Thornwood] ──── 1h ──── [Dungeon]  │
╰──────────────────────────────────────────╝
```

- Undiscovered reachable: shown as `[???]` (name hidden)
- Undiscovered unreachable: fully hidden
- `visible_before_visit = 1` locations: always shown with full name
- Click accessible location → initiates MOVEMENT action in the game

---

## 2. Persistent Hero System

### The Problem with Campaign-Scoped Heroes

V1 design: Hero belongs to one campaign. Campaign ends = hero is done (or dead).
V2 design: **Hero is a persistent entity that lives across multiple campaigns.**

### New Data Model

```
Character (persistent hero, lives across campaigns)
  ├── sheet_json (stats, skills, spells) — PERSISTS
  ├── inventory — PERSISTS
  ├── gold — PERSISTS
  ├── XP & advancement — PERSISTS
  ├── visited_locations[] — PERSISTS (hero's world map history)
  └── Campaigns (one-to-many)
       ├── Campaign 1: "Zdrada pod Graustein"  [COMPLETED ✓]
       ├── Campaign 2: "Dungeon Cieni"          [ACTIVE ▶]
       └── Campaign 3: [available to start]
```

### Between Campaigns

When a campaign ends (victory or death with survivor):
- Hero is placed in "rest state" — full HP/Mana restored
- Active conditions cleared
- Player can spend pending XP
- Player selects next adventure

**Campaign selection screen:**
```
"Przygoda w Graustein dobiegła końca.
 Co dalej, Aldric?"

[🗺️ Nowa kampania]    ← LLM generates from Ideas Bank, personalised to hero
[⚔️ Wyprawa do lochu] ← pick a dungeon from world map
[📜 Zlecenie]         ← short 1-session scenario
[🏘️ Eksploruj świat] ← free roam, no active quest
```

### What Persists / What Resets

| Data | Persists | Resets |
|------|---------|--------|
| Stats (STR, DEX, etc.) | ✅ | — |
| Skills and ranks | ✅ | — |
| Spells and upgrades (Scholar) | ✅ | — |
| Equipment and inventory | ✅ | — |
| Gold | ✅ | — |
| XP total | ✅ | — |
| Visited world locations | ✅ | — |
| Bonds and weaknesses | ✅ (can evolve) | — |
| Campaign-specific conditions | — | ✅ |
| HP / Mana | — | ✅ (fully restored) |
| Death save counter | — | ✅ |
| Active combat state | — | ✅ |
| Campaign plan | — | Per campaign |

### Hero Death

Death is NOT the end of the hero file. Options presented:
- **Restart the campaign** — same hero, same world, try again (campaign resets)
- **Accept death** — hero file marked as "fallen". Player creates a NEW hero. The fallen hero's name/deeds remain in the world (gravestone, NPC references).

Legacy: a fallen hero can become a named NPC or a legend referenced in future campaigns. Admin can promote a fallen hero's entry from the character records into `npc_definitions` as a ghost, ancestor, or historical figure.

---

## 3. Dungeon Runs (Standalone Content)

### Two Types of Dungeon Content

| Type | Triggered by | Length | Repeatable | Rewards |
|------|------------|--------|-----------|---------|
| **Story dungeon** | Campaign plot requires it | 3-8 sessions | No | XP + narrative progress |
| **Exploration dungeon** | Player chooses from world map | 1-3 sessions | Yes (cooldown) | XP + gold + loot |

### Exploration Dungeon Design

- Available as nodes on the world map (⚔️ dungeon icon)
- Hero must travel to the dungeon location first (map traversal)
- On arrival: "Wchodzisz do lochu. Jesteś gotowy?" → combat + exploration begins
- Generated from `campaign_ideas` with `category = 'dungeon_seed'`
- Scaled to hero's current stats (enemies pulled from appropriate tier)
- No narrative arc required — GM generates atmospheric descriptions only

**Dungeon properties (in campaign_ideas structured_data):**
```json
{
  "category": "dungeon_seed",
  "title": "Goblin Warren",
  "location_key": "goblin_warren",
  "rooms": 7,
  "enemy_pool": ["goblin", "goblin_archer", "goblin_shaman"],
  "boss_enemy": "goblin_warchief",
  "loot_tier": "standard",
  "atmosphere": "cramped tunnels, smell of rot, flickering torchlight",
  "cooldown_days": 3
}
```

**Repeatability with cooldown:**
- Same dungeon cleared → cooldown timer starts (e.g. 3 in-world days)
- After cooldown: enemies respawn, loot resets
- Prevents infinite instant-farming while allowing repeated runs
- Cooldown stored in `game_sessions` or `character_dungeon_runs` table

---

## 4. XP-Based Progression (WFRP Style)

### No Hard Level Gates

**Level** = `total_XP ÷ 100` rounded down. Displayed for context but doesn't gate anything.

Everything is purchased with XP directly. Player chooses what to invest in.

### XP Cost Table

| Purchase | XP Cost | Notes |
|---------|---------|-------|
| Stat +1 (e.g. STR 12→13) | `50 × current_modifier` | Higher stats = more expensive |
| Skill rank +1 | `30 × current_rank` (min 30) | Higher ranks = more expensive |
| New spell (Scholar) | 75 XP | Must meet INT ≥ 12 requirement |
| Upgrade spell Rank 1→2 | 50 XP | — |
| Upgrade spell Rank 2→3 | 100 XP | — |
| New archetype ability | 150 XP | Special class-specific powers |

**Stat cost examples:**
- STR 10→11 (mod 0→0): 50 × 0 = **0 XP** (getting off the floor is free-ish)
- STR 12→13 (mod +1→+1): 50 × 1 = **50 XP**
- STR 14→15 (mod +2→+2): 50 × 2 = **100 XP**
- STR 16→17 (mod +3→+3): 50 × 3 = **150 XP**
- STR 18→19 would be 200 XP but stat cap is 20

### Magic Tied to INT/WIS, Not Level

```python
# Scholar Mana pool
max_mana = 8 + (INT_modifier × 3)

# INT 10 (mod 0)  → 8 Mana
# INT 12 (mod +1) → 11 Mana
# INT 14 (mod +2) → 14 Mana
# INT 16 (mod +3) → 17 Mana
# INT 18 (mod +4) → 20 Mana

# Spell DC (effect spells)
spell_dc = 10 + INT_modifier

# Spell attack (offensive spells)
spell_attack = d20 + INT_modifier
```

Raising INT directly improves: Mana pool + spell DC + attack accuracy.
Scholar who dumps XP into INT gets exponentially more powerful magic.

### XP Spending Timing

On level-up or after combat: XP granted immediately, "⬆️ Advancement available" badge appears on character sheet. Player can spend:
- **During long rest** (recommended, most immersive — "you reflect on your experiences")
- **Anytime outside combat** (force-spend if they want)

The badge persists until XP is spent.

---

## 5. Hero Journal (Summary / History Rework)

With persistent heroes across campaigns, history must span all campaigns.

### Structure

```
📖 Kroniki Aldrica (persistent hero journal)
├── Rozdział 1: "Zdrada pod Graustein"  [UKOŃCZONE]
│    2-paragraph AI summary
│    Key decisions, how it ended, XP gained
├── Rozdział 2: "Dungeon Cieni"          [AKTYWNE]
│    Running summary, updated every 10 turns
└── Rozdział 3: ...
```

- Each completed campaign = one Chapter
- AI generates 2-paragraph Chapter Summary on campaign completion
- Journal accessible from character sheet at any time
- `/mem <query>` searches across ALL chapters (not just current campaign)

### GM Continuity

At the start of each new session (first turn after a gap), automatically inject:
- Last chapter's brief summary into narrator context
- Current campaign's active scene summary
- Any NPCs the hero has met before who appear in this location

This prevents the GM from "forgetting" past events.

---

## 6. Debug System

### Toggle

```
Admin panel → User Management → [user row] → Debug mode: ON/OFF
Also: admin can toggle their own debug mode mid-session via [🐛 Debug] button
```

Debug mode flag stored in `game_sessions.session_flags.debug_mode: bool`.
Completely invisible and non-functional for users with `debug_mode = false`.

### Debug Panel (Overlay in Frontend)

Collapsible panel, positioned as a small tab on the right edge of the screen.
Contains sections admin can individually toggle on/off:

| Section | What it shows |
|---------|--------------|
| **Game State** | Current WSM state, full session_flags JSON |
| **Last Intent** | ACTION tag parsed from last player input, raw text |
| **Mechanic Result** | Full Resolver output — rolls, modifiers, final outcome |
| **LLM Prompts** | Full intent parser prompt + narrator prompt |
| **LLM Response** | Raw narrator output before post-processing/strip |
| **Campaign Plan** | Plan JSON — beats visited, deviations, active act |
| **Character** | Full sheet_json raw |
| **Location** | Current location DB record raw |
| **NPC** | Last interacted NPC record (key, personality_prompt, keyword_triggers) |
| **Enemy** | Last combat enemy records with behavior profile |
| **Performance** | LLM call latency per turn (intent parse ms + narrator ms) |

### Debug Commands (Only Active in Debug Mode)

All via slash commands, only parsed when `debug_mode = true`:

| Command | Effect |
|---------|--------|
| `/debug set-hp 5` | Force character HP to value |
| `/debug set-state COMBAT` | Force WSM state |
| `/debug give-item healing_potion` | Grant item to inventory |
| `/debug trigger-fear` | Force a fear test on next turn |
| `/debug trigger-crit` | Force next attack to be a critical hit |
| `/debug skip-intent ACTION:ATTACK:target=goblin_1` | Bypass Intent Parser, inject tag directly |
| `/debug show-context` | Dump full narrator context to debug panel |
| `/debug set-xp 500` | Set XP total |
| `/debug force-miscast` | Force next spell to miscast |
| `/debug add-condition frightened` | Apply condition directly |

Admin can also see in the debug panel which **NPC key** and **enemy key** are active — confirming the correct DB records are being used (not invented hallucinations).

---

## Summary of New Systems Added This Session

| System | Phase | Notes |
|---|---|---|
| Visual World Builder | 08 Admin | Cytoscape.js, node-edge graph, drag NPC/enemy onto locations |
| location_connections table | 01 Foundation DB | Travel routes between locations |
| map_x / map_y / map_icon on game_locations | 01 Foundation DB | Positioning for visual editor |
| Persistent hero across campaigns | Architecture change | Character outlives individual campaigns |
| Hero death legacy system | 10 Polish | Fallen heroes become world lore |
| Dungeon run system | 06 Economy | Standalone farmable content |
| Dungeon cooldown tracking | 06 Economy | Prevents instant-farm |
| XP-based WFRP-style progression | 06 Economy | No level gates, everything purchasable |
| Magic tied to INT not level | 06 Economy | max_mana = 8 + INT_mod × 3 |
| Hero Journal (cross-campaign) | 10 Polish | Replaces per-campaign history |
| Debug system | 09 Frontend | Toggle per user, full state visibility |
