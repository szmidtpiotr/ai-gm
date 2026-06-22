/**
 * REGRESSION #923 (GF3) — lobby-screen HTML containers exist and are activatable via showScreen().
 * Acceptance: _showLobbyScreen() shows lobby-screen div with all required containers
 * (members list, invite section, start button). Host/guest visibility controlled by JS.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #923 — lobby-screen exists in DOM and has required containers", async ({ page }) => {
  // Login first
  await page.goto("/");
  await page.waitForSelector("#login-username", { timeout: 10000 });
  await page.fill("#login-username", "demo");
  await page.fill("#login-password", "demo");
  await page.click("#login-form button");
  await page.waitForTimeout(2000);

  // Verify lobby-screen div exists in DOM
  const lobbyScreen = await page.locator("#lobby-screen");
  await expect(lobbyScreen).toHaveCount(1);

  // Verify all required containers from _renderLobby() are present
  const requiredIds = [
    "lobby-screen-title",
    "lobby-screen-subtitle",
    "lobby-members-list",
    "lobby-invite-section",
    "lobby-guest-section",
    "lobby-start-section",
    "lobby-join-link-section",
    "lobby-start-btn",
    "lobby-start-hint",
    "lobby-invite-username",
    "lobby-invite-msg",
    "lobby-invite-link-box",
    "lobby-invite-link-text",
    "lobby-join-token-input",
    "lobby-join-msg",
  ];

  for (const id of requiredIds) {
    const el = await page.locator(`#${id}`);
    await expect(el, `#${id} powinno istnieć (#923)`).toHaveCount(1);
  }
});

test("REGRESSION #923 — showScreen('lobby-screen') activates the lobby screen", async ({ page }) => {
  await page.goto("/");
  await page.waitForSelector("#login-username", { timeout: 10000 });
  await page.fill("#login-username", "demo");
  await page.fill("#login-password", "demo");
  await page.click("#login-form button");
  await page.waitForTimeout(2000);

  // Call showScreen('lobby-screen') — must not throw and must activate the screen
  const result = await page.evaluate(() => {
    if (typeof showScreen !== "function") return "showScreen not found";
    showScreen("lobby-screen");
    const el = document.getElementById("lobby-screen");
    if (!el) return "lobby-screen not found";
    return el.classList.contains("screen--active") ? "active" : "not-active";
  });

  expect(result, "lobby-screen should become screen--active after showScreen()").toBe("active");
});

test("REGRESSION #923 — lobby-start-btn is disabled by default", async ({ page }) => {
  await page.goto("/");
  await page.waitForSelector("#login-username", { timeout: 10000 });
  await page.fill("#login-username", "demo");
  await page.fill("#login-password", "demo");
  await page.click("#login-form button");
  await page.waitForTimeout(2000);

  const startBtn = page.locator("#lobby-start-btn");
  await expect(startBtn).toBeDisabled();
});
