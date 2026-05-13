# TASK 43 — Player World Map

**Phase:** 09 — Frontend
**Status:** ❌ Not Started
**Depends on:** TASK 40 (World Builder — same data source), TASK 08 (Location System)

---

## Overview

The player-facing world map renders the same location and connection data created by the admin in the World Builder (TASK 40), but with fog of war, read-only interaction, and click-to-travel. It uses Cytoscape.js in a stripped-down configuration — no editing controls, no admin UI. The map is accessible via a button in the left panel or character sheet and opens as a side panel (not full-screen — the player must still see the chat).

---

## Visibility Rules — Fog of War

Four visibility states for a location node:

| State | Condition | Rendered As |
|---|---|---|
| Always visible | `location.visible_before_visit = 1` | Full name, full icon, coloured node |
| Visited | Key is in `character.visited_location_keys` | Full name, full icon, coloured node |
| Reachable unvisited | Connected (via any edge) to a visited or always-visible node; not yet visited | Grey node, `"???"` label, greyed icon |
| Hidden | Not connected to any visited node and `visible_before_visit = 0` | Not rendered at all |

Edges (connections between locations):
- Edge between two fully visible nodes: rendered normally (label shows travel time + danger level).
- Edge between a visible node and a reachable-unvisited node: rendered greyed-out, label shows only distance (`"~3h"`), no danger level (hero doesn't know the danger of an unvisited route).
- Edge connecting to a hidden node: not rendered.

This produces true fog of war: the player sees the shape of the known world expanding outward as they explore, with mystery beyond the frontier.

---

## Map Panel UI

### Container

- Opened via: "🗺 Mapa" button in left panel, OR "Mapa świata" button on character sheet.
- Renders as a collapsible right-side drawer (width: ~40% of viewport).
- Chat column remains fully interactive behind the map panel.
- Map panel has its own close button [✕] and can be toggled without interrupting gameplay.

### Map Rendering

Uses Cytoscape.js in read-only mode (`userZoomingEnabled: true`, `userPanningEnabled: true`, `autoungrabify: true` — nodes cannot be dragged).

Node stylesheet (differs from admin World Builder — no editing affordances):

```javascript
{
  selector: 'node[visibility = "visited"]',
  style: {
    'background-color': '#c8a96e',     // parchment gold — known locations
    'border-color': '#8b6914',
    'label': 'data(label)',
    'color': '#f5e6c8',
    'font-size': '11px'
  }
},
{
  selector: 'node[visibility = "reachable"]',
  style: {
    'background-color': '#3a3a3a',     // dark grey — unknown frontier
    'border-color': '#555',
    'label': '"???"',
    'color': '#666',
    'font-size': '10px',
    'opacity': 0.7
  }
},
{
  selector: 'node[id = "current_location"]',
  style: {
    'border-color': '#ff4444',
    'border-width': '3px',
    'background-color': '#c8a96e',
    // Pulsing animation handled via CSS class toggle
  }
}
```

Current location marker: a `📍` badge overlaid on the current location node (rendered via Cytoscape node badge or a positioned HTML element).

### Edge Hover Tooltip

Hovering an edge shows a tooltip:
- Fully visible edge: *"Podróż do Thornwood Forest — 3 godziny — Niebezpieczna"*
- Greyed edge: *"Nieznana ścieżka — ~3 godziny"*

Tooltip is a plain HTML overlay positioned near the mouse cursor.

---

## Click-to-Travel

Clicking an accessible location node (visited, always-visible, or reachable-unvisited) initiates travel. Clicking an unvisited reachable node is allowed — the hero is heading into unknown territory.

### Confirmation Dialog

On node click, a confirmation overlay appears inside the map panel:

```
┌──────────────────────────────────────────────────────────┐
│  Podróżujesz do Thornwood Forest                         │
│  Odległość: 3 godziny  ·  Teren: niebezpieczny           │
│                                                           │
│  [Wyrusz]                           [Anuluj]              │
└──────────────────────────────────────────────────────────┘
```

If the destination is reachable-unvisited: add *"(nieznany teren)"* to the description.

### Travel Action Dispatch

On confirming [Wyrusz]:

1. Close the confirmation overlay.
2. Close the map panel (or minimise — user preference).
3. Dispatch a movement action to the turn pipeline. Two accepted formats:
   - **Structured:** send `{ "action_type": "MOVEMENT", "destination": "thornwood_forest" }` directly to the backend action endpoint — bypasses text parsing entirely.
   - **Text fallback:** send `"Podróżuję do Thornwood Forest"` as a normal turn message if the structured endpoint is not yet implemented.

   Prefer the structured form. The intent parser is not involved; the World State Manager validates the connection and resolves the movement directly.

4. On movement confirmed by WSM response: `character.visited_location_keys` is updated server-side. The map panel, when next opened, will show the new location as visited and its neighbours as reachable.

### Blocked Travel

If a node is not reachable (no path from any visited node) and `visible_before_visit = 0`, it is not rendered and cannot be clicked. If by admin configuration a location is visible (`visible_before_visit = 1`) but has no connection to any visited node, clicking it should respond: *"Nie znasz drogi do tego miejsca."*

---

## Visited Location Tracking

`character.visited_location_keys` is the single source of truth. It is:
- Written by the WSM when movement to a new location is confirmed.
- Read by the map panel's API endpoint to compute visibility states.
- Read by the Hero Journal (TASK 45) to show the cross-campaign visited map.
- Never written by the frontend directly.

The map API endpoint does the fog-of-war computation server-side — the frontend receives pre-classified nodes (visibility state already resolved), not raw location data.

---

## API

### GET /api/campaigns/{campaign_id}/world-map

Returns location nodes and edges, with visibility pre-computed for the requesting character.

Query parameter: `character_id` (required).

Response:
```json
{
  "nodes": [
    {
      "key": "graustein",
      "label": "Graustein",
      "map_icon": "town",
      "x_pos": 120,
      "y_pos": 80,
      "visibility": "visited",
      "is_current": true
    },
    {
      "key": "thornwood_forest",
      "label": "Thornwood Forest",
      "map_icon": "forest",
      "x_pos": 220,
      "y_pos": 80,
      "visibility": "reachable",
      "is_current": false
    }
  ],
  "edges": [
    {
      "from_key": "graustein",
      "to_key": "thornwood_forest",
      "travel_time_hours": 3,
      "danger_level": "dangerous",
      "visibility": "partial"
      // 'full' = both ends visited | 'partial' = one end unvisited | 'hidden' = not returned
    }
  ]
}
```

Hidden nodes and their edges are not included in the response.

---

## Cytoscape.js Configuration Notes

- Same library version as admin World Builder to avoid bundle duplication.
- Use a separate stylesheet object — do not import admin stylesheet.
- `autoungrabify: true` — nodes not draggable by player.
- `boxSelectionEnabled: false`.
- Enable `wheelSensitivity: 0.3` (smoother zoom for map panning).
- Layout: `preset` (positions loaded from `x_pos` / `y_pos` stored in DB, same as admin World Builder).

---

## Test Checklist

1. **Fog of war rendering:** Create a map with 5 locations — 1 visited, 2 reachable, 2 hidden. Verify only 3 nodes render, hidden nodes absent, reachable nodes show `"???"`.
2. **Click-to-travel:** Click a reachable node, confirm [Wyrusz] — verify structured MOVEMENT action dispatched, WSM movement resolved, new location added to `visited_location_keys`.
3. **Visited persistence across campaigns:** Complete a campaign, start a new one — verify previously visited locations still appear as visited on the new campaign's map.
4. **Current location marker:** Navigate to a location — verify `📍` marker appears on correct node, previous node no longer marked.
5. **Edge tooltip:** Hover a full-visibility edge — verify travel time and danger level shown. Hover a partial-visibility edge — verify only distance shown, no danger level.
