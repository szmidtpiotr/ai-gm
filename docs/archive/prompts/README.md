# Archived FAZA/fix start-prompts

These per-phase start-prompts (`prompt_b.md`, `prompt_l.md`, `prompt_fix_mass.md`, …)
were used by **mass-implement v1**, which carried the full prompt skeleton in each file.

**mass-implement v2** replaced them with:
- a single built-in template (`.claude/skills/mass-implement/references/prompt-template.md`), and
- a small inline `<!-- MASS-ZAKRES -->` block at the top of each task doc (notes.md / fix_list.md).

FAZA mode now takes a bare token instead of a prompt file: `/mass-implement L L6-L10`.

Kept here for audit/history only — not read by any tool. Doc mentions of `prompt_X.md`
elsewhere (notes.md, game_mechanics.md) are historical references to this archive.
