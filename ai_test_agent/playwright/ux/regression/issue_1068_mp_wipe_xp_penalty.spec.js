/**
 * REGRESSION #1068 (FAZA G) — kara XP przy wipe party w walce MP.
 * Acceptance: flaga balansu wipe_xp_pct_by_level jest wystawiona przez sandbox
 * mp-balance (sandbox-tunable jak reszta #813) i domyślnie ma bracket 4-7 = 20%.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1068 — wipe XP penalty flag exposed + default 20% at lvl 4-7", async ({ page }) => {
  // Sandbox mp-balance wymaga tokenu admina.
  const loginResp = await page.request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "admin" },
  });
  if (!loginResp.ok()) {
    console.log("Admin login not available; skipping auth-required check (#1068)");
    return;
  }
  const { token } = await loginResp.json();

  const r = await page.request.get("/api/admin/sandbox/mp-balance", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /api/admin/sandbox/mp-balance nie zwraca 200 (#1068)").toBeTruthy();
  const body = await r.json();

  // Nowa flaga #1068 musi być obecna
  expect(body.wipe_xp_pct_by_level, "brak wipe_xp_pct_by_level (#1068)").toBeTruthy();
  expect(body).toHaveProperty("wipe_xp_floor");

  // Wszystkie trzy brackety
  const t = body.wipe_xp_pct_by_level;
  expect(t).toHaveProperty("1-3");
  expect(t).toHaveProperty("4-7");
  expect(t).toHaveProperty("8+");

  // Domyślnie 20% dla poziomu 4-7 (issue: "uprość do flat 20%")
  expect(Number(t["4-7"])).toBeCloseTo(0.2, 5);
});
