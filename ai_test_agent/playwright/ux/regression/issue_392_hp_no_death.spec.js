/**
 * REGRESSION #392 — HP death check / narrative death forbidden
 * Verifies that the LLM cannot kill the character without mechanical permission
 * (HP ≤ 0 via DEATH_TRIGGER / death_save). Playing 20 "czekam" turns with full
 * HP must never result in a death state.
 */
const { test, expect } = require("@playwright/test");
const { enterGame, sendMultipleTurns } = require("../../helpers/player_flow");

const DEATH_WORDS = [
  "umarł", "zginął", "nie żyje", "koniec przygody",
  "twoja postać zginęła", "twoja postać nie żyje", "bohater umiera",
];
const DEATH_SELECTORS = [".death-screen", ".campaign-ended", "[data-state='dead']"];

test.describe("REGRESSION #392 — narrative death forbidden without HP check", () => {
  test("20 turns of 'czekam' — character never dies with full HP", async ({ page }) => {
    await enterGame(page);

    const responses = await sendMultipleTurns(page, "czekam", 20, {
      afterEach: async (_text, i) => {
        // After each turn: no death UI must appear
        for (const sel of DEATH_SELECTORS) {
          const locator = page.locator(sel);
          const visible = await locator.isVisible().catch(() => false);
          expect(visible, `Death selector "${sel}" appeared after turn ${i + 1}`).toBe(false);
        }
      },
    });

    // None of the GM responses should contain death-related phrases
    for (let i = 0; i < responses.length; i++) {
      const lower = responses[i].toLowerCase();
      for (const word of DEATH_WORDS) {
        expect(lower, `Turn ${i + 1} response contains forbidden death word "${word}"`).not.toContain(word);
      }
    }

    // Campaign still active after 20 turns
    await expect(page.locator("#game-screen.screen--active")).toBeVisible();
    await expect(page.locator("#send-btn")).toBeEnabled();
  });
});
