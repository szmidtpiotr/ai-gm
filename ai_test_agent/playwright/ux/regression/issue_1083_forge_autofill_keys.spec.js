/**
 * REGRESSION #1083 — Forge generate-plan auto-fills required_npc_keys + required_beats.
 * Acceptance: response from generate-plan includes auto_filled_npc_keys field (may be []).
 * Verify endpoint contract — auth required, route exists.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1083 — forge generate-plan endpoint is auth-gated (not 404)", async ({ page }) => {
  const r = await page.request.post("/api/admin/forge/templates/1/generate-plan", {
    data: { suggested_act_count: 2 },
  });
  expect(
    r.status(),
    "Expected 401 (auth required) not 404 — endpoint must exist"
  ).toBe(401);
});

test("REGRESSION #1083 — forge templates list returns required_npc_keys field", async ({ page }) => {
  // Login and fetch template list — verify required_npc_keys key exists in schema
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "login failed").toBeTruthy();
  const { token } = await login.json();

  const r = await page.request.get("/api/admin/forge/templates", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "templates list must return 200").toBeTruthy();
  const body = await r.json();
  const items = body.items || [];
  if (items.length > 0) {
    expect(
      "required_npc_keys" in items[0],
      "Template must have required_npc_keys field"
    ).toBeTruthy();
    expect(
      "required_beats" in items[0],
      "Template must have required_beats field"
    ).toBeTruthy();
  }
});
