/**
 * REGRESSION #1173 — MP: Enter podczas "GM tworzy narrację…" nie może resubmitować rundy.
 * Acceptance: handleSubmit ma guard `_sendEnabled` (Enter omija wyłączony przycisk),
 * a _setComposerState wyłącza też input (nie tylko przycisk), zostawiając widza z
 * żywym inputem na /whisper. Weryfikacja kontraktu źródła multiplayer_ui.js.
 *
 * Bug był czysto kliencki (code-review, żaden endpoint się nie zmienił).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1173 — handleSubmit guard + input.disabled", async ({ page }) => {
  const r = await page.request.get("/js/multiplayer_ui.js?probe=1173");
  expect(r.ok(), "multiplayer_ui.js nie serwuje się (200)").toBeTruthy();
  const src = await r.text();

  // handleSubmit blokuje submit gdy composer wyłączony.
  const hs = src.indexOf("async function handleSubmit");
  expect(hs, "brak handleSubmit w multiplayer_ui.js").toBeGreaterThan(-1);
  const hsBody = src.slice(hs, hs + 1400);
  expect(hsBody, "handleSubmit nie sprawdza _sendEnabled (#1173)").toMatch(/if \(!_sendEnabled\)\s*return/);

  // _setComposerState wyłącza input (guard Enter), ale nie widzowi.
  const scs = src.indexOf("function _setComposerState");
  expect(scs, "brak _setComposerState").toBeGreaterThan(-1);
  const scsBody = src.slice(scs, scs + 900);
  expect(scsBody, "_setComposerState nie wyłącza inputu (#1173)").toMatch(/inp\.disabled\s*=\s*!enabled\s*&&\s*!_isSpectator/);
});
