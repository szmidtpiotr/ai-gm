# TASK 40 — Visual World Builder

**Status:** ❌ Not Started
**Phase:** 08 — Admin Tools
**Priority:** HIGH — foundational for all location, NPC, and enemy placement
**Depends on:** Task 01 (DB Schema — location tables), Task 09 (NPC System), Task 10 (Data Tables)
**Unlocks:** Task 43 (Player World Map), Task 08 (Location System uses connection graph), Task 41 (Dungeon Runs need location nodes)

---

## Overview

The World Builder is a visual node-edge graph editor in the admin panel. It is the primary tool for creating and managing the game world:

- **Locations** are interactive bubbles (nodes)
- **Travel routes** are connecting lines (edges) with travel time and danger flags
- **NPCs and Enemies** are assigned to locations by dragging from a library panel
- **Sub-locations** (rooms within a town) are managed as nested children
- **Pending locations** (created by GM mid-campaign) appear as dashed bubbles waiting for approval

The world grows organically: admin seeds it before launch, campaigns add to it, admin curates what stays.

---

## Design Context

### Why Visual Instead of Forms?

The world is a spatial structure — relationships between locations matter as much as the locations themselves. A form can't convey "Graustein is 3 hours from Thornwood, which borders the Dungeon." A graph can. Admin needs to see the whole world at once to make good decisions about new location placements.

### The World as a Living Document

```
Admin builds initial world (10-15 locations)
         ↓
Player campaign starts → GM creates "Old Mill Ruins" mid-session
         ↓
Old Mill Ruins appears as 🟡 PENDING bubble on admin's world map
         ↓
Admin reviews, repositions, assigns enemies, approves
         ↓
Old Mill Ruins becomes permanent — available to all future campaigns
```

Every campaign enriches the world. The admin curates what enrichment sticks.

### Connection to the Game Engine

The `location_connections` table is not just for display — it is the data structure the **World State Machine** uses to validate player movement. A player cannot travel from Graustein to the Dungeon unless a connection exists between them (directly or via intermediate locations).

---

## Technology

**Cytoscape.js** — chosen for this task.

Reasons:
- Purpose-built for interactive graph/network visualization (not general SVG)
- Drag-and-drop node repositioning built in
- Edge creation via user interaction (drag between nodes)
- Custom styling per node state (pending/permanent/active)
- Works with vanilla JS — no React/Vue required
- MIT license, actively maintained
- `cytoscape-edgehandles` plugin for click-to-connect interaction

Load via CDN in admin panel:
```html
<script src="https://unpkg.com/cytoscape/dist/cytoscape.min.js"></script>
<script src="https://unpkg.com/cytoscape-edgehandles/cytoscape-edgehandles.js"></script>
```

---

## Database Schema

### Additions to `game_locations`

```sql
-- Map positioning (Cytoscape coordinates)
ALTER TABLE game_locations ADD COLUMN map_x REAL DEFAULT NULL;
ALTER TABLE game_locations ADD COLUMN map_y REAL DEFAULT NULL;

-- Visual type (determines icon and colour)
ALTER TABLE game_locations ADD COLUMN map_icon TEXT DEFAULT 'town'
    CHECK(map_icon IN ('town','dungeon','forest','ruin','castle','cave','road','camp','port','ruins'));

-- Whether visible on player map before they visit
ALTER TABLE game_locations ADD COLUMN visible_before_visit INTEGER DEFAULT 0;
-- 0 = fog of war (hidden until visited)
-- 1 = always shown (famous city, known landmark)

-- Review status (already added in Task 10, confirm here)
-- review_status TEXT CHECK(review_status IN ('permanent','pending_review','discarded'))
```

### New Table: `location_connections`

