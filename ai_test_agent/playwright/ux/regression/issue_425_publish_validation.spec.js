/**
 * REGRESSION #425 (E10) — Forge publish validation is deployed + auth-gated.
 * The validation logic (missing NPCs/beats → 422) is covered deterministically by
 * pytest. This spec confirms the publish endpoint is live and rejects unauthenticated
 * publish attempts (so the validation path is reachable only by admins).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #425 — forge template publish endpoint is auth-gated", async ({ page }) => {
  const r = await page.request.patch("/api/admin/forge/templates/999999999", {
    data: { status: "published" },
  });
  // Without an admin token the publish must NOT succeed (401 auth, never 200).
  expect(r.status(), "publish must be auth-gated (#425)").toBe(401);
});
