# Phase 8A — Cursor ↔ Perplexity research notes

Branch: `combat-system-2.0` (Combat System 2.0).  
This file is for **open research**: Cursor records questions here; paste Perplexity answers in the green blocks.

---

## Context (read-only synthesis)

- `phase8a_implementation_plan.md` describes an `active_combat` model with fields such as **phase**, **turn_order**, **current_actor_id**, **loot_pool**, etc., and points to `backend/migrations/` plus a generated `active_combat_ddl.sql`.
- The current codebase already has **`backend/app/db/migrations/014_active_combat.sql`**, applied at startup via `run_app_sql_migrations()` in `main.py` (glob `*.sql`, `executescript`). `combat_service.py` and tests reference **`status`**, **`current_turn`**, **`round`**, **`combatants`**, not the exact naming from the long-form plan in every place.
- `step_1.1_database_migration.txt` repeats the safety checklist and migration requirements but does not define the canonical column list (it defers to `active_combat_ddl.sql`, which is **not present** in the repo tree searched from the workspace).

---

## Q1 — Doc vs repo: single source of truth

<span style="color:red"><strong>Cursor (for Perplexity)</strong><br />
Our Phase 8A written plan describes an <code>active_combat</code> table with lifecycle fields (e.g. phase, loot, actor indexing) that partly diverge from the already-shipped SQLite DDL in <code>backend/app/db/migrations/014_active_combat.sql</code> plus additive <code>ALTER</code> in admin migrations (<code>location_tag</code>). What is a practical workflow to keep <strong>product docs</strong>, <strong>ORM/service code</strong>, and <strong>SQLite migrations</strong> aligned so implementers do not follow an obsolete DDL? Should generated <code>active_combat_ddl.sql</code> live in-repo and be the only authority, or should docs reference the migration file path explicitly?</span>

<span style="color:green"><strong>Perplexity</strong><br />
<em>(Wklej tutaj odpowiedź z Perplexity.)</em></span>

---

## Q2 — SQLite migration strategy on every app boot

<span style="color:red"><strong>Cursor (for Perplexity)</strong><br />
The app runs every <code>*.sql</code> under <code>app/db/migrations/</code> with <code>executescript</code> at startup (idempotent <code>CREATE TABLE IF NOT EXISTS</code> / <code>CREATE INDEX IF NOT EXISTS</code>). What are the main risks compared to a numbered migration ledger (Alembic, goose, custom <code>schema_migrations</code> table)? Under what conditions is “glob + IF NOT EXISTS + ALTER in Python helpers” considered acceptable for a small FastAPI + SQLite service?</span>

<span style="color:green"><strong>Perplexity</strong><br />
<em>(Wklej tutaj odpowiedź z Perplexity.)</em></span>

---

## Q3 — Extending combat state: columns vs JSON

<span style="color:red"><strong>Cursor (for Perplexity)</strong><br />
Combat state today stores structured blobs in <code>combatants</code> and <code>turn_order</code> as TEXT (JSON). The roadmap adds loot pools, victory/defeat phases, and richer turn tracking. For SQLite at modest scale, what are trade-offs between <strong>new top-level columns</strong> (e.g. <code>loot_pool</code>, <code>phase</code>) versus <strong>versioned JSON inside <code>combatants</code></strong> with backward-compatible parsing in Python? Any patterns from game backends or CRDT-lite state you would recommend?</span>

<span style="color:green"><strong>Perplexity</strong><br />
<em>(Wklej tutaj odpowiedź z Perplexity.)</em></span>

---

## Q4 — Rollback story for shipped databases

<span style="color:red"><strong>Cursor (for Perplexity)</strong><br />
Step 1.1 asks for a reversible migration including <code>DROP TABLE</code> rollback. SQLite cannot easily “down” migrate data that was already written if we only ship forward scripts on boot. What is a sensible rollback policy for **already-deployed** solo-player DB files: snapshot before migrate, export combat row, or document “rollback = restore backup” only?</span>

<span style="color:green"><strong>Perplexity</strong><br />
<em>(Wklej tutaj odpowiedź z Perplexity.)</em></span>

---

## Access check (2026-04-24)

- **Local workspace path:** `docs/combat_system_2/step_1.1_database_migration.txt` — mode `0777`, readable/writable.
- **piotrszmidt@192.168.1.61:** `~/ai-gm/docs/combat_system_2/step_1.1_database_migration.txt` — `-rwxrwxr-x`, owner `piotrszmidt:piotrszmidt`. **No SSH permission fix was required.**

---

## Waiting on Perplexity

After you run the four prompts above in Perplexity, paste each answer into the matching **green** block. Cursor can then reconcile `phase8a_implementation_plan.md` / step files with code in a follow-up (only when you ask for edits).
