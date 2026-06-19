# mass-implement v2 — generic, robust, drop-in

**Date:** 2026-06-19 · **Status:** approved (Piotr) → implementing
**Goal:** make `/mass-implement` (1) robust to bad input, (2) free of separate prompt files, (3) drop-in across projects, and publishable to `szmidtpiotr/ClaudeCode-Tools`.

## Problem (v1 pains)

1. **Silent wrong parsing** — parser expects rigid structure (`## FAZA X` in notes.md, `## KOLEJNOŚĆ IMPLEMENTACJI` region in fix_list.md). Format drift (e.g. an unresolved merge conflict) → it picks the wrong tasks instead of failing.
2. **12 separate `prompt_*.md` files** — each carries the full ~80% skeleton + its ~20% scope. High maintenance; "is the prompt file correct?" is a recurring friction.
3. **Hardcoded to AI-GM** — `ROOT=/home/claude/projects/DEV_AIGM`, host `.61`, `renumber_fix_list.sh`, `prompt_fix_mass.md`. Not portable.

## Design (Approach 1 — config + built-in template + inline ZAKRES)

### A. Project config — `.claude/mass-implement.json`
Single file holds all project invariants. Schema (`references/config.schema.md`):
```jsonc
{
  "version": 1,
  "run_host": { "type": "local" },          // or {"type":"ssh","host":"user@ip","remote_root":"/path","git_user":"x"}
  "github":   { "owner": "...", "repo": "..." },
  "branch":   "develop",
  "checklists": {
    "faza": { "file": "notes.md",   "section_prefix": "## FAZA", "id_pattern": "{PREFIX}[0-9]+[a-z]?" },
    "list": { "file": "fix_list.md", "region_prefix": "## KOLEJNOŚĆ", "id_prefix": "FIX",
              "renumber_script": "scripts/renumber_fix_list.sh" }   // optional
  },
  "child": {
    "spec_files": ["CLAUDE.md", "game_mechanics.md"],
    "pipeline":   ["/tdd", "/code-review", "/playwright-test-report"]
  }
}
```
Core reads this — **zero hardcode**. Missing file → `--init` is suggested.

### B. Built-in prompt template — `references/prompt-template.md`
The shared ~80% skeleton, shipped with the skill: read rules+spec+checklist → one-task algorithm → **already-done check** → implement via configured pipeline → verify → update checklist+spec → STOP + plain-Polish report + status marker + ZASADY ŻELAZNE. Placeholders (`{ID}`, `{SPEC_FILES}`, `{PIPELINE}`, `{ZAKRES}`, `{GITHUB}`) filled from config + the inline ZAKRES.

### C. Inline ZAKRES block (per faza / list)
Small block at the top of the faza section in the task doc (decisions, out-of-scope, TDD exceptions, id→work mapping). The orchestrator extracts and injects it into the template. Replaces the bespoke 20% of each old prompt file. No standalone prompt file.

### D. Preflight validator
Runs before any spawn:
- **Structural corruption** (merge markers `<<<<<<<`/`=======`/`>>>>>>>`, unparseable region) → **refuse whole run**, point at the offending line in plain Polish.
- **Ambiguous task** in the selected set (line present but can't extract id/issue) → **skip + report** at end (never silently drop, never refuse all).
- **Per-task already-done check** (executed by the child via the template): if the issue's test is already green / code matches acceptance → mark `[x]`, comment the issue, emit `MASS_STATUS: DONE-ALREADY`, do **not** re-implement.

### E. `--init` bootstrap — `scripts/init.sh`
New-project setup:
1. **Auto-detect:** repo root (git), parse CLAUDE.md for test command / host / repo / branch, scan for checklist-like `.md`.
2. **Interview** (plain Polish, only the un-inferred): which file is the task list, how to verify, host local vs ssh.
3. **Write** `.claude/mass-implement.json` + drop a commented ZAKRES template into the task doc.
4. **Validate:** run `--list`; show parsed plan or point at what's wrong.
5. Report "gotowe, odpalaj `/mass-implement <plik> [selektor]`".
Relationship: `workflow-loop` authors the plan/checklist; `--init` wires the autorunner to it.

### F. Migration + cleanup (AI-GM)
1. Migrate `prompt_fix_mass.md` ZAKRES → inline block + `.claude/mass-implement.json`.
2. Archive the 12 historical `prompt_*.md` (completed/paused fazy) to `docs/archive/prompts/` (audit trail) — not hard-deleted.
3. De-hardcode `orchestrate.sh`. Grep-verify no other caller before removing root prompts.
4. Verify `--list fix_list.md` produces the same plan as v1.

## Status markers (extended)
`DONE` · `DONE-ALREADY` (was implemented, just ticked) · `GATE — <reason>` · `ERROR — <reason>` · plus orchestrator-level `SKIPPED-AMBIGUOUS` in the summary.

## Out of scope
- Parallel children (stays sequential — no DB/test races).
- Auto-resolving the `notes.md` merge conflict (separate task).
- Rewriting completed-faza prompts as inline blocks (archived instead).

## Verification
- `--list` on: good file → correct plan; merge-conflicted file → refuse-all with line; file with one malformed task → that task in SKIPPED, rest planned.
- `--init` dry-run on a scratch repo → writes valid config, `--list` parses.
- No real autonomous run until Piotr approves; no prompt-file deletion until grep-clean + archived.

## Publish
Generic version (no AI-GM specifics; AI-GM values only as the example config) → `ClaudeCode-Tools/Skills/mass-implement/{SKILL.md,README.md,scripts/,references/}`.