```sql
CREATE TABLE location_connections (
    id                  INTEGER PRIMARY KEY,
    from_location_key   TEXT NOT NULL REFERENCES game_locations(key),
    to_location_key     TEXT NOT NULL REFERENCES game_locations(key),

    -- Travel properties
    travel_hours        REAL NOT NULL DEFAULT 1.0,
    travel_description  TEXT,
    -- e.g. "Forest road, poorly maintained — bandits reported"

    -- Danger level (affects GM narrative and random encounter chance)
    danger_level        TEXT DEFAULT 'low'
        CHECK(danger_level IN ('none','low','medium','high','extreme')),

    -- Optional gate (player must have item/flag to use this route)
    requires_item_key   TEXT DEFAULT NULL,
    requires_flag       TEXT DEFAULT NULL,
    -- e.g. requires_item_key = 'ferry_token' for a river crossing

    -- Direction
    is_bidirectional    INTEGER DEFAULT 1,
    -- 0 = one-way (e.g. a waterfall you can go down but not up)

    -- Seasonal/conditional availability
    is_active           INTEGER DEFAULT 1,
    -- Can be toggled by admin or narrative events (bridge destroyed, pass snowed in)

    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX idx_location_connections_pair
    ON location_connections(from_location_key, to_location_key);
```

### New Table: `location_npc_assignments`

Replaces the `npc_keys` JSON array on game_locations with a proper relation table:

```sql
CREATE TABLE location_npc_assignments (
    id              INTEGER PRIMARY KEY,
    location_key    TEXT NOT NULL REFERENCES game_locations(key),
    npc_key         TEXT NOT NULL REFERENCES npc_definitions(key),
    assignment_type TEXT DEFAULT 'resident'
        CHECK(assignment_type IN ('resident','visitor','quest_only','patrol')),
    -- resident = always here
    -- visitor = here sometimes (narrative-driven)
    -- quest_only = only present when specific campaign beat is active
    -- patrol = moves between locations (future feature)
    notes           TEXT,
    is_active       INTEGER DEFAULT 1
);
```

### New Table: `location_enemy_assignments`

Replaces the `enemy_keys` JSON array on game_locations:

```sql
CREATE TABLE location_enemy_assignments (
    id              INTEGER PRIMARY KEY,
    location_key    TEXT NOT NULL REFERENCES game_locations(key),
    enemy_key       TEXT NOT NULL REFERENCES game_config_enemies(key),
    spawn_chance    REAL DEFAULT 1.0,
    -- 1.0 = always present, 0.3 = 30% chance per encounter
    max_count       INTEGER DEFAULT 3,
    -- max number of this enemy type in one encounter at this location
    notes           TEXT,
    is_active       INTEGER DEFAULT 1
);
```

---

## Admin World Builder — Full UI Specification

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ 🗺️ World Builder                    [+ Location] [+ Connect] [💾]│
├──────────────────┬───────────────────────────────────────────────┤
│  LIBRARY         │                                               │
│  Search: [____]  │        ╭─────────╮                           │
│                  │        │Graustein│──── 2h low ────╮          │
│  NPC POOL        │        │ 🏘️ town  │                │          │
│  👤 Wotan       D│        │ 👤👤 👹  │           ╭────────╮     │
│  👤 Bremer      D│        ╰─────────╯           │  Mill  │     │
│  👤 Guard       D│              │                │  🏚️   │     │
│  [+ New NPC]    │              3h high           ╰────────╯     │
│                  │              │                               │
│  ENEMY POOL      │        ╭─────────╮  🟡 NEW ←── pending      │
│  👹 Goblin      D│        │Thornwood│   ╭──────────╮           │
│  🐺 Wolf        D│        │  🌲      │   │Old Mill  │           │
│  💀 Skeleton    D│        │  👹🐺    │───│  🏚️ ?   │           │
│  [+ New Enemy]  │        ╰────┬────╯   ╰──────────╯           │
│                  │            1h med                            │
│  FILTER          │        ╭─────────╮                           │
│  ● All           │        │ Dungeon │                           │
│  ○ Pending (2)   │        │  ⚔️     │                           │
│  ○ My campaign   │        │  💀👹👹  │                           │
│                  │        ╰─────────╯                           │
└──────────────────┴───────────────────────────────────────────────┘
```

**D** = drag handle (drag NPC/Enemy onto a location node to assign)

### Node Visual States

```
╭─────────────╮   ← PERMANENT: solid border, full colour
│ Graustein   │
│ 🏘️ town     │
│ 👤👤 👹     │   ← avatar row: assigned NPCs + enemy types
╰─────────────╯

