/**
 * REGRESSION #950 — Party Chat panel invisible in single-player session.
 * Acceptance:
 *   1. #party-chat-panel is hidden by default (index.html attribute).
 *   2. game.js calls multiplayerUI.deactivate() at the start of enterGame().
 *   3. multiplayer_ui.js exposes minimizePartyChat() on window.multiplayerUI.
 *   4. window.multiplayerUI.deactivate remains in the public API (backward compat).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #950 — party-chat-panel hidden by default in HTML", async ({ page }) => {
  const r = await page.request.get("/");
  expect(r.ok(), "index.html not accessible (#950)").toBeTruthy();
  const body = await r.text();
  const panelIdx = body.indexOf('id="party-chat-panel"');
  expect(panelIdx, "#party-chat-panel not found in index.html (#950)").toBeGreaterThan(-1);
  const snippet = body.slice(panelIdx, panelIdx + 120);
  expect(snippet, "#party-chat-panel must have hidden attribute by default (#950)").toContain("hidden");
});

test("REGRESSION #950 — enterGame() deactivates party chat for single-player", async ({ page }) => {
  const r = await page.request.get("/front/js/screens/game.js");
  expect(r.ok(), "game.js not accessible (#950)").toBeTruthy();
  const src = await r.text();
  const idx = src.indexOf("async function enterGame(");
  expect(idx, "enterGame function not found in game.js").toBeGreaterThan(-1);
  const fnStart = src.slice(idx, idx + 500);
  expect(fnStart, "enterGame() must call deactivate() — sticky party chat bug (#950)").toContain("deactivate");
});

test("REGRESSION #950 — minimizePartyChat exposed on window.multiplayerUI", async ({ page }) => {
  const r = await page.request.get("/front/js/multiplayer_ui.js");
  expect(r.ok(), "multiplayer_ui.js not accessible (#950)").toBeTruthy();
  const src = await r.text();
  expect(src, "minimizePartyChat must be in multiplayer_ui.js (#950)").toContain("minimizePartyChat");
  const apiIdx = src.indexOf("window.multiplayerUI");
  expect(apiIdx, "window.multiplayerUI not found").toBeGreaterThan(-1);
  const apiSnippet = src.slice(apiIdx, apiIdx + 300);
  expect(apiSnippet, "deactivate must remain in public API (#950 backward compat)").toContain("deactivate");
});
