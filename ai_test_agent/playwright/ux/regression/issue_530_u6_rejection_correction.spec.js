/**
 * REGRESSION #530 (U6) — Rejection correction pattern.
 * Acceptance: backend healthy after U6 integration; llm_tag_errors endpoint not crashing.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #530 — backend health OK after U6 integration", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "Backend not healthy after U6 deployment (#530)").toBeTruthy();
  const body = await r.json();
  expect(body.status).toBe("ok");
});

test("REGRESSION #530 — tag-errors endpoint does not crash", async ({ page }) => {
  const r = await page.request.get("/api/admin/campaigns/1/tag-errors", {
    failOnStatusCode: false,
  });
  expect(
    r.status() === 200 || r.status() === 404 || r.status() === 401,
    `Unexpected status ${r.status()} — backend crash on tag-errors (#530)`
  ).toBeTruthy();
});
