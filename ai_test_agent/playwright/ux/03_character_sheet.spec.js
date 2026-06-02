const { test, expect } = require("@playwright/test");
const { enterGame, openCharacterSheet, DEFAULT_HERO } = require("../helpers/player_flow");

test.describe("UX: character sheet", () => {
  test("mobile sheet opens with hero name", async ({ page }) => {
    await enterGame(page);
    await openCharacterSheet(page);
    await expect(page.locator("#sheet-character-name")).toContainText(DEFAULT_HERO);
    await expect(page.locator("#tab-stats")).toBeVisible();
  });
});
