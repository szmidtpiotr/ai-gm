---
doc: 05-id-and-class-contracts
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

# ID And Class Contracts

Do not rename these selectors in Figma handoff or implementation. They are referenced directly from JavaScript.

## Global App And Auth

| Selector | JS file | Function/owner | What breaks if renamed |
|---|---|---|---|
| `#game-app` | `app.js` | `_setAuthedUiVisible` | App cannot show/hide after auth |
| `#auth-overlay` | `app.js` | `_setAuthedUiVisible` | Login overlay cannot hide/show |
| `#player-login-btn` | `app.js` | `initPlayerAuthGate` | Login click stops |
| `#player-logout-btn` | `app.js` | `initPlayerAuthGate` | Logout stops |
| `#player-login-status` | `app.js` | `initPlayerAuthGate` | Login errors/status disappear |
| `#player-username` | `app.js` | `initPlayerAuthGate` | Username cannot be read |
| `#player-password` | `app.js` | `initPlayerAuthGate` | Password cannot be read |

## LLM Settings

| Selector | JS file | Function/owner | What breaks if renamed |
|---|---|---|---|
| `#llm-controls` | `actions.js` | `setLlmControlsCollapsed` | Settings collapse state fails |
| `#llm-controls-body` | CSS/HTML | collapsed panel | Body may remain visible |
| `#llm-settings-toggle-btn` | `actions.js` | `initLlmSettingsCollapse` | Toggle stops |
| `#llm-settings-toggle-hint` | `actions.js` | `setLlmControlsCollapsed` | Saved/Connect hint stops |
| `#llm-player-admin-only` | `actions.js` | `applyPlayerLlmSettingsAccessUi` | Admin-only fields cannot hide |
| `#llm-provider-select` | `actions.js` | provider controls | Provider selection stops |
| `#llm-base-url-input` | `actions.js` | provider payload | Base URL not saved |
| `#llm-api-key-input` | `actions.js` | provider payload | API key not saved |
| `#llm-base-url-field` | `actions.js` | form visibility | URL field cannot hide |
| `#llm-api-key-field` | `actions.js` | form visibility | API key field cannot hide |
| `#engine-select` | `api.js` / `actions.js` | model loading | Model list/selection breaks |
| `#test-ollama-btn` | `events.js` | connect handler | Connect button stops |
| `#show-all-models-toggle` | `actions.js` | model list toggle | OpenAI model filtering breaks |
| `#openai-models-toggle-wrap` | `actions.js` | visibility | Toggle wrapper cannot hide |

## Campaign And Character

| Selector | JS file | Function/owner | What breaks if renamed |
|---|---|---|---|
| `#campaign-select` | `api.js`, `events.js` | campaign loading/change | Campaign selection breaks |
| `#create-campaign-btn` | `events.js` | `createCampaign` | New campaign flow stops |
| `#reset-campaign-btn` | `events.js` | reset flow | Reset campaign stops |
| `#reset-character-btn` | `events.js` | reset flow | Reset character stops |
| `#delete-campaign-btn` | `events.js` | delete flow | Delete campaign stops |
| `#campaign-create-overlay` | `ui.js`, `events.js` | campaign modal | Modal cannot open/close |
| `#campaign-create-form` | `events.js` | submit handler | Create campaign submit stops |
| `#campaign-create-title-input` | `actions.js` | create payload | Title cannot be read |
| `#campaign-create-close` | `events.js` | close handler | Close button stops |
| `#character-create-overlay` | `ui.js`, `events.js` | character modal | Character creation visibility breaks |
| `#character-create-form` | `events.js`, `actions.js` | create character | Submit/archetype dataset breaks |
| `#character-create-name` | `actions.js` | create payload | Name cannot be read |
| `#character-create-background` | `actions.js` | create payload | Background cannot be read |
| `#character-create-submit` | `actions.js`, `events.js` | create flow | Create button state breaks |
| `#character-create-close` | `events.js` | close handler | Close/cancel cleanup breaks |
| `.archetype-card` | `events.js` | archetype selection | Archetype choice stops |

## Character Wizard

| Selector | JS file | Function/owner | What breaks if renamed |
|---|---|---|---|
| `#character-create-step-indicator` | `character_wizard.js` | `showWizardChrome` | Step label disappears |
| `#character-create-step-1-wrap` | `character_wizard.js` | `showStep1Only` | Step 1 cannot show/hide |
| `#character-wizard-host` | `character_wizard.js` | wizard chrome | Wizard content cannot show |
| `#character-wizard-panel` | `character_wizard.js` | dynamic render | Wizard pages do not render |
| `#character-wizard-nav` | `character_wizard.js` | nav row | Back row layout breaks |
| `#character-wizard-back` | `character_wizard.js` | back handler | Back stops |
| `#wiz-id-appearance` | `character_wizard.js` | finalize | Appearance override lost |
| `#wiz-id-personality` | `character_wizard.js` | finalize | Personality override lost |
| `#wiz-id-flaw` | `character_wizard.js` | identity fill | Flaw field lost |
| `#wiz-id-bond` | `character_wizard.js` | identity fill | Bond field lost |
| `[data-act]` | `character_wizard.js` | delegated actions | Wizard buttons stop |

## Chat, Composer, Roll, Archive

