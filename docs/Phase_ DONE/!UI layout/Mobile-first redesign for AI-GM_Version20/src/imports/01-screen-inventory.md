---
doc: 01-screen-inventory
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

# Screen Inventory

Use this as the canonical frame list for Figma. Each screen should be designed at 390 px width first, with a 375 px check and 320 px stress pass.

| Screen | Polish Name | Trigger | HTML Container | Visibility State | Dismissal | Mobile Concern |
|---|---|---|---|---|---|---|
| Auth overlay | Logowanie | App load without stored `ai-gm:playerAuth` | `#auth-overlay` | `style.display = flex/none`, `aria-hidden` | Successful login | Full-screen login must center, avoid keyboard clipping |
| Main game collapsed | Gra | Successful login/bootstrap | `#game-app` | `style.display = block/none` | Logout | Should be 100dvh shell, not max-width desktop card |
| Settings expanded | Ustawienia LLM | `#llm-settings-toggle-btn` click | `#llm-controls` / `#llm-controls-body` | `.llm-controls--collapsed` | Same toggle | Panel should slide down, not push chat too far below fold |
| Chat feed | Czat / Narracja | `loadTurns`, `addMessage`, streaming response | `#chat` | `.chat`, `.archive-hidden` | N/A | Main scroll region, bottom anchored, thumb reachable |
| Roll card message | Karta rzutu | Text marker `__AI_GM_ROLL_V1__` or combat marker | `.roll-card.roll-card--light` inside `.message` | Rendered by `buildRollCardHtml()` / `buildCombatRollCardHtml()` | N/A | Card must fit 100% width and remain readable in bubbles |
| Thinking bubble | GM myśli | Before SSE stream starts | `#thinking-bubble` | Dynamic `.message.assistant.thinking` | Replaced/removed programmatically | Keep fixed width to avoid jitter; respect reduced motion |
| Streaming bubble | Odpowiedź GM | First SSE token | `#streaming-bubble` | `.message.assistant.streaming` | Finalized by stream end | No reflow jitter during token updates |
| Sheet panel | Karta postaci | `#dice-btn` click | `#sheet-panel`, `#sheet-panel-body` | `.play-area.sheet-open`, `aria-hidden` | Same button | Redesign as bottom sheet on mobile, not side panel |
| Sheet with combat slot | Karta + walka | Active combat state | `#combat-panel-slot` | `display:block`, `aria-hidden=false` | Combat end or sync null | Combat summary should become sticky top banner on mobile |
| Composer normal | Pole akcji | Default playable state | `.composer`, `#input`, `.composer-actions` | `display:grid`, enabled textarea | N/A | Sticky bottom, safe-area padding, keyboard-aware |
| Composer combat | Walka: akcje | Active combat and player turn | `#composer-combat-send-slot` | `display:flex`, `aria-hidden=false`, `#send-btn` hidden | Combat end/enemy turn | Attack/Flee must be large bottom actions |
| Character creation step 1 | Tworzenie postaci | Campaign selected without character | `#character-create-overlay`, `#character-create-step-1-wrap` | `display:flex`, `aria-hidden=false` | Close/backdrop only before blocking wizard | Full-screen modal on mobile, archetype cards stack |
| Character wizard stats | Kreator: statystyki | Step 1 submit and character POST success | `#character-wizard-host`, `#character-wizard-panel` | `window.state.charCreationWizard.step === 2` | Back to step 1 | Dense +/- controls need 44 px targets |
| Character wizard skills | Kreator: umiejętności | Confirm stats | `#character-wizard-panel` | `step === 3` | Back to stats | Skill rows can overflow; use one-column mobile list |
| Character wizard identity | Kreator: tożsamość | Confirm skills | `#character-wizard-panel` | `step === 4` | Back to skills, Begin story | Loading and locked fields need clear trust cues |
| Campaign modal | Nowa kampania | `#create-campaign-btn` | `#campaign-create-overlay` | `display:flex`, `aria-hidden=false` | `#campaign-create-close`, backdrop | Simple mobile full-screen dialog |
| Campaign death screen | In Memoriam | HTTP 410 or player death summary | `#campaign-death-screen`, `#campaign-death-inner` | `hidden`, `body.campaign-death-active`, `aria-hidden` | Close button, backdrop, Escape | Cinematic full-bleed overlay; keep close reachable |
| History summary modal | Podsumowanie kampanii | `#history-summary-btn` | `#history-summary-overlay` | `display:flex`, `aria-hidden=false` | `#history-summary-close`, backdrop | Long text needs modal-internal scroll |
| Action popup | Rzut / Akcja | Pending roll + `updateActionTriggerBtn(true)` | `#action-popup`, `#action-popup-backdrop` | `.hidden`, positioned fixed | Explicit popup buttons | Should behave like bottom action sheet on mobile |
| Archive toggle bar | Archiwum | Always above chat | `.chat-toolbar`, `#archive-toggle-btn` | `aria-pressed`, `data-count`, `#chat.archive-hidden` | Toggle button | Keep compact; avoid stealing chat height |
| Slash autocomplete | Komendy / | Typing `/` in `#input` | `#slash-popup` | `.slash-popup--open`, `aria-hidden` | Escape, pick, invalid context | Must appear above keyboard, max 4 items visible |
| Combat loot modal | Łupy | Enemy killed with loot | `#combat-loot-layer` | `display:flex`, `aria-hidden` | `#combat-loot-dismiss` | Bottom sheet or centered card, 1-column loot rows |
| Combat end screen | Koniec walki | Combat status `ended` | `#combat-end-layer` | `display:flex`, `aria-hidden` | Continue button | Victory/defeat/fled states need distinct variants |

## Implementation Flags

- `#auth-overlay` blocks the whole app until login.
- `#game-app` is hidden before auth, then becomes the app shell.
- `#character-create-overlay` is forced when a campaign has no character for `expectCharacterCreationForCampaignId`.
- `#sheet-panel` is controlled by `window.state.sheetPanelOpen` and persisted in `localStorage`.
- `#combat-panel-slot` is visible only during active combat through `combatInput._syncSheetChrome()`.
- `#composer-combat-send-slot` replaces `#send-btn` only when combat is active and `current_turn === "player"`.
- `#campaign-death-screen` uses `hidden`, `aria-hidden`, and `body.campaign-death-active`.

## Mobile Priority Notes

The current implementation uses a desktop-like side sheet above 900 px and a full-width sheet below 900 px. The redesign should upgrade this to a mobile bottom sheet with an 80% max height, drag handle affordance, and sticky combat header when combat is active. Keep the same container IDs so the current JS remains compatible.
