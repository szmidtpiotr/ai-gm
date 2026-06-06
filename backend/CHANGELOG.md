# Changelog — AI-GM

Format: `vX.Y.Z — YYYY-MM-DD — opis`

---

## v1.2.0-dev — 2026-06-06 — Faza 1: World Loop Core

In progress (Faza 1 — C tasks).

### Added
- **C1** — STORY_STALE injection: after 5 turns without location change, LLM suggests leaving (#355)

### Changed
- Admin panel v3 is now the sole admin interface (`/admin3/`)
- `/admin` → `/admin3/` redirect via Nginx

---

## v1.1.0 — 2026-06-05 — Faza 0: World State Machine

Faza 0 (B tasks) — 100% complete.

### Added
- **B1** — World State Machine (WSM) — action validation gate (#336)
- **B2** — WSM: MOVEMENT action with hex validation (#337)
- **B3** — Gate mechanic (locked gates, key items, quests) (#338)
- **B4** — NPC memory per campaign (first-talk flag, persistent attitude) (#339)
- **B5** — Campaign Kompas — hints panel for available actions (#340)
- **B6** — World State history viewer (admin + player) (#352)
- **B7** — DEV Inspector panel (admin debug overlay in player UI) (#354)

### Changed
- Dungeon system refactored to use WSM
- Combat zones (engaged/ranged) fully wired to WSM

---

## v1.0.0 — 2026-06-01 — Faza -1: Cleanup & Foundation

Faza -1 (A tasks) — 100% complete.

### Added
- **A4** — Git version tagging system (v1.0.0, v1.1.0-dev, v1-stable)
- **A5** — Maintenance notification middleware + player banner
- **A7** — Admin panel v3 routing (/admin3/)
- **A12** — Game config seed to git; player data stays private

### Removed
- Dead code: voice-service (708MB), observability stack, docs/OLD (~1.1GB total)

### Fixed
- DB schema: missing columns in game_locations
- Deploy scripts: dirty-check ignore untracked files

---

## v0.3 — metrics-dashboards-dev

Observability stack (Grafana/Loki/Prometheus). Deprecated — removed in A1.

## v0.2 — observability-dev

Loki logging integration.

## v0.1 — phase0-complete

Initial working game loop: login, character, campaign, combat, inventory.
