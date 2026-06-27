/**
 * REGRESSION #1008 — Po wskrzeszeniu gracz widzi treść kampanii (ekran śmierci znika przy wejściu).
 * Acceptance: gdy zalega overlay #death-screen (bohater wskrzeszony z innej powierzchni — admin),
 * wejście do żywej kampanii (enterGame) MUSI ukryć overlay i pokazać czat. Test izoluje enterGame:
 * overlay wstrzyknięty na ekranie kampanii, karta klikana force (omija przechwycenie pointerów).
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";
const TEST_HERO = "[TEST] Krasnolud Wojownik";
const TEST_CAMPAIGN_ID = 999968;

async function loginDemo(page) {
  await page.goto(`${BASE}/`);
  await page.waitForSelector("#login-screen.screen--active", { timeout: 15000 });
  await page.fill("#login-username", "demo");
  await page.fill("#login-password", "demo");
  await page.locator("#login-form button[type='submit']").click();
  await page.waitForFunction(
    () => ["heroes-screen", "game-screen", "campaigns-screen"].some(
      (id) => document.getElementById(id)?.classList.contains("screen--active")
    ),
    null,
    { timeout: 25000 }
  );
}

// Doprowadź do ekranu wyboru kampanii dla test-hero (bez wchodzenia do gry).
async function gotoCampaignsScreen(page) {
  const onGame = await page.evaluate(
    () => document.getElementById("game-screen")?.classList.contains("screen--active")
  );
  if (onGame) {
    await page.locator("#home-btn").click({ force: true }).catch(() => {});
    await page.waitForSelector("#heroes-screen.screen--active", { timeout: 15000 }).catch(() => {});
  }
  const onCampaigns = await page.evaluate(
    () => document.getElementById("campaigns-screen")?.classList.contains("screen--active")
  );
  if (!onCampaigns) {
    const onHeroes = await page.evaluate(
      () => document.getElementById("heroes-screen")?.classList.contains("screen--active")
    );
    if (onHeroes) {
      const card = page.locator(".hero-card").filter({ hasText: TEST_HERO }).first();
      await card.waitFor({ state: "visible", timeout: 15000 });
      await card.click();
      const idleProceed = page.locator("#idle-hero-panel-proceed");
      if (await idleProceed.isVisible().catch(() => false)) await idleProceed.click();
    }
    await page.waitForSelector("#campaigns-screen.screen--active", { timeout: 20000 });
  }
}

async function clickCampaignCard(page, { force = false } = {}) {
  const campBtn = page.locator(`button.campaign-card[data-campaign-id="${TEST_CAMPAIGN_ID}"]`);
  await campBtn.waitFor({ state: "visible", timeout: 15000 });
  await campBtn.click({ force });
  await page.waitForSelector("#game-screen.screen--active", { timeout: 30000 });
}

test("REGRESSION #1008 — enterGame ukrywa zalegający overlay śmierci i pokazuje treść", async ({ page }) => {
  await loginDemo(page);

  // 1. Pierwsze wejście — czat z historią się renderuje (kampania ma tury, bez LLM)
  await gotoCampaignsScreen(page);
  await clickCampaignCard(page);
  await expect.poll(
    async () => page.locator("#chat-messages > *").count(),
    { timeout: 15000 }
  ).toBeGreaterThan(0);

  // 2. Wróć na ekran kampanii i wstrzyknij ZALEGAJĄCY overlay śmierci
  //    (symuluje bohatera wskrzeszonego z admina — overlay z poprzedniej śmierci)
  await gotoCampaignsScreen(page);
  await page.evaluate(() => {
    const ds = document.getElementById("death-screen");
    if (ds) { ds.hidden = false; document.body.style.overflow = "hidden"; }
  });

  // 3. Ponowne wejście do żywej kampanii. Karta force-click (overlay przechwytuje pointery).
  //    enterGame MUSI sprzątnąć overlay — to jest sedno fixu #1008.
  await clickCampaignCard(page, { force: true });

  // 4. Asercje: overlay zniknął, czat ma treść, body przewijalne
  await expect(page.locator("#death-screen")).toBeHidden({ timeout: 10000 });
  await expect.poll(
    async () => page.locator("#chat-messages > *").count(),
    { timeout: 15000 }
  ).toBeGreaterThan(0);
  const overflow = await page.evaluate(() => document.body.style.overflow);
  expect(overflow, "body.overflow musi być odblokowane po wejściu (#1008)").not.toBe("hidden");
});
