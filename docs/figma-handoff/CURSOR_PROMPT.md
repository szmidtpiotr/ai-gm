# 🎯 CURSOR PROMPT — AI-GM Figma Mobile Handoff Documentation Generator

> **Copy this entire prompt into Cursor AI (Agent mode) and run it from the repo root.**
> It will auto-generate all files inside `/docs/figma-handoff/` based on the live frontend source.

---

## TASK

You are a senior front-end architect preparing a **complete Figma handoff package** for a mobile-first redesign of the **AI-GM** text-based RPG web app.

The goal: a Figma designer with **zero knowledge of the codebase** must be able to:
1. Understand every screen and every interactive component.
2. Design a polished, mobile-first (375 px baseline, 390 px ideal) UI.
3. Hand back assets that can be **dropped directly into the existing HTML/JS/CSS** with minimal restructuring.

You MUST read the following source files before generating any documentation:

```
frontend/index.html
frontend/styles.css
frontend/css/combat.css
frontend/js/ui.js
frontend/js/actions.js
frontend/js/app.js
frontend/js/api.js
frontend/js/character_wizard.js
frontend/js/combat_panel.js
frontend/js/combat_input.js
frontend/js/death_screen.js
frontend/js/slash_commands.js
frontend/js/events.js
frontend/js/main.js
frontend/js/state.js
```

After reading every file, generate the documents listed below inside `/docs/figma-handoff/`.

---

## FILES TO GENERATE

### 1. `00-project-overview.md`
High-level description of the product:
- What AI-GM is (Polish-language fantasy RPG, AI as Game Master)
- Primary audience & usage context (mobile players, single-session & ongoing campaigns)
- Tech stack summary relevant to the designer (Vanilla JS, no framework, HTML IDs are stable API contracts — **do NOT rename any HTML id or class that is referenced in JS**)
- Design goals: dark fantasy aesthetic, fast one-thumb reachability on mobile, no desktop-only affordances
- Languages: UI is Polish, stat abbreviations remain English (STR/DEX/CON/INT/WIS/CHA/LCK)
- List all 15 JS source files with a one-line role description each

### 2. `01-screen-inventory.md`
Exhaustive list of every distinct screen / view / overlay in the app. For each one:
- **Screen name** (in English and Polish)
- **Trigger**: what causes it to appear (e.g. `auth-overlay` visible on load if not logged in)
- **HTML container**: exact `id` or selector
- **State flags** that control visibility (CSS `hidden`, `aria-hidden`, `display:none`, JS toggles)
- **Dismissal method** (close button id, backdrop click, programmatic only)
- **Mobile concern**: note any known overflow / z-index / scroll issue to solve

Screens to document (minimum):
1. Auth overlay (`#auth-overlay`)
2. Main game view (`#game-app`) — collapsed settings
3. Main game view — expanded settings (`#llm-controls`)
4. Chat / narrative area (`#chat`) — normal messages
5. Chat — roll card message (`__AI_GM_ROLL_V1__` marker)
6. Chat — thinking bubble (dynamically inserted by ui.js)
7. Sheet panel (`#sheet-panel`) — character stats
8. Sheet panel — combat panel slot (`#combat-panel-slot` visible)
9. Composer area — normal mode
10. Composer area — combat mode (Attack + Flee buttons)
11. Character creation modal Step 1 (name + background + archetype)
12. Character wizard multi-step (steps 2-N driven by `character_wizard.js`)
13. Campaign creation modal
14. Campaign death screen (`#campaign-death-screen`)
15. History summary modal
16. Action popup (`#action-popup` — Rzuć kość / Akcja)
17. Archive toggle bar

### 3. `02-component-library.md`
For **every reusable UI component**, document:
- Component name
- HTML snippet (copy exact markup from source, add inline comments)
- CSS classes / custom properties used
- JS behaviour: what event listeners are attached, what state changes
- Mobile spec: minimum tap target (44×44 px), thumb zone, font size floor (14 px)
- States: default / hover / active / disabled / loading
- Figma notes: suggest component variant names

