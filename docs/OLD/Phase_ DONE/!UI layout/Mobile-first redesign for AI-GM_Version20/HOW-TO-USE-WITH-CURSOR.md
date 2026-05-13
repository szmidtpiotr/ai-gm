# How to Use AI-GM Version 18 with Cursor

**Quick handoff guide for AI coding assistants**

## Step 1: Open in Cursor

```bash
cursor /path/to/ai-gm
```

Or drag the folder into Cursor IDE.

## Step 2: Read These 3 Files First

Read in this exact order before making any changes:

### 1. HANDOFF.md (2 minutes)
- Version 18 scope and what's included/excluded
- File structure map
- Version bump policy (when to increment version)
- Known Figma Make limitations

### 2. src/imports/01-screen-inventory.md (3 minutes)
- Complete screen-to-file mapping
- Which file controls which user-visible screen
- Backend endpoints (currently mock with localStorage)

### 3. src/imports/05-id-and-class-contracts.md (2 minutes)
- Stable DOM IDs that must never be renamed
- Critical for test automation and vanilla JS compatibility
- Breaking these contracts requires version bump

**Total reading time: ~7 minutes**

## Step 3: Understand the Context

Paste this into Cursor chat for instant context:

```
This is AI-GM Version 18, a Polish dark fantasy text RPG.

READ FIRST (in order):
1. HANDOFF.md - version scope & policies
2. src/imports/01-screen-inventory.md - screen map
3. src/imports/05-id-and-class-contracts.md - stable DOM IDs

DESIGN SYSTEM:
- Dark fantasy theme (Warhammer/Baldur's Gate inspired)
- Aged gold (#b77a2b) on stone/parchment backgrounds
- All design tokens in src/styles/theme.css
- NEVER hardcode hex colors in JSX (use CSS variables)

TECH STACK:
- Vite 6 + React 19 + TypeScript 5
- Tailwind CSS v4
- Radix UI primitives (shadcn/ui)
- localStorage for persistence (no backend)
- Polish language UI

CODE ORGANIZATION:
- Screens: src/app/components/screens/
- Shared components: src/app/components/
- Game logic: src/lib/game-utils.ts
- Design tokens: src/styles/theme.css
- Documentation: src/imports/

CONVENTIONS:
- All screens have stable #id attributes (see 05-id-and-class-contracts.md)
- Design tokens only via CSS variables (var(--accent), var(--panel))
- Mobile-first (320px-390px primary target)
- Polish text throughout UI

CURRENT STATE:
✅ Login with username/password
✅ Campaign management (list, create, select)
✅ 4-step character creation wizard
✅ Skill exchange system (18 skills)
✅ Main game screen with chat
✅ Combat system with dark UI
✅ Character sheet with swipe tabs
✅ Death/restart flow

Continue implementing features following established patterns.
```

## Step 4: Start Developing

### Adding New Features

Follow this pattern:

1. **Check existing screens** for similar patterns
2. **Reuse components** from `src/app/components/` and `ui/`
3. **Use design tokens** from `theme.css` (never hardcode colors)
4. **Add stable IDs** for testability
5. **Document** in `src/imports/01-screen-inventory.md`

### Example: Adding a New Screen

```typescript
/**
 * [Screen Name]
 *
 * Purpose: [One-line description]
 * User Actions: [Main interactions]
 * Related Spec: src/imports/[XX-spec-name.md]
 * Stable IDs: #screen-id, #button-id
 */

import { useState } from "react";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

export function NewScreen({ onComplete }: NewScreenProps) {
  return (
    <div id="new-screen" className="min-h-screen bg-background">
      <Card className="p-6 bg-[var(--panel)] border-accent/20">
        {/* Use design tokens, not hex colors */}
        <h1 className="text-accent-light">Polish Title Here</h1>
      </Card>
    </div>
  );
}
```

Then:
- Add to `GamePhase` type in `App.tsx`
- Add routing in `App.tsx` return block
- Update `src/imports/01-screen-inventory.md`

### Modifying Existing Screens

1. **Read the header comment** in the screen file
2. **Check related spec** (e.g., `src/imports/09-character-wizard-spec.md`)
3. **Preserve stable IDs** listed in header comment
4. **Use existing patterns** for consistency

### Theme Changes

1. **Edit** `src/styles/theme.css` only
2. **Never hardcode** hex colors in JSX
3. **Test** on mobile viewport (390px)
4. **Bump version** to 19 in `HANDOFF.md` if changing tokens

## Step 5: Common Tasks

### "How do I add a new campaign feature?"