╭ ─ ─ ─ ─ ─ ╮   ← PENDING REVIEW: dashed border, faded
│ Old Mill   │     🟡 NEW badge top-right
│ 🏚️         │
╰ ─ ─ ─ ─ ─ ╯

╭═════════════╮   ← ACTIVE (player currently here): double border + pulse
║ Graustein   ║     📍 marker
║ 🏘️ town     ║
╰═════════════╯
```

### Node Icon Types

| `map_icon` | Symbol | Colour | Typical use |
|---|---|---|---|
| `town` | 🏘️ | Warm brown | Settlement, village, city |
| `dungeon` | ⚔️ | Dark red | Combat zone, cave, fortress |
| `forest` | 🌲 | Green | Wilderness, woods |
| `ruin` | 🏚️ | Grey | Abandoned building, old site |
| `castle` | 🏰 | Blue-grey | Noble fortress, keep |
| `cave` | 🕳️ | Dark grey | Underground entrance |
| `road` | 🗺️ | Yellow | Crossroads, waypoint |
| `camp` | 🏕️ | Orange | Temporary settlement |
| `port` | ⚓ | Blue | Harbour, dock |

### Connection Visual States

| Danger level | Line style | Colour |
|---|---|---|
| `none` | Thin solid | Light grey |
| `low` | Normal solid | White |
| `medium` | Normal solid | Orange |
| `high` | Bold | Red |
| `extreme` | Bold dashed | Dark red |

Travel time shown as label on edge: `2h` or `3h med` (hours + danger abbreviation).

---

## Node Interaction — Click to Open Detail Panel

Clicking any node opens a side panel on the right:

```
┌──────────────────────────────────────────┐
│ 📍 Graustein                      [Edit] │
│ Type: 🏘️ Town  │ Status: ✅ Permanent   │
│ Safe to rest: ✅ │ Visible: always       │
├──────────────────────────────────────────┤
│ NPCs PRESENT                      [+ Add]│
│                                          │
│  👤 Wotan        Karczmiarz  [resident] │
│     personality: gruff, knows everything │
│     [Remove from location]               │
│                                          │
│  👤 Hans Bremer  Kupiec      [resident] │
│     personality: nervous, hides guilt    │
│     [Remove from location]               │
│                                          │
├──────────────────────────────────────────┤
│ ENEMIES POSSIBLE                  [+ Add]│
│                                          │
│  👹 Bandit  standard  spawn: 80%  max:2 │
│     [Edit spawn]  [Remove]               │
│                                          │
├──────────────────────────────────────────┤
│ SUB-LOCATIONS               [+ Add sub] │
│                                          │
│  🏠 Karczma Pod Krzyżem  [safe ✅]     │
│     npcs: Wotan                          │
│  🏪 Rynek               [not safe]      │
│  🏰 Brama Zamkowa        [not safe]      │
│                                          │
├──────────────────────────────────────────┤
│ CONNECTIONS                              │
│                                          │
│  → Thornwood Forest   3h  ⚠️ high       │
│  → Old Mill           1h  ✅ low        │
│  [Draw new connection from here]        │
│                                          │
├──────────────────────────────────────────┤
│ CAMPAIGNS USING THIS LOCATION      (3)  │
│  Campaign 42 (active), 38, 31           │
├──────────────────────────────────────────┤
│ [🤖 AI Assistant]                       │
│ [✅ Approve]  [❌ Reject]  [🗑 Delete]  │
└──────────────────────────────────────────┘
```

**[🤖 AI Assistant]** opens Smart Entry chat inline — admin describes changes, agent fills fields.

**[Approve] / [Reject]** only shown for `pending_review` locations.

---

## Sub-Location System

Macro locations (towns, dungeons) contain sub-locations (individual rooms, buildings). These are children of the macro node — not shown as separate nodes on the world map, but managed in the detail panel.

```
Graustein (macro node)
├── Karczma Pod Krzyżem (sub: safe_for_rest=true)
│     assigned NPCs: Wotan
├── Rynek (sub: safe_for_rest=false)
└── Brama Zamkowa (sub: safe_for_rest=false)
     assigned enemies: Guard

