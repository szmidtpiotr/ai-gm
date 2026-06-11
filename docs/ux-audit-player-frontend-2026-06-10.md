# UI/UX Audit — AI-GM Text RPG Player Frontend

**Date:** 2026-06-10  
**Auditor:** Claude (AI agent)  
**URL:** https://aigm-dev.studio-colorbox.com/  
**Credentials:** demo / demo  
**Scope:** Player-facing frontend only (not admin panel)

---

## What Was Audited

| Screen | Mobile 390px | Tablet 768px | Desktop 1440px |
|---|---|---|---|
| Login | ✅ | ✅ | ✅ |
| Hero selection | ✅ | ✅ | ✅ |
| Campaign selection | ✅ | — | ✅ |
| Gameplay / narration | ✅ | ✅ | ✅ |

Screenshots saved to: `temp-img/audit_*.png`

---

## Executive Summary

The mobile experience is genuinely good in some areas — the dark fantasy aesthetic works, the color palette is cohesive, and the login screen is atmospheric. But the gameplay screen (the one users spend 95% of time in) has a critical wall-of-text problem that kills immersion and makes scanning impossible on a small screen. Desktop is a glorified phone wrapper — zero desktop adaptation.

---

## 1. Mobile Usability Issues

### P0 — Critical blockers

**Gameplay text is an undifferentiated wall.**  
The narration renders as one or two massive paragraphs of dense Polish text. No visual anchors, no paragraph breaks styled differently, no GM vs player turn distinction in the narration body. On a 390px screen, reading a fantasy text requires heavy cognitive work. The GM is a character — they should have visual presence, not be an anonymous text blob.

**Base font size is 15px** (`--font-size-base: 15px`) — below iOS accessibility minimum of 16px. On a 390px retina screen this is readable but fatiguing over a long session. The `xs` size is 11px — used in several secondary elements — which is unacceptable on mobile.

**Input bar text truncates** — "Co robisz? Możesz pisać swot" — "swot" appears cut off. The full phrase doesn't fit the placeholder width. Also: "swot" is either a typo or truncation of "swobodnie" — either way it reads as broken to a player.

**Status text in gameplay header is tiny.** "MD — MISTRZ GRY TURA" indicator at ~9.5px is illegible without zoom.

### P1 — High impact

**No visual scroll feedback in gameplay.** Long narrations don't give any cue that there's content above/below. No scroll progress indicator, no fade-at-edge treatment. Players on mobile won't know they missed text.

**Bottom navigation icons in gameplay** (Graj / Powrót / Ekwipunek) are text + icon but very tight. At 390px all three compete for space. Tapping the wrong one mid-combat is easy.

**Floating voice button** (yellow pill, bottom-right) overlaps content on several screens. On heroes screen it hovers over the "Zaproś znajomego" button zone. On gameplay it's present but its purpose is unclear without a label.

**HP bar in header** — the `12/12 HP` is present as text but there's no visual bar, no color state (red when low). Critical information for a game player.

### P2 — Polish issues

- Hero cards show `[TEST]` prefix on demo account — not a bug per se, but players see it
- Campaign description text cuts off mid-word (`"Bohater budzi się w nieznanym miejscu bez a..."`) — ellipsis truncation with no expand
- Delete button (red trash) on hero cards is flush against the card's right edge — easy to fat-finger while scrolling

---

## 2. Visual Hierarchy & Information Density

**Login screen: ✅ Best screen in the app.** Dark fantasy background, clear form, readable button. The atmospheric book/candle image works perfectly. The emoji icons (💀📜🔥) are charming but using emoji as UI chrome is unreliable (platform rendering varies, accessibility poor, no consistent sizing).

**Heroes screen: ✅ Good.** Card layout is clear. Status badges ("W KAMPANII" / "WOLNY") are legible. Information density is appropriate. The "Historia" button is nice. Main issue: cards have no tap feedback beyond the default — no ripple or highlight state.

**Campaign selection: ✅ Good structure, weak copy.** Three card types (Nowa / Gotowa / Loch) are clear distinctions. Active campaign section below works. Card descriptions are helpful but cut off.

**Gameplay screen: ❌ Hierarchy is flat.**
- Every paragraph has identical weight
- No GM "speech" vs narration distinction
- No visual marker for "turn start / turn end"
- No contextual info visible (location? time of day?) — the ToD system exists in CSS (`data-tod-mode`) but it's not surfaced visually in a way a player can read
- The header icon row (map/journal/inventory/settings) uses emoji/text characters, not SVG icons — inconsistent sizes

---

## 3. Game Feel / Immersion Gaps

**The game has good bones for atmosphere but the experience feels like a chat app, not a game.**

The biggest immersion gap: there's no separation between what the GM says and what happens in the world. A good text RPG needs:
- GM's narration styled as narration (prose, atmospheric)
- Player's action clearly echoed back
- System messages (dice rolls, combat outcomes) styled distinctly — currently the code has `--user-bubble` and `--gm-bubble` CSS vars but from the gameplay screenshot this bubble system isn't visible in the narration body; it appears as continuous prose

