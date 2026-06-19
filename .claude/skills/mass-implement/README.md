# mass-implement

Auto-run a whole checklist **task-by-task**, one real named resumable `claude` session per
task. Each task gets its own `TASK <PREFIX>-N` session (visible in `/resume`); the run
auto-advances on success and **STOPS on a gate** (a decision you must make, a spec↔code
contradiction, or an unmet dependency). Config-driven and **drop-in across projects**.

## Quick start (new project)

```
/mass-implement --init        # detect + ask a few questions + write config + validate
/mass-implement <list> --list # preview the plan (spawns nothing)
/mass-implement <list> P0     # run all unchecked P0 tasks
```

## How it works

| Piece | Role |
|---|---|
| `.claude/mass-implement.json` | project invariants — host, repo, branch, checklist files, id grammar, verify pipeline. No hardcode. |
| `references/prompt-template.md` | the shared ~80% child-prompt skeleton (built in — no per-phase prompt files). |
| `<!-- MASS-ZAKRES -->` block | the per-phase ~20% (decisions, out-of-scope, exceptions) inline at the top of the task doc. |
| `scripts/orchestrate.sh` | parses the checklist, runs preflight, spawns one child per task. |
| `scripts/init.sh` | `detect` / `validate` helpers for `--init`. |

## Two modes

- **LIST mode** — `<file>` is a task list (`fix_list.md`, `TASKS.md`). Selector: omitted /
  `#767` / `P0` / `5` / `3-7`.
- **FAZA mode** — a bare token (`L`, `SF`, `faza B`) or a file containing a `FAZA X` token.
  Selector: `L6-L10` / `L6` / `6-10` / `6`.

## Robustness (fail-loud, never silent-wrong)

- Merge markers / unparseable region → **refuse the whole run**, pointing at the line.
- Ambiguous task line → **skip + report** (`SKIPPED-AMBIGUOUS`); never silently dropped.
- **Already-done check** — the child verifies real state first; if a task is already
  implemented (the checkbox lied) it ticks it and emits `DONE-ALREADY` instead of redoing it.

## Status markers

`DONE` · `DONE-ALREADY` · `GATE — <reason>` · `ERROR — <reason>` · `SKIPPED-AMBIGUOUS`.

## Requirements

`jq`, `uuidgen`, and the `claude` CLI on PATH. Config + schema docs in `references/`.

## Safety

Children run sequentially with `--dangerously-skip-permissions` and obey the project rules in
`child.spec_files` (target env only, never prod, propose commits — never `git push`). Always
preview with `--list` before a real run.
