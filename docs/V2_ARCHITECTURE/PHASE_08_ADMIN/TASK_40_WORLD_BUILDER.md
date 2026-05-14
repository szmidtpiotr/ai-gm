# TASK 40 — Visual World Builder (Hex Grid)

**Status:** 🔶 In Progress
**Phase:** 08 — Admin Tools
**Priority:** HIGH — foundational for player world map (Task 43) and dungeon entry
**Depends on:** Task 01 (DB Schema), Task 09 (NPC System), Task 14 (Combat — dungeon entry)
**Unlocks:** Task 43 (Player World Map), Task 41 (Dungeon Runs — hex entry point)

---

## Design Decisions (Locked 2026-05-15)

All decisions from game-design analysis sessions are final. Do not reopen without explicit discussion.

| Decision | Value |
|---|---|
| Map unit | **1 hex = 1 hour travel** (starting value; test plan below) |
| Terrain time | **No time difference per terrain** — route length = time. Terrain = encounter flavor only. |
| Hex flags | **Two-layer model**: Global layer (shared world) + Campaign overlay (private to campaign) |
| Fog of war | Empty hex outline on player map for unvisited hexes; full content on admin map |
| GM edit rights | GM can place new hexes anytime; edit their own hexes' global layer + any hex's campaign layer; cannot edit/delete other GMs' or admin's global hexes |
| Travel resolution | **Chain (Option B)**: A* pathfind, per-hex encounter roll, interrupt on trigger |
| Zoom | Three CSS breakpoints (World / Region / Hex Detail) on one SVG canvas |
| Dungeon entry | Mode switch via `dungeon_run` system — NOT a zoom level |
| Teleport | Separate `hex_teleport_connections` table; pathfinder treats as extra edges; renders as curved dashed line |
| Old model | Delete Cytoscape.js world builder; delete test location data from DB |

---

## Core Concept

The world is a **hex grid**. Each hex is a tile representing terrain (forest, plains, town, dungeon, etc.). Travel time = count of hexes traversed × 1 hour each. The map grows organically — admin seeds it, GMs extend it mid-session, everything persists across campaigns.

```
Town → [plains] → [forest] → [forest] → Dungeon  =  3 hours
Town → [plains] → [plains] → [mountains] → [mountains] → City  =  4 hours
```

---

## Two-Layer Hex Model

Every hex has two independent data layers:

**Layer A — Global (shared world)**
Terrain type, label, atmosphere, encounter pool. Shared across ALL campaigns. Persistent forever. Campaign 1 placing a forest hex means Campaign 7 sees that forest.

**Layer B — Campaign overlay (private)**
Narrative encounters, campaign-specific labels, GM notes, fog-of-war state (discovered?). Invisible to other campaigns. The same forest hex can have different narrative content per campaign.

---

## Map Scales (Zoom Levels)

Three rendering breakpoints on one continuous SVG zoom:

| Level | Trigger | What's visible |
|---|---|---|
| **World** | zoom < 20% | Major named hexes only, travel lines between regions |
| **Region** | zoom 20–70% | All placed hexes, terrain colours, named hex labels — **default play view** |
| **Hex Detail** | zoom > 70% | Single hex in detail panel; full content, encounters, campaign overlay |

The dungeon map is a **mode switch** (not a zoom level). Clicking Enter on a dungeon hex launches the `dungeon_run` room map. "Exit Dungeon" returns to hex map.

---

## Travel System

### Hex Pathfinding (Chain Travel)

Player says "I travel to Thornwood" → backend:
1. A* pathfind shortest route on hex grid
2. Include `hex_teleport_connections` as extra edges
3. For each hex along path: roll encounter vs. `encounter_chance`
4. Check campaign overlay: any `narrative_encounter` here?
5. On encounter: interrupt travel at that hex, resolve encounter, player can continue
6. No interrupts: full journey narrated in one GM response
7. Advance world clock by total travel hours

### Teleport Connections

Non-adjacent hex links for boat routes, magic portals, tunnels. Render as curved dashed lines on map. Player map shows the connection only when at least one endpoint is in their discovered hexes. Pathfinder uses these as normal edges — chain travel routes through them naturally.

Travel time for teleports counts normally. Encounter rolls apply (sea voyage should have pirates!).

### Travel Time Calibration

Starting value: **1h per hex**

Test plan: Place a town + dungeon 3 hexes apart (3h). Place a city 8 hexes away (8h ≈ full travel day). Validate: Does 3h feel like "nearby threat"? Does 8h feel like "real expedition"? Adjust if both answers are not yes.

---

## Database Schema

### New Tables

