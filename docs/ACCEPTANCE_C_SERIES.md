# Acceptance Tests — C1–C19 (FAZA 1 core loop)

Executable acceptance suite for the FAZA 1 task series (GitHub issues #355–#375).
Two layers, one runner, one report. Unimplemented tasks fail on purpose — the
suite doubles as an **executable backlog**.

## Layers

| Layer | Where | What it proves | Driven by |
|-------|-------|----------------|-----------|
| **pytest (mechanical)** | `backend/tests/acceptance/test_c_series_acceptance.py` | Deterministic backend truth — endpoints, utils, DB invariants | urllib → `localhost:8000` (in-container) + direct `/data/ai_gm.db` reads |
| **Playwright (E2E)** | `ai_test_agent/playwright/ux/acceptance/c01..c19_*.spec.js` (one file per task) | Player-observable behaviour. LLM-playable tasks **play the game with a real model** (≤30 turns) toward the goal | `helpers/acceptance.js` → `playUntilGoal()` |

A task can be GREEN in pytest but `⊘ skipped`/`—` in E2E when it is not observable
from the player client (e.g. C5 enemy wound penalty). pytest is authoritative for
mechanical correctness; E2E is authoritative for player-facing behaviour.

## Task → layer map

| Task | Issue | Primary layer | Goal (acceptance) |
|------|-------|---------------|-------------------|
| C1  | #355 | E2E (LLM) | After N turns in one spot the GM suggests movement |
| C2  | #356 | pytest + E2E | Bogus hex move does not relocate the player |
| C3  | #357 | E2E (LLM) | ATTACK with no enemies does not start combat |
| C4  | #360 | pytest | `wound_penalty` maps HP% → 0/-1/-2/-4 |
| C5  | #358 | pytest | Same penalty applies to enemies; combat_service uses it |
| C6  | #359 | pytest | `GET /api/config/wound-thresholds` returns thresholds |
| C7  | #361 | pytest + E2E | `POST /characters/{id}/spend-xp/skill` wired + validates |
| C8  | #362 | pytest + E2E | `spend-xp/stat` wired; CON+1 recomputes hp_max |
| C9  | #363 | E2E (UI) | Long-rest "Ucz się" modal opens |
| C10 | #364 | E2E (LLM) | A suggested quest lands in `quests_active` |
| C11 | #365 | E2E (LLM) | Quest auto-completes after its objective |
| C12 | #366 | pytest | `[SPEND_GOLD]` deducts from config, ignores unknown keys |
| C13 | #367 | E2E (LLM) | LLM uses only GP — no silver/copper |
| C14 | #368 | E2E (UI) | New player lands on Heroes screen, not the wizard |
| C15 | #369 | E2E (UI) | API error shows a toast, not a blank screen |
| C16 | #370 | E2E (UI) | Delete needs a confirmation modal |
| C17 | #373 | E2E (LLM) | LLM does not narrate equipment loss; knows weapon/gold |
| C18 | #374 | pytest + E2E | Campaign starts on a known hex / (0,0) fallback |
| C19 | #375 | pytest + E2E | Hero starts a campaign at full HP |

## Run

```bash
# Everything + combined report (on the DEV host .61)
./scripts/acceptance_c_series.sh          # → ACCEPTANCE_C_SERIES_REPORT.md

# pytest only (fast, deterministic)
ssh claude@192.168.1.61 'docker exec ai-gm-dev-backend-1 \
  pytest tests/acceptance/test_c_series_acceptance.py -v'

# Playwright only — whole suite (real LLM, slow)
ssh claude@192.168.1.61 'docker exec ai-gm-dev-test-agent-1 \
  npx playwright test playwright/ux/acceptance/ \
  --config=playwright/playwright.config.js --reporter=list'

# A single task — one file per task (run individually, also from the Tools UI)
ssh claude@192.168.1.61 'docker exec ai-gm-dev-test-agent-1 \
  npx playwright test playwright/ux/acceptance/c13_gold_only.spec.js \
  --config=playwright/playwright.config.js --reporter=list'
```

> **Backend code is baked into the image.** After editing the pytest file,
> `docker cp` it in (or rebuild). Playwright specs live in a mounted volume and
> hot-reload — no rebuild needed.

## LLM requirements

The E2E layer needs a working active LLM preset (see issue #395 — the active
preset is the single source of truth). The seeded test player (`ai_test_player`,
user 1095) uses OpenAI `gpt-4.1-mini`; the global preset is OpenAI `gpt-4.1`.
Turn budget is capped per test (≤30) so a never-reached goal still terminates.

## Adding a task

1. pytest: add `test_cNN_*` with a deterministic assertion.
2. E2E: add a `test("CNN (#issue) — …")` block; for behavioural goals use
   `playUntilGoal(page, { messages, maxTurns, goal })`.
3. Register the C-code in `scripts/acceptance_c_series.sh` `TASK` map.
