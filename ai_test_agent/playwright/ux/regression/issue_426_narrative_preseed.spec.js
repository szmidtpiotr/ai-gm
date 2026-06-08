/**
 * REGRESSION #426 (E11) — template launch path is live (narrative pre-seeding).
 * The actual narrative_state seeding from template narrative_hooks is covered
 * deterministically by pytest. This spec confirms the create-campaign template_id
 * code path is deployed: launching from a non-existent published template is
 * rejected with 404 (proving template_id is read, not silently ignored).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #426 — create-campaign honors template_id (404 for missing)", async ({ page }) => {
  const r = await page.request.post("/api/campaigns", {
    data: {
      title: "E11 probe", system_id: "fantasy", model_id: "default",
      owner_user_id: 1, language: "pl", mode: "pre_built", status: "active",
      template_id: 999999999,
    },
  });
  expect(r.status(), "missing published template must 404 (#426)").toBe(404);
});
