/**
 * REGRESSION #427 (E12) — template workflow draft → review → published.
 * Acceptance: the player-facing list exposes ONLY published templates (draft/review
 * stay hidden), and the admin status-change endpoint is auth-gated. Transition logic
 * (review accepted, invalid rejected, revert) is covered deterministically by pytest.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #427 — player list shows only published templates", async ({ page }) => {
  const r = await page.request.get("/api/campaign-templates");
  expect(r.ok(), "/api/campaign-templates not 200 (#427)").toBeTruthy();
  const items = (await r.json()).items || [];
  for (const t of items) {
    expect(t.status, `non-published template leaked to players (#427): id=${t.id} status=${t.status}`).toBe("published");
  }
});

test("REGRESSION #427 — admin template status change is auth-gated", async ({ page }) => {
  const r = await page.request.patch("/api/admin/forge/templates/999999999", {
    data: { status: "review" },
  });
  expect(r.status(), "status change must require admin auth (#427)").toBe(401);
});