Dungeon of Shadows (macro node)
├── Entry Chamber (sub)
├── Corridor 1 (sub)
├── Goblin Barracks (sub, enemies: Goblin×3, Goblin Archer×1)
└── Boss Chamber (sub, enemies: Goblin Warchief)
```

Sub-locations appear as a collapsible list within the macro's detail panel. Each sub-location has:
- Name
- `safe_for_rest` toggle
- Assigned NPCs (inherited from parent or specific to this sub)
- Assigned enemies (specific to this sub — dungeon room has different enemies than the entrance)

The World State Machine uses sub-locations for granular movement within a macro. Player can move freely between subs in the same macro (no validation needed — just narrative). Moving between macros requires a `location_connections` edge.

---

## NPC / Enemy Assignment

### Method 1 — Drag from Library

1. Hover NPC/Enemy card in library → drag handle appears
2. Drag card onto target location node
3. Assign dialog: confirm assignment type (resident/visitor/quest_only)
4. Assignment saved to `location_npc_assignments` or `location_enemy_assignments`

### Method 2 — From Detail Panel

Click `[+ Add]` in NPCs section → search box appears → filter by name/type → click to assign.

For enemies: also set `spawn_chance` (0.0–1.0) and `max_count` per encounter.

### Method 3 — From NPC/Enemy Record

When creating a new NPC via Smart Entry or form, field: `home_location_key` assigns them directly. Default: unassigned (visible in library but not on any location).

### Visual Feedback on Node

After assignment, the node's avatar row updates to show assigned entities:
```
╭─────────────╮
│ Graustein   │
│ 🏘️ town     │
│ 👤👤 👹     │  ← 2 NPCs (blue), 1 enemy type (red)
╰─────────────╯
```
Clicking an avatar opens that NPC/Enemy's record in a quick-view sidebar.

---

## Connection Editor

### Creating a New Connection

1. Click `[Draw new connection from here]` in detail panel — OR —
1. Click `[+ Connect]` button in toolbar, then click source node, then target node
2. `edgehandles` plugin handles the drag-between-nodes interaction
3. Connection dialog appears:

```
New Connection
From: Graustein → To: Thornwood Forest

Travel time: [3.0] hours
Description: [Forest road, poorly maintained]
Danger level: ○ none  ○ low  ● medium  ○ high  ○ extreme
Requires item: [________] (optional)
Bidirectional: ✅

[Cancel] [Save Connection]
```

### Editing an Existing Connection

Click on an edge line on the map → connection detail popup:
```
Graustein ←──3h──→ Thornwood
Danger: medium ⚠️
[Edit] [Delete]
```

### Connection Validation

Before saving a connection:
- Check: no duplicate connection in same direction
- Check: travel_hours > 0
- Warning if creating a one-way connection (easy to forget)
- Warning if connecting two sub-locations (sub-to-sub connections should be within same macro — flagged but not blocked)

---

## Pending Review Flow

When the GM emits `[CREATE_LOCATION: key=old_mill_ruins, label="Stary Młyn", type=sub, parent_key=graustein_town, atmosphere="crumbling stone walls, smell of rot"]` mid-session:

### Automatic Processing
1. Backend creates `game_locations` record with `review_status = 'pending_review'`
2. `map_x` and `map_y` auto-set: near parent location + small random offset
3. `map_icon` inferred from location_type (sub of town → 'ruin' default)

### Admin Sees
- 🟡 NEW badge count in admin nav: "Świat (2 oczekujące)"
- Pending location appears on world map as dashed bubble near its parent
- Library panel "Pending (2)" filter highlights it

### Admin Actions
1. **Reposition** — drag bubble to correct position on map
2. **Review** — click to open detail panel, edit name/description/icon
3. **Assign NPCs/Enemies** — drag from library
4. **Connect** — draw connection to parent or adjacent locations
5. **Approve** → `review_status = 'permanent'`
6. **Reject** → `review_status = 'discarded'` (fades from map; still usable in current active session)

---

## Player-Facing World Map

Different rendering of the same data. Implemented in **Task 43 (Player World Map)** — this task only builds the admin editor.

Key difference: player map is read-only, applies fog-of-war, shows player's current location marker, and clicking an accessible location initiates a `MOVEMENT` action in the game.

Data flow between admin map and player map:
```
Admin: [Graustein] ──3h──> [Thornwood]  (in DB)
         ↓
