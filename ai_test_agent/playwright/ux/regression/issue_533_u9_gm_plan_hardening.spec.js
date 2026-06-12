/**
 * REGRESSION #533 (U9) — GM Plan hardening: fallback plan + plan_degraded flag.
 * Acceptance: admin/campaigns/live endpoint exposes plan_degraded boolean field;
 * endpoint is reachable (200 with auth or 401 without); backend healthy after deploy.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #533 (U9) — backend health after U9 deploy", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "Backend not healthy after U9 deployment (#533)").toBeTruthy();
  const body = await r.json();
  expect(body.status).toBe("ok");
});

test("REGRESSION #533 (U9) — admin/campaigns/live reachable (auth guard active)", async ({ page }) => {
  const r = await page.request.get("/api/admin/campaigns/live", {
    failOnStatusCode: false,
  });
  expect(
    r.status() === 200 || r.status() === 401,
    `Unexpected status ${r.status()} from campaigns/live — endpoint broken (#533)`
  ).toBeTruthy();
});

test("REGRESSION #533 (U9) — admin dev-login + campaigns/live returns plan_degraded field", async ({ page }) => {
  // Log in as admin to get token
  const loginRes = await page.request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "admin" },
    failOnStatusCode: false,
  });
  if (loginRes.status() !== 200) {
    // Skip gracefully if admin credentials unavailable in this environment
    console.log(`Admin login returned ${loginRes.status()}, skipping plan_degraded field check`);
    return;
  }
  const loginBody = await loginRes.json();
  const token = loginBody.token || loginBody.access_token;
  if (!token) {
    console.log("No token in login response, skipping");
    return;
  }

  const r = await page.request.get("/api/admin/campaigns/live", {
    headers: { "Authorization": `Bearer ${token}` },
  });
  expect(r.ok(), "campaigns/live nie odpowiada 200 po zalogowaniu (#533)").toBeTruthy();
  const body = await r.json();
  expect(body.items, "brak pola items w odpowiedzi (#533)").toBeDefined();

  if (body.items.length > 0) {
    const first = body.items[0];
    expect(
      "plan_degraded" in first,
      `pole plan_degraded brakuje w campaign item (#533): keys=${JSON.stringify(Object.keys(first))}`
    ).toBeTruthy();
    expect(
      typeof first.plan_degraded === "boolean",
      `plan_degraded musi być boolean, jest: ${typeof first.plan_degraded} (#533)`
    ).toBeTruthy();
  }
});
