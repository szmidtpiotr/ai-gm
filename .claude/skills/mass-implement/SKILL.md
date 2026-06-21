---
name: mass-implement
description: >-
  Auto-run a whole checklist task-by-task, one real named resumable Claude session
  per task. Config-driven (.claude/mass-implement.json) and drop-in across projects.
  Two modes: FAZA mode ("/mass-implement L [L6-L10]" or "/mass-implement faza B") for
  phase checklists, and LIST mode ("/mass-implement fix_list.md [#767|P0|3-7]") for
  issue/bug lists. Use when the user says "/mass-implement <file|faza> [selector]",
  "wdroż całą fazę/listę", "lec zadanie po zadaniu", or wants one start-prompt applied
  to every unchecked task without pasting it per session. First-time setup in a new
  project: "/mass-implement --init". Each task = its own session "TASK <PREFIX>-N" in
  the /resume picker; auto-advances, STOPS on a gate.
---

# mass-implement v2

Fans one verification pipeline across every unchecked task in a checklist — each task in
its **own real, named, resumable** `claude` session (visible in `/resume`). Auto-advances
on success, **STOPS on a gate**. Config-driven and project-agnostic.

## Architecture (what makes it generic + robust)

- **`.claude/mass-implement.json`** — project invariants (host, repo, branch, checklist
  files, id grammar, verify pipeline). No hardcode. Schema: `references/config.schema.md`.
- **Built-in child-prompt template** (`references/prompt-template.md`) — the shared ~80%
  skeleton. **No per-faza prompt files.**
- **Inline ZAKRES block** — the per-faza/list ~20% (decisions, out-of-scope, exceptions,
  id→work mapping) lives in a `<!-- MASS-ZAKRES:START/END -->` block at the top of the
  task doc, next to the tasks it governs. Template: `references/zakres-template.md`.
- **Preflight (fail-loud, never silent-wrong):** merge markers / unparseable region →
  **refuse the whole run** with the offending line; an ambiguous task line → **skip +
  report** (never silently dropped, never aborts the run).
- **Per-task already-done check:** the child first verifies whether the task is already
  implemented (checkbox can lie). If so it ticks it and emits `DONE-ALREADY` — no rework.

## Invocation

```
/mass-implement <@milestone|file|faza-token> [selector] [--list]
/mass-implement --init        # first-time setup in a new project
```

- **MILESTONE mode** (preferred — GitHub is the single source of truth) — arg1 is
  `@Name` or `milestone:Name`; a partial name resolves to the full milestone title
  (`@Multiplayer` → `Multiplayer (Faza 5)`). Tasks come **straight from GitHub**
  (`gh issue list --milestone`), open issues only, in ascending number order
  (= dependency order). Skips issues labelled `gate`/`later`/`blocked`/`deferred`
  or whose title carries `(later)` / leading `later —`. **Never** skips `backlog`
  (that is the repo's default To-Do state). `fix_list.md` is NOT a task source here —
  it only carries the static `MASS-ZAKRES` instruction block. Selector: omitted (all
  actionable) · `#799` (one issue) · `799-810` (number range).
- **LIST mode** — `<file>` is a task list (e.g. `fix_list.md`). Selector: omitted (all
  unchecked) · `#767` (one issue) · `P0` (a `### P0` section) · `5` (global index) · `3-7`
  (index range). *Legacy — prefer MILESTONE mode; mirroring milestone→fix_list is the
  drift the new mode removes.*
- **FAZA mode** — `<file>` carries a `FAZA X` token, OR pass a **bare token**: `L`, `SF`,
  `faza B`. Selector: `L6-L10` · `L6` · `6-10` · `6` · omitted. Tasks read from the faza
  section of the configured checklist.
- `--list` — print the plan and exit; spawn nothing. **Always preview with `--list` first.**

## First-time setup — `--init` (agent-driven)

When the user runs `/mass-implement --init`:
1. **Detect:** `bash .claude/skills/mass-implement/scripts/init.sh detect` → repo root,
   branch, GitHub owner/repo, checklist candidates. Also read CLAUDE.md for the test
   command / host / environment rules.
2. **Ask the user** (plain language, one at a time) only the gaps you couldn't infer:
   which file is the task list (and/or the faza checklist), how a change is verified
   (the pipeline), whether commands run locally or over SSH.
3. **Write `.claude/mass-implement.json`** from the schema (`references/config.schema.md`)
   using detected + answered values. Drop a `references/zakres-template.md` block at the
   top of the task doc for the user to fill (or fill it yourself if you know the scope).
4. **Validate:** `bash .claude/skills/mass-implement/scripts/init.sh validate`, then
   `… orchestrate.sh <file> --list` to confirm the plan parses.
5. Report in plain language: "gotowe — odpalaj `/mass-implement <plik> [selektor]`".

Relationship: `workflow-loop` authors the plan/checklist + ZAKRES; `--init` wires this
autorunner to them.

## Steps for the agent (a normal run)

1. **Parse args.** No file/token and not `--init` → ask. `--init` → run the setup flow above.
2. **Preview the plan** (catches wrong file/selector + shows skipped/ambiguous):
   ```bash
   bash .claude/skills/mass-implement/scripts/orchestrate.sh <file|token> [selector] --list
   ```
   Stop here if the user passed `--list`. If preflight refuses (merge markers etc.), relay
   the offending lines and stop — do not work around it.
3. **Launch the real run in the background** (children take minutes each; never foreground):
   ```bash
   setsid bash .claude/skills/mass-implement/scripts/orchestrate.sh <file|token> [selector] </dev/null
   ```
   Use `run_in_background: true`. If the outer `setsid` trips `Stream closed`, retry without
   it (plain `bash …`); the per-child `setsid` inside still protects the task sessions.
   Tell the user sessions appear as `TASK <PREFIX>-N` as they start.
4. **On completion** read the summary (`.runs/run_*.summary`) and report in plain language:
   tasks `DONE`/`DONE-ALREADY` (+ session uuids for `--resume`); if it stopped — which task
   and the gate reason + its `claude --resume <uuid>`; any `SKIPPED-AMBIGUOUS` lines; what's
   next in the queue.

## Status markers (child's last output line)

`DONE` · `DONE-ALREADY` (was implemented, just ticked) · `GATE — <reason>` (owner decision /
spec↔code contradiction / unmet hard dep) · `ERROR — <reason>`. Orchestrator adds
`SKIPPED-AMBIGUOUS` to the summary for unparseable task lines.

## Mechanics / safety

- Children run `--dangerously-skip-permissions` (headless) and obey the project rules from
  `child.spec_files`: target env only, never prod/release branch, **propose commits, never
  `git push`**. Each child makes real autonomous changes — that's the point; use `--list` first.
- Children run **sequentially** (no DB/test races). A gate halts the rest.
- Run artifacts in `.claude/skills/mass-implement/.runs/` (logs + id→session→uuid→status map).

## Examples

```
/mass-implement --init                  # set up a new project
/mass-implement fix_list.md P0 --list   # preview all unchecked P0
/mass-implement fix_list.md #743        # just issue #743
/mass-implement L L6-L10                # faza L, tasks 6..10 (bare token)
/mass-implement faza SF --list          # preview all unchecked SF tasks
/mass-implement @Multiplayer --list     # MILESTONE mode: preview all actionable
/mass-implement @Multiplayer 799-810    # milestone Multiplayer, issues #799..810
/mass-implement milestone:FIX #748      # milestone "Bugi i poprawki (FIX)", one issue
```
