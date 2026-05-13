# Phase 10: Frontend Revamp (Mobile-First)

**Start:** 2026-05-08  
**Status:** In Progress  
**Location:** `frontend/front/`  
**URL:** `https://aigm-dev.studio-colorbox.com/front/`

## Goal

Create a mobile-first alternative frontend based on Figma designs v18-20. The new frontend runs in parallel with the legacy frontend (`frontend/index.html`) and will eventually replace it.

## Design Principles

- **Mobile-first:** Touch-friendly, slide-up panels, responsive breakpoints
- **Dark theme:** `#1a1a2e` background, `#c9a54a` gold accent
- **Tab-based character sheet:** Stats / Skills / Inventory tabs
- **Clean UX:** Minimal chrome, focus on narrative gameplay

## Tech Stack

- Vanilla HTML/CSS/JS (no build step)
- CSS Grid/Flexbox layout
- CSS variables for theming
- Reuses backend API from legacy frontend

## Files

| File | Description |
|------|-------------|
| `frontend/front/index.html` | Main HTML structure |
| `frontend/front/css/styles.css` | Design system (~800 lines) |
| `frontend/front/js/app.js` | Application logic |
| `frontend/front/img/` | Figma reference screens |
| `frontend/nginx.conf` | Route `/front/` |

## Related Tasks

- **T28.5** — Initial mobile-first frontend (DONE)
- **T29** — XP spending UI (pending, may be implemented here)
