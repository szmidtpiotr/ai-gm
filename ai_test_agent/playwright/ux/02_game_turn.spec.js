const { test, expect } = require("@playwright/test");
const { enterGame, sendTurnAndWaitForGm } = require("../helpers/player_flow");
const { getPlayerState, loadConfig } = require("../helpers/game_state");

test.describe("UX: in-game turn", () => {
  test("send message and receive GM bubble (stub LLM)", async ({ page }) => {
    await enterGame(page);
    const gm = await sendTurnAndWaitForGm(page, "Opisz otoczenie w jednym zdaniu.");
    const text = (await gm.innerText()).trim();
    expect(text.length).toBeGreaterThan(5);

    const cfg = loadConfig();
    const state = await getPlayerState(cfg.character_id);
    expect(state).toBeTruthy();
  });
});
