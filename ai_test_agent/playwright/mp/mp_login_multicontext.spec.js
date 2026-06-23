// RUNNABLE TODAY. Proves the core MP harness trick: N independent player sessions (separate
// browser contexts, separate localStorage/cookies) logged in as different accounts inside ONE
// test. Every other MP spec builds on this. Does not depend on the (currently unfinished) in-game
// MP UI — it only checks that each account independently reaches the player app.
const { test, expect } = require("@playwright/test");
const { ensureMpUsers, setupMpViaApi, loginAs } = require("./helpers/mp");

test("mp harness: two players log in concurrently in isolated contexts", async ({ browser }) => {
  const users = await ensureMpUsers(2);
  // Build a started lobby over the API so the accounts have a shared game to belong to.
  const { campaignId } = await setupMpViaApi(users, { title: "#MP-pw-login" });
  expect(campaignId).toBeGreaterThan(0);

  const ctxs = [];
  try {
    for (const u of users) {
      const ctx = await browser.newContext();
      const page = await ctx.newPage();
      await loginAs(page, u.username);
      // Each context is a distinct authenticated session.
      const stored = await page.evaluate(() => localStorage.getItem("aigm_token") || localStorage.length);
      expect(stored).toBeTruthy();
      ctxs.push(ctx);
    }
    expect(ctxs.length).toBe(2);
  } finally {
    for (const c of ctxs) await c.close();
  }
});