```sql
-- Global hex grid (shared world)
CREATE TABLE world_hexes (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    q                           INTEGER NOT NULL,
    r                           INTEGER NOT NULL,
    hex_type                    TEXT NOT NULL DEFAULT 'plains',
    label                       TEXT,
    atmosphere                  TEXT,
    encounter_chance            REAL NOT NULL DEFAULT 0.15,
    encounter_pool              TEXT NOT NULL DEFAULT '[]',  -- JSON array of enemy keys
    location_key                TEXT REFERENCES game_locations(key),
    discovered_in_campaign_id   INTEGER,
    created_by_gm               INTEGER NOT NULL DEFAULT 0,
    created_by_campaign_id      INTEGER,
    is_active                   INTEGER NOT NULL DEFAULT 1,
    created_at                  TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX idx_world_hexes_coords ON world_hexes(q, r);

-- Per-campaign hex data (private overlay)
CREATE TABLE campaign_hex_data (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id         INTEGER NOT NULL,
    hex_q               INTEGER NOT NULL,
    hex_r               INTEGER NOT NULL,
    narrative_encounter TEXT,       -- campaign-specific encounter description
    campaign_label      TEXT,       -- override label for this campaign ("The Witch's Hut")
    campaign_notes      TEXT,       -- GM private notes
    discovered          INTEGER NOT NULL DEFAULT 0,  -- fog of war: has player visited?
    UNIQUE(campaign_id, hex_q, hex_r)
);

-- Terrain type config (admin-editable, seeded)
CREATE TABLE hex_type_config (
    hex_type            TEXT PRIMARY KEY,
    label               TEXT NOT NULL,
    travel_hours        REAL NOT NULL DEFAULT 1.0,
    encounter_base_chance REAL NOT NULL DEFAULT 0.15,
    map_color           TEXT NOT NULL DEFAULT '#4a6a4a',
    map_icon            TEXT,
    is_active           INTEGER NOT NULL DEFAULT 1
);

-- Non-adjacent travel connections (boat, portal, tunnel)
CREATE TABLE hex_teleport_connections (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    from_q              INTEGER NOT NULL,
    from_r              INTEGER NOT NULL,
    to_q                INTEGER NOT NULL,
    to_r                INTEGER NOT NULL,
    travel_type         TEXT NOT NULL DEFAULT 'boat'
        CHECK(travel_type IN ('boat','magic','tunnel','portal')),
    travel_hours        REAL NOT NULL DEFAULT 8.0,
    encounter_chance    REAL NOT NULL DEFAULT 0.2,
    requires_item_key   TEXT DEFAULT NULL,
    label               TEXT,
    is_bidirectional    INTEGER NOT NULL DEFAULT 1,
    is_active           INTEGER NOT NULL DEFAULT 1
);
```

### Terrain Type Seed Data

| hex_type | Label | Travel h | Encounter % | Color |
|---|---|---|---|---|
| road | Droga | 1.0 | 5% | #c8a86c |
| plains | Równiny | 1.0 | 15% | #7a9a4a |
| forest | Las | 1.0 | 30% | #2d5a2d |
| hills | Wzgórza | 1.0 | 20% | #8a7a5a |
| mountains | Góry | 1.0 | 25% | #6a6a6a |
| swamp | Bagno | 1.0 | 40% | #4a5a3a |
| river | Rzeka | 1.0 | 10% | #3a6a8a |
| town | Miasto | 0.0 | 0% | #c8a86c |
| dungeon | Loch | 0.0 | 100% | #5a1a1a |
| ruins | Ruiny | 1.0 | 60% | #6a5a4a |
| castle | Zamek | 0.0 | 0% | #5a5a8a |

Note: `travel_hours = 0.0` for towns/dungeons/castles means entering them costs no travel time — you're already there.

---

## API Endpoints

### Admin World Builder

```
GET  /api/admin/world/map
     → All hexes (global layer) + all teleport connections
     → Used to initialize the hex canvas

GET  /api/admin/world/hex-types
     → Terrain type config with colors and encounter rates

POST /api/admin/world/hexes
     Body: {q, r, hex_type, label, atmosphere, encounter_chance, encounter_pool, location_key}
     → Paint a hex

PATCH /api/admin/world/hexes/{q}/{r}
     → Update global layer data

DELETE /api/admin/world/hexes/{q}/{r}
     → Delete hex (blocked if any campaign has campaign_hex_data referencing it)

POST /api/admin/world/teleport-connections
     Body: {from_q, from_r, to_q, to_r, travel_type, travel_hours, label, requires_item_key, is_bidirectional}

DELETE /api/admin/world/teleport-connections/{id}
```

