# DOM_CONTRACT

Ponizszych selektorow nie wolno zmieniac bez rownoleglego refaktoru JS.

## Auth

- `#game-app`
- `#auth-overlay`
- `#player-login-btn`
- `#player-logout-btn`
- `#player-login-status`
- `#player-username`
- `#player-password`

## Core Gameplay

- `#chat`
- `.composer`
- `#input`
- `#send-btn`
- `#dice-btn`
- `#sheet-panel`
- `#sheet-panel-body`
- `#history-panel`

## Campaign / Character

- `#campaign-select`
- `#create-campaign-btn`
- `#delete-campaign-btn`
- `#reset-campaign-btn`
- `#reset-character-btn`
- `#campaign-create-overlay`
- `#campaign-create-form`
- `#campaign-create-title-input`
- `#character-create-overlay`
- `#character-create-form`
- `#character-create-name`
- `#character-create-background`

## Combat

- `#combat-panel-slot`
- `#composer-combat-send-slot`
- `#composer-combat-attack`
- `#composer-combat-flee`
- `#combat-debug-status`

## History / Death / Slash

- `#history-summary-overlay`
- `#history-summary-body`
- `#history-summary-regenerate-btn`
- `#campaign-death-screen`
- `#campaign-death-inner`
- `#campaign-death-close-btn`
- `#slash-popup`

## Notes

- Dopuszczalne: opakowanie dodatkowym wrapperem.
- Niedopuszczalne: zmiana ID, usuniecie elementu, zmiana semantyki event targetu.
