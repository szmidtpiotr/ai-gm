/**
 * REGRESSION #392 — HP death check / narrative death forbidden
 * Verifies that the LLM cannot kill the character without mechanical permission
 * (HP ≤ 0 via DEATH_TRIGGER / death_save). Playing turns with full HP through
 * the STORY_STALE threshold must never result in a death state.
 */
const { test, expect } = require("@playwright/test");
const { enterGame, sendMultipleTurns } = require("../../helpers/player_flow");

const TURNS = 6; // past the STORY_STALE threshold of 5 — covers the original bug scenario
const TURN_TIMEOUT = 180_000; // 3 min per turn — Ollama can be slow on first cold start

const DEATH_WORDS = [
  "umarł", "zginął", "nie żyje", "koniec przygody",
  "twoja postać zginęła", "twoja postać nie żyje", "bohater umiera",
];
const DEATH_SELECTORS = [".death-screen", ".campaign-ended", "[data-state='dead']"];

test.describe("REGRESSION #392 — narrative death forbidden without HP check", () => {
  test(`${TURNS} turns of 'czekam' — character never dies with full HP`, async ({ page }) => {
    test.setTimeout(TURNS * TURN_TIMEOUT + 60_000);
    await enterGame(page);

    const responses = await sendMultipleTurns(page, "czekam", TURNS, {
      timeout: TURN_TIMEOUT,
      afterEach: async (_text, i) => {
        for (const sel of DEATH_SELECTORS) {
          const visible = await page.locator(sel).isVisible().catch(() => false);
          expect(visible, `Death selector "${sel}" appeared after turn ${i + 1}`).toBe(false);
        }
      },
    });

    for (let i = 0; i < responses.length; i++) {
      const lower = responses[i].toLowerCase();
      for (const word of DEATH_WORDS) {
        expect(lower, `Turn ${i + 1} response contains forbidden death word "${word}"`).not.toContain(word);
      }
    }

    await expect(page.locator("#game-screen.screen--active")).toBeVisible();
    await expect(page.locator("#send-btn")).toBeEnabled();
  });
});
