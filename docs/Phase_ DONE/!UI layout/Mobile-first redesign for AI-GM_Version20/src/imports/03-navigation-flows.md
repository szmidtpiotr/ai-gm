---
doc: 03-navigation-flows
version: 1.0.0
generated: 2026-04-26
source_files:
  - frontend/index.html
  - frontend/styles.css
  - frontend/css/combat.css
  - frontend/js/ui.js
  - frontend/js/actions.js
  - frontend/js/app.js
  - frontend/js/api.js
  - frontend/js/character_wizard.js
  - frontend/js/combat_panel.js
  - frontend/js/combat_input.js
  - frontend/js/death_screen.js
  - frontend/js/slash_commands.js
  - frontend/js/events.js
  - frontend/js/main.js
  - frontend/js/state.js
---

# Navigation Flows

Every Figma prototype link should map to one of these journeys. Element IDs in labels are implementation contracts.

## First Visit To Play

```mermaid
flowchart TD
  A[Load page] --> B[DOMContentLoaded]
  B --> C[initPlayerAuthGate()]
  C --> D[#auth-overlay visible]
  D --> E[#player-login-btn click]
  E --> F[POST /api/auth/login]
  F --> G[bootstrap()]
  G --> H[loadCampaigns()]
  H --> I{Campaign exists?}
  I -->|No| J[#create-campaign-btn / #campaign-create-overlay]
  I -->|Yes| K[#campaign-select]
  J --> L[createCampaignFromForm()]
  K --> M[loadCharacters()]
  L --> M
  M --> N{Character exists?}
  N -->|No| O[#character-create-overlay step 1]
  O --> P[createCharacterFromForm()]
  P --> Q[enterCharacterCreationWizard()]
  Q --> R[Stats -> Skills -> Identity]
  R --> S[characterWizardFinalize()]
  N -->|Yes| T[loadTurns()]
  S --> T
  T --> U[#chat + .composer playable]
```

## Return Visit

```mermaid
flowchart TD
  A[Load page] --> B[initPlayerAuthGate()]
  B --> C{localStorage ai-gm:playerAuth?}
  C -->|Yes| D[_setAuthedUiVisible true]
  D --> E[bootstrap()]
  E --> F[loadUserLlmSettings()]
  F --> G[loadCampaigns()]
  G --> H[loadCharacters()]
  H --> I[loadTurns()]
  I --> J[renderTurnsToChat()]
  C -->|No| K[#auth-overlay]
```

## Combat Loop

```mermaid
flowchart TD
  A[Narrative turn] --> B{GM starts combat or /atak used}
  B --> C[combatPanel.render()]
  C --> D[#combat-panel-slot visible]
  D --> E[combatInput.syncWithCombat()]
  E --> F{current_turn}
  F -->|player| G[#composer-combat-attack / #composer-combat-flee visible]
  G --> H[_onAttack() or _onFlee()]
  H --> I[/combat/resolve-attack or /combat/flee]
  I --> J[buildCombatRollCardHtml()]
  J --> K[triggerCombatNarration()]
  K --> L[GM SSE narrative]
  L --> M{combat ended?}
  M -->|No| E
  M -->|Victory| N[loot popup -> victory overlay]
  M -->|Defeat| O[defeat overlay or death save prompt]
```

Trigger elements/functions:

- `#composer-combat-attack` -> `CombatInput.init()` -> `combatPanel._onAttack()`.
- `#composer-combat-flee` -> `combatPanel._onFlee()`.
- Enter in `#input` during player combat turn -> `triggerPlayerAttackFromEnter()`.
- Enemy turn -> `combatInput._triggerEnemyTurnFromInput()`.

## Character Sheet Inspection

```mermaid
flowchart TD
  A[#chat] --> B[#dice-btn click]
  B --> C[setSheetPanelOpen()]
  C --> D[renderCharacterSheetPanel()]
  D --> E[#sheet-panel shown]
  E --> F[#dice-btn click again]
  F --> G[#sheet-panel hidden]
```

Mobile prototype should show this as a bottom sheet, even though current implementation uses a side panel on wide screens.

## History Summary

```mermaid
flowchart TD
  A[#history-summary-btn] --> B[openHistorySummaryModal()]
  B --> C[#history-summary-overlay]
  C --> D[loadHistorySummaryModalContent()]
  D --> E[#history-summary-body]
  E --> F[#history-summary-regenerate-btn]
  F --> G[POST /history/summary]
  C --> H[#history-summary-close or backdrop]
  H --> I[closeHistorySummaryModal()]
```

## Settings Expand

```mermaid
flowchart TD
  A[#llm-settings-toggle-btn] --> B[initLlmSettingsCollapse click handler]
  B --> C[setLlmControlsCollapsed()]
  C --> D{collapsed?}
  D -->|Yes| E[#llm-controls-body hidden]
  D -->|No| F[#llm-controls-body visible]
  F --> G[#test-ollama-btn]
  G --> H[connectLlmSettings()]
  H --> I[loadHealth + loadModels]
```

## Death Flow

```mermaid
flowchart TD
  A[turns/stream or loadTurns] --> B{HTTP 410?}
  B -->|Yes| C[showCampaignDeathScreen()]
  C --> D[GET /death-summary]
  D --> E[#campaign-death-inner DeathCard]
  E --> F[#death-start-new-btn]
  F --> G[setCampaignModalOpen true]
  E --> H[#campaign-death-close-btn / backdrop / Escape]
  H --> I[dismissCampaignDeathScreen()]
```

## Replaceable Flow Notes

Keep flow entry points stable: login, campaign select, character wizard, chat send, sheet toggle, combat attack/flee, settings toggle, and death close. Future features can add new branches, but should not remove these canonical routes without updating this document and `05-id-and-class-contracts.md`.