Player map renders the same edge
         ↓
Player clicks [Thornwood]: frontend sends "I travel to Thornwood Forest"
         ↓
Intent Parser: [ACTION:MOVEMENT:destination=thornwood]
         ↓
WSM validates: location_connections has edge graustein→thornwood? YES
         ↓
Movement resolves
```

---

## Admin API Endpoints

### World Map Data

```
GET  /api/admin/world/map
     → Returns all locations (with map_x, map_y, icon, status) + all connections
     → Used to initialise Cytoscape.js graph

POST /api/admin/world/locations
     → Create new location (also via Smart Entry)

PATCH /api/admin/world/locations/{key}
     → Update position, name, icon, safe_for_rest, visible_before_visit, review_status

DELETE /api/admin/world/locations/{key}
     → Soft delete (is_active=0); blocks if any active campaign uses this location
```

### Connections

```
POST   /api/admin/world/connections
        Body: {from, to, travel_hours, description, danger_level, is_bidirectional}

PATCH  /api/admin/world/connections/{id}
        → Edit travel time, danger, description, active status

DELETE /api/admin/world/connections/{id}
        → Hard delete (no soft delete — connections are not campaign-specific)
```

### Assignments

```
POST   /api/admin/world/locations/{key}/npcs
        Body: {npc_key, assignment_type}

DELETE /api/admin/world/locations/{key}/npcs/{npc_key}

POST   /api/admin/world/locations/{key}/enemies
        Body: {enemy_key, spawn_chance, max_count}

DELETE /api/admin/world/locations/{key}/enemies/{enemy_key}
```

### Sub-Locations

```
POST   /api/admin/world/locations/{key}/sub-locations
        Body: {key, label, safe_for_rest}

PATCH  /api/admin/world/locations/{key}/sub-locations/{sub_key}

DELETE /api/admin/world/locations/{key}/sub-locations/{sub_key}
```

### Pending Review

```
GET    /api/admin/world/pending
        → All pending locations with usage count

PATCH  /api/admin/world/locations/{key}/review
        Body: {action: "approve" | "discard"}
```

---

## Smart Entry Integration

The `[🤖 AI Assistant]` button in the detail panel opens the universal Smart Entry chat, pre-loaded with the location's current data and the `game_locations` schema descriptor.

Example interaction:
```
Admin: "This mill should be abandoned for decades — add
        some atmosphere and assign a couple of skeletons"

Agent: "Updated:
  Description: 'Kamienne ściany pokryte mchem, koło wodne
  stoi od lat. Skrzypi w wietrze.'
  Atmosphere: 'Zapach stęchlizny i starych kości'
  Enemies added: Skeleton (spawn: 70%, max: 2)

  [Preview changes] Save?"

Admin: "Yes" → PATCH /api/admin/world/locations/old_mill_ruins
```

---

## Connection to Game Engine

### Context Injection (per-turn)

When the Context Injector builds the narrator prompt, it includes:
```python
location = db.get_location(current_location_key)
npcs = db.get_location_npcs(current_location_key)       # from location_npc_assignments
enemies = db.get_location_enemies(current_location_key) # from location_enemy_assignments
connections = db.get_connections(current_location_key)  # from location_connections

