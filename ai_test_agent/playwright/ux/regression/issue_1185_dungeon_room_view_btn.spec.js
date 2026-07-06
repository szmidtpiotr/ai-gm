/**
 * REGRESSION #1185 (code-review) — podgląd obrazu pokoju lochu: przycisk #dungeon-room-view-btn
 * musi istnieć w HUD lochu (wcześniej brakowało go w index.html → toggle roomViewBtn.hidden = no-op).
 * Acceptance: index.html zawiera <button id="dungeon-room-view-btn"> wewnątrz klastra #dungeon-hud,
 * startuje jako hidden, a app.js podpina go pod showCurrentTileImageModal.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1185 — przycisk podglądu obrazu komnaty istnieje i jest podpięty", async ({ page }) => {
  // index.html serwowany przez nginx (proxy /api → backend; statyki z frontendu)
  const htmlResp = await page.request.get("/index.html");
  expect(htmlResp.ok(), "index.html nie odpowiada 200 (#1185)").toBeTruthy();
  const html = await htmlResp.text();

  const idxHud = html.indexOf('id="dungeon-hud"');
  const idxBtn = html.indexOf('id="dungeon-room-view-btn"');
  expect(idxHud, "brak kontenera #dungeon-hud").toBeGreaterThan(-1);
  expect(idxBtn, "brak #dungeon-room-view-btn w index.html").toBeGreaterThan(-1);
  expect(idxBtn, "przycisk musi leżeć wewnątrz/za klastrem #dungeon-hud").toBeGreaterThan(idxHud);

  // przycisk domyślnie ukryty
  const btnFragment = html.slice(idxBtn, html.indexOf(">", idxBtn) + 1);
  expect(btnFragment.includes("hidden"), "przycisk musi startować jako hidden").toBeTruthy();

  // wiring w app.js
  const jsResp = await page.request.get("/js/app.js");
  expect(jsResp.ok(), "app.js nie odpowiada 200 (#1185)").toBeTruthy();
  const js = await jsResp.text();
  expect(
    /dungeon-room-view-btn['"]\)\?\.addEventListener\(\s*['"]click['"]\s*,\s*showCurrentTileImageModal/.test(js),
    "brak podpięcia przycisku pod showCurrentTileImageModal"
  ).toBeTruthy();
});
