# Figma Handoff Package (Local Only)

This folder is intentionally ignored by git (`figma-handoff/` in `.gitignore`).

Purpose:
- Provide a clean context package for Figma / Figma Make.
- Keep design notes and UI constraints close to the current codebase.
- Let you copy/paste one concise brief instead of sharing entire repository history.

How to use:
1. Open files in this folder.
2. Copy `FIGMA_BRIEF.md` into Figma Make prompt/context.
3. If needed, also copy selected sections from `UI_SPEC.md`.
4. Build layout in Figma, then send the frame URL back here for code implementation.

Recommended update flow:
- After major frontend change, update this package.
- Keep naming in Figma aligned with names in `COMPONENT_MAP.md`.
