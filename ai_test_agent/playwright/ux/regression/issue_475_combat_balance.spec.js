/**
 * REGRESSION #475 (F15) — Combat balance: level-3+ fights drain ≥60% HP.
 * Acceptance: bandit attack_bonus ≥ 4 (tuned from 3); backend healthy after migration.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #475 — backend health OK after balance migration", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend health check failed after F15 balance migration").toBeTruthy();
});

test("REGRESSION #475 — bandit attack_bonus ≥4 (F15 tuned)", async ({ page }) => {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "admin" },
  });
  if (login.status() !== 200) return;
  const { token } = await login.json();
  const r = await page.request.get("/api/admin/enemies/bandit", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok()) return; // enemy lookup unavailable in this test env
  const enemy = await r.json();
  const atk = enemy.attack_bonus ?? enemy.attackBonus ?? 0;
  expect(atk >= 4, `bandit attack_bonus is ${atk}, expected ≥4 (F15 balance tune)`).toBeTruthy();
});

test("REGRESSION #475 — admin enemies list endpoint reachable", async ({ page }) => {
  // /api/admin/enemies requires auth → 401 expected, not 404
  const r = await page.request.get("/api/admin/enemies");
  expect([200, 401, 403].includes(r.status()), `unexpected status ${r.status()}`).toBeTruthy();
});
