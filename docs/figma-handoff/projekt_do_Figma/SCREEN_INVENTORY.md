# SCREEN_INVENTORY

## Core Screens

- `#auth-overlay` - ekran logowania.
- `#game-app` - glowny shell gry po zalogowaniu.
- `#chat` - feed narracji i odpowiedzi AI.
- `.composer` - input i akcje wysylki.
- `#sheet-panel` - karta postaci / panel boczny.

## Overlays / Modals

- `#character-create-overlay` - tworzenie postaci.
- `#campaign-create-overlay` - tworzenie kampanii.
- `#history-summary-overlay` - podsumowanie historii.
- `#campaign-death-screen` - ekran smierci kampanii.

## Dynamic Views

- Thinking bubble (`#thinking-bubble`) podczas oczekiwania na stream.
- Streaming bubble (`#streaming-bubble`) podczas SSE.
- Combat host `#combat-panel-slot` (aktywny panel walki).
- Action popup `#action-popup` (rzut/akcja).
- Slash popup `#slash-popup` (autocomplete komend).

## Mobile Critical Areas

- Composer + keyboard overlap.
- Bottom-sheet behavior dla `#sheet-panel`.
- Sticky action buttons w combat.
- Modal max-height i scroll wewnetrzny.