context_block = f"""
=== ŚWIAT ===
Lokacja: {location.label}
Opis: {location.description}
Atmosfera: {location.atmosphere}
Dostępne NPC: {format_npcs(npcs)}
Możliwi wrogowie: {format_enemies(enemies)}
Można dotrzeć do: {format_connections(connections)}
"""
```

### World State Machine (movement validation)

```python
def validate_movement(from_key: str, to_key: str) -> tuple[bool, str]:
    # Check direct connection
    conn = db.get_connection(from_key, to_key)
    if not conn:
        # Check if to_key is a sub-location of current macro
        parent = db.get_parent_location(to_key)
        if parent and parent.key == get_macro_parent(from_key):
            return True, ""  # Free movement within same macro
        return False, "Nie ma drogi do tego miejsca."

    if not conn.is_active:
        return False, "Ta droga jest zablokowana."

    if conn.requires_item_key:
        if not player_has_item(conn.requires_item_key):
            item = db.get_item(conn.requires_item_key)
            return False, f"Potrzebujesz {item.label} aby tędy przejść."

    return True, ""
```

---

## Implementation Phases (Within This Task)

Build in this order — each sub-step is testable independently:

1. **DB migrations** — all new tables and columns
2. **Admin API** — CRUD endpoints for locations, connections, assignments
3. **Cytoscape.js init** — render existing locations as nodes (no interaction yet)
4. **Node drag-to-reposition** — positions saved to DB on drag-end
5. **Node click → detail panel** — read-only first
6. **Create location** — click empty canvas → dialog → new node
7. **Draw connection** — edgehandles plugin, save to DB
8. **NPC/Enemy drag assignment** — library panel drag-drop
9. **Sub-location management** — in detail panel
10. **Pending review flow** — dashed nodes, approve/reject
11. **Smart Entry integration** — AI assistant button in detail panel
12. **Visual polish** — node colours, edge styles, danger indicators

---

## Test Checklist

- [ ] Admin opens world builder → all existing locations rendered as nodes
- [ ] Admin drags a node → position saved, reloading preserves position
- [ ] Admin creates new location via `[+ Location]` → appears as node
- [ ] Admin draws connection between two locations → saved to `location_connections`
- [ ] Admin drags NPC from library onto location → `location_npc_assignments` record created
- [ ] Admin drags Enemy onto location → `location_enemy_assignments` record created with default spawn_chance
- [ ] Admin adds sub-location → appears in detail panel, safe_for_rest toggle works
- [ ] GM creates `[CREATE_LOCATION]` mid-session → pending bubble appears on admin map
- [ ] Admin approves pending location → becomes solid, `review_status = 'permanent'`
- [ ] Admin rejects pending location → fades, `review_status = 'discarded'`
- [ ] Smart Entry: admin types "add a skeleton enemy" → agent proposes, admin approves → enemy assigned
- [ ] Connection with `requires_item_key`: player without item gets blocked by WSM
- [ ] Closed connection (`is_active=0`): WSM blocks movement along it
- [ ] Player map: only approved locations visible, fog-of-war on unvisited
- [ ] Deleting a location with active campaigns: blocked with error message

---

## Related Tasks

- Task 01 (DB Schema) — migrations live there
- Task 09 (NPC System) — NPCs pulled from `npc_definitions` into the library panel
- Task 10 (Data Tables) — pending_review pattern used here
- Task 32 (World Review Queue) — the simpler table-based review UI; World Builder replaces/extends it
- Task 43 (Player World Map) — read-only player-facing version of this data
- Task 41 (Dungeon Runs) — dungeons are location nodes on the world map
- Task 03 (World State Machine) — reads `location_connections` for movement validation
- Task 04 (Context Injector) — reads location assignments for per-turn context