**No tactile response** for sending a turn. After typing and submitting, what happens? Is there a loading state while the LLM generates? From the screenshots there's no visible AI "thinking" indicator between turns.

**No ambient world-building signals.** The background image for gameplay is a dungeon (`bg-dungeon.jpg`) but it's barely visible behind the dark text overlay. There's a `data-tod-period` system (Noc/etc.) in the CSS that should change the atmosphere — but whether it actually does anything visible is unclear from static screenshots.

**No sound design cues** — for a text RPG, subtle audio (ambient dungeon sound, dice roll SFX on combat, dramatic sting when something bad happens) would dramatically increase immersion. This is currently zero.

**Empty black space on desktop replaces world-building opportunity.** A desktop user gets a 420px column floating in dark gradient. That empty space could be: location art, an ambient map, the GM's portrait, atmospheric particles — anything.

---

## 4. Desktop Experience Delta

**Brutal assessment: desktop is not a real experience.**

The CSS intentionally caps at `max-width: 420px` (non-game screens) / `max-width: 600px` (game screen) on 1024px+. On a 1440px monitor the game sits in a narrow column with ~400px of black on each side.

This is a philosophical choice (phone-form-factor as aesthetic — like a "retro handheld RPG"), but it reads as an incomplete port, not a design decision, because there's no decorative frame, no ambient content, no intentional use of the empty space.

**What the blank space could be:**
- A persistent world map panel (left)
- Character stats sidebar (right, collapsed to icons normally)
- Atmospheric scene illustration that changes with location
- Background particle effects tied to time-of-day

**Desktop-only UX failures:**
- Font sizes optimized for 390px become too small for someone 60cm from a monitor
- Touch target sizes (44px min) are appropriate for mobile but desktop needs hover states + keyboard shortcuts
- No keyboard shortcut to submit turn (Ctrl+Enter / Enter) — may exist in JS but not discoverable

---

## 5. Prioritized Issue List

### P0 — Fix before any new features

| # | Issue | Screen | Impact |
|---|---|---|---|
| 1 | Wall-of-text gameplay: no visual differentiation between turns, GM voice, player echo | Gameplay | Core experience broken |
| 2 | Base font 15px, xs font 11px — below mobile readability minimum | All | Accessibility + fatigue |
| 3 | No AI "thinking" indicator between turn submission and LLM response | Gameplay | Player thinks app froze |
| 4 | Input placeholder truncated / broken copy ("swot") | Gameplay | Professionalism |

### P1 — High priority

| # | Issue | Screen | Impact |
|---|---|---|---|
| 5 | HP has no visual bar / no danger state (red when <30%) | Gameplay header | Game-critical info invisible |
| 6 | No scroll feedback in narration (long texts invisible below fold) | Gameplay | Players miss story |
| 7 | Floating voice button overlaps interactive content | Heroes, Campaigns | Accidental taps |
| 8 | Emoji used as UI icons (💀📜🔥⚔📜) — inconsistent rendering, no accessibility | Login, Heroes | Platform reliability |
| 9 | Status line "MD — MISTRZ GRY TURA" at 9.5px | Gameplay | Unreadable |
| 10 | Zero desktop layout — 400px+ of empty black on 1440px | Desktop | Not a desktop app |

### P2 — Should fix

| # | Issue | Screen | Impact |
|---|---|---|---|
| 11 | No turn/time-of-day visual feedback despite CSS system existing | Gameplay | Missed atmosphere |
| 12 | Campaign description truncated, no expand | Campaign select | Context loss |
| 13 | Delete button flush to card edge, easy to fat-finger | Heroes | Accidental deletion |
| 14 | No ambient audio / SFX system | All | Immersion gap |
| 15 | Bottom nav 3 items competing at 390px | Gameplay | Navigation errors |
| 16 | No ripple/tap feedback on hero cards | Heroes | Feels unresponsive |
| 17 | Background art barely visible in gameplay — dark overlay too aggressive | Gameplay | Aesthetic waste |

---

## Redesign Recommendation

If doing a full redesign, the strongest direction is **split-panel on desktop, card-first on mobile**.

### Mobile
Keep the current dark fantasy color system (it's genuinely good). Fix typography. Replace emoji with SVG icon set (Lucide or custom). Make narration feel like a scroll/parchment — actual visible GM "voice" styling, player action as a distinct style. Add typing indicator.

### Desktop
Use the sidebar space. Left panel = world context (location, map miniature, time of day, active conditions). Center = narration scroll. Right = character quick-stats, last roll. This transforms it from "phone app on big screen" into a proper RPG client.

### Typography
Current Inter is clean but cold. Lora (already loaded) for GM narration body, Cinzel (already loaded) for headers/titles, Inter for UI chrome only. The fonts are already imported — they're just not being used in gameplay.

### Color System
`--accent: #c9a54a` (gold), deep dark browns, the `--gm-bubble` green / `--user-bubble` blue are good starting points. Don't throw them away in a redesign.

---

## What Was NOT Audited

- Combat UI (no live combat encounter reachable via Playwright)
- Death screen
- Inventory / equipment panel (panel slide-in)
- New hero creation wizard
- Admin panel (out of scope)
