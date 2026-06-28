/**
 * REGRESSION #1008 (część 2) — combat-heavy kampania po wskrzeszeniu pokazuje NIEPUSTY czat.
 * Acceptance: wejście do kampanii z dużą historią walki (combat_turns) renderuje bąbelki —
 * jeden wadliwy wiersz nie może wyzerować całego czatu (per-item try/catch w enterGame).
 *
 * Używa demo + bohatera Mizel (read-only: 93 tury → enterGame NIE wysyła tury otwierającej).
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";
const HERO_ID = 999420;        // Mizel (demo)
const CAMPAIGN_ID = 99791;     // combat-heavy, 93 tury + 87 combat_turns

test("REGRESSION #1008 — combat-heavy kampania renderuje niepusty czat", async ({ page }) => {
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

  // Wejście wprost do kampanii Mizela przez przywrócenie sesji (F5-restore path).
  await page.evaluate(([h, c]) => {
    localStorage.setItem("aigm_hero_id", String(h));
    localStorage.setItem("aigm_campaign_id", String(c));
  }, [HERO_ID, CAMPAIGN_ID]);
  await page.reload();
  await page.waitForSelector("#game-screen.screen--active", { timeout: 30000 });

  // Czat MUSI mieć treść (combat cards + narracja). Overlay śmierci ukryty.
  await expect.poll(
    async () => page.locator("#chat-messages > *").count(),
    { timeout: 20000 }
  ).toBeGreaterThan(5);
  await expect(page.locator("#death-screen")).toBeHidden();
});