### Player World Map

```
GET /api/campaigns/{id}/world-map
    → Hexes visible to player (only discovered hexes + empty outlines for adjacent unvisited)
    → Includes campaign overlay data (campaign_label if set, narrative_encounter stripped)

POST /api/campaigns/{id}/travel
     Body: {destination_q, destination_r, character_id}
     → A* pathfind, chain travel resolution, returns narrative
```

---

## Admin UI

### Technology

**Honeycomb.js** (hex geometry) + **SVG** (rendering). Not Cytoscape.js.

```html
<script src="https://cdn.jsdelivr.net/npm/honeycomb-grid@4/dist/honeycomb.min.js"></script>
```

### Interactions

- **Click empty hex** → terrain type picker → hex painted
- **Click painted hex** → detail panel opens (edit global layer, add campaign overlay, set encounter pool)
- **Right-click hex** → context menu: Edit / Delete / Draw teleport from here
- **Scroll/pinch** → zoom (three breakpoints auto-switch rendering layers)
- **Draw teleport** → click source hex → click destination hex → connection dialog

### Detail Panel (per hex)

```
┌──────────────────────────────────────────┐
│ [forest] (4, -2)              [Edit] [🗑]│
│ Label: Thornwood Forest                  │
│ Atmosphere: Ciemny, wilgotny las...      │
├──────────────────────────────────────────┤
│ GLOBAL — Encounter Pool         [Edit]   │
│  goblin (40%) · wolf (30%) · bandit (30%)│
│  Base chance: 30%                        │
├──────────────────────────────────────────┤
│ CAMPAIGN OVERLAY               [+ Add]   │
│  Campaign 42: "Jaskinia czarownicy"      │
│  Campaign 38: (none)                     │
├──────────────────────────────────────────┤
│ TELEPORT CONNECTIONS                     │
│  (none from this hex)  [+ Draw]          │
├──────────────────────────────────────────┤
│ LINKED LOCATION: (none)         [+ Link] │
└──────────────────────────────────────────┘
```

---

## World State Machine Integration

Movement validation changes from `location_connections` check to hex adjacency + teleport:

```python
def validate_movement(from_hex, to_hex, campaign_id, character_id):
    # Check 1: Adjacent hex exists and is active
    if are_adjacent(from_hex, to_hex):
        target = get_hex(to_hex)
        if not target:
            return False, "Nieznane terytorium."
        return True, compute_travel(target, campaign_id)

    # Check 2: Teleport connection exists
    conn = get_teleport_connection(from_hex, to_hex)
    if conn:
        if conn.requires_item_key and not player_has_item(conn.requires_item_key):
            item = get_item(conn.requires_item_key)
            return False, f"Potrzebujesz {item.label}."
        return True, compute_teleport_travel(conn, campaign_id)

    return False, "Nie ma drogi do tego miejsca."
```

---

## Implementation Order

1. DB migrations — world_hexes, campaign_hex_data, hex_type_config (+ seed), hex_teleport_connections
2. Admin API — CRUD for hexes and teleport connections
3. Frontend — replace world_builder.js (Cytoscape → Honeycomb.js hex SVG canvas)
4. Three zoom levels (CSS layer breakpoints)
5. Hex paint interaction (click empty → pick terrain → save)
6. Hex detail panel (click painted → read/edit)
7. Teleport connection drawing tool
8. Player map endpoint (fog of war + campaign overlay)
9. WSM movement validation rewrite
10. Chain travel A* implementation
11. Delete old location test data from DB

---

## Test Checklist

- [ ] Paint a forest hex at (0,0) → appears on map, saved to DB
- [ ] Click hex → detail panel shows terrain type, encounter pool
- [ ] Paint 3 adjacent hexes between town and dungeon → chain travel chains them (3h)
- [ ] Draw teleport connection port→island → curved dashed line on map
- [ ] Player travels port→island → pathfinder uses teleport edge (8h boat included in total)
- [ ] Encounter roll triggers mid-journey → travel interrupts at that hex
- [ ] Player map: unvisited hex shows empty outline; visited shows full terrain
- [ ] Campaign overlay: Campaign 1's "witch's hut" label on forest hex not visible in Campaign 2
- [ ] GM places hex mid-session → hex appears globally, no approval needed
- [ ] Admin deletes hex with campaign_hex_data referencing it → blocked with error
- [ ] Dungeon hex: "Enter Dungeon" button appears → launches dungeon_run room map
- [ ] Zoom World: only major named hexes visible
- [ ] Zoom Region: all hexes, terrain colours, labels
- [ ] Zoom Hex Detail: single hex fills panel automatically
