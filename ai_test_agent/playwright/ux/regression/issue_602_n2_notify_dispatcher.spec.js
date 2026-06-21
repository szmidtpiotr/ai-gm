/**
 * REGRESSION #602 (N2) — unified multichannel notify() dispatcher.
 * Acceptance: /api/admin/notify/preview/{user_id} returns the dry-run channel
 * selection (telegram > web_push > email) with the player's channel_order; a
 * user with no prefs resolves to channel=null + empty enabled set (no crash).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #602 — notify preview returns dispatcher channel contract", async ({ page }) => {
  const r = await page.request.get("/api/admin/notify/preview/1");
  expect(r.ok(), "preview endpoint nie odpowiada 200 (#602)").toBeTruthy();

  const body = await r.json();
  // contract shape
  expect(body).toHaveProperty("channel");
  expect(body).toHaveProperty("enabled_channels");
  expect(body).toHaveProperty("channel_order");

  // default order = telegram > web_push > email (Numbers Policy default)
  expect(body.channel_order).toBe("telegram,web_push,email");

  // user with no prefs row → nothing enabled, no channel chosen, no crash
  expect(Array.isArray(body.enabled_channels)).toBeTruthy();
  expect(body.enabled_channels.length).toBe(0);
  expect(body.channel).toBeNull();
});