Components to document (minimum — find more by reading source):
- `PrimaryButton` (`#send-btn`, `#player-login-btn`)
- `SecondaryButton` (class `.secondary`)
- `DangerButton` (class `.danger`)
- `CombatButton` — Attack (`.combat-input-btn--attack`) and Flee (`.combat-input-btn--flee`)
- `RollButton` (`#contextual-roll-btn`, `#dice-btn`)
- `ChatMessage` — narrator bubble (class from ui.js `renderMessage`)
- `ChatMessage` — player bubble
- `ChatMessage` — system / OOC
- `RollCard` — full anatomy (die face, stat, modifier, DC, verdict badge)
- `ThinkingBubble` — animated dots
- `StatusDot` (`.status-dot`) — Backend / Ollama / Loki
- `StatBlock` — one stat row in character sheet (STR … LCK)
- `SkillRow` — skill name + rank pips
- `ArchetypeCard` (`.archetype-card` — Warrior / Scholar)
- `ActionPopup` — 2-button overlay
- `ArchiveToggleBar`
- `ComposerTextarea` (`#input`)
- `CampaignSelector` dropdown + action buttons
- `LLMSettingsPanel` — collapsed vs expanded
- `ModalOverlay` — generic wrapper
- `DeathCard` — full anatomy
- `CombatPanel` — HP bar, enemy name, initiative tracker

### 4. `03-navigation-flows.md`
Mermaid flowcharts for every user journey:
1. **First visit → play**: Load → Auth → Select/Create Campaign → Create Character (wizard steps) → Chat
2. **Return visit**: Load → Auth (auto-login if token) → Resume campaign → Chat
3. **Combat loop**: Narrative turn → GM emits Roll Initiative → Roll card → Attack/Flee buttons appear → Attack → Roll Attack → Hit/Miss → Damage → Enemy HP update → Enemy death / Player incapacitation
4. **Character sheet inspection**: Chat → tap 👤 → Sheet panel slides in → stat/skill inspection → close
5. **History summary**: Chat → 📜 Historia → modal → AI regenerate
6. **Settings expand**: tap Settings → LLM panel expands → change provider/model → Connect → collapse
7. **Death flow**: HP ≤ 0 → Campaign death screen → reveal secret → dismiss

For each flow: annotate which **HTML element** triggers each transition and which **JS function** handles it (read source to find exact function names).

### 5. `04-mobile-layout-spec.md`
Complete responsive layout specification:

#### Breakpoints
| Name | Width | Notes |
|---|---|---|
| Mobile S | 320 px | minimum supported |
| Mobile M | 375 px | design baseline |
| Mobile L | 390–430 px | iPhone 14–16 range |
| Tablet | 768 px | optional stretch goal |

#### Layout Architecture (describe for each breakpoint)
For mobile: **single-column, full-viewport-height app shell**

```
┌─────────────────────────┐  ← 100dvh
│  TOP BAR                │  status dots + Settings toggle + Logout
│  [collapse: LLM panel]  │  hidden by default, slides down on tap
├─────────────────────────┤
│                         │
│  CHAT FEED              │  flex-grow, overflow-y scroll
│  (narrative messages)   │  scroll-anchor: bottom
│                         │
├─────────────────────────┤
│  COMPOSER               │  sticky bottom
│  [textarea + actions]   │  resizes on focus (avoid keyboard occlusion)
└─────────────────────────┘
```

**Sheet panel on mobile**: slides in as a bottom sheet (80% height), NOT a side panel.
**Combat panel on mobile**: replaces or overlays top bar during combat.

#### Safe Areas
- Use `env(safe-area-inset-bottom)` for composer padding (iPhone notch).
- Use `env(safe-area-inset-top)` for top bar.

#### Touch Targets
- All interactive elements: minimum 44×44 px.
- Buttons in composer row: minimum 48 px height.
- Roll card verdict badge: minimum 36 px height tap area.

#### Typography Scale
| Token | Size | Weight | Usage |
|---|---|---|---|
| `--text-xs` | 11 px | 400 | Debug, muted hints |
| `--text-sm` | 13 px | 400 | Sheet labels, status |
| `--text-base` | 15 px | 400 | Chat text (narrator) |
| `--text-md` | 16 px | 500 | Player input, buttons |
| `--text-lg` | 18 px | 600 | Modal headings |
| `--text-xl` | 22 px | 700 | Death screen title |

#### Spacing System (8-px grid)
`4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 px`

#### Color Tokens (extract from `styles.css` CSS custom properties)
List every `--` variable found in styles.css with its current value and a semantic alias suggestion, e.g.:
- `--bg` → `color/surface/base`
- `--border` → `color/border/default`
- (find all remaining vars by reading styles.css)

### 6. `05-id-and-class-contracts.md`
> ⚠️ CRITICAL for handoff: This file tells the designer **which HTML IDs and class names must never change** because JavaScript references them directly.

For every JS file, extract every `document.getElementById`, `querySelector`, `querySelectorAll`, `addEventListener` call that targets a string selector. Group by screen. Output as a table:

| HTML id / class | JS file | Function | What breaks if renamed |
|---|---|---|---|
| `#send-btn` | actions.js | `initSendButton` | Send action stops working |
| `#chat` | ui.js | `appendMessage` | All messages fail to render |
| ... (find all ~80+ selectors) | | | |

At the bottom, list all CSS custom properties (`--variable`) that are also referenced in JS (e.g. for dynamic theme switching) — these must be preserved by name.

### 7. `06-roll-card-anatomy.md`
Deep-dive on the Roll Card component (this is the most complex UI element):
- Exact HTML structure emitted by `ui.js` `renderRollCard()` (copy the template with annotations)
- All verdict states with Polish labels and suggested icon/color:
  - `✅ SUKCES` — green
  - `❌ PORAŻKA` — red  
  - `⚡ TRAFIENIE KRYTYCZNE` — gold (nat 20)
  - `💀 KRYTYCZNA PORAŻKA` — dark red (nat 1)
- DC badge labels: Łatwe / Średnie / Trudne / Ekstremalne / Legendarne
- Dice face visual spec: d20 polygon SVG or icon font, large (56 px), shows rolled number
- Modifier display: `+3` / `-1` formatting
- Stat abbreviation badge: `STR` / `DEX` etc. — English, uppercase
- Animation suggestions: dice roll entrance (300 ms ease-out, slight scale bounce)
- Mobile sizing: card max-width 100%, padding 16 px, verdict badge full-width on mobile

### 8. `07-combat-panel-spec.md`
Full specification of the combat UI (Phase 8A/8B):
- `#combat-panel-slot` — where it is injected in DOM, when it becomes visible
- Combat panel anatomy: enemy name, enemy HP bar, player HP echo, initiative order, turn indicator
- `#composer-combat-send-slot` — Attack + Flee buttons: position, size, color, disabled states
- `#combat-debug-status` — should be **hidden in production design** (debug only)
- State transitions: `display:none` → visible when `active_combat` exists in backend
- Mobile: combat panel as a sticky top banner (shows enemy name + HP bar always visible during combat)
- Suggested Figma frames: Combat — Enemy Turn, Combat — Player Turn, Combat — Victory, Combat — Defeat

### 9. `08-death-screen-spec.md`
Full specification of the death/defeat screen:
- `#campaign-death-screen` — full-screen overlay with backdrop
- `#campaign-death-inner` — card content injected by `death_screen.js`
- Content anatomy: character name, cause of death, **secret revealed** (never shown before death), epitaph text, restart CTA
- Close button `#campaign-death-close-btn` behaviour
- Design tone: cinematic, dark, emotional — suggest gothic/medieval typography, candlelight color palette
- Mobile: full-bleed overlay, vertically centered card, swipe-down to dismiss suggestion

### 10. `09-character-wizard-spec.md`
Step-by-step specification of the character creation wizard:
- Step 1: Name + Background textarea + Archetype grid (Warrior / Scholar cards)
- Subsequent steps (read `character_wizard.js` to enumerate all steps): stat distribution, skill selection, identity (appearance / personality / flaw / bonds / secret)
- `#character-wizard-panel` — dynamic content host
- Nav: Back button `#character-wizard-back`, no explicit Next (each step auto-advances or has inline submit)
- Stat distribution rules: sum locked, min 8, max 18 — UI must show running total
- Skill swap rules: max 5 swaps, sum unchanged — UI must show swap counter
- Secret field: MUST be visually marked as "hidden from others" — suggest lock icon, dimmed style
- Mobile: each wizard step = full-screen modal page, swipe-left to advance, swipe-right = back

### 11. `10-slash-commands-ux.md`
Documentation of the slash command autocomplete UI:
- Trigger: typing `/` in `#input` textarea
- Autocomplete dropdown: position (above textarea), max items shown, keyboard navigation
- Commands to show (read `slash_commands.js` for full list with descriptions)
- `/helpme` — OOC mode indicator: suggest a visual badge in the composer (e.g. `[OOC]` pill)
- `/sheet` — opens sheet panel
- `/mem [query]` — memory query, suggest loading indicator in chat
- Mobile UX: dropdown should appear above keyboard, max 4 items visible, large tap targets

### 12. `11-accessibility-checklist.md`
Accessibility requirements the Figma design must respect:
- All modals: `role="dialog"`, `aria-modal="true"`, focus trap on open, return focus on close
- Status dots: must have visible text label (not dot-only) — already present as `.status-dot-label`
- Roll cards: `aria-live="polite"` region — design must not hide verdict text in image-only format
- Color contrast: all text on dark backgrounds ≥ 4.5:1 (WCAG AA)
- Touch targets: ≥ 44×44 px for all interactive elements
- Keyboard: Tab order must follow visual reading order
- Animations: respect `prefers-reduced-motion` — all entrance animations must have a no-motion fallback
- Language: `lang="pl"` on `<html>` — Figma prototype should reflect Polish copy
- List every `aria-*` attribute currently in index.html and note whether the design must preserve or can change it

