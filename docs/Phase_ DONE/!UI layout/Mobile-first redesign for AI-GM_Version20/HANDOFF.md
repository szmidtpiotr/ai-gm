# AI-GM Version 18 Handoff

**Version:** 18  
**Date:** 2026-04-26  
**Status:** Complete  
**Figma File:** N/A (built directly in code)

## What's In Scope

Version 18 includes:
- Complete authentication flow (login with username/password)
- Campaign management (list, create, select)
- 4-step character creation wizard with skill exchange
- Main game screen with chat, combat, and character sheet
- Death/restart flow
- Mobile-first responsive design with desktop support
- Dark fantasy theme (aged gold + stone textures)

## What's Out of Scope

- Real authentication/backend integration (uses localStorage only)
- Multiplayer/real-time features
- Advanced AI/LLM integration (placeholder responses)
- Payment/subscription features
- Analytics/telemetry
- Accessibility audit (basic support only)

## Design System Ownership

**CRITICAL:** Do not modify the dark fantasy theme without bumping to Version 19.

Core design tokens are defined in `src/styles/theme.css`:
- Color palette: `--accent` (aged gold #b77a2b), `--panel` (stone), `--text` (parchment)
- Typography scale: `--text-xs` through `--text-xl`
- Spacing: 8px grid system (`--space-1` through `--space-16`)
- Border radius: `--radius` (12px)

Any changes to these tokens constitute a design system change and require version increment.

## File Structure Map

```
/workspaces/default/code/
├── HANDOFF.md              (this file)
├── IMPLEMENTATION.md       (technical stack & architecture)
├── QUICKSTART.md          (setup commands)
├── .env.example           (environment template)
├── package.json
├── src/
│   ├── app/
│   │   ├── App.tsx                              (main router/orchestrator)
│   │   ├── components/
│   │   │   ├── screens/
│   │   │   │   ├── login-screen.tsx            (auth entry)
│   │   │   │   ├── campaign-select.tsx         (campaign list)
│   │   │   │   ├── campaign-create.tsx         (new campaign flow)
│   │   │   │   ├── character-creation.tsx      (4-step wizard)
│   │   │   │   ├── game-screen.tsx             (main play area)
│   │   │   │   └── death-screen.tsx            (game over)
│   │   │   ├── character-sheet-tabs.tsx        (drawer with stats/skills/inventory)
│   │   │   ├── combat-ui.tsx                   (battle interface)
│   │   │   ├── chat-message.tsx                (message bubbles)
│   │   │   ├── message-composer.tsx            (input bar)
│   │   │   └── ui/                             (shadcn components)
│   │   └── ...
│   ├── lib/
│   │   ├── game-utils.ts                       (dice, combat, loot generators)
│   │   └── utils.ts                            (cn helper)
│   ├── styles/
│   │   └── theme.css                           (design tokens)
│   └── imports/                                (documentation)
│       ├── 00-project-overview.md
│       ├── 01-screen-inventory.md
│       ├── 02-component-library.md
│       ├── 03-navigation-flows.md
│       ├── 04-mobile-layout-spec.md
│       ├── 05-id-and-class-contracts.md
│       └── feature-specs/
│           ├── character-creation-wizard.md
│           ├── combat-panel.md
│           └── skill-exchange.md
└── ...
```

## Version Bump Policy

Increment version when:
- Adding/removing screens
- Changing design tokens in theme.css
- Modifying stable DOM IDs listed in 05-id-and-class-contracts.md
- Breaking changes to data structures in localStorage
- Changing navigation flow state machine

Do NOT bump for:
- Bug fixes within existing screens
- Internal refactoring that preserves contracts
- Adding new optional features without removing old ones

## Known Limitations (Figma Make Environment)

1. **No Backend:** All data stored in localStorage; no real API integration
2. **No Build Process:** Cannot run `npm run build` or `vite build` in this environment
3. **Dev Server Only:** Preview runs on internal dev server, no production deployment
4. **No Database:** Campaign/character data exists only in browser storage
5. **Mock Combat:** Combat logic is deterministic randomness, not balanced

These limitations are inherent to the Figma Make environment and documented explicitly here rather than implied.

## Handoff to Cursor

To give this codebase to Cursor AI:

1. Extract/download the complete `/workspaces/default/code` folder
2. Open in Cursor IDE
3. Read these files first (in order):
   - `HANDOFF.md` (this file)
   - `src/imports/01-screen-inventory.md` (screen map)
   - `src/imports/05-id-and-class-contracts.md` (stable DOM contracts)
4. Run `pnpm install && pnpm dev` (see QUICKSTART.md)

## Contact

Built for AI-GM Polish fantasy RPG project.  
Original design conversations retained in session history.
