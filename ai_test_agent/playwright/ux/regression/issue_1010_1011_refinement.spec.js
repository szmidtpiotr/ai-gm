/**
 * REGRESSION #1010 + #1011 (refinement) — critical/optional beats + main/side quests vs victory.
 * Acceptance: the quests endpoint still serves the active-quest contract that the
 * victory check (#1009) reads; main quests block, side quests don't (logic covered by pytest).
 * Deterministic contract probe — full critical-path victory is exercised by pytest + smoke.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1010/#1011 — quests endpoint serves active-quest contract", async ({ page }) => {
  // Any campaign id; endpoint must return the documented shape regardless of contents.
  const r = await page.request.get("/api/campaigns/99767/quests");
  expect(r.ok(), "quests endpoint must answer 200 (#1011)").toBeTruthy();
  const body = await r.json();
  expect(body, "response must be an object").toBeTruthy();
  expect(Array.isArray(body.active_quests), "active_quests must be a list (#1009 victory reads it)").toBeTruthy();
  // Each active quest must expose the fields the HUD + victory check rely on.
  for (const q of body.active_quests) {
    expect(typeof q.title === "string", "quest needs a title").toBeTruthy();
  }
});
