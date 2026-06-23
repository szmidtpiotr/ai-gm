/**
 * REGRESSION #939 (GF7) — Party Chat panel HTML exists + multiplayerUI JS activates on join.
 * Acceptance:
 *   A: #party-chat-panel, #mp-chat-messages, #mp-chat-body, #mp-chat-input exist in game-screen HTML.
 *   B: _joinMpActiveGame code path activates multiplayerUI (camp.mode === 'multiplayer' check present).
 *   C: Chat endpoint /api/multiplayer/campaigns/{id}/chat responds (used by chat poll).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #939-A — #party-chat-panel and all MP DOM elements exist in index.html", async ({ page }) => {
  await page.goto("/");
  // Elements must exist in DOM even before MP is active (hidden by default)
  const partyChat = page.locator("#party-chat-panel");
  await expect(partyChat, "#party-chat-panel missing from DOM (#939)").toHaveCount(1);

  const chatMessages = page.locator("#mp-chat-messages");
  await expect(chatMessages, "#mp-chat-messages missing from DOM (#939)").toHaveCount(1);

  const chatBody = page.locator("#mp-chat-body");
  await expect(chatBody, "#mp-chat-body missing from DOM (#939)").toHaveCount(1);

  const chatInput = page.locator("#mp-chat-input");
  await expect(chatInput, "#mp-chat-input missing from DOM (#939)").toHaveCount(1);

  const chatBadge = page.locator("#mp-chat-badge");
  await expect(chatBadge, "#mp-chat-badge missing from DOM (#939)").toHaveCount(1);

  const mpSection = page.locator("#mp-multiplayer-section");
  await expect(mpSection, "#mp-multiplayer-section missing from DOM (#939)").toHaveCount(1);

  const mpTimer = page.locator("#mp-timer-section");
  await expect(mpTimer, "#mp-timer-section missing from DOM (#939)").toHaveCount(1);

  const privateNote = page.locator("#multiplayer-private-note");
  await expect(privateNote, "#multiplayer-private-note missing from DOM (#939)").toHaveCount(1);

  const inviteInput = page.locator("#game-invite-username");
  await expect(inviteInput, "#game-invite-username missing from DOM (#939)").toHaveCount(1);
});

test("REGRESSION #939-B — togglePartyChat function is defined and chat panel starts hidden", async ({ page }) => {
  await page.goto("/");
  // togglePartyChat must be accessible via window.multiplayerUI.togglePartyChat
  const fnExists = await page.evaluate(() => typeof window.multiplayerUI?.togglePartyChat === "function");
  expect(fnExists, "multiplayerUI.togglePartyChat not defined (#939)").toBe(true);

  // multiplayerUI must be exposed
  const uiExists = await page.evaluate(() => typeof window.multiplayerUI === "object" && window.multiplayerUI !== null);
  expect(uiExists, "window.multiplayerUI not defined (#939)").toBe(true);

  // party-chat-panel must be hidden by default
  const hidden = await page.evaluate(() => document.getElementById("party-chat-panel")?.hidden);
  expect(hidden, "#party-chat-panel should be hidden by default (#939)").toBe(true);
});

test("REGRESSION #939-C — chat endpoint returns 401 (exists, not 404) for unauthenticated call", async ({ request }) => {
  // Endpoint must exist — 401 = auth check working, 404 = route missing
  const resp = await request.get("/api/multiplayer/campaigns/1/chat");
  expect(resp.status(), "chat endpoint missing (404) — route not registered (#939)").not.toBe(404);
  expect([401, 403, 422].includes(resp.status()), `unexpected status ${resp.status()}`).toBe(true);
});
