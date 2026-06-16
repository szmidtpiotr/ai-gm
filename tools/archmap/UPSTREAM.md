# Upstream: archmap kit

This `tools/archmap/` is the AI-GM **instance** of the reusable archmap kit.

- **Kit (generic, reusable):** https://github.com/szmidtpiotr/archmap (private)
  — engine scripts, the authoring method (`SKILL.md`), an HTML template, and this very
  map as `examples/ai-gm-combat`.
- **This folder = project data + a copy of the engine.** Project-specific parts live
  here: `architecture-map.html` (combat nodes), `overlay/node-map.json`,
  `overlay/heat-source.json`, `overlay/map-overlay.json`.
  The engine scripts (`overlay/update_overlay.py`, `update_heat.py`, `drift_check.py`,
  `refresh.sh`) are copies of the kit's `engine/` — generic, project-agnostic.

## Keeping in sync

- **Refresh this map** (issue badges + heat + drift): `./overlay/refresh.sh` (cron on .61).
  See `INSTRUKCJA.md`. Served by `archmap.service` at http://192.168.1.61:4747/.
- **Engine improvements** (new render features, smarter overlay) go to the kit repo first,
  then copy the changed `engine/*` back here. See the kit's `UPDATING.md` (Flow 2).
- **Build a map for a different project:** clone the kit and follow its
  `USE_IN_NEW_PROJECT.md` — point an agent at the kit and it authors a new map.

Note: in the kit, engine scripts live under `engine/`; here they live under `overlay/`
next to the project data (historical layout). Functionally identical.
