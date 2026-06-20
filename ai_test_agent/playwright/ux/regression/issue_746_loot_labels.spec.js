/**
 * REGRESSION #746 (L-fix) — Nazwy łupów po polsku w modalu walki.
 * Dwa fixy: (1) backend preview łupu pobiera `label` z DB zamiast key.replace,
 * (2) komunikat o złocie po polsku "ZŁ (dodano)" zamiast "GP (already added)".
 * Acceptance: serwowany /js/app.js zawiera polski komunikat o złocie i NIE zawiera
 * starego angielskiego ciągu — to weryfikuje, że fix dotarł do przeglądarki gracza.
 * (Ścieżka preview łupu jest bramkowana walką LLM → pokryta testem pytest.)
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #746 — serwowany app.js ma polski komunikat o złocie", async ({ page }) => {
  const r = await page.request.get("/js/app.js");
  expect(r.ok(), "GET /js/app.js nie odpowiada 200 (#746)").toBeTruthy();
  const body = await r.text();

  expect(
    body.includes("ZŁ (dodano)"),
    "app.js musi zawierać polski komunikat 'ZŁ (dodano)' (#746)"
  ).toBeTruthy();
  expect(
    body.includes("GP (already added)"),
    "app.js NIE może już zawierać angielskiego 'GP (already added)' (#746)"
  ).toBeFalsy();
});
