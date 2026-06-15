---
name: mass-implement
description: >-
  Auto-run a whole FAZA checklist task-by-task, one real named resumable Claude
  session per task. Use when Piotr says "/mass-implement <promptfile> [range]",
  "wdroż całą fazę", "lec zadanie po zadaniu", or wants the FAZA start-prompt
  (prompt_b.md, prompt_sf.md, ...) applied to every unchecked task without
  pasting it manually per session. Each task = its own session named "TASK X-N"
  in the /resume picker; auto-advances on success, STOPS on a gate.
---

# mass-implement

Replaces the manual loop: *paste prompt_X.md → rename session "TASK X-N" → run one
task → STOP → open new session → repeat*. One command fans the FAZA start-prompt
across every unchecked task, each in its **own real, named, resumable** `claude`
session that shows up in the `/resume` picker so Piotr can reopen any single task
later and finish verification in the exact session it was done.

## Invocation

```
/mass-implement <promptfile> [range] [--list]
```

- `<promptfile>` — FAZA start-prompt, bare name or path: `prompt_b.md`, `prompt_sf.md`, …
- `[range]` — optional task window: `B6-B10`, `B6`, `6-10`, `6`. Omitted = all unchecked.
- `--list` — preview the plan only; spawn nothing.

The FAZA prefix (B / SF / HI / L …) is auto-derived from the `FAZA X` token in the
prompt file, and the task list is parsed from `notes.md → ## FAZA X` (the single
source of truth for `[ ]`/`[x]` status).

## How it behaves (the two decisions Piotr locked in)

- **Autonomy = auto, stop on gates.** Runs unchecked tasks in checklist order.
  Each child session ends with a marker. `DONE` → next task. `GATE`/`ERROR`/missing
  → the whole run **STOPS** and reports which task and why. Gates: a decision Piotr
  must make (e.g. D2/D3), a code↔design contradiction, a "kamień"/playtest/SMOKE
  item, or an unmet hard dependency (e.g. #595).
- **One real session per task.** Each task is a separate `claude` process named
  `TASK <PREFIX>-<N>` with a fixed session id → appears in `/resume`. Resume any with
  `claude --resume <uuid>` (uuids printed in the run summary).

## Steps for the agent

1. **Parse args** from the user's `/mass-implement` line. If no promptfile → ask which.
2. **Preview the plan** — run list mode and show Piotr the ordered task list, so he
   sees exactly what will run and can catch a wrong FAZA/range:
   ```bash
   bash .claude/skills/mass-implement/scripts/orchestrate.sh <promptfile> [range] --list
   ```
   If the user passed `--list`, stop here.
3. **Launch the real run in the background** (children take many minutes each;
   never foreground — it would blow the Bash timeout). Run from the project root,
   wrapped in `setsid … </dev/null` so the run survives a SIGHUP when Piotr
   resumes/closes the launching session (without it the orchestrator + its current
   child get reaped, leaving a `TASK <PREFIX>-N` session staged-but-idle):
   ```bash
   setsid bash .claude/skills/mass-implement/scripts/orchestrate.sh <promptfile> [range] </dev/null
   ```
   Use `run_in_background: true`. Tell Piotr: sessions will appear in the panel as
   `TASK <PREFIX>-N` as they start; he can watch live and reopen any one later.
4. **On completion** (you get re-invoked when the background job exits) read the
   summary file printed in the output (`.claude/skills/mass-implement/.runs/run_*.summary`)
   and report in plain Polish:
   - which tasks went `DONE` (+ their session uuids for `--resume`),
   - if it stopped: **which task and the gate reason**, and the resume command for
     that session so Piotr can decide/finish there,
   - what is next in the queue.

## Mechanics / safety

- Children run with `--dangerously-skip-permissions` (headless can't prompt). They
  obey the base prompt: **DEV `.61` only, never PROD, never `git push` without
  approval** — they only *propose* commits. This is the one real risk: each child
  makes real DEV code/DB changes autonomously. That is the intended behavior of an
  auto run; use `--list` first if unsure.
- Children run **sequentially** (no DB/test races). A gate halts the rest.
- The full FAZA start-prompt is reused verbatim per task; mass-implement only pins
  "your ONE task is exactly <id>" + the `MASS_STATUS` marker contract on top.
- Run artifacts: `.claude/skills/mass-implement/.runs/` (run log, per-task logs,
  summary with the id→session-name→uuid→status map).

## Examples

```
/mass-implement prompt_b.md --list      # what would run for FAZA B
/mass-implement prompt_b.md B6-B10      # only B6..B10 (unchecked ones)
/mass-implement prompt_sf.md            # every unchecked SF task
```
