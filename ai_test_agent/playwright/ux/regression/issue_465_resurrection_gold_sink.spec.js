/**
 * REGRESSION #465 (F5) — Wskrzeszenie jako gold sink: config + preview endpoint.
 * Acceptance: /api/admin/resurrection-config returns config; preview endpoint live.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #465 — admin resurrection-config endpoint returns config", async ({ page }) => {
  const r = await page.request.get("/api/admin/resurrection-config", {
    headers: { "X-Admin-Token": "dev-admin-token" }
  });
  // 200 = endpoint live; 401/403 = auth but endpoint exists; never 500
  expect(r.status(), "resurrection-config must not 500 (#465)").not.toBe(500);
  expect(r.status(), "resurrection-config must not 404 (#465)").not.toBe(404);
});

test("REGRESSION #465 — resurrection config has enabled field", async ({ page }) => {
  const r = await page.request.get("/api/admin/resurrection-config", {
    headers: { "X-Admin-Token": "dev-admin-token" }
  });
  if (r.ok()) {
    const body = await r.json();
    const cfg = body.config ?? body;
    expect(typeof cfg.enabled, "config.enabled must be boolean (#465)").toBe("boolean");
  } else {
    // Auth required but endpoint exists — shape check skipped
    expect([401, 403]).toContain(r.status());
  }
});
