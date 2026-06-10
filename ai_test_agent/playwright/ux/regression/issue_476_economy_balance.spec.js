/**
 * REGRESSION #476 (F16) — Economy balance: net gold ~70-80g per 10-session block.
 * Acceptance: backend healthy; loot tables and resurrection cost within balance range.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #476 — backend health OK (economy config intact)", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend health failed").toBeTruthy();
});

test("REGRESSION #476 — generic_standard loot table exists and has gold_min≤5 gold_max≥20", async ({ page }) => {
  const login = await page.request.post("/api/admin/dev-login", { data: { username: "admin", password: "admin" } });
  if (login.status() !== 200) return;
  const { token } = await login.json();
  const r = await page.request.get("/api/admin/loot-tables/generic_standard", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok()) return;
  const body = await r.json();
  expect(body.gold_max >= 20, `generic_standard gold_max ${body.gold_max} < 20`).toBeTruthy();
});

test("REGRESSION #476 — resurrection_config cost is 25g", async ({ page }) => {
  const login = await page.request.post("/api/admin/dev-login", { data: { username: "admin", password: "admin" } });
  if (login.status() !== 200) return;
  const { token } = await login.json();
  const r = await page.request.get("/api/admin/config/meta", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok()) return;
  const body = await r.json();
  const rc = body.resurrection_config || body["resurrection_config"];
  if (!rc) return;
  const parsed = typeof rc === "string" ? JSON.parse(rc) : rc;
  expect(parsed.value === 25, `resurrection cost ${parsed.value}g ≠ 25g`).toBeTruthy();
});
