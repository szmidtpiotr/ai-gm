# Changelog — AI-GM

Format: `vX.Y.Z — YYYY-MM-DD — opis`

---

## v1.2.3 — 2026-06-07 — Harness testów C1–C19 + panel Playwright w admin3

### Added
- Harness testów akceptacyjnych C1–C19 (pytest + Playwright), uruchamialny z admin3 → Narzędzia → 🎭 Playwright — każde zadanie jako osobny test
- Panel Playwright w admin3 odpala wszystkie suity (regression / acceptance / admin3) z UI; skan rekursywny + run po pliku lub grupie
- Smoke testy admin3 (dev-login + 14 sekcji bocznego menu)
- Regression Playwright dla #355 (STORY_STALE) i #390 (zegar in-game)

### Fixed
- #394 — przycisk „Atakuj" pozostawał aktywny po wygranej walce
- #395 — aktywny preset LLM jako jedyne źródło prawdy (brak cichego fallbacku do Ollama/gemma)
- #391 — TRAVEL_HINT gdy brak odkrytych hexów
- #390 — zegar in-game tyka (advance_clock obsługuje `minutes=` + akumulacja)
- reset_test_env: czyści `model_id` kampanii + zapewnia wiersz `game_sessions`

---

## v1.2.2 — 2026-06-07 — Faza 1 Core Loop (C9-C19)

### Added
- **C17** — Inventory context injection — LLM dostaje faktyczny ekwipunek postaci per turę (koniec halucynacji "straciłeś wszystko")
- **C18** — Nowe kampanie startują na wcześniej odkrytych hexach (nie na pustkowiu)
- **C19** — Bohater wchodzi w nową kampanię z pełnym HP i maną
- **C10-C13** — Systemowe tagi QUEST_SUGGEST, SPEND_GOLD, mechaniczne śledzenie questów, reguła złota w system_prompt
- **C14-C16** — Hero-first flow, error boundary na loadHeroes, modal potwierdzenia kasowania kampanii
- **C9** — Modal długiego odpoczynku — "Ucz się" UI z levelupem

### Fixed
- Opening scene zawsze generowana z kontekstem planu GM (nie domyślny las)
- Pasywna obserwacja nie wyzwala zbędnego rzutu Awareness
- Streaming LLM URL fix, BUILD_CAMP gate, debug bloki usunięte z player UI

---

## v1.2.1 — 2026-06-06 — Faza 1: World Loop Core (C1-C8)

### Added / Fixed
- **C1** — STORY_STALE: po 5 turach bez zmiany lokacji LLM sugeruje ruch (#355)
- **C2** — Walidacja ruchu mechaniczna: hex, terrain, World State update (#356)
- **C3** — Gate walki: sprawdzanie scene_enemies przed każdym ATTACK (#357)
- **C4** — wound_penalty utility: unifikacja hp_current/hp_max → roll modifier (#360)
- **C5** — Symetria ran: wound_penalty dla wrogów (nie tylko gracza) (#358)
- **C6** — Progi ran frontend/backend: stałe z API zamiast hardcode (#359)
- **C7** — XP spend skill: poprawne koszty (100/75/150 XP), rank ceiling=3 (#361)
- **C8** — XP spend stat: koszty per game_mechanics.md (50/100/200/400), ceiling=19, CON→hp_max (#362)

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
