# 📱 AI-GM — Figma Mobile Handoff

This folder contains the complete specification package for the mobile-first redesign of the **AI-GM** frontend.

A Figma designer should read these documents in order before opening any design tool.

## How to use

1. **Run the Cursor prompt** in `CURSOR_PROMPT.md` to auto-generate all spec files from the live source code.
2. Share the generated folder with your Figma designer.
3. After design is complete, follow `12-implementation-guide.md` to integrate the new UI.

## Document Index

| File | Description |
|---|---|
| `CURSOR_PROMPT.md` | **← Start here.** Paste into Cursor Agent to generate all docs. |
| `00-project-overview.md` | What is AI-GM, tech stack, design goals |
| `01-screen-inventory.md` | Every screen, modal, and overlay with triggers |
| `02-component-library.md` | Every reusable component with HTML, CSS, JS behaviour |
| `03-navigation-flows.md` | Mermaid flowcharts for every user journey |
| `04-mobile-layout-spec.md` | Breakpoints, layout shell, typography, spacing, color tokens |
| `05-id-and-class-contracts.md` | ⚠️ HTML IDs/classes that must NEVER be renamed |
| `06-roll-card-anatomy.md` | Deep-dive on the Roll Card (most complex component) |
| `07-combat-panel-spec.md` | Combat UI specification (Phase 8A/8B) |
| `08-death-screen-spec.md` | Death/defeat screen specification |
| `09-character-wizard-spec.md` | Character creation wizard steps |
| `10-slash-commands-ux.md` | Slash command autocomplete UX |
| `11-accessibility-checklist.md` | WCAG requirements for the new design |
| `12-implementation-guide.md` | Developer guide: how to replace the frontend |
| `13-figma-file-structure.md` | Suggested Figma file organisation |

## Current Phase

🔴 **Phase 8B — Combat System Frontend** is the next phase after Figma handoff.
The combat UI (`07-combat-panel-spec.md`) should be designed as part of this package.

## Branch

Create new work on: `phase-8b-frontend-mobile`
