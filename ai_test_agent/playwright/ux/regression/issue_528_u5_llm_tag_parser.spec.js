/**
 * REGRESSION #528 (U5) — Centralny parser tagów LLM + tabela llm_tag_errors.
 * Acceptance: endpoint /api/admin/campaigns/{id}/tag-error-count zwraca {campaign_id, tag_error_count};
 * nowa kampania zaczyna od 0 błędów tagów.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #528 U5 — tag-error-count endpoint returns valid shape", async ({ page }) => {
  const loginResp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(loginResp.ok(), "Admin login failed (#528)").toBeTruthy();
  const { token } = await loginResp.json();

  // Use /api/admin/campaigns/live which returns active campaigns without owner_id filter
  const campsResp = await page.request.get("/api/admin/campaigns/live", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(campsResp.ok(), "Campaigns live list failed (#528)").toBeTruthy();
  const camps = await campsResp.json();
  const items = camps.items || [];
  expect(items.length, "No active campaigns found (#528)").toBeGreaterThan(0);
  const campId = items[0].id;

  const r = await page.request.get(`/api/admin/campaigns/${campId}/tag-error-count`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `tag-error-count endpoint not ok for campaign ${campId} (#528)`).toBeTruthy();
  const body = await r.json();
  expect(typeof body.campaign_id, "campaign_id missing (#528)").toBe("number");
  expect(typeof body.tag_error_count, "tag_error_count missing (#528)").toBe("number");
  expect(body.tag_error_count, "tag_error_count must be >= 0 (#528)").toBeGreaterThanOrEqual(0);
});

test("REGRESSION #528 U5 — llm_tag_errors table exists in DB", async ({ page }) => {
  const loginResp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await loginResp.json();
  const r = await page.request.get("/api/admin/campaigns/1/tag-error-count", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.status(), "llm_tag_errors table missing or query failed (#528)").toBe(200);
});
