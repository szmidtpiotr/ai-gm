/**
 * REGRESSION #965 — usunięto 4 stare dev/test funkcje z zakładki Ustawienia (player UI).
 * Acceptance: serwowany index.html nie zawiera już Skopiuj-log, Reset kampanii, Reset postaci,
 * Test: Śmierć; FAB raportu bugów testerów (#955) pozostaje nietknięty.
 */
const { test, expect } = require("@playwright/test");

const REMOVED = [
  'id="debug-log-section"',
  'id="debug-copy-btn"',
  'id="debug-log-preview"',
  'id="reset-campaign-btn"',
  'id="reset-character-btn"',
  'id="test-death-btn"',
  "settings-admin-actions",
  "debug-turns-btn",
];

test("REGRESSION #965 — usunięte dev/test elementy nie są już serwowane", async ({ page }) => {
  const r = await page.request.get("/front/index.html");
  expect(r.ok(), "index.html nie odpowiada 200 (#965)").toBeTruthy();
  const html = await r.text();

  for (const needle of REMOVED) {
    expect(html.includes(needle), `usunięty element wciąż w HTML: ${needle}`).toBeFalsy();
  }

  // #955 FAB raportu bugów to osobna ścieżka — musi zostać.
  expect(html.includes("bug-report-fab"), "FAB raportu bugów (#955) zniknął — regresja").toBeTruthy();
});

test("REGRESSION #965 — app.js bez martwych referencji do usuniętych guzików", async ({ page }) => {
  const r = await page.request.get("/front/js/app.js");
  expect(r.ok(), "app.js nie odpowiada 200 (#965)").toBeTruthy();
  const js = await r.text();

  for (const needle of ["btnResetCampaign", "btnResetCharacter", "debug-copy-btn", "turns/debug-log"]) {
    expect(js.includes(needle), `martwa referencja w app.js: ${needle}`).toBeFalsy();
  }
});