### 13. `12-implementation-guide.md`
Instructions for the developer receiving the Figma design:
- How to export design tokens from Figma to CSS custom properties
- CSS variable naming convention to follow
- Which files to replace vs which to keep (`index.html` structure must be preserved; only CSS and template strings in JS can change)
- How to handle the bottom sheet pattern for the sheet panel on mobile (suggest CSS `transform: translateY` with transition)
- Keyboard avoid pattern: use `visualViewport` API resize event to adjust composer bottom padding
- Combat panel injection point: `#combat-panel-slot` — designer must provide empty slot container in layout
- Roll card: rendered as innerHTML by ui.js — designer must export the HTML template string, not a static frame
- Testing checklist after implementation: 19 UI tests in `tests/`, run them after CSS swap
- Branch strategy: create `phase-8b-frontend-mobile` from `phase-8-combat-system`

### 14. `13-figma-file-structure.md`
Suggested Figma file organisation the designer should follow:

```
AI-GM Mobile Redesign
├── 📐 Design System
│   ├── Colors (tokens)
│   ├── Typography
│   ├── Spacing & Grid
│   └── Icons
├── 🧩 Components
│   ├── Buttons (Primary / Secondary / Danger / Combat)
│   ├── Chat Messages (Narrator / Player / System / Roll Card)
│   ├── Combat Panel
│   ├── Sheet Panel
│   ├── Death Screen
│   ├── Modals (Campaign / Character / History)
│   └── Composer
├── 📱 Screens — Mobile 390px
│   ├── 00 Auth / Login
│   ├── 01 Game — Chat (idle)
│   ├── 02 Game — Chat (combat active)
│   ├── 03 Sheet Panel (bottom sheet)
│   ├── 04 Character Wizard (step 1–N)
│   ├── 05 Combat — Player Turn
│   ├── 06 Combat — Enemy Turn
│   ├── 07 Roll Card (all 4 verdict states)
│   ├── 08 Death Screen
│   ├── 09 Campaign Create Modal
│   ├── 10 History Summary Modal
│   └── 11 LLM Settings Panel (expanded)
├── 🔄 Prototype Flows
│   ├── First Visit Flow
│   ├── Combat Loop
│   └── Death Flow
└── 📋 Handoff Notes
    └── (link back to this /docs/figma-handoff/ folder)
```

For each screen frame, designer must annotate:
- Frame name matching this spec
- All interactive hotspots with target frame
- Component instance names matching `02-component-library.md`
- Redline spacing using 8-px grid
- All text layers using token names from `04-mobile-layout-spec.md`

---

## GENERATION RULES

1. **Read source files first** — do not hallucinate function names, CSS classes, or HTML ids. Extract them from actual source.
2. Every code snippet must be **copied from source**, not reconstructed.
3. HTML id and class names in all documents must match **exactly** what is in `index.html` and CSS files.
4. Polish UI strings must be copied verbatim (e.g. `Wyślij`, `Atak`, `Ucieczka`, `Rzuć kość`).
5. Each generated file must begin with a YAML front-matter block:
   ```yaml
   ---
   doc: [filename without extension]
   version: 1.0.0
   generated: [today's date]
   source_files: [list of files read]
   ---
   ```
6. Where the source is ambiguous or a function is not yet implemented (e.g. Phase 8B combat UI), add a `> ⚠️ NOT YET IMPLEMENTED — design placeholder needed` callout.
7. After generating all files, output a `README.md` inside `/docs/figma-handoff/` that lists all files with one-line descriptions and links.

---

## OUTPUT SUMMARY

After completing all files, print:
```
✅ Figma Handoff Documentation generated:
- 00-project-overview.md
- 01-screen-inventory.md
- 02-component-library.md
- 03-navigation-flows.md
- 04-mobile-layout-spec.md
- 05-id-and-class-contracts.md
- 06-roll-card-anatomy.md
- 07-combat-panel-spec.md
- 08-death-screen-spec.md
- 09-character-wizard-spec.md
- 10-slash-commands-ux.md
- 11-accessibility-checklist.md
- 12-implementation-guide.md
- 13-figma-file-structure.md
- README.md
Total: 15 files in /docs/figma-handoff/
```
