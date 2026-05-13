---
doc: 06-roll-card-anatomy
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

# Roll Card Anatomy

Roll cards are dynamic chat components. They are not static images. The designer should provide component specs that a developer can translate into HTML template strings in `frontend/js/ui.js`.

## Markers

- Player/skill roll marker: `__AI_GM_ROLL_V1__`
- Combat roll marker: `__AI_GM_COMBAT_ROLL_V1__`
- GM roll marker: `__AI_GM_GM_ROLL_V1__`

These markers are parsed by `tryParseRollCardFromText()`, `tryParseCombatRollCardFromText()`, and `tryParseGmRollCardFromText()`.

## Skill Roll Structure

Rendered by `buildRollCardHtml(data)`.

```html
<div class="roll-card roll-card--light roll-card--success">
  <div class="roll-card__line roll-card__line--head">🎲 Rzut: Atak (STR)</div>
  <div class="roll-card__line roll-card__line--detail">
    1d20:&nbsp;&nbsp;<span class="roll-card__die roll-card__die--nat20">20</span>
    &nbsp;&nbsp;|&nbsp;&nbsp; Modyfikator (ranga + biegłość): +3
  </div>
  <div class="roll-card__line roll-card__line--wynik">Wynik: <strong>23</strong> — ⚡ TRAFIENIE KRYTYCZNE</div>
</div>
```

Root variants:

- `.roll-card--success`
- `.roll-card--fail`
- `.roll-card--neutral`
- `.roll-card--pending`

## Combat Roll Structure

Rendered by `buildCombatRollCardHtml(data)`.

```html
<div class="roll-card roll-card--light combat-roll-card roll-card--success">
  <div class="combat-roll-card__intent">Opis akcji gracza...</div>
  <div class="roll-card__sep" role="separator"></div>
  <div class="roll-card__line roll-card__line--head">🎲 Bohater — ATAK (STR)</div>
  <div class="roll-card__line roll-card__line--detail">
    1d20:&nbsp;&nbsp;<span class="roll-card__die">14</span>
    &nbsp;&nbsp;|&nbsp;&nbsp; STR: +2 &nbsp;&nbsp;|&nbsp;&nbsp; Wynik: <strong>16</strong>
  </div>
  <div class="roll-card__line roll-card__line--wynik">Rzut: 16 vs AC 14 — ✅ TRAFIENIE — obrażenia: 6</div>
</div>
```

Flee uses the same root plus `.roll-card--neutral`, with a `🏃` header and one result line.

## Verdict States

| State | Current label | Suggested visual |
|---|---|---|
| Success | `(sukces)` / `✅ TRAFIENIE` | green accent, left border |
| Fail | `(porażka)` / `❌ PUDŁO` | red accent, left border |
| Critical hit | `⚡ TRAFIENIE KRYTYCZNE` | gold accent, die highlight |
| Critical failure | `💀 KRYTYCZNA PORAŻKA` / `fatalne pudło` | dark red/purple accent |
| Dodge | `🌀 UNIK` / `przeciwnik unika` | teal accent |
| Pending | `🎲 Rzut w toku…` | muted italic placeholder |

## DC Labels

Defined by `dcLabelPl(dc)`:

- `8` -> `Łatwe`
- `12` -> `Średnie`
- `16` -> `Trudne`
- `20` -> `Ekstremalne`
- `25` -> `Legendarne`

When a DC is present, the result line appends `· DC 16 (Trudne)`.

## Dice Face

Current implementation uses inline text in `.roll-card__die`. The redesign can use a d20 polygon-like badge, but it must remain text-based HTML so dynamic numbers can be rendered. Recommended mobile size: 32-40 px inline for compact cards; 56 px only for expanded/detail variants.

## Mobile Layout

- Card width: 100% of containing bubble.
- Padding: 12-16 px.
- Detail line can wrap; avoid horizontal scrolling.
- Verdict should be visually scannable in the final line.
- Keep Polish result text visible; do not encode success purely as color or icon.

## Animation

Optional entrance: 180-300 ms ease-out, slight translate/scale. Must respect `prefers-reduced-motion`. Do not animate every streamed token; roll card appears after payload parse.

## Future Upgrade Notes

The template can be replaced later if the root classes and marker parsing remain intact. If Figma exports a richer roll card, update `buildRollCardHtml()`, `buildCombatRollCardHtml()`, and this file together.
