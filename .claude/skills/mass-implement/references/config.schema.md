# `.claude/mass-implement.json` — config schema

Project invariants the orchestrator reads. Created by `/mass-implement --init`.
All paths are relative to the repo root (the directory containing `.claude/`).

| Field | Type | Required | Meaning |
|---|---|---|---|
| `version` | int | yes | Schema version (currently `1`). |
| `run_host` | object | yes | Where children run. `{"type":"local"}` or `{"type":"ssh","host":"user@ip","remote_root":"/path","git_user":"name"}`. |
| `github` | object | no | `{"owner":"...","repo":"..."}` — for issue-backed task ids. Omit for projects without GitHub issues. |
| `branch` | string | yes | Working branch children commit to (never the default/release branch). |
| `checklists.faza` | object | no | FAZA mode: `file` (checklist path), `section_prefix` (e.g. `## FAZA`), `id_pattern` (`{PREFIX}` placeholder, e.g. `{PREFIX}[0-9]+[a-z]?`). |
| `checklists.list` | object | no | LIST mode: `file`, `region_prefix` (e.g. `## KOLEJNOŚĆ`), `id_prefix` (e.g. `FIX`), optional `renumber_script`. |
| `child.spec_files` | string[] | yes | Files the child MUST read first (rules + spec). |
| `child.pipeline` | string[] | yes | Verification pipeline, in order (e.g. `["/tdd","/code-review","/playwright-test-report"]`). |

At least one of `checklists.faza` / `checklists.list` must be present.

## Example (AI-GM)
```json
{
  "version": 1,
  "run_host": { "type": "ssh", "host": "claude@192.168.1.61",
                "remote_root": "/home/piotrszmidt/ai-gm", "git_user": "piotrszmidt" },
  "github": { "owner": "szmidtpiotr", "repo": "ai-gm" },
  "branch": "develop",
  "checklists": {
    "faza": { "file": "notes.md", "section_prefix": "## FAZA", "id_pattern": "{PREFIX}[0-9]+[a-z]?" },
    "list": { "file": "fix_list.md", "region_prefix": "## KOLEJNOŚĆ", "id_prefix": "FIX",
              "renumber_script": "scripts/renumber_fix_list.sh" }
  },
  "child": {
    "spec_files": ["CLAUDE.md", "game_mechanics.md"],
    "pipeline": ["/tdd", "/code-review", "/playwright-test-report"]
  }
}
```

## Example (minimal, local, no GitHub)
```json
{
  "version": 1,
  "run_host": { "type": "local" },
  "branch": "dev",
  "checklists": { "list": { "file": "TASKS.md", "region_prefix": "## Tasks", "id_prefix": "T" } },
  "child": { "spec_files": ["README.md"], "pipeline": ["/test-driven-development"] }
}
```
