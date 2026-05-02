# AI-GM UI Adaptation Handoff - Dark Fantasy Theme

**Date:** 2026-04-26  
**Type:** Visual Layer Adaptation (Non-Breaking)  
**Target:** Production Vanilla HTML/CSS/JS App  
**Scope:** CSS/Tokens/Minimal HTML - Zero JS Logic Changes

---

## Critical Constraints

### ✅ KEEP (Do Not Change)
- All backend API endpoints and contracts
- All DOM element IDs currently used by JS
- All JS event bindings and selectors
- Information architecture and user flows
- Feature set and functionality
- Vanilla HTML/CSS/JS stack

### 🎨 CHANGE (Visual Layer Only)
- CSS custom properties (design tokens)
- Visual styling (colors, spacing, typography)
- Layout classes (keeping same DOM structure)
- Additive HTML wrappers (non-breaking)

---

## Adaptation Strategy

This is a **visual-only redesign** from light/neutral UI to **dark fantasy theme** (Warhammer/Baldur's Gate inspired).

### Design Direction
- **Palette:** Aged parchment text (#f2eadc) on stone/charcoal backgrounds (#18120e, #0a0806)
- **Accents:** Candlelight gold (#b77a2b, #d4a857) for interactive elements
- **Typography:** System fonts, readable contrast ratios
- **Spacing:** Mobile-first 44px touch targets, 8px grid
- **Animations:** Subtle fades, no disruption to existing behavior

### Implementation Approach
1. **Phase 1:** CSS tokens only (theme.css variables)
2. **Phase 2:** Layout container classes
3. **Phase 3:** Component visual styling
4. **Phase 4:** Modal/overlay styling
5. **Phase 5:** Responsive breakpoints
6. **Phase 6:** Regression testing

---

## File Structure

### Files to Modify
```
frontend/
├── styles.css                  ← Primary adaptation target
├── css/combat.css              ← Combat-specific styling
└── index.html                  ← Minimal class additions only
```

### Files to Preserve (No Changes)
```
frontend/js/
├── main.js                     ← Keep all JS unchanged
├── ui.js
├── api.js
├── actions.js
├── events.js
├── app.js
├── character_wizard.js
├── combat_panel.js
├── combat_input.js
├── death_screen.js
└── slash_commands.js
```

---

## Implementation Sequence

### Step 1: CSS Token Migration (1-2 hours)
**Goal:** Replace color/spacing values with CSS custom properties

**Action:**
1. Add design tokens to `styles.css` at top:
```css
:root {
  /* Surface Colors */
  --bg: #0a0806;
  --panel: #18120e;
  --panel-2: #221a15;
  
  /* Text Colors */
  --text: #f2eadc;
  --muted: #b4a58d;
  
  /* Accent Colors */
  --accent: #b77a2b;
  --accent-light: #d4a857;
  --accent-dark: #8a5a1f;
  
  /* Status Colors */
  --danger: #b91c1c;
  --ok: #15803d;
  
  /* Chat Message Colors */
  --chat-player: #1e3a5f;
  --chat-gm: #2d4a2d;
  --chat-system: #5a5040;
  
  /* Spacing (8px grid) */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  
  /* Border */
  --radius: 12px;
  --border: rgba(183, 122, 43, 0.2);
}
```

2. Replace hardcoded hex values with `var(--token-name)`

**Regression Check:**
- [ ] Page still loads
- [ ] No console errors
- [ ] Layout unchanged (only colors shift)

---

### Step 2: Layout Container Classes (2-3 hours)
**Goal:** Update background colors and panel styles

**Target Selectors (from existing HTML):**
- `body` → `background: var(--bg);`
- `.app-shell` or main container → `background: var(--bg);`
- `.chat-container` → `background: var(--bg);`
- `.panel` or `.sidebar` → `background: var(--panel);`
- `.modal`, `.overlay` → `background: var(--panel-2);`

**DO NOT:**
- Change element IDs
- Remove classes used by JS
- Alter DOM structure

**Regression Check:**
- [ ] App shell renders correctly
- [ ] Panels maintain size/position
- [ ] Modals still open/close

---

### Step 3: Chat/Message Styling (3-4 hours)
**Goal:** Style message bubbles for dark theme

**Target Classes (preserve class names):**
```css
/* Player messages */
.message.player {
  background: var(--chat-player);
  color: var(--text);
  border-radius: var(--radius);
  padding: var(--space-3);
}

/* GM messages */
.message.gm {
  background: var(--chat-gm);
  color: var(--text);
}

/* System messages */
.message.system {
  background: var(--chat-system);
  color: var(--muted);
}

/* Roll cards */
.roll-card {
  background: var(--panel-2);
  border: 1px solid var(--accent);
  color: var(--accent-light);
}
```

**Regression Check:**
- [ ] Messages still render
- [ ] Streaming bubbles work
- [ ] Roll cards display correctly
- [ ] Archive toggle works

---

### Step 4: Combat Panel Styling (2-3 hours)
**Goal:** Adapt combat UI to dark theme

**File:** `frontend/css/combat.css`

**Target Selectors (preserve IDs):**
```css
#combat-ui {
  background: var(--panel);
  border: 1px solid var(--accent);
  color: var(--text);
}

#combat-attack-button {
  background: var(--accent);
  color: var(--bg);
}

#combat-flee-button {
  background: transparent;
  border: 1px solid var(--accent);
  color: var(--accent);
}

.hp-bar {
  background: #1a1410;
}

.hp-bar-fill {
  background: linear-gradient(to right, #15803d, #22c55e);
}
```

**Regression Check:**
- [ ] Combat panel appears on encounter
- [ ] Attack button triggers attack
- [ ] Flee button triggers flee
- [ ] HP bars update correctly
- [ ] Victory/defeat overlays show

---

### Step 5: Modal/Overlay Styling (2-3 hours)
**Goal:** Style modals for dark theme

**Target Overlays:**
- Login modal
- Character wizard
- Death screen
- Settings panel
- Character sheet panel

**Pattern:**
```css
.modal-overlay {
  background: rgba(10, 8, 6, 0.95);
}

.modal-content {
  background: var(--panel);
  border: 1px solid var(--accent);
  border-radius: var(--radius);
  color: var(--text);
}

.modal-header {
  border-bottom: 1px solid var(--border);
  color: var(--accent-light);
}

.modal-button-primary {
  background: var(--accent);
  color: var(--bg);
}

.modal-button-secondary {
  background: transparent;
  border: 1px solid var(--accent);
  color: var(--accent);
}
```

**Regression Check:**
- [ ] Login modal works
- [ ] Character wizard flow completes
- [ ] Death screen displays
- [ ] Settings panel opens/closes
- [ ] Character sheet panel shows stats

---

### Step 6: Responsive Tuning (1-2 hours)
**Goal:** Ensure mobile-first design works

**Breakpoints:**
```css
/* Mobile-first baseline: 375px */
@media (max-width: 640px) {
  /* Ensure 44px touch targets */
  button,
  input[type="submit"],
  .interactive {
    min-height: 44px;
  }
}

/* Desktop: 1024px+ */
@media (min-width: 1024px) {
  /* Maintain existing desktop layout */
}
```

**Regression Check:**
- [ ] Mobile (375px) - all features work
- [ ] Tablet (768px) - no layout breaks
- [ ] Desktop (1440px) - original layout preserved

---

## DOM Contract Preservation

### Critical IDs (DO NOT RENAME)

**Screens:**
- `#login-screen`
- `#character-creation`
- `#game-screen`
- `#death-screen`

**Components:**
- `#chat-messages`
- `#combat-ui`
- `#combat-actions`
- `#message-composer`
- `#character-sheet-button`
- `#settings-button`

**Interactive Elements:**
- `#username`
- `#password`
- `#character-name`
- `#message-input`
- `#send-button`
- `#combat-attack-button`
- `#combat-flee-button`

**Complete list in:** `DOM-CONTRACT-PRESERVATION.md` (see attached docs)

---

## API Contract Preservation

### Endpoints (Do Not Change)
```
POST   /api/auth/login
GET    /api/campaigns
POST   /api/campaigns
GET    /api/campaigns/{id}/character
POST   /api/campaigns/{id}/character
POST   /api/campaigns/{id}/turns
GET    /api/campaigns/{id}/combat
POST   /api/campaigns/{id}/combat/attack
POST   /api/campaigns/{id}/combat/flee
```

### Request/Response Formats
Keep existing JSON structures. No GraphQL, no new auth model.

---

## Regression Testing Checklist

### Must Pass Before Deploy

**Authentication:**
- [ ] Login form submits
- [ ] Auth token stored
- [ ] Protected routes work
- [ ] Logout clears session

**Campaign Management:**
- [ ] Campaign list loads
- [ ] Create campaign works
- [ ] Select campaign loads character
- [ ] Delete campaign works
- [ ] Reset campaign works

**Character Creation:**
- [ ] Wizard opens
- [ ] All 4 steps work
- [ ] Stats allocation works
- [ ] Character saves to backend
- [ ] Wizard closes on complete

**Chat Interface:**
- [ ] Messages render
- [ ] User can send messages
- [ ] Streaming responses appear
- [ ] Thinking bubbles show
- [ ] Archive toggle works
- [ ] Slash commands autocomplete

**Combat System:**
- [ ] Combat panel appears on encounter
- [ ] Attack button works
- [ ] Flee button works
- [ ] HP bars update
- [ ] Victory overlay shows loot
- [ ] Defeat triggers death screen

**Character Sheet:**
- [ ] Panel opens from button
- [ ] Stats display correctly
- [ ] HP shows current/max
- [ ] Skills list renders

**Settings:**
- [ ] Settings panel opens
- [ ] LLM model selector works
- [ ] Sound toggle works
- [ ] Settings save to localStorage

**Death Flow:**
- [ ] Death screen appears at HP=0
- [ ] Death summary loads
- [ ] Restart button works
- [ ] Main menu button works

---

## Implementation Diff Guide

### Example: Updating Chat Message Styles

**Before (styles.css):**
```css
.message {
  background: #ffffff;
  color: #000000;
  padding: 12px;
  border-radius: 8px;
}

.message.player {
  background: #e3f2fd;
  align-self: flex-end;
}

.message.gm {
  background: #f3e5f5;
  align-self: flex-start;
}
```

**After (styles.css with tokens):**
```css
.message {
  background: var(--panel-2);
  color: var(--text);
  padding: var(--space-3);
  border-radius: var(--radius);
}

.message.player {
  background: var(--chat-player);
  align-self: flex-end;
}

.message.gm {
  background: var(--chat-gm);
  align-self: flex-start;
}
```

**Changed:** Color values only  
**Preserved:** Class names, DOM structure, layout properties  
**JS Impact:** None (no selector changes)

---

## "No-Go" List

### ❌ DO NOT DO THESE

1. **Change JS API contracts** - Keep all existing endpoint calls
2. **Rename DOM IDs** - All IDs must stay exactly the same
3. **Remove classes used by JS** - Check `events.js` for bindings
4. **Alter DOM structure** - Keep parent/child relationships
5. **Change data attributes** - Preserve `data-*` attributes
6. **Modify event handlers** - Don't touch JS event logic
7. **Break streaming chat** - SSE parsing must work unchanged
8. **Hide features** - All existing features must remain visible
9. **Require new backend endpoints** - Use only existing API
10. **Introduce framework dependencies** - Stay vanilla HTML/CSS/JS

---

## Safe Changes Allowed

### ✅ YOU CAN DO THESE

1. **Add CSS custom properties** - New tokens in `:root`
2. **Update color values** - Change hex/rgba in CSS
3. **Modify spacing** - Update padding/margin values
4. **Add wrapper divs** - Non-breaking additive HTML
5. **Change typography** - Font family, size, weight
6. **Update border radius** - Visual polish
7. **Add box shadows** - Depth and elevation
8. **Modify animations** - CSS transitions/keyframes
9. **Update backgrounds** - Gradients, textures
10. **Polish hover states** - Interactive feedback

---

## Handoff Deliverables

### For Cursor AI Implementation

**Read in this order:**
1. `UI-ADAPTATION-HANDOFF.md` (this file)
2. `DOM-CONTRACT-PRESERVATION.md` - Complete ID list
3. `TOKEN-MAP-ADAPTATION.md` - Before/after color map
4. `IMPLEMENTATION-SEQUENCE.md` - Step-by-step guide

**Context Prompt for Cursor:**
```
This is a UI adaptation project for AI-GM production app.

CRITICAL CONSTRAINTS:
- Vanilla HTML/CSS/JS stack (no React/frameworks)
- Preserve ALL DOM IDs listed in DOM-CONTRACT-PRESERVATION.md
- Keep ALL backend API contracts unchanged
- Visual layer adaptation only (CSS tokens + minimal HTML)

APPROACH:
1. Add CSS custom properties to styles.css
2. Replace hardcoded colors with var(--tokens)
3. Update component styles following dark fantasy theme
4. Test regression checklist after each phase

THEME: Dark fantasy (Warhammer inspired)
- Aged gold (#b77a2b) on stone (#18120e)
- Parchment text (#f2eadc)
- All tokens in TOKEN-MAP-ADAPTATION.md

DO NOT:
- Change JS files
- Rename DOM IDs
- Modify API endpoints
- Break existing features

Continue following IMPLEMENTATION-SEQUENCE.md steps.
```

---

## Support Files

- `DOM-CONTRACT-PRESERVATION.md` - Full ID/class list
- `TOKEN-MAP-ADAPTATION.md` - Color/spacing token guide
- `API-INTEGRATION-ASSUMPTIONS.md` - Backend contract reference
- `SCREEN-INVENTORY-ADAPTATION.md` - Screen-by-screen visual specs
- `IMPLEMENTATION-SEQUENCE.md` - Detailed step-by-step
- `REGRESSION-CHECKLIST.md` - Testing matrix

---

**Status:** Ready for Implementation  
**Risk Level:** Low (visual-only, non-breaking)  
**Estimated Time:** 12-16 hours total
