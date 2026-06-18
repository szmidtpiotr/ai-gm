---
name: mass-implement
description: >-
  Auto-run a whole checklist task-by-task, one real named resumable Claude
  session per task. Two modes: FAZA mode ("/mass-implement prompt_b.md [B6-B10]"
  — FAZA start-prompt applied to notes.md tasks) and LIST mode
  ("/mass-implement fix_list.md [#767|P0|3-7]" — fix_list.md issues via
  prompt_fix_mass.md). Use when Piotr says "/mass-implement <file> [selector]",
  "wdroż całą fazę/listę", "lec zadanie po zadaniu", or wants a start-prompt
  applied to every unchecked task without pasting it per session. Each task = its
  own session named "TASK X-N" in the /resume picker; auto-advances, STOPS on a gate.
---

# mass-implement

Replaces the manual loop: *paste prompt_X.md → rename session "TASK X-N" → run one
task → STOP → open new session → repeat*. One command fans the FAZA start-prompt
across every unchecked task, each in its **own real, named, resumable** `claude`
session that shows up in the `/resume` picker so Piotr can reopen any single task
later and finish verification in the exact session it was done.

## Invocation

```
/mass-implement <file> [selector] [--list]
```

The orchestrator auto-detects the mode from `<file>`:

**FAZA mode** — `<file>` is a FAZA start-prompt containing a `FAZA X` token
(`prompt_b.md`, `prompt_sf.md`, …):
- `[selector]` = task window: `B6-B10`, `B6`, `6-10`, `6`. Omitted = all unchecked.
- FAZA prefix (B / SF / HI / L …) auto-derived from the `FAZA X` token; task list
  parsed from `notes.md → ## FAZA X` (the source of truth for `[ ]`/`[x]`).

**LIST mode** — `<file>` is a task-list with no `FAZA X` token (`fix_list.md`):
- `[selector]` addresses one or more tasks:
  - omitted → all unchecked
  - `#767` → the task for issue **#767**
  - `P0` … `Pn` → all unchecked tasks under the `### P0` section
  - `5` → the task with global index **5**
  - `3-7` → tasks with global index **3..7**
- Tasks parsed from the `## KOLEJNOŚĆ IMPLEMENTACJI` region (lines like
  `- [ ] 5. #767 — …`). On every run the file is re-numbered 1..n in priority order
  via `scripts/renumber_fix_list.sh` so indices stay stable & visible (checked tasks
  keep their number, so ranges don't shift as work gets done). Child prompt =
  `prompt_fix_mass.md`; task id = `FIX<issue>`; session = `TASK FIX-<issue>`.

`--list` — preview the plan only; spawn nothing (works in both modes).

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

1. **Parse args** from the user's `/mass-implement` line. If no file → ask which.
   Note: `fix_list.md #767` means file=`fix_list.md`, selector=`#767` (LIST mode).
2. **Preview the plan** — run list mode and show Piotr the ordered task list, so he
   sees exactly what will run and can catch a wrong file/selector:
   ```bash
   bash .claude/skills/mass-implement/scripts/orchestrate.sh <file> [selector] --list
   ```
   If the user passed `--list`, stop here.
3. **Launch the real run in the background** (children take many minutes each;
   never foreground — it would blow the Bash timeout). Run from the project root.
   The orchestrator already wraps each **child** in `setsid env -u CLAUDE*` so the
   per-task session survives a SIGHUP. Wrapping the **orchestrator** in an outer
   `setsid … </dev/null` adds protection if Piotr closes the launching session:
   ```bash
   setsid bash .claude/skills/mass-implement/scripts/orchestrate.sh <file> [selector] </dev/null
   ```
   Use `run_in_background: true`. **Caveat:** the outer `setsid` can trip a
   `Tool permission request failed: Error: Stream closed` in some harness states —
   if that happens, retry the launch **without** the outer `setsid` (plain
   `bash …orchestrate.sh <file> [selector]` with `run_in_background: true`); the
   per-child `setsid` inside the orchestrator still protects the task sessions.
   Tell Piotr: sessions appear in the panel as `TASK <PREFIX>-N` as they start.
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
# FAZA mode
/mass-implement prompt_b.md --list      # what would run for FAZA B
/mass-implement prompt_b.md B6-B10      # only B6..B10 (unchecked ones)
/mass-implement prompt_sf.md            # every unchecked SF task

# LIST mode (fix_list.md)
/mass-implement fix_list.md #767        # just issue #767
/mass-implement fix_list.md P0          # all unchecked P0 tasks
/mass-implement fix_list.md 9-12 --list # preview index range 9..12
/mass-implement fix_list.md             # every unchecked task on the list
```