| Selector | JS file | Function/owner | What breaks if renamed |
|---|---|---|---|
| `#chat` | `ui.js`, `api.js`, `actions.js` | render/scroll/clear | Chat rendering breaks |
| `.composer` | `ui.js` | `getEls`, `updateUiState` | Composer visibility breaks |
| `#input` | many | send, slash, combat input | Main input stops |
| `#send-btn` | `events.js` | `sendMessage` | Send stops |
| `#dice-btn` | `events.js` | sheet toggle | Sheet toggle stops |
| `#contextual-roll-btn` | `actions.js`, `events.js` | legacy roll | Roll state updates break |
| `#thinking-bubble` | `ui.js` | thinking lifecycle | Streaming replacement breaks |
| `#streaming-bubble` | `ui.js` | streaming lifecycle | Streaming finalize breaks |
| `#archive-toggle-btn` | `ui.js` | archive toggle | Archive toggle stops |
| `#archive-toggle-count` | `ui.js` | archive count | Count stops |
| `.archive-toggle-label` | `ui.js` | label update | Label stops |
| `.is-archived-bubble` | `ui.js` / CSS | archive filter | Archived messages cannot hide |
| `.chat-back-in-game` | `ui.js` / CSS | archive separator | Separator filter breaks |
| `#action-popup` | `ui.js` | pending roll popup | Popup cannot show/position |
| `#popup-roll-btn` | `ui.js` | pending roll action | Roll choice stops |
| `#popup-action-btn` | `ui.js` | pending action | Action choice stops |
| `#action-popup-roll-hint` | `ui.js` | hint copy | Hint cannot update |

## Sheet, History, Debug

| Selector | JS file | Function/owner | What breaks if renamed |
|---|---|---|---|
| `.play-area` | `actions.js` | sheet open class | Sheet layout state breaks |
| `#sheet-panel` | `actions.js`, `ui.js` | sheet panel | Sheet cannot open/position popup |
| `#sheet-panel-body` | `actions.js` | sheet rendering | Sheet content missing |
| `.sheet-fluff` | `combat_input.js` | combat chrome | Identity block not hidden in combat |
| `#history-panel` | `ui.js`, `api.js` | history render | History panel breaks |
| `#history-summary-btn` | `actions.js` | open summary | Summary modal stops |
| `#history-summary-overlay` | `actions.js` | modal visibility | Summary cannot open/close |
| `#history-summary-close` | `actions.js` | close handler | Close stops |
| `#history-summary-regenerate-btn` | `actions.js` | regenerate | Regenerate stops |
| `#history-summary-body` | `actions.js` | content | Summary text missing |
| `#history-summary-empty` | `actions.js` | empty state | Empty state missing |
| `#history-summary-loading` | `actions.js` | loading state | Loading state missing |
| `#copy-debug-btn` | `actions.js` | debug snapshot | Debug copy stops |
| `#combat-debug-status` | `actions.js`, `api.js` | combat debug | Debug label stops |

## Combat

| Selector | JS file | Function/owner | What breaks if renamed |
|---|---|---|---|
| `#combat-panel-slot` | `combat_panel.js`, `combat_input.js` | panel host injection | Combat panel cannot mount |
| `#combat-panel-host` | `combat_panel.js` | dynamic host | Combat panel lifecycle breaks |
| `#combat-panel-body` | `combat_panel.js` | combatants render | Combatants missing |
| `#combat-panel-actions` | `combat_panel.js` | panel actions | Legacy actions break |
| `#combat-panel-msg` | `combat_panel.js` | status/errors | Combat messages missing |
| `#combat-engine-turns` | `combat_panel.js` | engine log | Turn log missing |
| `#combat-btn-attack` | `combat_panel.js` | panel attack | Panel attack stops |
| `#combat-btn-flee` | `combat_panel.js` | panel flee | Panel flee stops |
| `#combat-loot-layer` | `combat_panel.js` | loot modal | Loot overlay breaks |
| `#combat-end-layer` | `combat_panel.js` | end overlay | Victory/defeat overlay breaks |
| `#composer-combat-send-slot` | `combat_input.js` | composer combat mode | Attack/Flee composer state breaks |
| `#composer-combat-attack` | `combat_input.js` | composer attack | Attack button stops |
| `#composer-combat-flee` | `combat_input.js` | composer flee | Flee button stops |

## Death Screen

| Selector | JS file | Function/owner | What breaks if renamed |
|---|---|---|---|
| `#campaign-death-screen` | `death_screen.js` | death overlay | Death screen cannot show/hide |
| `#campaign-death-inner` | `death_screen.js` | death card injection | Death content missing |
| `#campaign-death-close-btn` | `death_screen.js` | close handler | Close stops |
| `#campaign-death-backdrop` | `death_screen.js` | backdrop close | Backdrop close stops |
| `#death-start-new-btn` | `death_screen.js` | new campaign CTA | Start-new flow stops |

## Slash Commands

| Selector | JS file | Function/owner | What breaks if renamed |
|---|---|---|---|
| `#slash-popup` | `slash_commands.js` | autocomplete popup | Slash UI cannot render |
| `.slash-popup-list` | `slash_commands.js` | list render | Items cannot mount |
| `.slash-popup-item` | `slash_commands.js` | option state | Selection styling breaks |
| `.slash-popup-item--active` | `slash_commands.js` / CSS | highlight | Keyboard active item invisible |
| `.slash-popup-cmd` | `slash_commands.js` | command text | Command label styling breaks |
| `.slash-popup-desc` | `slash_commands.js` | description | Description styling breaks |

## JS-Referenced CSS Variables

No CSS custom properties are directly read or written from JS via `getPropertyValue()` or `style.setProperty()` for theme switching. JS does embed inline fallback variables in template strings, including `--border`, `--panel`, `--text`, `--color-border`, `--color-surface`, and related fallbacks. Preserve canonical variable names in `:root`, and either define or remove fallback aliases during a token cleanup.
