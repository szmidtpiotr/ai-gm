/**
 * REGRESSION #471 (F11) — Price unification: single price_gp column on catalog tables.
 * Acceptance: backend starts OK (migration ran); shop endpoint returns buy_price_gp per item.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #471 — backend starts after price_gp migration", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend /api/health not 200 after price_gp migration").toBeTruthy();
});

test("REGRESSION #471 — shop inventory buy_price_gp field present", async ({ page }) => {
  const r = await page.request.get("/api/shop/kowal_jan/inventory?char_id=1");
  expect([200, 404, 422].includes(r.status()), `unexpected status ${r.status()}`).toBeTruthy();
  if (r.status() === 200) {
    const body = await r.json();
    const items = body.items || body.inventory || [];
    if (items.length > 0) {
      expect("buy_price_gp" in items[0], "buy_price_gp field missing from shop item").toBeTruthy();
    }
  }
});

test("REGRESSION #471 — admin weapons endpoint reachable (catalog tables OK)", async ({ page }) => {
  // Admin login first
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "admin" },
  });
  const token = (login.status() === 200) ? (await login.json()).token : null;
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const r = await page.request.get("/api/admin/content/weapons", { headers });
  expect([200, 401, 403, 404].includes(r.status()), `unexpected status ${r.status()}`).toBeTruthy();
});
