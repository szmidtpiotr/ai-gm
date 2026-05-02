# SPEC_UI_ADAPTATION

## Objective

Dopasowac obecny frontend AI-GM do projektu Figma (mobile-first), bez przepisywania logiki gry.

## Technical Context

- Frontend: static `index.html` + `styles.css` + vanilla JS modules.
- Backend: FastAPI, endpointy pod `/api/*`.
- Kluczowy runtime stan:
  - `ai-gm:playerAuth`
  - `ai-gm:selectedCampaignId`
  - `ai-gm:selectedCharacterId`
  - `ai-gm:sheetPanelOpen`
  - `ai-gm:llmSettingsCollapsedPref`

## Hard Constraints

- Zachowac wszystkie selektory z `DOM_CONTRACT.md`.
- Zachowac aktualne endpointy i ksztalt payloadow.
- Nie zmieniac kolejnosci ladowania skryptow w `index.html`.
- Zachowac obsluge:
  - streamingu SSE,
  - trybu combat,
  - modali (character/campaign/history/death).

## UX Scope

- Login overlay
- Main game shell (chat + composer + sheet panel)
- Campaign/character flows
- Combat panel i combat composer
- History summary modal
- Death screen
- Slash command popup

## Delivery Requirements for Figma Handoff

- Dwa breakpointy: 390 (primary mobile), 1280 (desktop reference).
- Tokens nazwane semantycznie (surface, text, accent, border, radius, spacing).
- Jasna specyfikacja komponentow:
  - states: default/hover/active/disabled/error
  - spacing
  - typography
  - iconography

## Acceptance Criteria

- Brak regresji funkcjonalnych w login/campaign/character/chat/combat.
- Brak poziomego scrolla na 320-390 px.
- Chat i composer stabilne przy otwartej klawiaturze mobilnej.
- Zgodnosc wizualna z Figma na kluczowych ekranach.