1. Check `src/app/App.tsx` for campaign state management
2. Look at `campaign-select.tsx` and `campaign-create.tsx` for patterns
3. localStorage keys follow: `campaigns_{username}` and `campaign_{username}_{id}`
4. Update both in sync

### "How do I modify the combat system?"

1. Read `src/imports/07-combat-panel-spec.md`
2. Edit `src/app/components/combat-ui.tsx`
3. Game logic in `src/lib/game-utils.ts` (dice, damage, etc.)
4. Preserve IDs: `#combat-ui`, `#combat-attack-button`, `#combat-flee-button`

### "How do I change the character creation flow?"

1. Read `src/imports/09-character-wizard-spec.md`
2. Edit `src/app/components/screens/character-creation.tsx`
3. 4 steps currently: Name → Stats → Skills → Backstory
4. Skill exchange drawer uses 18 available skills (see `allAvailableSkills` array)

### "How do I integrate a real backend?"

1. Read `IMPLEMENTATION.md` section "Mock vs Real API Integration"
2. Create `src/lib/api-client.ts` with fetch calls
3. Replace localStorage calls in screens with `apiClient.*` methods
4. Set `VITE_API_BASE_URL` in `.env`

## Step 6: Running & Testing

```bash
# Dev server (auto-starts in Figma Make)
pnpm dev

# Type check
pnpm exec tsc --noEmit

# Production build (outside Figma Make)
pnpm build
pnpm preview
```

**Test flow:**
1. Login → any username/password
2. Create campaign → "Test Campaign"
3. Character creation → all 4 steps
4. Game → send message, trigger combat
5. Character sheet → click user icon, swipe tabs

## Step 7: Before Committing

- [ ] No hardcoded hex colors (use `var(--accent)` etc.)
- [ ] Stable IDs preserved (check `05-id-and-class-contracts.md`)
- [ ] Mobile tested (390px viewport)
- [ ] Polish text used (no English in UI)
- [ ] Design tokens follow `theme.css`
- [ ] Screen documented in `01-screen-inventory.md`

## Cursor-Specific Tips

### Use "@" mentions
```
@HANDOFF.md what's the version policy?
@01-screen-inventory.md which file has the login screen?
@theme.css what's the accent color?
```

### Multi-file edits
```
Update the character creation wizard:
@character-creation.tsx add a new step
@01-screen-inventory.md document the change
```

### Context from specs
```
I want to modify combat. Show me:
@07-combat-panel-spec.md
@combat-ui.tsx
@game-utils.ts rollDice function
```

## Common Mistakes to Avoid

❌ **DON'T:** Hardcode `#b77a2b` in JSX  
✅ **DO:** Use `text-accent` or `var(--accent)`

❌ **DON'T:** Rename `#character-creation` to `#char-create`  
✅ **DO:** Keep stable IDs unchanged (listed in 05-id-and-class-contracts.md)

❌ **DON'T:** Change design tokens without version bump  
✅ **DO:** Edit `theme.css` and bump to Version 19 in HANDOFF.md

❌ **DON'T:** Add English text in UI  
✅ **DO:** Use Polish throughout (e.g., "Zaloguj się" not "Login")

❌ **DON'T:** Create `/pages` or `/routes` folders  
✅ **DO:** Use `/screens` for top-level views

## Need Help?

- **Architecture questions:** See `IMPLEMENTATION.md`
- **Setup issues:** See `QUICKSTART.md` common errors
- **Screen changes:** Check `src/imports/01-screen-inventory.md`
- **Design system:** See `src/styles/theme.css`
- **Game mechanics:** See `src/lib/game-utils.ts`

## Quick Reference Card

```
THEME TOKENS
------------
--accent         #b77a2b (aged gold)
--panel          #18120e (stone)
--text           #f2eadc (parchment)
--muted          #b4a58d (faded ink)

SCREEN FILES
------------
login-screen.tsx          Auth entry
campaign-select.tsx       Campaign list
campaign-create.tsx       New campaign
character-creation.tsx    4-step wizard
game-screen.tsx           Main play area
death-screen.tsx          Game over

SHARED COMPONENTS
-----------------
character-sheet-tabs.tsx  Stats drawer with swipe
combat-ui.tsx             Battle interface
chat-message.tsx          Message bubbles
message-composer.tsx      Input bar

UTILITIES
---------
lib/game-utils.ts         Dice, combat, loot
lib/utils.ts              cn() helper

PERSISTENCE
-----------
campaigns_{username}                 → Campaign list
campaign_{username}_{campaignId}     → Full state
```

---

**You're ready to build!** 🚀

Start with small changes to understand the codebase, then tackle larger features.  
All documentation is self-contained in this package - no external dependencies.
