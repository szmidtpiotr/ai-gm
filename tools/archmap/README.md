# archmap — interactive codebase architecture map

Self-contained, hand-positioned HTML map of a codebase: clusters of nodes (one per
significant file/function/table), critical-path highlighting, plain-English
explanations, click-to-detail sidebar, feature filters, pan/zoom, and a live overlay
of GitHub issues + runtime traffic. One HTML file, no build step, opens in a browser.

> Status: **pilot** inside the AI-GM repo, mapping the Combat subsystem. Designed to be
> lifted out into a standalone reusable repo later (see "Extracting" below).

## Layout

```
tools/archmap/
├── architecture-map.html      # the map (skeleton hand-authored from real file reads)
├── INSTRUKCJA.md              # operator guide (Polish, plain language)
├── README.md                  # this file
└── overlay/
    ├── refresh.sh             # cron entrypoint: issues + heat + drift
    ├── update_overlay.py      # GitHub issues -> bug/fix badges
    ├── update_heat.py         # runtime DB -> per-node heat (calls/errors/p95)
    ├── drift_check.py         # disk files vs map nodes -> staleness report
    ├── node-map.json          # file path -> node id
    ├── heat-source.json       # event/call type -> node id
    └── map-overlay.json       # GENERATED — read by the map at startup
```

## Two layers

- **Skeleton** (nodes, edges, positions, roles, plain-English, critical path, dead code):
  authored by reading every file. Changes only when the code *structure* changes.
  Regenerated on demand by an agent, never auto-rewritten in CI (manual positions are
  the whole point of readability).
- **Overlay** (`map-overlay.json`): purely mechanical, refreshed by cron.
  - `update_overlay.py` reads each open issue's `## Files changed`, maps paths to nodes
    via `node-map.json`, writes bug/fix badges.
  - `update_heat.py` aggregates runtime events from the DB into per-node heat.

## Keeping it fresh

| Change | Who / how |
|---|---|
| Issue opened/closed, new task | automatic — `refresh.sh` via cron |
| New / deleted file in scope | `drift_check.py` flags it → ask an agent: "update the map" |
| Large subsystem rebuild | ask an agent: "regenerate map <subsystem>" |

## Connection to observability (AI-GM Phase 11)

The map's "heat" layer reads the same `game_events` / `llm_call_log` tables that the
observability phase introduces (`docs/V2_ARCHITECTURE/08_OBSERVABILITY_AND_MCP.md`).
The single event sink `log_combat_turn` is the map node where the Phase 11 game-event
writer plugs in — so map + observability ship as one phase. Enable the `_phase11`
sources in `heat-source.json` once those tables exist; no code change needed.

## Building a map (the method)

The authoring method lives in `architecture-map.md` (the skill spec at repo root):
map the stack → find the seam → read every file (never guess) → label edges with what
flows → tag for filters → surface dead code → write the default "notable findings".

## Extracting into a standalone repo

Generic, project-agnostic parts: the skill spec, the overlay scripts, and the
`node-map.json` / `heat-source.json` shapes. Project-specific parts: the contents of
`architecture-map.html` and the actual path→node entries. To reuse elsewhere:

1. Copy `tools/archmap/` into the new project (or clone the future `archmap` repo).
2. Run the skill / ask an agent to author `architecture-map.html` for that codebase.
3. Fill `node-map.json` with that project's file→node mapping.
4. Point `heat-source.json` / `refresh.sh` at that project's repo + DB.
